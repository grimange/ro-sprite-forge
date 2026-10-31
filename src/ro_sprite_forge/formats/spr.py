"""SPR 2.1 decoder and serializer with indexed/RGBA pool preservation."""

from dataclasses import dataclass, field
import struct
from typing import Any, Iterator, Sequence

from ro_sprite_forge.formats.errors import require
from ro_sprite_forge.formats.reader import BinaryReader

SPR_MAGIC = b"SP"
SPR_SUPPORTED_VERSION = b"\x01\x02"  # Version 2.1 (minor 1, major 2)

MAX_SPR_IMAGES = 4096
MAX_IMAGE_DIMENSION_PIXELS = 1024 * 1024
MAX_AGGREGATE_PIXELS = 64 * 1024 * 1024  # 64 Megapixels aggregate decompression budget


def encode_rle(pixels: bytes, *, path: str | None = None) -> bytes:
    """Encode 1-byte-per-pixel indexed data using canonical SPR 2.1 zero-run RLE."""
    require(isinstance(pixels, (bytes, bytearray)) and len(pixels) > 0, "SPR indexed pixels must be non-empty bytes", path=path)
    out = bytearray()
    i = 0
    n = len(pixels)
    while i < n:
        b = pixels[i]
        if b != 0:
            out.append(b)
            i += 1
        else:
            run = 0
            while i < n and pixels[i] == 0 and run < 255:
                run += 1
                i += 1
            out.append(0)
            out.append(run)
    require(len(out) <= 0xFFFF, "SPR RLE encoded payload exceeds uint16 length limit", path=path)
    return bytes(out)


def _decode_rle(raw_rle: bytes, expected_pixels: int, *, path: str | None = None) -> bytes:
    """Decode SPR 2.1 zero-run RLE payload with strict overrun/underrun validation."""
    length = len(raw_rle)
    encoded = BinaryReader(raw_rle, path=path)
    pixels = bytearray()
    while encoded.pos < length:
        x = encoded.read("B")
        if x == 0:
            count = max(encoded.read("B"), 1)
            require(len(pixels) + count <= expected_pixels, "SPR RLE overrun", path=path)
            pixels.extend(b"\x00" * count)
        else:
            require(len(pixels) + 1 <= expected_pixels, "SPR RLE overrun", path=path)
            pixels.append(x)
    require(len(pixels) == expected_pixels, "SPR RLE underrun", path=path)
    return bytes(pixels)


@dataclass(frozen=True)
class IndexedImage:
    """Lossless indexed sprite image with 1-byte-per-pixel palette indices."""

    width: int
    height: int
    pixels: bytes  # Length width * height, each byte is palette index 0..255
    rle_length: int
    raw_rle: bytes | None = field(default=None, compare=False, repr=False)

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def to_rgba(self, palette: bytes, *, canonicalize_transparent: bool = True) -> bytes:
        """Convert indexed pixels to top-down RGBA bytes using provided 1024-byte palette."""
        require(len(palette) == 1024, "palette must be exactly 1024 bytes")
        out = bytearray(self.width * self.height * 4)
        idx = 0
        for p in self.pixels:
            if p == 0 and canonicalize_transparent:
                # Canonical transparent pixel: RGBA (0, 0, 0, 0)
                out[idx : idx + 4] = b"\x00\x00\x00\x00"
            else:
                base = p * 4
                out[idx : idx + 3] = palette[base : base + 3]
                out[idx + 3] = 0xFF
            idx += 4
        return bytes(out)

    def to_pil(self, palette: bytes, *, canonicalize_transparent: bool = True):
        """Convert to PIL Image."""
        from PIL import Image

        rgba = self.to_rgba(palette, canonicalize_transparent=canonicalize_transparent)
        return Image.frombytes("RGBA", (self.width, self.height), rgba)


@dataclass(frozen=True)
class RgbaImage:
    """Truecolor sprite image with 4-byte-per-pixel top-down RGBA."""

    width: int
    height: int
    rgba: bytes  # Length width * height * 4

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def to_pil(self):
        """Convert to PIL Image."""
        from PIL import Image

        return Image.frombytes("RGBA", (self.width, self.height), self.rgba)


class SprDocument:
    """Decoded SPR 2.1 container preserving indexed and truecolor image pools.

    Can be unpacked as (images, indexed_count) for compatibility with audited ro_reference.
    """

    def __init__(
        self,
        indexed_images: Sequence[IndexedImage],
        rgba_images: Sequence[RgbaImage],
        palette: bytes,
    ):
        self.indexed_images = tuple(indexed_images)
        self.rgba_images = tuple(rgba_images)
        self.palette = palette
        self._pil_cache: list[Any] | None = None

    @property
    def indexed_count(self) -> int:
        return len(self.indexed_images)

    @property
    def rgba_count(self) -> int:
        return len(self.rgba_images)

    @property
    def total_count(self) -> int:
        return len(self.indexed_images) + len(self.rgba_images)

    @property
    def images(self) -> list[Any]:
        """List of PIL Image objects: indexed images first, then RGBA images."""
        if self._pil_cache is None:
            converted = [img.to_pil(self.palette) for img in self.indexed_images]
            truecolor = [img.to_pil() for img in self.rgba_images]
            self._pil_cache = converted + truecolor
        return list(self._pil_cache)

    def __iter__(self) -> Iterator[Any]:
        """Support unpacking: images, indexed_count = read_spr(data)."""
        return iter((self.images, self.indexed_count))

    def __len__(self) -> int:
        return self.total_count

    def __getitem__(self, index: int) -> Any:
        return self.images[index]


def read_spr(data: bytes, *, path: str | None = None) -> SprDocument:
    """Decode SPR 2.1 binary payload into SprDocument.

    Preserves indexed zero-run RLE representation, 1024-byte palette,
    and truecolor ABGR/RGBA image pools.
    """
    require(len(data) >= 8, "truncated binary resource: SPR file too small for header", path=path)
    magic = data[:2]
    require(magic == SPR_MAGIC, f"not an SPR file: invalid magic header {magic!r}", path=path)
    version = data[2:4]
    require(
        version == SPR_SUPPORTED_VERSION,
        f"only SPR 2.1 is supported; found version {version[1]}.{version[0]}",
        path=path,
    )

    r = BinaryReader(data, path=path)
    _ = r.take(4)
    ni, nr = r.read("HH")
    require(0 <= ni <= MAX_SPR_IMAGES and 0 <= nr <= MAX_SPR_IMAGES, "invalid SPR image count", path=path)
    require(0 < ni + nr <= MAX_SPR_IMAGES, "too many SPR images", path=path)

    aggregate_pixels = 0
    indexed: list[IndexedImage] = []
    rgba_list: list[RgbaImage] = []

    for _ in range(ni):
        w, h, length = r.read("HHH")
        require(0 < w * h <= MAX_IMAGE_DIMENSION_PIXELS, "invalid SPR dimensions", path=path)
        aggregate_pixels += w * h
        require(aggregate_pixels <= MAX_AGGREGATE_PIXELS, "aggregate SPR pixel decompression budget exceeded", path=path)
        require(length <= r.remaining, "truncated binary payload", path=path)

        raw_rle = r.take(length)
        pixels = _decode_rle(raw_rle, w * h, path=path)
        indexed.append(IndexedImage(width=w, height=h, pixels=pixels, rle_length=length, raw_rle=raw_rle))

    for _ in range(nr):
        w, h = r.read("HH")
        require(0 < w * h <= MAX_IMAGE_DIMENSION_PIXELS, "invalid SPR dimensions", path=path)
        aggregate_pixels += w * h
        require(aggregate_pixels <= MAX_AGGREGATE_PIXELS, "aggregate SPR pixel decompression budget exceeded", path=path)
        raw = r.take(w * h * 4)
        # Convert bottom-up ABGR to top-down RGBA bytes
        rgba = b"".join(
            raw[y * w * 4 : (y + 1) * w * 4][x : x + 4][::-1]
            for y in range(h - 1, -1, -1)
            for x in range(0, w * 4, 4)
        )
        rgba_list.append(RgbaImage(width=w, height=h, rgba=rgba))

    palette = r.take(1024)
    require(len(palette) == 1024, "truncated SPR palette", path=path)
    require(r.pos == len(data), "trailing SPR data", path=path)

    return SprDocument(indexed_images=indexed, rgba_images=rgba_list, palette=palette)


def write_spr(doc: SprDocument, *, path: str | None = None) -> bytes:
    """Serialize SprDocument into an SPR 2.1 binary payload.

    Preserves unchanged indexed RLE representations, 1024-byte palette,
    and truecolor RGBA pools deterministically.
    """
    require(isinstance(doc, SprDocument), "expected SprDocument instance", path=path)
    ni = len(doc.indexed_images)
    nr = len(doc.rgba_images)
    require(0 <= ni <= MAX_SPR_IMAGES and 0 <= nr <= MAX_SPR_IMAGES, "invalid SPR image count", path=path)
    require(0 < ni + nr <= MAX_SPR_IMAGES, "too many SPR images", path=path)
    require(isinstance(doc.palette, (bytes, bytearray)) and len(doc.palette) == 1024, "invalid SPR palette length", path=path)

    out = bytearray(SPR_MAGIC + SPR_SUPPORTED_VERSION + struct.pack("<HH", ni, nr))
    aggregate_pixels = 0

    for img in doc.indexed_images:
        require(isinstance(img, IndexedImage), "expected IndexedImage in indexed pool", path=path)
        w, h = img.width, img.height
        require(type(w) is int and type(h) is int and 0 < w <= 0xFFFF and 0 < h <= 0xFFFF, "invalid SPR dimensions", path=path)
        require(0 < w * h <= MAX_IMAGE_DIMENSION_PIXELS, "invalid SPR dimensions", path=path)
        aggregate_pixels += w * h
        require(aggregate_pixels <= MAX_AGGREGATE_PIXELS, "aggregate SPR pixel decompression budget exceeded", path=path)
        require(isinstance(img.pixels, (bytes, bytearray)) and len(img.pixels) == w * h, "SPR indexed pixel length mismatch", path=path)

        if img.raw_rle is not None:
            require(isinstance(img.raw_rle, (bytes, bytearray)), "invalid SPR raw RLE bytes", path=path)
            encoded = bytes(img.raw_rle)
            require(len(encoded) == img.rle_length and len(encoded) <= 0xFFFF, "SPR raw RLE length mismatch", path=path)
            decoded = _decode_rle(encoded, w * h, path=path)
            require(decoded == bytes(img.pixels), "SPR raw RLE content mismatch with pixels", path=path)
        else:
            encoded = encode_rle(bytes(img.pixels), path=path)

        out += struct.pack("<HHH", w, h, len(encoded))
        out += encoded

    for img in doc.rgba_images:
        require(isinstance(img, RgbaImage), "expected RgbaImage in truecolor pool", path=path)
        w, h = img.width, img.height
        require(type(w) is int and type(h) is int and 0 < w <= 0xFFFF and 0 < h <= 0xFFFF, "invalid SPR dimensions", path=path)
        require(0 < w * h <= MAX_IMAGE_DIMENSION_PIXELS, "invalid SPR dimensions", path=path)
        aggregate_pixels += w * h
        require(aggregate_pixels <= MAX_AGGREGATE_PIXELS, "aggregate SPR pixel decompression budget exceeded", path=path)
        raw = img.rgba
        require(isinstance(raw, (bytes, bytearray)) and len(raw) == w * h * 4, "SPR RGBA pixel length mismatch", path=path)
        out += struct.pack("<HH", w, h)
        # Convert top-down RGBA to bottom-up ABGR
        out += b"".join(
            raw[y * w * 4 : (y + 1) * w * 4][x : x + 4][::-1]
            for y in range(h - 1, -1, -1)
            for x in range(0, w * 4, 4)
        )

    out += bytes(doc.palette)
    return bytes(out)


def write_rgba_spr(images: Sequence[Any], *, path: str | None = None) -> bytes:
    """Serialize truecolor RGBA images into an SPR 2.1 binary payload.

    Note: This creates truecolor (RGBA) SPR entries with an empty palette.
    It does not write indexed RLE sprites and is not an indexed byte-preserving operation.
    """
    require(0 < len(images) <= MAX_SPR_IMAGES, "invalid SPR export image count", path=path)
    out = bytearray(SPR_MAGIC + SPR_SUPPORTED_VERSION + struct.pack("<HH", 0, len(images)))
    for image in images:
        if hasattr(image, "size") and hasattr(image, "convert"):
            w, h = image.size
            raw = image.convert("RGBA").tobytes()
        elif hasattr(image, "width") and hasattr(image, "height") and hasattr(image, "rgba"):
            w, h = image.width, image.height
            raw = image.rgba
        else:
            raise TypeError(f"unsupported image type for write_rgba_spr: {type(image)}")
        require(0 < w * h <= MAX_IMAGE_DIMENSION_PIXELS, "invalid SPR export dimensions", path=path)
        out += struct.pack("<HH", w, h)
        # Convert top-down RGBA to bottom-up ABGR
        out += b"".join(
            raw[y * w * 4 : (y + 1) * w * 4][x : x + 4][::-1]
            for y in range(h - 1, -1, -1)
            for x in range(0, w * 4, 4)
        )
    return bytes(out + bytes(1024))

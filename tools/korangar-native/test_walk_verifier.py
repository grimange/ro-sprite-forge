"""Redistributable capture/upload controls, without GPU or private resources."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from verify_walk import NativeMismatch, check_capture, sha, upload_identity


class CaptureChecks(unittest.TestCase):
    def test_binary_alpha_upload_identity(self):
        image = Image.new('RGBA', (2, 1))
        image.putdata([(12, 34, 56, 255), (99, 88, 77, 0)])
        self.assertEqual(upload_identity(image)['upload_rgba_sha256'], sha(bytes([12, 34, 56, 255, 0, 0, 0, 0])))

    def test_partial_alpha_cannot_claim_exact_upload_parity(self):
        with self.assertRaisesRegex(NativeMismatch, 'UNSUPPORTED_UPLOAD_COMPARISON'):
            upload_identity(Image.new('RGBA', (1, 1), (10, 20, 30, 128)))

    def capture(self, root, *, empty=False, size=(512, 512)):
        image = Image.new('RGBA', size, (0, 0, 0, 255))
        if not empty:
            image.putpixel((1, 1), (21, 43, 65, 255))
        path = root / 'frame.png'
        image.save(path)
        return dict(file=path.name, png_sha256=sha(path.read_bytes()), drawn_layers=1,
                    non_background_pixels=0 if empty else 1, passes=['opaque', 'transparent', 'wboit_resolve'])

    def test_actual_capture_content_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            check_capture(self.capture(root), root, 1)

    def test_empty_render_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(NativeMismatch, 'EMPTY_NATIVE_RENDER'):
                check_capture(self.capture(root, empty=True), root, 1)

    def test_corrupted_capture_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = self.capture(root)
            (root / 'frame.png').write_bytes(b'corrupt')
            with self.assertRaisesRegex(NativeMismatch, 'capture/hash'):
                check_capture(capture, root, 1)

    def test_wrong_dimensions_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(NativeMismatch, 'capture/dimensions'):
                check_capture(self.capture(root, size=(32, 32)), root, 1)

    def test_wrong_visibility_count_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = self.capture(root)
            capture['non_background_pixels'] = 999
            with self.assertRaisesRegex(NativeMismatch, 'capture/visible_pixels'):
                check_capture(capture, root, 1)

    def test_capture_cannot_escape_evidence_directory(self):
        with self.assertRaisesRegex(NativeMismatch, 'capture/local_filename'):
            check_capture(dict(file='../frame.png'), Path('/tmp'), 1)

//! Independent bounded adapter around pinned Korangar format decoders.
use ragnarok_bytes::{ByteReader, FromBytes};
use ragnarok_formats::{action::ActionsData, sprite::SpriteData, version::GenericFormatMetadata};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{fs::File, io::Read};
type Result<T> = std::result::Result<T, String>;
fn ensure(ok: bool, message: &str) -> Result<()> {
    if ok { Ok(()) } else { Err(message.into()) }
}
fn hex(b: &[u8]) -> String {
    b.iter().map(|v| format!("{v:02x}")).collect()
}
fn hash(b: &[u8]) -> String {
    hex(&Sha256::digest(b))
}
struct Cursor<'a> {
    data: &'a [u8],
    at: usize,
}
impl<'a> Cursor<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8]> {
        let end = self.at.checked_add(n).ok_or("offset overflow")?;
        let b = self.data.get(self.at..end).ok_or("truncated record")?;
        self.at = end;
        Ok(b)
    }
    fn u16(&mut self) -> Result<usize> {
        Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap()) as usize)
    }
    fn u32(&mut self) -> Result<usize> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()) as usize)
    }
    fn count(&mut self, max: usize) -> Result<usize> {
        let n = self.u32()?;
        ensure(n <= max, "count budget")?;
        Ok(n)
    }
    fn end(&self) -> Result<()> {
        ensure(self.at == self.data.len(), "trailing bytes")
    }
}
// Preflight bounds every count before upstream allocation and preserves opaque events.
fn preflight_act(data: &[u8]) -> Result<Vec<String>> {
    let mut c = Cursor { data, at: 0 };
    ensure(c.take(4)? == b"AC\x04\x02", "unsupported ACT version/magic")?;
    let actions = c.u16()?;
    ensure((1..=4096).contains(&actions), "action budget")?;
    c.take(10)?;
    let (mut motions, mut layers) = (0, 0);
    for _ in 0..actions {
        let n = c.count(4096)?;
        motions += n;
        ensure(motions <= 65536, "motion budget")?;
        for _ in 0..n {
            c.take(32)?;
            let n = c.count(1024)?;
            layers += n;
            ensure(layers <= 262144, "layer budget")?;
            c.take(n * 36)?;
            c.take(4)?;
            let anchors = c.count(64)?;
            c.take(anchors * 16)?;
        }
    }
    let n = c.count(4096)?;
    let mut events = Vec::new();
    for _ in 0..n {
        events.push(hex(c.take(40)?));
    }
    c.take(actions * 4)?;
    c.end()?;
    Ok(events)
}
fn preflight_spr(data: &[u8]) -> Result<()> {
    let mut c = Cursor { data, at: 0 };
    ensure(c.take(4)? == b"SP\x01\x02", "unsupported SPR version/magic")?;
    let ni = c.u16()?;
    let nr = c.u16()?;
    ensure((1..=4096).contains(&(ni + nr)), "image count budget")?;
    let mut total = 0;
    for i in 0..ni + nr {
        let w = c.u16()?;
        let h = c.u16()?;
        let pixels = w * h;
        ensure((1..=1048576).contains(&pixels), "invalid dimensions")?;
        total += pixels;
        ensure(total <= 67108864, "pixel budget")?;
        if i < ni {
            let length = c.u16()?;
            let encoded = c.take(length)?;
            let mut e = Cursor {
                data: encoded,
                at: 0,
            };
            let mut decoded = 0;
            while e.at < encoded.len() {
                let b = e.take(1)?[0];
                decoded += if b == 0 {
                    usize::from(e.take(1)?[0]).max(1)
                } else {
                    1
                };
                ensure(decoded <= pixels, "RLE overrun")?;
            }
            ensure(decoded == pixels, "RLE underrun")?;
        } else {
            c.take(pixels * 4)?;
        }
    }
    c.take(1024)?;
    c.end()
}
fn report(act: &[u8], spr: &[u8]) -> Result<Value> {
    let events = preflight_act(act)?;
    preflight_spr(spr)?;
    let mut ar = ByteReader::with_default_metadata::<GenericFormatMetadata>(act);
    let a = ActionsData::from_bytes(&mut ar).map_err(|e| format!("ACT upstream: {e:?}"))?;
    let mut sr = ByteReader::with_default_metadata::<GenericFormatMetadata>(spr);
    let s = SpriteData::from_bytes(&mut sr).map_err(|e| format!("SPR upstream: {e:?}"))?;
    ensure(
        ar.get_offset() == act.len() && sr.get_offset() == spr.len(),
        "upstream trailing bytes",
    )?;
    let actions=a.actions.iter().map(|action| {
        action.motions.iter().map(|m| {
            ensure(m.event_id.unwrap()>=-1 && m.event_id.unwrap() < events.len() as i32,"invalid event reference")?;
            let clips=m.sprite_clips.iter().map(|l| {
                let pool=l.sprite_type.unwrap();let index=l.sprite_number;
                ensure(index>=-1,"invalid negative image index")?;
                if index>=0 {
                    let count=match pool {0=>s.palette_image_data.len(),1=>s.rgba_image_data.len(),_=>return Err("invalid image pool".into())};
                    ensure((index as usize)<count,"invalid image reference")?;
                }
                let scale=l.zoom2.unwrap();ensure(scale.x.is_finite() && scale.y.is_finite(),"nonfinite scale")?;
                Ok(json!({"x":l.position.x,"y":l.position.y,"sprite":index,"mirror":l.mirror_on,"color":l.color.unwrap(),"scale_x":scale.x.to_bits(),"scale_y":scale.y.to_bits(),"angle":l.angle.unwrap(),"pool":pool}))
            }).collect::<Result<Vec<_>>>()?;
            let bounds=m.range1.iter().chain(m.range2.iter()).copied().collect::<Vec<_>>();
            let anchors=m.attach_points.iter().map(|v|json!({"opaque":v.ignored,"x":v.position.x,"y":v.position.y,"attribute":v.attribute})).collect::<Vec<_>>();
            Ok(json!({"bounds":bounds,"clips":clips,"event":m.event_id.unwrap(),"anchors":anchors}))
        }).collect::<Result<Vec<_>>>()
    }).collect::<Result<Vec<_>>>()?;
    let delays = a.delays.unwrap();
    for v in &delays {
        ensure(v.is_finite() && *v > 0., "invalid delay")?;
    }
    let palette = s
        .palette
        .unwrap()
        .colors
        .iter()
        .flat_map(|c| [c.red, c.green, c.blue, c.reserved])
        .collect::<Vec<_>>();
    let mut images = Vec::new();
    for (index, i) in s.palette_image_data.iter().enumerate() {
        let rgba = i
            .data
            .0
            .iter()
            .flat_map(|p| {
                if *p == 0 {
                    [0, 0, 0, 0]
                } else {
                    let n = usize::from(*p) * 4;
                    [palette[n], palette[n + 1], palette[n + 2], 255]
                }
            })
            .collect::<Vec<_>>();
        images.push(json!({"pool":0,"index":index,"width":i.width,"height":i.height,"indices":hex(&i.data.0),"rgba":hex(&rgba)}));
    }
    for (index, i) in s.rgba_image_data.iter().enumerate() {
        let mut rgba = Vec::new();
        let stride = usize::from(i.width) * 4;
        for row in i.data.chunks_exact(stride).rev() {
            for p in row.chunks_exact(4) {
                rgba.extend(p.iter().rev());
            }
        }
        images.push(json!({"pool":1,"index":index,"width":i.width,"height":i.height,"indices":Value::Null,"rgba":hex(&rgba)}));
    }
    Ok(
        json!({"schema":"rsf.oracle-structure/v1","sources":{"act":hash(act),"spr":hash(spr)},"act":{"version":"2.4","reserved":hex(&a.reserved),"actions":actions,"events":events,"delays":delays.iter().map(|v|v.to_bits()).collect::<Vec<_>>()},"spr":{"version":"2.1","indexed_count":s.palette_image_data.len(),"truecolor_count":s.rgba_image_data.len(),"palette":hex(&palette),"images":images}}),
    )
}
fn read(path: &str) -> Result<Vec<u8>> {
    let mut b = Vec::new();
    File::open(path)
        .map_err(|e| e.to_string())?
        .take(134217729)
        .read_to_end(&mut b)
        .map_err(|e| e.to_string())?;
    ensure(b.len() <= 134217728, "file budget")?;
    Ok(b)
}
fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let result = if args.len() == 2 {
        read(&args[0]).and_then(|a| read(&args[1]).and_then(|s| report(&a, &s)))
    } else {
        Err("usage: rsf-rust-oracle ACT SPR".into())
    };
    match result {
        Ok(v) => println!("{v}"),
        Err(e) => {
            eprintln!("INVALID_INPUT: {e}");
            std::process::exit(3);
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_reader() {
        let mut c = Cursor {
            data: &[1, 2, 3],
            at: 0,
        };
        assert!(c.take(usize::MAX).is_err());
        assert_eq!(c.at, 0);
        assert_eq!(c.take(2).unwrap(), [1, 2]);
        assert!(c.take(2).is_err());
    }
    #[test]
    fn headers() {
        for n in 0..16 {
            assert!(preflight_act(&vec![0; n]).is_err());
            assert!(preflight_spr(&vec![0; n]).is_err());
        }
    }
    #[test]
    fn minimal_act() {
        let mut b = b"AC\x04\x02\x01\0".to_vec();
        b.extend([0; 10]);
        b.extend([0; 8]);
        b.extend(1f32.to_le_bytes());
        assert_eq!(preflight_act(&b).unwrap(), Vec::<String>::new());
        b.push(0);
        assert!(preflight_act(&b).is_err());
    }
}

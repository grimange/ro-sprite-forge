#![feature(adt_const_params, generic_const_exprs, allocator_api)]
#![allow(incomplete_features, dead_code, unused_imports, unexpected_cfgs)]
//! Isolated native presentation: no server, gameplay, UI or replacement renderer.
extern crate self as korangar_audio;

#[cfg(test)]
mod tests {
    use super::*;
    use world::Camera;

    #[test]
    fn native_camera_opposites() {
        assert_eq!(PresentationCamera { opposite: false }.camera_direction(), 0);
        assert_eq!(PresentationCamera { opposite: true }.camera_direction(), 4);
    }

    #[test]
    fn native_direction_masks_out_of_range() {
        assert_eq!(u16::from(Direction::from(8)), 0);
        assert_eq!(u16::from(Direction::from(15)), 7);
    }

    #[test]
    fn native_public_state_transitions() {
        let mut state = world::AnimationState::new(EntityType::Player, ClientTick(0));
        state.walk(EntityType::Player, 150, ClientTick(0));
        assert!(state.is_walking());
        state.hurt(EntityType::Player, 1000, ClientTick(10));
        assert!(state.is_hurt());
        assert!(!state.is_walking());
        state.dead(EntityType::Player, ClientTick(20));
        assert!(state.is_dead());
        assert!(!state.is_hurt());
    }
}
extern crate self as ragnarok_packets;
use cgmath::{Matrix4, Point3, SquareMatrix, Vector3};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::{Arc, Mutex};
mod direction;
pub use direction::Direction;
mod entity_type;
pub use entity_type::EntityType;
mod graphics;
mod walk;
pub use graphics::Color;
pub fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
#[derive(Debug, Copy, Clone)]
pub struct ClientTick(pub u32);
#[derive(Debug, Copy, Clone)]
pub struct EntityId(pub u32);
pub type SoundEffectKey = u64;
pub struct AudioEngine<T>(std::marker::PhantomData<T>);
impl<T> AudioEngine<T> {
    pub fn load(&self, name: &str) -> SoundEffectKey {
        let digest = Sha256::digest(name.as_bytes());
        u64::from_le_bytes(digest[..8].try_into().unwrap())
    }
}
mod world {
    mod animation;
    pub use animation::*;
    mod camera;
    pub use camera::*;
    mod actions;
    pub use crate::EntityType;
    pub use actions::*;
}
mod loaders {
    pub mod action;
    pub use action::*;
    pub mod sprite;
    pub use sprite::*;
    pub mod animation;
    pub use animation::*;
    pub mod texture;
    pub use texture::*;
    pub mod color;
    pub mod error;
    pub use crate::GameFileLoader;
    pub const FALLBACK_ACTIONS_FILE: &str = "npc\\missing.act";
    pub const FALLBACK_SPRITE_FILE: &str = "npc\\missing.spr";
}
pub struct GameFileLoader {
    files: BTreeMap<String, Value>,
    pub trace: Mutex<Vec<Value>>,
}
impl korangar_loaders::FileLoader for GameFileLoader {
    fn get(&self, path: &str) -> Result<Vec<u8>, korangar_loaders::FileNotFoundError> {
        let Some(spec) = self.files.get(path) else {
            self.trace
                .lock()
                .unwrap()
                .push(json!({"path":path,"status":"MISSING"}));
            return Err(korangar_loaders::FileNotFoundError::new(path.into()));
        };
        let bytes = std::fs::read(spec["path"].as_str().unwrap()).expect("private input readable");
        let digest = sha(&bytes);
        let valid = spec["sha256"] == digest;
        self.trace.lock().unwrap().push(json!({"path":path,"sha256":digest,"length":bytes.len(),"status":if valid {"LOADED_CORRECT_RESOURCE"} else {"RESOURCE_MISMATCH"}}));
        if !valid {
            return Err(korangar_loaders::FileNotFoundError::new(path.into()));
        }
        Ok(bytes)
    }
}
struct PresentationCamera {
    opposite: bool,
}
impl world::Camera for PresentationCamera {
    fn camera_position(&self) -> Point3<f32> {
        Point3::new(0., 10., if self.opposite { 40. } else { -40. })
    }
    fn focus_point(&self) -> Point3<f32> {
        Point3::new(0., 10., 0.)
    }
    fn generate_view_projection(&mut self, _: graphics::ScreenSize) {}
    fn look_up_vector(&self) -> Vector3<f32> {
        Vector3::unit_y()
    }
    fn view_projection_matrices(&self) -> (Matrix4<f32>, Matrix4<f32>) {
        let view = Matrix4::look_to_lh(
            self.camera_position(),
            self.view_direction(),
            Vector3::unit_y(),
        );
        // Native pipeline uses reverse depth (Greater); deterministic orthographic
        // presentation only replaces gameplay camera placement/projection.
        let projection = Matrix4::new(
            0.05, 0., 0., 0., 0., 0.05, 0., 0., 0., 0., -0.001, 0., 0., 0., 0.9, 1.,
        );
        (view, projection)
    }
    fn view_projection_matrix(&self) -> Matrix4<f32> {
        let (v, p) = self.view_projection_matrices();
        p * v
    }
    fn view_direction(&self) -> Vector3<f32> {
        Vector3::new(0., 0., if self.opposite { -1. } else { 1. })
    }
}
fn set_action(state: &mut world::AnimationState, kind: EntityType, action: &str) {
    match action {
        "Idle" => state.idle(kind, ClientTick(0)),
        "Walk" => state.walk(kind, 150, ClientTick(0)),
        "Attack" => state.attack(kind, 1000, false, ClientTick(0)),
        "CriticalAttack" => state.attack(kind, 1000, true, ClientTick(0)),
        "Hurt" => state.hurt(kind, 1000, ClientTick(0)),
        "Die" => state.dead(kind, ClientTick(0)),
        _ => panic!("ACTION_UNSUPPORTED"),
    }
}
fn locate(data: &world::AnimationData, frame: &world::AnimationFrame) -> (usize, usize) {
    for (a, action) in data.animations.iter().enumerate() {
        for (f, entry) in action.frames.iter().enumerate() {
            if std::ptr::eq(frame, entry) {
                return (a, f);
            }
        }
    }
    panic!("unowned frame")
}
fn parts(frame: &world::AnimationFrame) -> Vec<Value> {
    frame.frame_parts.iter().map(|p|json!({"part":p.animation_index,"image":p.sprite_number,"offset":[p.offset.x,p.offset.y],"size":[p.size.x,p.size.y],"mirror":p.mirror,"angle":p.angle,"color":[p.color.red,p.color.green,p.color.blue,p.color.alpha],"affine":Into::<[[f32;4];4]>::into(p.affine_matrix)})).collect()
}
fn main() {
    use world::Camera;
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(
        args.len(),
        3,
        "usage: rsf-korangar-native PRIVATE_INPUT.json PRIVATE_OUTPUT_DIR"
    );
    let inputs: Value = serde_json::from_slice(&std::fs::read(&args[1]).unwrap()).unwrap();
    // Avoid entering the native recursive missing-resource fallback with an
    // invalid positive fixture set. Actual delivered bytes are checked again
    // at the FileLoader boundary; this is only a fail-fast staging check.
    let required_parts: Vec<String> = if let Some(actors) = inputs["walk"]["actors"].as_array() {
        actors.iter().flat_map(|a| a["parts"].as_array().unwrap().iter().map(|p|p.as_str().unwrap().to_string())).collect()
    } else {
        ["novice_body", "novice_head", "orc_skeleton"].iter().map(|s|s.to_string()).collect()
    };
    for name in required_parts {
        for extension in ["act", "spr"] {
            let identifier = format!("data\\sprite\\{name}.{extension}");
            let spec = &inputs["files"][&identifier];
            let path = spec["path"]
                .as_str()
                .expect("RESOURCE_MOUNT_FAILED: required fixture path");
            let bytes = std::fs::read(path).expect("MISSING_MODIFIED_RESOURCE: required fixture readable");
            assert_eq!(
                spec["sha256"].as_str(),
                Some(sha(&bytes).as_str()),
                "RESOURCE_MISMATCH: staging {identifier}"
            );
        }
    }
    let output = Path::new(&args[2]);
    assert!(!output.exists(), "new output directory required");
    std::fs::create_dir_all(output).unwrap();
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::VULKAN,
        ..wgpu::InstanceDescriptor::new_without_display_handle()
    });
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        force_fallback_adapter: true,
        ..Default::default()
    }))
    .unwrap();
    let info = format!("{:?}", adapter.get_info());
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("RSF pinned native presentation"),
        required_features: wgpu::Features::empty(),
        required_limits: wgpu::Limits::default(),
        ..Default::default()
    }))
    .unwrap();
    let (device, queue) = (Arc::new(device), Arc::new(queue));
    let texture = Arc::new(loaders::TextureLoader {
        device: device.clone(),
        queue: queue.clone(),
    });
    let camera = PresentationCamera { opposite: false };
    let (view, projection) = camera.view_projection_matrices();
    let mut renderer = graphics::Renderer::new(
        device.clone(),
        queue.clone(),
        info.clone(),
        &texture,
        projection * view,
        view,
    );
    if inputs.get("walk").is_some() {
        walk::run(&inputs, output, texture, &mut renderer, &info);
        return;
    }
    let mut cases = Vec::new();
    let mut prepared = Vec::new();
    let mut resources = Vec::new();
    let mut negatives = Vec::new();
    for (actor, kind, part_names) in [
        (
            "novice",
            EntityType::Player,
            vec!["novice_body".to_string(), "novice_head".to_string()],
        ),
        ("orc", EntityType::Monster, vec!["orc_skeleton".to_string()]),
    ] {
        let loader = Arc::new(GameFileLoader {
            files: serde_json::from_value(inputs["files"].clone()).unwrap(),
            trace: Mutex::new(Vec::new()),
        });
        let sprite = loaders::SpriteLoader::new(loader.clone(), texture.clone());
        let action = loaders::ActionLoader::new(
            loader.clone(),
            Arc::new(AudioEngine(std::marker::PhantomData)),
        );
        let data = loaders::AnimationLoader::new()
            .load(&sprite, &action, kind, &part_names)
            .unwrap();
        let loaded = loader.trace.lock().unwrap().clone();
        assert_eq!(loaded.len(), part_names.len() * 2);
        assert!(
            loaded
                .iter()
                .all(|t| t["status"] == "LOADED_CORRECT_RESOURCE")
        );
        resources.push(json!({"actor":actor,"loaded":loaded,"parts":part_names,"stored_images":data.animation_pair.iter().map(|p|p.sprites.textures.len()).collect::<Vec<_>>()}));
        prepared.push(json!({"actor":actor,"actions":data.animations.iter().map(|a|a.frames.iter().map(|f|json!({"offset":[f.offset.x,f.offset.y],"size":[f.size.x,f.size.y],"parts":parts(f),"event":format!("{:?}",f.event)})).collect::<Vec<_>>()).collect::<Vec<_>>()}));
        for (semantic, player_group, monster_group) in [
            ("Idle", 0, 0),
            ("Walk", 1, 1),
            ("Attack", 5, 2),
            ("Hurt", 6, 3),
            ("Die", 8, 4),
        ] {
            for opposite in [false, true] {
                let camera = PresentationCamera { opposite };
                let camera_view = if opposite { 4 } else { 0 };
                assert_eq!(camera.camera_direction(), camera_view);
                for direction in 0..8u16 {
                    let view = (camera_view + usize::from(direction)) & 7;
                    let expected_slot = if kind == EntityType::Player {
                        player_group
                    } else {
                        monster_group
                    } * 8
                        + view;
                    let count = data.animations[expected_slot].frames.len();
                    let delay = data.delays[expected_slot];
                    let factor = if semantic == "Walk" { 20. } else { 50. };
                    let mut state = world::AnimationState::new(kind, ClientTick(0));
                    set_action(&mut state, kind, semantic);
                    let mut sequence = Vec::new();
                    for step in 0..count + 2 {
                        let tick = if semantic == "Attack" || semantic == "Hurt" {
                            ((step as f64 + 0.1) * 1000. / count as f64) as u32
                        } else {
                            ((step as f64 + 0.1) * f64::from(delay * factor)) as u32
                        };
                        state.update(ClientTick(tick));
                        let frame = data.get_frame(&state, &camera, Direction::from(direction));
                        let (slot, index) = locate(&data, frame);
                        let expected_frame = if semantic == "Idle" && kind == EntityType::Player {
                            0
                        } else if ["Idle", "Walk"].contains(&semantic) {
                            step % count
                        } else {
                            step.min(count - 1)
                        };
                        assert_eq!(
                            (slot, index),
                            (expected_slot, expected_frame),
                            "REQUESTED_SLOT_VERIFIED failed {actor}/{semantic}/{direction}/{tick}"
                        );
                        let mut instructions = Vec::new();
                        data.render(
                            &mut instructions,
                            &camera,
                            false,
                            EntityId(1),
                            Point3::new(0., 0., 0.),
                            &state,
                            Direction::from(direction),
                            1.,
                            1.,
                        );
                        assert_eq!(instructions.len(), frame.frame_parts.len());
                        for (i, (instruction, part)) in
                            instructions.iter().zip(&frame.frame_parts).enumerate()
                        {
                            assert!(Arc::ptr_eq(
                                &instruction.texture,
                                &data.animation_pair[part.animation_index].sprites.textures
                                    [part.sprite_number]
                            ));
                            assert_eq!(instruction.frame_part_transform, part.affine_matrix);
                            assert_eq!(instruction.mirror, part.mirror);
                            assert_eq!(instruction.extra_depth_offset, 0.005 * i as f32);
                        }
                        let capture = if !opposite
                            && [0, 4, 7].contains(&direction)
                            && [0, count / 2, count - 1].contains(&step)
                        {
                            let name = format!("{actor}-{semantic}-{direction}-{index}.png");
                            Some(renderer.capture(&instructions, &output.join(name)))
                        } else {
                            None
                        };
                        sequence.push(json!({"tick":tick,"resolved_slot":slot,"resolved_view":slot%8,"frame":index,"layers":instructions.len(),"capture":capture}));
                    }
                    cases.push(json!({"actor":actor,"requested_action":semantic,"requested_direction":direction,"camera_view":camera_view,"resolved_view":view,"requested_slot":expected_slot,"resolved_slot":sequence[0]["resolved_slot"],"source_delay":delay,"native_delay_factor":factor,"duration":if ["Attack","Hurt"].contains(&semantic){Some(1000)}else{None},"frames_in_slot":count,"sequence":sequence,"fallback":"NONE","status":"REQUESTED_SLOT_VERIFIED"}));
                }
            }
        }
        if kind == EntityType::Monster {
            let mut state = world::AnimationState::new(kind, ClientTick(0));
            set_action(&mut state, kind, "CriticalAttack");
            let frame = data.get_frame(&state, &camera, Direction::North);
            let (slot, index) = locate(&data, frame);
            assert_eq!(slot, 0);
            negatives.push(json!({"case":"monster_critical_attack","requested":"Attack3","resolved_slot":slot,"frame":index,"status":"FALLBACK_DETECTED","reason":"native monster catch-all maps Attack3 to group zero"}));
            let mut short = (*data).clone();
            short.animations.truncate(8);
            short.delays.truncate(8);
            set_action(&mut state, kind, "Die");
            let frame = short.get_frame(&state, &camera, Direction::NorthWest);
            let (slot, _) = locate(&short, frame);
            assert_eq!(slot, 7);
            negatives.push(json!({"case":"truncated_action_set_modulo","requested_slot":39,"resolved_slot":slot,"status":"FALLBACK_DETECTED"}));
            assert_ne!(slot, 6);
            negatives.push(json!({"case":"incorrect_view_expectation","expected_slot":6,"actual_slot":slot,"status":"NATIVE_FAILURE"}));
        }
        let before = loader.trace.lock().unwrap().len();
        sprite
            .get_or_load(&format!("{}.spr", part_names[0]))
            .unwrap();
        assert_eq!(before, loader.trace.lock().unwrap().len());
    }
    let mut files: BTreeMap<String, Value> =
        serde_json::from_value(inputs["files"].clone()).unwrap();
    for extension in ["act", "spr"] {
        let source = files[&format!("data\\sprite\\orc_skeleton.{extension}")].clone();
        files.insert(format!("data\\sprite\\npc\\missing.{extension}"), source);
    }
    files.insert("data\\sprite\\wrong_hash.act".into(),json!({"path":inputs["files"]["data\\sprite\\orc_skeleton.act"]["path"],"sha256":"0".repeat(64)}));
    let negative_loader = Arc::new(GameFileLoader {
        files,
        trace: Mutex::new(Vec::new()),
    });
    let actions = loaders::ActionLoader::new(
        negative_loader.clone(),
        Arc::new(AudioEngine(std::marker::PhantomData)),
    );
    let sprites = loaders::SpriteLoader::new(negative_loader.clone(), texture);
    actions.load("unavailable.act").unwrap();
    sprites.load("unavailable.spr").unwrap();
    actions.load("wrong_hash.act").unwrap();
    let trace = negative_loader.trace.lock().unwrap().clone();
    assert!(trace.iter().any(|t| t["status"] == "MISSING"));
    assert!(trace.iter().any(|t| t["status"] == "RESOURCE_MISMATCH"));
    assert!(
        trace
            .iter()
            .any(|t| t["path"] == "data\\sprite\\npc\\missing.act")
    );
    negatives.push(json!({"case":"native_loader_missing_and_hash_mismatch","trace":trace,"status":"FALLBACK_DETECTED","fallback_fixture":"isolated audited Orc bytes under fallback identifiers"}));
    assert_eq!(u16::from(Direction::from(8)), 0);
    negatives.push(json!({"case":"unsupported_direction_8","status":"ACTION_UNSUPPORTED","native_masked_direction":0,"accepted_as_success":false}));
    let report = json!({"schema":"rsf.native.v1","mode":"isolated_native_presentation","revision":"3f3d88a583203f09d079712f43343c1041258ffd","resources":resources,"prepared":prepared,"cases":cases,"negative_cases":negatives,"gameplay_reachability":"NOT_TESTED","sound_playback":"NOT_TESTED"});
    let bytes = serde_json::to_vec_pretty(&report).unwrap();
    std::fs::write(output.join("native-report.json"), &bytes).unwrap();
    std::fs::write(
        output.join("environment.json"),
        serde_json::to_vec_pretty(&json!({"adapter":info})).unwrap(),
    )
    .unwrap();
    println!(
        "{}",
        json!({"status":"NATIVE_EXECUTED","report_sha256":sha(&bytes),"cases":cases.len(),"negative_cases":negatives.len(),"adapter":renderer.info})
    );
}

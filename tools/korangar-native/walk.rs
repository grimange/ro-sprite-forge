//! RSF-27 diagnostics around the existing pinned selection and draw corridor.
//! No image resolver or renderer is implemented here.
use super::*;
use std::sync::OnceLock;
static UPLOADS: OnceLock<Mutex<BTreeMap<u64, Value>>> = OnceLock::new();
pub fn record_texture(texture: &graphics::Texture, width: u32, height: u32, bytes: &[u8]) {
    UPLOADS.get_or_init(Default::default).lock().unwrap().insert(
        texture.get_id(), json!({"width":width,"height":height,"upload_rgba_sha256":sha(bytes)}));
}
fn upload(texture: &graphics::Texture) -> Value {
    UPLOADS.get().unwrap().lock().unwrap()[&texture.get_id()].clone()
}
pub fn run(inputs: &Value, output: &Path, texture: Arc<loaders::TextureLoader>, renderer: &mut graphics::Renderer, info: &str) {
    use world::Camera;
    let mut actors = Vec::new();
    let mut cases = Vec::new();
    let mut negatives = Vec::new();
    for spec in inputs["walk"]["actors"].as_array().unwrap() {
        let name = spec["id"].as_str().unwrap();
        let kind = if spec["kind"] == "player" { EntityType::Player } else { EntityType::Monster };
        let names: Vec<String> = serde_json::from_value(spec["parts"].clone()).unwrap();
        let loader = Arc::new(GameFileLoader { files: serde_json::from_value(inputs["files"].clone()).unwrap(), trace: Mutex::new(Vec::new()) });
        let sprites = loaders::SpriteLoader::new(loader.clone(), texture.clone());
        let actions = loaders::ActionLoader::new(loader.clone(), Arc::new(AudioEngine(std::marker::PhantomData)));
        let data = loaders::AnimationLoader::new().load(&sprites, &actions, kind, &names).unwrap();
        // A declared frame probe is a test request, never clamped into success.
        if inputs["walk"]["probe"]["actor"] == name {
            let probe = &inputs["walk"]["probe"];
            let slot = probe["slot"].as_u64().unwrap() as usize;
            let frame = probe["frame"].as_u64().unwrap() as usize;
            assert!(slot < data.animations.len(), "ACTION_UNSUPPORTED");
            assert!(frame < data.animations[slot].frames.len(), "INVALID_REQUESTED_FRAME");
        }
        let loaded = loader.trace.lock().unwrap().clone();
        assert_eq!(loaded.len(), names.len()*2, "RESOURCE_LOAD_COUNT");
        assert!(loaded.iter().all(|r| r["status"] == "LOADED_CORRECT_RESOURCE"), "RESOURCE_MISMATCH");
        let image_pools: Vec<Value> = data.animation_pair.iter().map(|p| json!({
            "indexed_count":p.sprites.palette_size,
            "truecolor_count":p.sprites.textures.len()-p.sprites.palette_size,
            "textures":p.sprites.textures.iter().map(|t|upload(t)).collect::<Vec<_>>()
        })).collect();
        let prepared: Vec<Value> = data.animations.iter().map(|a| json!(a.frames.iter().map(|f| json!({
            "offset":[f.offset.x,f.offset.y],"size":[f.size.x,f.size.y],"parts":parts(f),"event":format!("{:?}",f.event)
        })).collect::<Vec<_>>())).collect();
        // All reachable directions, both camera orientations. Native get_frame
        // supplies the selected frame; locate observes its pointer identity.
        for semantic in spec["actions"].as_array().unwrap() {
            let semantic = semantic.as_str().unwrap();
            let group = match (semantic,kind) {
                ("Walk",_)=>1, ("Idle",_)=>0,
                ("Attack",EntityType::Player)=>5, ("Attack",_)=>2,
                ("Die",EntityType::Player)=>8, ("Die",_)=>4,
                _=>panic!("ACTION_UNSUPPORTED")
            };
            for opposite in [false,true] {
                let camera = PresentationCamera { opposite };
                for direction in 0..8u16 {
                    let view = (camera.camera_direction()+usize::from(direction))&7;
                    let expected_slot = group*8+view;
                    assert!(expected_slot<data.animations.len(), "ACTION_UNSUPPORTED");
                    let count = data.animations[expected_slot].frames.len();
                    assert!(count>0, "INVALID_REQUESTED_FRAME");
                    let delay = data.delays[expected_slot];
                    let factor = if semantic=="Walk" {20.} else {50.};
                    let mut state = world::AnimationState::new(kind,ClientTick(0));
                    set_action(&mut state,kind,semantic);
                    let mut sequence=Vec::new();
                    for step in 0..count+2 {
                        let tick = if semantic=="Attack" {((step as f64+0.1)*1000./count as f64) as u32}
                                   else {((step as f64+0.1)*f64::from(delay*factor)) as u32};
                        state.update(ClientTick(tick));
                        let frame=data.get_frame(&state,&camera,Direction::from(direction));
                        let (slot,index)=locate(&data,frame);
                        let expected_frame=if semantic=="Idle" && kind==EntityType::Player {0}
                            else if ["Walk","Idle"].contains(&semantic) {step%count} else {step.min(count-1)};
                        assert_eq!((slot,index),(expected_slot,expected_frame),"REQUESTED_ACTION_MISMATCH");
                        let mut instructions=Vec::new();
                        data.render(&mut instructions,&camera,false,EntityId(1),Point3::new(0.,0.,0.),&state,Direction::from(direction),1.,1.);
                        assert_eq!(instructions.len(),frame.frame_parts.len());
                        let selected: Vec<Value>=instructions.iter().zip(&frame.frame_parts).enumerate().map(|(ordinal,(instruction,part))| {
                            let expected=&data.animation_pair[part.animation_index].sprites.textures[part.sprite_number];
                            assert!(Arc::ptr_eq(&instruction.texture,expected),"TEXTURE_SELECTION_MISMATCH");
                            assert_eq!(instruction.frame_part_transform,part.affine_matrix);
                            assert_eq!(instruction.mirror,part.mirror);
                            assert_eq!(instruction.extra_depth_offset,0.005*ordinal as f32);
                            json!({"part":part.animation_index,"image":part.sprite_number,"upload":upload(&instruction.texture)})
                        }).collect();
                        let capture=if !opposite && direction==0 && step<count {
                            let filename=format!("{name}-{semantic}-{direction}-{index}.png");
                            let mut value=renderer.capture(&instructions,&output.join(&filename));
                            value["file"]=json!(filename);
                            Some(value)
                        } else {None};
                        sequence.push(json!({"tick":tick,"resolved_slot":slot,"resolved_view":slot%8,"frame":index,"layers":instructions.len(),"selected":selected,"capture":capture}));
                    }
                    cases.push(json!({"actor":name,"requested_action":semantic,"requested_direction":direction,"camera_view":camera.camera_direction(),"resolved_view":view,"requested_slot":expected_slot,"resolved_slot":sequence[0]["resolved_slot"],"source_delay":delay,"native_delay_factor":factor,"duration":if semantic=="Attack" {Some(1000)} else {None},"frames_in_slot":count,"sequence":sequence,"fallback":"NONE","status":"REQUESTED_SLOT_VERIFIED"}));
                }
            }
        }
        // Exercise the actual native fallback/masking behavior, never count it as exact proof.
        if kind==EntityType::Monster {
            let camera=PresentationCamera {opposite:false};
            let mut short=(*data).clone();short.animations.truncate(8);short.delays.truncate(8);
            let mut state=world::AnimationState::new(kind,ClientTick(0));set_action(&mut state,kind,"Walk");
            let (slot,index)=locate(&short,short.get_frame(&state,&camera,Direction::North));
            assert_eq!(slot,0);
            negatives.push(json!({"actor":name,"case":"truncated_walk_modulo","requested_slot":8,"resolved_slot":slot,"frame":index,"status":"FALLBACK_OBSERVED","accepted_as_exact":false}));
            set_action(&mut state,kind,"CriticalAttack");
            let (slot,_)=locate(&data,data.get_frame(&state,&camera,Direction::North));assert_eq!(slot,0);
            negatives.push(json!({"actor":name,"case":"unsupported_critical_attack","resolved_slot":slot,"status":"FALLBACK_OBSERVED","accepted_as_exact":false}));
        }
        let before=loader.trace.lock().unwrap().len();
        sprites.get_or_load(&format!("{}.spr",names[0])).unwrap();
        actions.get_or_load(&format!("{}.act",names[0])).unwrap();
        assert_eq!(before,loader.trace.lock().unwrap().len(),"CACHE_RELOADED");
        actors.push(json!({"actor":name,"kind":spec["kind"],"parts":names,"loaded":loaded,"pools":image_pools,"prepared":prepared,"delays":data.delays,"cache_reused":true}));
    }
    assert_eq!(u16::from(Direction::from(8)),0);
    negatives.push(json!({"case":"unsupported_direction_8","native_masked_direction":0,"status":"ACTION_UNSUPPORTED","accepted_as_exact":false}));
    let report=json!({"schema":"rsf.native-walk/v1","mode":"isolated_native_presentation","revision":"3f3d88a583203f09d079712f43343c1041258ffd","actors":actors,"cases":cases,"negative_cases":negatives,"gameplay_reachability":"NOT_TESTED","sound_playback":"NOT_TESTED","pixel_parity":"UNVERIFIED"});
    let bytes=serde_json::to_vec_pretty(&report).unwrap();
    std::fs::write(output.join("native-report.json"),&bytes).unwrap();
    std::fs::write(output.join("environment.json"),serde_json::to_vec_pretty(&json!({"adapter":info})).unwrap()).unwrap();
    println!("{}",json!({"status":"NATIVE_EXECUTED","report_sha256":sha(&bytes),"cases":cases.len()}));
}

//! Test-only offscreen contexts around the pinned native entity drawer.
use std::sync::{Arc, OnceLock};
use wgpu::util::DeviceExt;
use wgpu::*;
mod color;
pub use color::Color;
mod texture;
pub use texture::{AttachmentTexture, Texture};
mod buffer;
pub use buffer::Buffer;
mod instruction;
pub use instruction::EntityInstruction;
mod abi;
mod traits;
use abi::*;
pub mod entity;
pub mod resolve;
pub mod passes {
    pub(crate) use super::traits::*;
    pub(crate) use super::{ForwardRenderPassContext, PostProcessingRenderPassContext};
}
pub mod shader_compiler {
    pub struct ShaderCompiler {
        pub device: std::sync::Arc<wgpu::Device>,
    }
    impl ShaderCompiler {
        pub fn create_shader_module(&self, _: &str, name: &str) -> wgpu::ShaderModule {
            let bytes = std::fs::read(format!("shaders/{name}.spv"))
                .expect("freshly compiled pinned shader");
            self.device
                .create_shader_module(wgpu::ShaderModuleDescriptor {
                    label: Some(name),
                    source: wgpu::util::make_spirv(&bytes),
                })
        }
    }
}
pub struct ScreenSize {
    pub width: f32,
    pub height: f32,
}
pub enum BindlessSupport {
    Full,
    None,
}
impl PartialEq for BindlessSupport {
    fn eq(&self, other: &Self) -> bool {
        std::mem::discriminant(self) == std::mem::discriminant(other)
    }
}
pub struct Capabilities;
impl Capabilities {
    pub fn bindless_support(&self) -> BindlessSupport {
        BindlessSupport::None
    }
    pub fn get_max_texture_binding_array_count(&self) -> u32 {
        1
    }
}
pub struct Msaa;
impl Msaa {
    pub fn sample_count(&self) -> u32 {
        1
    }
    pub fn multisampling_activated(&self) -> bool {
        false
    }
}
pub(crate) struct RenderInstruction<'a> {
    pub entities: &'a [EntityInstruction],
}
pub(crate) trait Prepare {
    fn prepare(&mut self, device: &Device, instructions: &RenderInstruction);
    fn upload(
        &mut self,
        device: &Device,
        belt: &mut util::StagingBelt,
        encoder: &mut CommandEncoder,
    );
}
pub(crate) struct GlobalContext {
    pub solid_pixel_texture: Arc<Texture>,
    pub msaa: Msaa,
    pub global: BindGroup,
    pub forward: BindGroup,
}
use traits::*;
pub(crate) struct ForwardRenderPassContext;
pub(crate) struct PostProcessingRenderPassContext;
impl
    RenderPassContext<
        { BindGroupCount::Two },
        { ColorAttachmentCount::Three },
        { DepthAttachmentCount::One },
    > for ForwardRenderPassContext
{
    type PassData<'a> = ();
    fn new(_: &Device, _: &Queue, _: &crate::loaders::TextureLoader, _: &GlobalContext) -> Self {
        Self
    }
    fn create_pass<'a>(
        &mut self,
        _: &'a mut CommandEncoder,
        _: &GlobalContext,
        _: (),
    ) -> RenderPass<'a> {
        unreachable!("offscreen attachments supplied by harness")
    }
    fn bind_group_layout(device: &Device) -> [&'static BindGroupLayout; 2] {
        [
            GlobalContext::global_bind_group_layout(device),
            GlobalContext::forward_bind_group_layout(device),
        ]
    }
    fn color_attachment_formats(&self) -> [TextureFormat; 3] {
        [
            TextureFormat::Rgba8UnormSrgb,
            TextureFormat::Rgba16Float,
            TextureFormat::R8Unorm,
        ]
    }
    fn depth_attachment_output_format(&self) -> [TextureFormat; 1] {
        [TextureFormat::Depth32Float]
    }
}
impl
    RenderPassContext<
        { BindGroupCount::One },
        { ColorAttachmentCount::One },
        { DepthAttachmentCount::None },
    > for PostProcessingRenderPassContext
{
    type PassData<'a> = ();
    fn new(_: &Device, _: &Queue, _: &crate::loaders::TextureLoader, _: &GlobalContext) -> Self {
        Self
    }
    fn create_pass<'a>(
        &mut self,
        _: &'a mut CommandEncoder,
        _: &GlobalContext,
        _: (),
    ) -> RenderPass<'a> {
        unreachable!("offscreen attachments supplied by harness")
    }
    fn bind_group_layout(device: &Device) -> [&'static BindGroupLayout; 1] {
        [GlobalContext::global_bind_group_layout(device)]
    }
    fn color_attachment_formats(&self) -> [TextureFormat; 1] {
        [TextureFormat::Rgba8UnormSrgb]
    }
    fn depth_attachment_output_format(&self) -> [TextureFormat; 0] {
        []
    }
}
impl GlobalContext {
    pub fn offscreen(
        device: &Device,
        _queue: &Queue,
        loader: &crate::loaders::TextureLoader,
        vp: cgmath::Matrix4<f32>,
        view: cgmath::Matrix4<f32>,
    ) -> Self {
        use cgmath::SquareMatrix;
        let uniforms = GlobalUniforms {
            view_projection: vp.into(),
            view: view.into(),
            inverse_view: view.invert().unwrap().into(),
            inverse_projection: cgmath::Matrix4::identity().into(),
            inverse_view_projection: vp.invert().unwrap().into(),
            indicator_positions: [[0.; 4]; 4],
            indicator_color: [0.; 4],
            ambient_color: [1.; 4],
            camera_position: [0., 10., -40., 1.],
            forward_size: [512, 512],
            interface_size: [512, 512],
            pointer_position: [0, 0],
            animation_timer: 0.,
            point_light_count: 0,
            enhanced_lighting: 1,
            shadow_method: 0,
            shadow_detail: 0,
            use_sdsm: 0,
        };
        let buf = |label: &str, data: &[u8], usage: BufferUsages| {
            device.create_buffer_init(&util::BufferInitDescriptor {
                label: Some(label),
                contents: data,
                usage,
            })
        };
        let uniform = buf(
            "native globals",
            bytemuck::bytes_of(&uniforms),
            BufferUsages::UNIFORM,
        );
        let sampler = device.create_sampler(&SamplerDescriptor {
            mag_filter: FilterMode::Linear,
            min_filter: FilterMode::Linear,
            ..Default::default()
        });
        let comparison = device.create_sampler(&SamplerDescriptor {
            compare: Some(CompareFunction::LessEqual),
            ..Default::default()
        });
        let global = device.create_bind_group(&BindGroupDescriptor {
            label: Some("native globals"),
            layout: Self::global_bind_group_layout(device),
            entries: &[
                BindGroupEntry {
                    binding: 0,
                    resource: uniform.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 1,
                    resource: BindingResource::Sampler(&sampler),
                },
                BindGroupEntry {
                    binding: 2,
                    resource: BindingResource::Sampler(&sampler),
                },
                BindGroupEntry {
                    binding: 3,
                    resource: BindingResource::Sampler(&sampler),
                },
                BindGroupEntry {
                    binding: 4,
                    resource: BindingResource::Sampler(&comparison),
                },
            ],
        });
        let make_view = |format, layers, dimension| {
            let t = device.create_texture(&TextureDescriptor {
                label: Some("zero-light native context"),
                size: Extent3d {
                    width: 32,
                    height: 32,
                    depth_or_array_layers: layers,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: TextureDimension::D2,
                format,
                usage: TextureUsages::TEXTURE_BINDING | TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            });
            t.create_view(&TextureViewDescriptor {
                dimension: Some(dimension),
                ..Default::default()
            })
        };
        let shadow = make_view(
            TextureFormat::Depth32Float,
            3,
            TextureViewDimension::D2Array,
        );
        let cube = make_view(
            TextureFormat::Depth32Float,
            6,
            TextureViewDimension::CubeArray,
        );
        let counts = make_view(TextureFormat::R32Uint, 1, TextureViewDimension::D2);
        let filtered = make_view(TextureFormat::Rgba8Unorm, 3, TextureViewDimension::D2Array);
        let directional = DirectionalLightUniforms {
            view_projection: cgmath::Matrix4::identity().into(),
            color: [0.; 4],
            direction: [0., -1., 0., 0.],
        };
        let dir = buf(
            "directional",
            bytemuck::bytes_of(&directional),
            BufferUsages::UNIFORM,
        );
        let points = buf("no points", &[0; 64], BufferUsages::STORAGE);
        let indices = buf(
            "no tile lights",
            &vec![0; size_of::<TileLightIndices>() * 32 * 32],
            BufferUsages::STORAGE,
        );
        let partition = DirectionalLightPartition {
            view_projection: cgmath::Matrix4::identity().into(),
            interval_end: 1000.,
            world_space_texel_size: 1.,
            near_plane: 0.1,
            far_plane: 1000.,
        };
        let partitions = buf(
            "native partition ABI",
            bytemuck::cast_slice(&[partition; 3]),
            BufferUsages::STORAGE,
        );
        let kernel = buf(
            "unused shadow kernel",
            &vec![0; size_of::<KernelUniforms>()],
            BufferUsages::UNIFORM,
        );
        let forward = device.create_bind_group(&BindGroupDescriptor {
            label: Some("native forward zero-light context"),
            layout: Self::forward_bind_group_layout(device),
            entries: &[
                BindGroupEntry {
                    binding: 0,
                    resource: dir.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 1,
                    resource: BindingResource::TextureView(&shadow),
                },
                BindGroupEntry {
                    binding: 2,
                    resource: points.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 3,
                    resource: BindingResource::TextureView(&counts),
                },
                BindGroupEntry {
                    binding: 4,
                    resource: indices.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 5,
                    resource: BindingResource::TextureView(&cube),
                },
                BindGroupEntry {
                    binding: 6,
                    resource: partitions.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 7,
                    resource: kernel.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 8,
                    resource: BindingResource::TextureView(&filtered),
                },
            ],
        });
        Self {
            solid_pixel_texture: loader.create_color(
                "white",
                image::RgbaImage::from_pixel(1, 1, image::Rgba([255; 4])),
                false,
            ),
            msaa: Msaa,
            global,
            forward,
        }
    }
}
pub(crate) struct Renderer {
    pub device: Arc<Device>,
    pub queue: Arc<Queue>,
    pub info: String,
    global: GlobalContext,
    drawer: entity::ForwardEntityDrawer,
    resolve: resolve::PostProcessingWboitResolveDrawer,
    color: AttachmentTexture,
    accumulation: AttachmentTexture,
    revealage: AttachmentTexture,
    depth: TextureView,
}
impl Renderer {
    pub fn new(
        device: Arc<Device>,
        queue: Arc<Queue>,
        info: String,
        loader: &crate::loaders::TextureLoader,
        vp: cgmath::Matrix4<f32>,
        view: cgmath::Matrix4<f32>,
    ) -> Self {
        let compiler = shader_compiler::ShaderCompiler {
            device: device.clone(),
        };
        let global = GlobalContext::offscreen(&device, &queue, loader, vp, view);
        let drawer = entity::ForwardEntityDrawer::new(
            &Capabilities,
            &device,
            &queue,
            &compiler,
            &global,
            &ForwardRenderPassContext,
        );
        let resolve = resolve::PostProcessingWboitResolveDrawer::new(
            &Capabilities,
            &device,
            &queue,
            &compiler,
            &global,
            &PostProcessingRenderPassContext,
        );
        let attachment = |format| {
            AttachmentTexture::new(
                &device,
                TextureDescriptor {
                    label: Some("native offscreen"),
                    size: Extent3d {
                        width: 512,
                        height: 512,
                        depth_or_array_layers: 1,
                    },
                    mip_level_count: 1,
                    sample_count: 1,
                    dimension: TextureDimension::D2,
                    format,
                    usage: TextureUsages::RENDER_ATTACHMENT
                        | TextureUsages::TEXTURE_BINDING
                        | TextureUsages::COPY_SRC,
                    view_formats: &[],
                },
                None,
            )
        };
        let color = attachment(TextureFormat::Rgba8UnormSrgb);
        let accumulation = attachment(TextureFormat::Rgba16Float);
        let revealage = attachment(TextureFormat::R8Unorm);
        let depth = device
            .create_texture(&TextureDescriptor {
                label: Some("native reverse depth"),
                size: Extent3d {
                    width: 512,
                    height: 512,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: TextureDimension::D2,
                format: TextureFormat::Depth32Float,
                usage: TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            })
            .create_view(&Default::default());
        Self {
            device,
            queue,
            info,
            global,
            drawer,
            resolve,
            color,
            accumulation,
            revealage,
            depth,
        }
    }
    pub fn capture(
        &mut self,
        entities: &[EntityInstruction],
        path: &std::path::Path,
    ) -> serde_json::Value {
        let mut encoder = self.device.create_command_encoder(&Default::default());
        let mut belt = util::StagingBelt::new((*self.device).clone(), 1024 * 1024);
        self.drawer
            .prepare(&self.device, &RenderInstruction { entities });
        self.drawer.upload(&self.device, &mut belt, &mut encoder);
        {
            let attachment = |view, clear| {
                Some(RenderPassColorAttachment {
                    view,
                    resolve_target: None,
                    depth_slice: None,
                    ops: Operations {
                        load: LoadOp::Clear(clear),
                        store: StoreOp::Store,
                    },
                })
            };
            let mut pass = encoder.begin_render_pass(&RenderPassDescriptor {
                label: Some("unchanged native entity drawer"),
                color_attachments: &[
                    attachment(self.color.get_texture_view(), wgpu::Color::BLACK),
                    attachment(
                        self.accumulation.get_texture_view(),
                        wgpu::Color::TRANSPARENT,
                    ),
                    attachment(self.revealage.get_texture_view(), wgpu::Color::WHITE),
                ],
                depth_stencil_attachment: Some(RenderPassDepthStencilAttachment {
                    view: &self.depth,
                    depth_ops: Some(Operations {
                        load: LoadOp::Clear(0.),
                        store: StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                ..Default::default()
            });
            pass.set_bind_group(0, &self.global.global, &[]);
            pass.set_bind_group(1, &self.global.forward, &[]);
            self.drawer.draw(
                &mut pass,
                entity::ForwardEntityDrawData {
                    entities,
                    pass_mode: entity::EntityPassMode::Opaque,
                },
            );
            self.drawer.draw(
                &mut pass,
                entity::ForwardEntityDrawData {
                    entities,
                    pass_mode: entity::EntityPassMode::Transparent,
                },
            );
        }
        {
            let mut pass = encoder.begin_render_pass(&RenderPassDescriptor {
                label: Some("unchanged native WBOIT resolve"),
                color_attachments: &[Some(RenderPassColorAttachment {
                    view: self.color.get_texture_view(),
                    resolve_target: None,
                    depth_slice: None,
                    ops: Operations {
                        load: LoadOp::Load,
                        store: StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            pass.set_bind_group(0, &self.global.global, &[]);
            self.resolve.draw(
                &mut pass,
                resolve::PostProcessingWboitResolveDrawData {
                    accumulation_texture: &self.accumulation,
                    revealage_texture: &self.revealage,
                },
            );
        }
        let read = self.device.create_buffer(&BufferDescriptor {
            label: Some("private capture"),
            size: 512 * 512 * 4,
            usage: BufferUsages::COPY_DST | BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        encoder.copy_texture_to_buffer(
            TexelCopyTextureInfo {
                texture: self.color.get_texture(),
                mip_level: 0,
                origin: Origin3d::ZERO,
                aspect: TextureAspect::All,
            },
            TexelCopyBufferInfo {
                buffer: &read,
                layout: TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(512 * 4),
                    rows_per_image: None,
                },
            },
            Extent3d {
                width: 512,
                height: 512,
                depth_or_array_layers: 1,
            },
        );
        belt.finish();
        self.queue.submit([encoder.finish()]);
        let (tx, rx) = std::sync::mpsc::channel();
        read.slice(..).map_async(MapMode::Read, move |r| {
            tx.send(r).unwrap();
        });
        self.device.poll(PollType::wait_indefinitely()).unwrap();
        rx.recv().unwrap().unwrap();
        let pixels = read.slice(..).get_mapped_range();
        let lit = pixels
            .chunks_exact(4)
            .filter(|p| p[..3] != [0, 0, 0])
            .count();
        image::save_buffer(path, &pixels, 512, 512, image::ColorType::Rgba8).unwrap();
        serde_json::json!({"non_background_pixels":lit,"png_sha256":crate::sha(&std::fs::read(path).unwrap()),"drawn_layers":entities.len(),"passes":["opaque","transparent","wboit_resolve"]})
    }
}

# utils 模块

def __getattr__(name):
    """Lazy imports to avoid circular/import errors."""
    if name in ('create_backend', 'create_backend_from_env', 'rewrite_note', 'rewrite_batch'):
        from utils.rewrite import create_backend, create_backend_from_env, rewrite_note, rewrite_batch
        return globals().get(name) or {
            'create_backend': create_backend,
            'create_backend_from_env': create_backend_from_env,
            'rewrite_note': rewrite_note,
            'rewrite_batch': rewrite_batch,
        }[name]
    if name in ('ImageProcessor', 'process_image', 'process_images',
                'light_processor', 'medium_processor', 'heavy_processor'):
        from utils.image_processor import (
            ImageProcessor, process_image, process_images,
            light_processor, medium_processor, heavy_processor
        )
        return globals().get(name) or {
            'ImageProcessor': ImageProcessor,
            'process_image': process_image,
            'process_images': process_images,
            'light_processor': light_processor,
            'medium_processor': medium_processor,
            'heavy_processor': heavy_processor,
        }[name]
    raise AttributeError(f"module 'utils' has no attribute '{name}'")

# Keep direct imports for backward compatibility
from utils.image_processor import (
    ImageProcessor, process_image, process_images,
    light_processor, medium_processor, heavy_processor
)

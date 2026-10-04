"""
Thumbnail caching system for fast image loading
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Transparent areas are filled with this (the dark theme background).
BACKGROUND_COLOR = (30, 32, 36)


def _load_scaled_rgb(image_path: str, size: Tuple[int, int]) -> Optional[Image.Image]:
    """Open an image, honour its EXIF rotation, shrink it to fit size,
    and flatten any transparency onto BACKGROUND_COLOR as RGB."""
    try:
        img = ImageOps.exif_transpose(Image.open(image_path))
    except Exception as e:
        logger.warning(f"Error loading image {image_path}: {e}")
        return None
    try:
        if img.width > 0 and img.height > 0:
            img.thumbnail(size, Image.Resampling.LANCZOS)
        if img.mode == 'RGB':
            return img
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, BACKGROUND_COLOR)
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            return background
        return img.convert('RGB')
    except Exception as e:
        logger.warning(f"Error creating thumbnail for {image_path}: {e}")
        return None


class ThumbnailCache:
    """Manages thumbnail generation and caching for card images"""

    THUMBNAIL_SIZE = (300, 450)
    PREVIEW_SIZE = (500, 750)
    # Phone-companion derivative: big enough to look good full-screen
    # on a modern iPhone, far smaller than the raw scans.
    PHONE_SIZE = (1000, 1500)

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            # Default to a .cache folder in the app directory
            self.cache_dir = Path(os.path.dirname(os.path.abspath(__file__))) / ".thumbnail_cache"
        else:
            self.cache_dir = Path(cache_dir)
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, image_path: str, size: Tuple[int, int]) -> str:
        """Generate a unique cache key for an image at a specific size"""
        # Use path + modification time + size for cache key
        try:
            mtime = os.path.getmtime(image_path)
        except OSError:
            mtime = 0
        
        key_string = f"{image_path}:{mtime}:{size[0]}x{size[1]}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cached thumbnail"""
        return self.cache_dir / f"{cache_key}.png"
    
    def get_thumbnail(self, image_path: str, size: Tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Get a thumbnail for an image, creating it if necessary.
        Returns a PIL Image object.
        """
        if size is None:
            size = self.THUMBNAIL_SIZE
        
        if not image_path or not os.path.exists(image_path):
            return None
        
        cache_key = self._get_cache_key(image_path, size)
        cache_path = self._get_cache_path(cache_key)
        
        # Check if cached thumbnail exists
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception as e:
                # Corrupted cache file, regenerate
                logger.debug("Corrupted cache file %s, regenerating: %s", cache_path, e)
                cache_path.unlink(missing_ok=True)
        
        img = _load_scaled_rgb(image_path, size)
        if img is None:
            return None

        try:
            img.save(cache_path, 'PNG', optimize=True)
            return img
        except Exception as e:
            logger.warning(f"Error saving thumbnail for {image_path}: {e}")
            return None
    
    def get_thumbnail_path(self, image_path: str, size: Tuple[int, int] = None) -> Optional[str]:
        """
        Get the path to a cached thumbnail, creating it if necessary.
        Returns the path to the thumbnail file.
        """
        if size is None:
            size = self.THUMBNAIL_SIZE
        
        if not image_path or not os.path.exists(image_path):
            return None
        
        cache_key = self._get_cache_key(image_path, size)
        cache_path = self._get_cache_path(cache_key)
        
        # Check if cached thumbnail exists and is valid
        if cache_path.exists():
            return str(cache_path)
        
        # Generate thumbnail
        thumb = self.get_thumbnail(image_path, size)
        if thumb:
            return str(cache_path)
        
        return None
    
    def clear_cache(self):
        """Clear all cached thumbnails"""
        for file in self.cache_dir.glob('*.png'):
            try:
                file.unlink()
            except OSError as e:
                logger.debug("Failed to delete cache file %s: %s", file, e)
    
    def get_cache_size(self) -> int:
        """Get the total size of the cache in bytes"""
        total = 0
        for file in self.cache_dir.glob('*.png'):
            try:
                total += file.stat().st_size
            except OSError:
                # File may have been deleted between glob and stat
                pass
        return total
    
    def get_cache_count(self) -> int:
        """Get the number of cached thumbnails"""
        return len(list(self.cache_dir.glob('*.png')))


# Global cache instance
_cache_instance = None


def get_cache() -> ThumbnailCache:
    """Get the global thumbnail cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ThumbnailCache()
    return _cache_instance

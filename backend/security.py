"""
Security utilities for path validation and input sanitization.

This module prevents path traversal attacks by ensuring that file paths
stay within expected directories before serving or reading them.
"""

import os
from typing import Optional, List

# Image file extensions we allow serving
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}


def is_safe_path(path: str, allowed_directories: Optional[List[str]] = None) -> bool:
    """
    Check if a file path is safe to access.

    A path is considered safe if:
    1. It resolves to a real path (no symlink tricks)
    2. It doesn't contain path traversal patterns
    3. If allowed_directories is provided, the resolved path must be within one of them

    Args:
        path: The file path to validate
        allowed_directories: Optional list of directories the path must be within

    Returns:
        True if the path is safe, False otherwise
    """
    if not path:
        return False

    try:
        # Resolve to absolute path, following symlinks
        real_path = os.path.realpath(path)

        # Check for null bytes (can be used to truncate paths in some systems)
        if '\x00' in path:
            return False

        # If no directory restrictions, just check the file exists
        if allowed_directories is None:
            return os.path.exists(real_path)

        # Check if the resolved path is within any of the allowed directories
        for allowed_dir in allowed_directories:
            allowed_real = os.path.realpath(allowed_dir)
            # Use os.path.commonpath to check containment
            try:
                common = os.path.commonpath([real_path, allowed_real])
                if common == allowed_real:
                    return True
            except ValueError:
                # Paths on different drives (Windows) - not allowed
                continue

        return False

    except (OSError, TypeError, ValueError):
        return False


def is_valid_image_path(path: str, allowed_directories: Optional[List[str]] = None) -> bool:
    """
    Check if a path points to a valid image file.

    Args:
        path: The file path to validate
        allowed_directories: Optional list of directories the path must be within

    Returns:
        True if the path is a valid, accessible image file
    """
    if not path:
        return False

    # Check extension
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    # Check path safety
    if not is_safe_path(path, allowed_directories):
        return False

    # Verify it's actually a file (not a directory)
    real_path = os.path.realpath(path)
    return os.path.isfile(real_path)


def is_valid_directory(path: str) -> bool:
    """True if path is an existing, accessible directory."""
    if not path or '\x00' in path:
        return False
    try:
        return os.path.isdir(os.path.realpath(path))
    except (OSError, TypeError, ValueError):
        return False

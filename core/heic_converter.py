"""
AirBridge - Smart Auto HEIC-to-JPG Converter
Seamlessly transforms Apple iPhone .HEIC/.HEIF photos into high-compatibility .JPG
Created by Chathunga
"""

import io
import os
import logging
from pathlib import Path
from typing import Tuple, Union, Optional
from PIL import Image, ImageOps

logger = logging.getLogger("AirBridge.HEICConverter")

# Register pillow_heif with PIL
_HEIF_REGISTERED = False
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HEIF_REGISTERED = True
    logger.info("pillow_heif registered successfully.")
except Exception as e:
    logger.warning(f"Could not register pillow_heif opener: {e}")


def is_heic_extension(filename: str) -> bool:
    """Check if filename has a HEIC or HEIF extension."""
    ext = Path(filename).suffix.lower()
    return ext in {".heic", ".heif", ".hif"}


def is_heic_data(data: bytes) -> bool:
    """Check if byte header matches HEIF/HEIC signature (ftypheic, ftypmif1, ftypmsf1, etc.)."""
    if len(data) < 12:
        return False
    # Check ISO base media file format brand at offset 4..12
    brand = data[4:12].lower()
    heic_signatures = [b"ftypheic", b"ftypheix", b"ftypheim", b"ftypheis", b"ftypmif1", b"ftypmsf1"]
    return any(sig in brand for sig in heic_signatures)


def convert_heic_bytes_to_jpg(
    file_bytes: bytes,
    original_filename: str,
    quality: int = 95
) -> Tuple[bytes, str]:
    """
    Convert raw HEIC/HEIF bytes to high-quality JPEG bytes.
    Returns: (jpg_bytes, new_filename)
    """
    stem = Path(original_filename).stem
    new_filename = f"{stem}.jpg"

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            # Preserve proper EXIF orientation
            try:
                img = ImageOps.exif_transpose(img)
            except Exception as e:
                logger.debug(f"exif_transpose skipped: {e}")

            # Convert color mode to RGB if RGBA, P, etc.
            if img.mode in ("RGBA", "LA", "P"):
                # Create white background for alpha channels
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Extract EXIF if present
            exif = img.info.get("exif")

            out_io = io.BytesIO()
            save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
            if exif:
                save_kwargs["exif"] = exif

            img.save(out_io, **save_kwargs)
            logger.info(f"Successfully converted '{original_filename}' to '{new_filename}'")
            return out_io.getvalue(), new_filename

    except Exception as e:
        logger.error(f"Failed to convert HEIC to JPG for {original_filename}: {e}")
        # Return original if conversion fails
        return file_bytes, original_filename


def convert_heic_file(
    input_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    quality: int = 95,
    remove_original: bool = False
) -> Path:
    """
    Convert a saved HEIC file on disk to a JPG file.
    Returns path to the new JPG file.
    """
    in_path = Path(input_path)
    out_dir = Path(output_dir) if output_dir else in_path.parent
    out_path = out_dir / f"{in_path.stem}.jpg"

    with in_path.open("rb") as f:
        data = f.read()

    jpg_data, _ = convert_heic_bytes_to_jpg(data, in_path.name, quality=quality)
    with out_path.open("wb") as f:
        f.write(jpg_data)

    if remove_original and out_path != in_path and in_path.exists():
        try:
            in_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove original HEIC file: {e}")

    return out_path

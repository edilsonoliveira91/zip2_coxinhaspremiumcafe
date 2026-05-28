from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def _resampling_filter():
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.LANCZOS


def get_max_image_upload_bytes():
    mb = getattr(settings, "IMAGE_UPLOAD_MAX_MB", 8)
    try:
        mb = int(mb)
    except (TypeError, ValueError):
        mb = 8
    return max(mb, 1) * 1024 * 1024


def validate_image_file_size(file_obj):
    if not file_obj:
        return
    size = getattr(file_obj, "size", None)
    if size is None:
        return
    max_bytes = get_max_image_upload_bytes()
    if size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValidationError(f"A imagem excede o limite de {max_mb} MB.")


def compress_image_field(image_field, max_size=(1600, 1600), quality=82):
    """Compresses an ImageField file in-place and keeps the same file name."""
    if not image_field or not getattr(image_field, "name", None) or Image is None:
        return False

    try:
        image_field.open("rb")
        original_bytes = image_field.read()
        image_field.close()

        if not original_bytes:
            return False

        original_size = len(original_bytes)

        with Image.open(BytesIO(original_bytes)) as img:
            img_format = (img.format or "JPEG").upper()

            if img_format == "PNG":
                target_format = "PNG"
            elif img_format == "WEBP":
                target_format = "WEBP"
            else:
                target_format = "JPEG"

            if target_format == "JPEG" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            if max_size:
                img.thumbnail(max_size, _resampling_filter())

            optimized = BytesIO()
            save_kwargs = {"optimize": True}

            if target_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality
            elif target_format == "PNG":
                save_kwargs["compress_level"] = 9

            img.save(optimized, format=target_format, **save_kwargs)
            new_bytes = optimized.getvalue()

        if len(new_bytes) >= original_size:
            return False

        file_name = image_field.name
        storage = image_field.storage
        storage.delete(file_name)
        storage.save(file_name, ContentFile(new_bytes))
        return True
    except Exception:
        return False

import logging
import magic
import boto3
from PIL import Image
from io import BytesIO

from . import immutable, config, llm_util
from .custom_exceptions import InfomundiCustomException

# Configure basic logging
target_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# r2/S3 client configuration
s3_client = boto3.client(
    "s3",
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET,
    region_name="auto",
)

# Preload magic for MIME detection
_mime_detector = magic.Magic(mime=True)

# Allowed settings
IMAGE_CATEGORIES = {
    "profile_picture": {"crop": True, "size": (500, 500)},
    "profile_banner": {"crop": False, "size": (1600, 400)},
    "profile_wallpaper": {"crop": False, "size": (1920, 1080)},
}

# Use LANCZOS resampling filter (ANTIALIAS deprecated in Pillow >=10)
RESAMPLE_FILTER = Image.LANCZOS


def is_extension_allowed(filename: str) -> bool:
    if "." not in filename:
        return True
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in immutable.IMAGE_EXTENSIONS


def has_valid_mime_type(stream: BytesIO) -> bool:
    header = stream.read(2048)
    mime = _mime_detector.from_buffer(header)
    stream.seek(0)
    return mime in immutable.IMAGE_MIME


def is_really_an_image(stream: BytesIO) -> bool:
    try:
        with Image.open(stream) as img:
            img.verify()
    except Exception:
        stream.seek(0)
        return False
    stream.seek(0)
    return True


def has_allowed_dimensions(
    stream: BytesIO, min_w=150, min_h=150, max_w=5000, max_h=5000
) -> bool:
    with Image.open(stream) as img:
        w, h = img.size
    stream.seek(0)
    return (min_w <= w <= max_w) and (min_h <= h <= max_h)


def validate_image(image_bytes: bytes, filename: str) -> None:
    """Runs all checks on the image and raises InfomundiCustomException(message=) on failure."""
    target_logger.info("Validating image %s", filename)

    if not is_extension_allowed(filename):
        raise InfomundiCustomException(message="Invalid file extension.")

    stream = BytesIO(image_bytes)
    if not has_valid_mime_type(stream):
        raise InfomundiCustomException(message="Disallowed MIME type.")

    if not is_really_an_image(stream):
        raise InfomundiCustomException(message="Cannot identify or decode image.")

    if not has_allowed_dimensions(stream):
        raise InfomundiCustomException(message="Image dimensions out of allowed range.")

    # AI-based inappropriate content check
    if llm_util.is_inappropriate(image_stream=BytesIO(image_bytes)):
        raise InfomundiCustomException(message="Image flagged as inappropriate.")

    target_logger.info("Image passed validation: %s", filename)


def process_image(image_bytes: bytes, category: str) -> BytesIO:
    """Crops/resizes the image per category rules and returns a WebP buffer."""
    rules = IMAGE_CATEGORIES.get(category)
    if rules is None:
        raise ValueError(f"Unknown category: {category}")

    stream = BytesIO(image_bytes)
    with Image.open(stream) as img:
        if rules["crop"]:
            side = min(img.width, img.height)
            left = (img.width - side) / 2
            top = (img.height - side) / 2
            img = img.crop((left, top, left + side, top + side))

        # Use LANCZOS filter for high-quality downsampling
        img.thumbnail(rules["size"], RESAMPLE_FILTER)
        img = img.convert("RGB")

        out = BytesIO()
        img.save(out, format="WEBP", optimize=True, quality=70, progressive=True)
        out.seek(0)
        return out


def upload_image(buffer: BytesIO, s3_key: str) -> None:
    """Uploads a BytesIO buffer to S3; raises on failure."""
    try:
        s3_client.upload_fileobj(buffer, config.BUCKET_NAME, s3_key)
        target_logger.info("Uploaded to %s", s3_key)
    except Exception as e:
        target_logger.error("Upload failed for %s: %s", s3_key, e)
        raise


def convert_and_save(file_stream, filename: str, category: str, s3_key: str) -> tuple:
    """
    Reads from a file-like object or bytes, validates, processes, and uploads.
    Returns (True, "Upload successful") on success, or (False, error_message) on failure.
    """
    try:
        # Read bytes from stream or accept raw bytes
        if hasattr(file_stream, "read"):
            try:
                file_stream.seek(0)
            except Exception:
                pass
            image_bytes = file_stream.read()
        elif isinstance(file_stream, (bytes, bytearray)):
            image_bytes = file_stream
        else:
            raise InfomundiCustomException(message="Unsupported file_stream type.")

        validate_image(image_bytes, filename)
        buffer = process_image(image_bytes, category)
        upload_image(buffer, s3_key)
        buffer.close()
        return (True, "Upload successful")

    except InfomundiCustomException as err:
        target_logger.warning("Validation error: %s", err.message)
        return (False, err.message)
    except Exception as e:
        target_logger.error("Error in convert_and_save: %s", e)
        return (False, "Unknown error")

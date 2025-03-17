import magic, boto3
from io import BytesIO
from PIL import Image

from . import immutable, config, llm_util

# r2 configuration
s3_client = boto3.client(
    's3',
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET,
    region_name='auto',
)


def convert_and_save(image_stream: bytes, image_category: str, s3_object_key: str, dimensions: tuple=(500, 500)) -> bool:
    """
    Uses PIL library to crop the image into a square (if it's a profile picture), 
    convert to jpeg and upload to the bucket.

    Arguments:
        image_stream: bytes
            The image iteself, in bytes.

        image_category: str
            The image category, should be in ('profile_picture', 'background_image')
        
        dimensions: tuple
            A tuple containing dimensions to save the image with. Example 500 width x 333 height would be: (500, 333)
        
        s3_object_key: str 
            Where to save the file in the bucket. Example: 'users/5045a910.jpg'

    Return:
        bool: True if the image got uploaded to the bucket. False otherwise.
    """
    if image_category not in ('profile_picture', 'profile_banner', 'profile_background'):
        return False

    image = Image.open(image_stream)

    # If the image is a profile picture, the image should be squared
    if image_category == 'profile_picture':
        shortest_side = min(image.width, image.height)
        left = (image.width - shortest_side) / 2
        top = (image.height - shortest_side) / 2
        right = (image.width + shortest_side) / 2
        bottom = (image.height + shortest_side) / 2

        image = image.crop((left, top, right, bottom))
        image.thumbnail(dimensions)
    
    image = image.convert("RGB")

    # Creates and saves the output image buffer so we can upload them later to the bucket.
    output_buffer = BytesIO()
    image.save(output_buffer, format="JPEG", optimize=True, quality=50, progressive=True)

    output_buffer.seek(0)

    # Tries to upload the buffer content to R2
    try:
        s3_client.upload_fileobj(output_buffer, config.BUCKET_NAME, s3_object_key)
    except Exception as e:
        return False
        
    # Close the buffer for God's sake
    output_buffer.close()
    return True


def is_extension_allowed(filename: str) -> bool:
    return ('.' in filename and \
        filename.rsplit('.', 1)[1].lower() in immutable.IMAGE_EXTENSIONS)


def is_really_an_image(file_stream) -> bool:
    try:
        with Image.open(file_stream) as img:
            # Verifies that an image can be opened and decoded
            img.verify()
        
        # Reset file stream position
        file_stream.seek(0)
    except Exception:
        return False

    return True


def has_valid_mime_type(file_stream: bytes) -> bool:
    # Reads the mime type from the first bytes of the image
    mime = magic.from_buffer(file_stream.read(2048), mime=True)
    
    # Reset file stream position
    file_stream.seek(0)
    
    return mime in ('image/png', 'image/jpeg', 'image/jpg', 'image/webp')


def has_allowed_dimensions(image_stream: bytes, min_width: int=200, min_height: int=200) -> bool:
    """Checks if image dimension is in range. The image should not be bigger than 3000x3000 to
    avoid pixel bomb DoS attack.
    
    Arguments
        image_stream (bytes): The image itself.
        min_width (int): Defaults to 300. The minimum width.
        min_height (int): Defaults to 300. The minimum height.

    Returns
        bool: If the image complies with the determined min and max width and height.
    """
    image = Image.open(image_stream)
    width, height = image.size

    minimum_dimensions = (width >= min_width and height >= min_height)
    maximum_dimensions = (width <= 3000 and height <= 3000)

    return minimum_dimensions and maximum_dimensions


def perform_all_checks(image_stream: bytes, filename: str) -> bool:
    """Performs all checks to make sure the user-supplied image is safe"""
    return (is_extension_allowed(filename) and has_valid_mime_type(image_stream) \
        and is_really_an_image(image_stream) and has_allowed_dimensions(image_stream) and not llm_util.is_inappropriate(image_stream))

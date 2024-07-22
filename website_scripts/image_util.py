import magic, boto3
from io import BytesIO
from PIL import Image

from . import immutable, config

# r2 configuration
s3_client = boto3.client(
    's3',
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET,
    region_name='auto',
)


def convert_to_jpg(image_stream: bytes, s3_object_key: str, dimensions: tuple=(500, 500)) -> bool:
    """Uses PIL library to crop the image into a quare, convert to jpeg, save the data a IO buffer and upload to the bucket.

    Arguments:
        image_stream: bytes
            The image iteself, in bytes.
        
        dimensions: tuple
            A tuple containing dimensions to save the image with. Example 500 width x 333 height would be: (500, 333)
        
        s3_object_key: str 
            Where to save the file in the bucket. Example: 'users/5045a910.jpg'
    """
    image = Image.open(image_stream)

    shortest_side = min(image.width, image.height)

    left = (image.width - shortest_side) / 2
    top = (image.height - shortest_side) / 2
    right = (image.width + shortest_side) / 2
    bottom = (image.height + shortest_side) / 2

    image = image.crop((left, top, right, bottom))
    image.thumbnail(dimensions)
    image = image.convert("RGB")

    output_buffer = BytesIO()
    image.save(output_buffer, format="JPEG", optimize=True, quality=50, progressive=True)

    output_buffer.seek(0)

    try:
        # Upload the buffer content to R2
        s3_client.upload_fileobj(output_buffer, config.BUCKET_NAME, s3_object_key)
    except Exception as e:
        return False
        
    output_buffer.close()
    return True


def allowed_mime_type(file_stream):
    mime = magic.from_buffer(file_stream.read(2048), mime=True)
    
    # Reset file stream position
    file_stream.seek(0)
    
    return mime in ['image/png', 'image/jpeg', 'image/jpg']


def verify_image_content(file_stream):
    try:
        with Image.open(file_stream) as img:
            # Verifies that an image can be opened and decoded
            img.verify()
        
        # Reset file stream position
        file_stream.seek(0)
        
        return True
    except Exception:
        return False


def allowed_file(filename: str) -> bool:
    for extension in immutable.IMAGE_EXTENSIONS:
        if filename.lower().endswith(extension):
            break
    else:
        return False

    return True


def check_image_dimensions(image_stream, min_width: int=300, min_height: int=300) -> bool:
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

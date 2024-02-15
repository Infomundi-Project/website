import magic
from PIL import Image

from . import immutable

def convert_to_webp(image_stream, filepath:str, dimensions: tuple=(500, 500)):
    """Uses PIL library to convert image stream to webp, saving locally.

    Arguments
        image_stream - Usually bytes. The image iteself.
        dimensions:tuple - A tuple containing dimensions to save the image with. Example 500 width x 333 height would be: (500, 333)
        filepath:str - Where to save the file in the system.
    
    Return: bool
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

    image.save(f"{filepath}.webp", format="webp", optimize=True, quality=70, method=6)
    
    return True


def allowed_mime_type(file_stream):
    mime = magic.from_buffer(file_stream.read(2048), mime=True)
    file_stream.seek(0)  # Reset file stream position
    return mime in ['image/png', 'image/jpeg', 'image/gif']


def verify_image_content(file_stream):
    try:
        with Image.open(file_stream) as img:
            img.verify()  # Verifies that an image can be opened and decoded
        file_stream.seek(0)  # Reset file stream position
        return True
    except Exception:
        return False


def allowed_file(filename):
    for extension in immutable.IMAGE_EXTENSIONS:
        if filename.lower().endswith(extension):
            break
    else:
        return False

    return True


def check_image_dimensions(image_stream, min_width: int=300, min_height: int=300):
    image = Image.open(image_stream)
    width, height = image.size
    return width >= min_width and height >= min_height

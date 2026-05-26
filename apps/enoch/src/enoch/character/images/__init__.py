"""Image-related command interface."""

from enoch.character.images.display import display_images as display
from enoch.character.images.upload import upload_image as upload

__all__ = ("display", "upload")

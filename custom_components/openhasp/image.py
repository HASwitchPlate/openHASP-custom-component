import logging
import pathlib
import asyncio
import requests
import struct

from .const import DATA_IMAGES
from PIL import Image, ImageOps, UnidentifiedImageError
from aiohttp import hdrs, web
import tempfile

from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.components.http.view import HomeAssistantView

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

def image_to_rgb565(in_image, size=(128, 128)):
    filesize = 0

    try:
        if in_image.startswith('http'):
            im = Image.open(requests.get(in_image, stream=True).raw)
        else:
            im = Image(in_image)
    except:
        _LOGGER.error("Failed to open %s", in_image)
        return

    im.thumbnail(size, Image.ANTIALIAS)

    height, width = size

    out_image = tempfile.NamedTemporaryFile(mode="wb")

    out_image.write(struct.pack('I', height<<21 | width<<10 | 4))

    img = im.convert('RGB')
    
    for pix in list(img.getdata()):
        r = (pix[0] >> 3) & 0x1F
        g = (pix[1] >> 2) & 0x3F
        b = (pix[2] >> 3) & 0x1F
        out_image.write(struct.pack('H', (r << 11) | (g << 5) | b))
    
    _LOGGER.debug("out_image: %s", out_image.name)

    return out_image

class ImageServeView(HomeAssistantView):
    """View to download images."""

    url = "/api/openhasp/serve/{image_id}"
    name = "api:openhasp:serve"
    requires_auth = False

    def __init__(self) -> None:
        """Initialize image serve view."""


    async def get(self, request: web.Request, image_id: str):
        """Serve image."""

        hass = request.app["hass"]
        target_file = hass.data[DOMAIN][DATA_IMAGES][image_id]

        _LOGGER.error("Get Image %s form %s", image_id, target_file.name)

        return web.FileResponse(
            target_file.name,
            headers={**CACHE_HEADERS, hdrs.CONTENT_TYPE: "image/bmp"}
        )
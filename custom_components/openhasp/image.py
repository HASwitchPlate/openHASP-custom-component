"""Image processing and serving functions."""

import logging
import struct
import tempfile

from PIL import Image
from aiohttp import hdrs, web
from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.components.http.view import HomeAssistantView
import requests

from .const import DATA_IMAGES, DOMAIN

_LOGGER = logging.getLogger(__name__)


def image_to_rgb565(in_image, size):
    """Transform image to rgb565 format according to LVGL requirements."""
    try:
        if in_image.startswith("http"):
            im = Image.open(requests.get(in_image, stream=True).raw)
        else:
            im = Image.open(in_image)
    except Exception:
        _LOGGER.error("Failed to open %s", in_image)
        return None

    original_width, original_height = im.size
    width, height = size

    width = min(w for w in [width, original_width] if w is not None)
    height = min(h for h in [height, original_height] if h is not None)

    im.thumbnail((height, width), Image.ANTIALIAS)

    out_image = tempfile.NamedTemporaryFile(mode="w+b")

    out_image.write(struct.pack("I", width << 21 | height << 10 | 4))

    img = im.convert("RGB")

    for pix in list(img.getdata()):
        r = (pix[0] >> 3) & 0x1F
        g = (pix[1] >> 2) & 0x3F
        b = (pix[2] >> 3) & 0x1F
        out_image.write(struct.pack("H", (r << 11) | (g << 5) | b))

    _LOGGER.debug("image_to_rgb565 out_image: %s", out_image.name)

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

        _LOGGER.debug("Get Image %s form %s", image_id, target_file.name)

        return web.FileResponse(
            target_file.name, headers={**CACHE_HEADERS, hdrs.CONTENT_TYPE: "image/bmp"}
        )

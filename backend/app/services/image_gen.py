"""Generate card image from prompt via OpenAI DALL·E 3 and save to local storage."""

import base64
import logging
import os
from app.config import get_settings

logger = logging.getLogger(__name__)

# Default content type for DALL·E 3 PNG
DEFAULT_CONTENT_TYPE = "image/png"


def generate_and_save_image(
    prompt: str,
    *,
    deck_id: str,
    card_id: str,
) -> tuple[str, str]:
    """
    Call image API with prompt, save file under storage_dir/decks/{deck_id}/{card_id}.png.
    Returns (storage_path, content_type). storage_path is relative, e.g. decks/{deck_id}/{card_id}.png.
    Raises if API key missing or API call fails.
    """
    settings = get_settings()
    if not (getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY")):
        raise ValueError("OPENAI_API_KEY is not set")
    storage_dir = getattr(settings, "image_storage_dir", None) or os.getenv("IMAGE_STORAGE_DIR", "uploads")
    deck_dir = os.path.join(storage_dir, "decks", deck_id)
    os.makedirs(deck_dir, exist_ok=True)
    filename = f"{card_id}.png"
    absolute_path = os.path.join(deck_dir, filename)
    relative_path = f"decks/{deck_id}/{filename}"

    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", getattr(settings, "openai_api_key", "")))
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
        response_format="b64_json",
    )
    b64 = response.data[0].b64_json
    if not b64:
        raise ValueError("Image API did not return b64_json")
    data = base64.b64decode(b64)
    with open(absolute_path, "wb") as f:
        f.write(data)
    logger.info("Saved image to %s", relative_path)
    return relative_path, DEFAULT_CONTENT_TYPE

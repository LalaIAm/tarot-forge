"""Tests for image generation service. Mocks OpenAI API."""

import base64
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.services.image_gen import generate_and_save_image


# Minimal 1x1 PNG (valid PNG bytes)
_MINIMAL_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def test_generate_and_save_image_returns_path_and_content_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "IMAGE_STORAGE_DIR": tmpdir}):
            mock_response = MagicMock()
            mock_response.data = [MagicMock(b64_json=_MINIMAL_PNG_B64)]
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_client.images.generate.return_value = mock_response
                mock_openai.return_value = mock_client
                path, content_type = generate_and_save_image(
                    "A fool at a cliff",
                    deck_id="deck-123",
                    card_id="card-456",
                )
                assert path == "decks/deck-123/card-456.png"
                assert content_type == "image/png"
                full_path = os.path.join(tmpdir, path)
                assert os.path.isfile(full_path)
                with open(full_path, "rb") as f:
                    data = f.read()
                assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_and_save_image_raises_when_api_key_missing():
    with patch("app.services.image_gen.get_settings") as mock_settings:
        mock_settings.return_value = type("S", (), {"openai_api_key": "", "image_storage_dir": tempfile.gettempdir()})()
        with patch("app.services.image_gen.os.getenv", return_value=None):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                generate_and_save_image("test", deck_id="d", card_id="c")

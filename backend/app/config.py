import os


def get_settings():
    """Simple settings: DATABASE_URL defaults to SQLite for MVP."""
    return type("Settings", (), {
        "database_url": os.getenv("DATABASE_URL", "sqlite:///./vibe_tarot.db"),
        "image_storage_dir": os.getenv("IMAGE_STORAGE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    })()

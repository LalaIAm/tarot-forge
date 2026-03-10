import os


def get_settings():
    """Simple settings: DATABASE_URL defaults to SQLite for MVP."""
    return type("Settings", (), {
        "database_url": os.getenv("DATABASE_URL", "sqlite:///./vibe_tarot.db"),
    })()

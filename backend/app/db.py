from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()
connect_args = {}
if "sqlite" in settings.database_url:
    connect_args["check_same_thread"] = False
# Use StaticPool for sqlite :memory: so all threads (e.g. TestClient request thread) share the same DB
kwargs = {"connect_args": connect_args} if connect_args else {}
if ":memory:" in settings.database_url:
    kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call on app startup or for tests."""
    from app import models  # noqa: F401 - register models with Base
    Base.metadata.create_all(bind=engine)

# Set in-memory DB before any app import so init_db() creates tables there
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Apply shared in-memory DB override so all API tests use the same DB
from tests import shared_db  # noqa: F401, E402

# Set in-memory DB before any app import so init_db() creates tables there
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

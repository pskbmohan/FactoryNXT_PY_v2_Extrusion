import os
from dotenv import load_dotenv

# override=False: real env vars (Docker Compose / DO App Platform) always
# take precedence over any .env file on disk.
load_dotenv(override=False)


def _normalise_db_url(url: str) -> str:
    """DigitalOcean App Platform injects DATABASE_URL as postgres://...
    SQLAlchemy 2.x requires postgresql+psycopg2://  — fix it here so
    the app works on both DO App Platform and local Docker Compose.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    _raw_db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/factorynxt",
    )
    SQLALCHEMY_DATABASE_URI = _normalise_db_url(_raw_db_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

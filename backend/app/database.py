import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)


def normalize_url(url: str) -> str:
    """Point bare postgres URLs at psycopg 3, the only Postgres driver installed.

    Hosted providers (Neon, Vercel Storage) hand out `postgres://` or
    `postgresql://`, which SQLAlchemy maps to psycopg2 and fails to import.
    """
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg://' + url[len(prefix):]
    return url


database_url = normalize_url(os.getenv('DATABASE_URL', 'sqlite:///./paid_growth.db'))
engine = create_engine(database_url, connect_args={'check_same_thread': False} if database_url.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session

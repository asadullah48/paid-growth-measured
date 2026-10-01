import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)
database_url = os.getenv('DATABASE_URL', 'sqlite:///./paid_growth.db')
engine = create_engine(database_url, connect_args={'check_same_thread': False} if database_url.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session

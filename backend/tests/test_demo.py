"""Public-demo switches: read-only mode, URL normalisation, bootstrap."""
import os

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('FRONTEND_ORIGIN', 'http://localhost:3000')

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import demo
from app.database import SessionLocal, normalize_url
from app.main import app
from app.models import Agency, User
from tests.test_workflows import HEADERS, PASSWORD, env, session  # noqa: F401  (fixture)


def test_postgres_urls_are_pointed_at_psycopg3():
    assert normalize_url('postgres://u:p@h/db?sslmode=require') == 'postgresql+psycopg://u:p@h/db?sslmode=require'
    assert normalize_url('postgresql://u:p@h/db') == 'postgresql+psycopg://u:p@h/db'
    assert normalize_url('postgresql+psycopg://u:p@h/db') == 'postgresql+psycopg://u:p@h/db'
    assert normalize_url('sqlite:///./x.db') == 'sqlite:///./x.db'


def test_read_only_is_off_by_default(env, monkeypatch):
    monkeypatch.delenv('DEMO_READ_ONLY', raising=False)
    client = session()
    assert client.get('/auth/me').json()['read_only'] is False
    created = client.post('/records/clients', json={'name': 'Writable'}, headers=HEADERS)
    assert created.status_code == 201, created.text


def test_read_only_refuses_writes_but_allows_sign_in_and_reads(env, monkeypatch):
    monkeypatch.setenv('DEMO_READ_ONLY', 'true')
    client = session()  # POST /auth/login still works
    assert client.get('/auth/me').json()['read_only'] is True
    assert client.get('/records/clients').status_code == 200
    for method, path, body in [
        ('post', '/records/clients', {'name': 'Should not exist'}),
        ('put', '/records/clients/1', {'name': 'Renamed'}),
        ('post', '/comments', {'record_id': 1, 'body': 'hello'}),
        ('post', '/creatives/1/decision', {'status': 'Approved'}),
    ]:
        response = getattr(client, method)(path, json=body, headers=HEADERS)
        assert response.status_code == 403, (path, response.text)
        assert 'read-only' in response.json()['detail']
    assert client.post('/auth/logout', headers=HEADERS).status_code in (200, 204)


def test_bootstrap_migrates_and_seeds_once(monkeypatch):
    monkeypatch.setenv('DEMO_BOOTSTRAP', 'true')
    monkeypatch.setenv('DEMO_PASSWORD', 'bootstrap-test-password')
    monkeypatch.setattr(demo, '_bootstrapped', False)
    demo.ensure_bootstrapped()
    monkeypatch.setattr(demo, '_bootstrapped', False)
    demo.ensure_bootstrapped()  # second run must change nothing
    with SessionLocal() as db:
        agencies = db.scalars(select(Agency)).all()
        assert [a.name for a in agencies] == ['Northstar Studio — Demo']
        assert db.scalar(select(func.count()).select_from(User)) == 5

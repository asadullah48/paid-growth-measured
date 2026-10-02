import csv
import io
import logging
import os
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import demo
from .database import get_db
from .models import Activity, Agency, LoginAttempt, LoginSession, Record, User, now
from .schemas import Campaign, Comment, Decision, Login, SCHEMAS
from .security import digest_token, hash_password, verify_password

app = FastAPI(title='Paid Growth, Measured', version='0.1.0')
ORIGIN = os.getenv('FRONTEND_ORIGIN', 'http://localhost:3000')
app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type', 'X-Requested-With'])
DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
WRITE_ROLES = {
    'clients': {'administrator', 'account_manager'},
    'employees': {'administrator', 'account_manager'},
    'orders': {'administrator', 'account_manager'},
    'tasks': {'administrator', 'account_manager', 'campaign_specialist', 'creative'},
    'creatives': {'administrator', 'account_manager', 'creative'},
    'campaigns': {'administrator', 'account_manager', 'campaign_specialist'},
}
TRANSITIONS = {
    'Draft': {'Confirmed', 'Cancelled'}, 'Confirmed': {'In Progress', 'Cancelled'},
    'In Progress': {'Awaiting Approval', 'Cancelled'},
    'Awaiting Approval': {'In Progress', 'Completed', 'Cancelled'}, 'Completed': set(), 'Cancelled': set(),
}


@app.middleware('http')
async def request_boundaries(request: Request, call_next):
    if demo.blocks(request.method, request.url.path):
        return JSONResponse({'detail': demo.READ_ONLY_MESSAGE}, status_code=403)
    if request.method in {'POST', 'PUT', 'DELETE', 'PATCH'}:
        if request.headers.get('origin') and request.headers['origin'] != ORIGIN:
            return Response('Origin not allowed', status_code=403)
        if request.headers.get('x-requested-with') != 'PaidGrowth':
            return Response('Required request header missing', status_code=403)
        body = await request.body()
        if len(body) > 1_000_000:
            return Response('Request exceeds 1 MB limit', status_code=413)
    try:
        await run_in_threadpool(demo.ensure_bootstrapped)
    except Exception:  # a broken database must not take the API down silently
        logging.getLogger(__name__).exception('Demo bootstrap failed')
        return JSONResponse({'detail': 'The demo database is not ready yet. Please try again shortly.'}, status_code=503)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get('pgm_session', '')
    session = db.get(LoginSession, digest_token(token))
    if not session or session.expires_at.replace(tzinfo=timezone.utc) <= now():
        raise HTTPException(401, 'Please sign in.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Session no longer valid.')
    return user


def user_view(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role, 'client_id': user.client_id}


def query_records(db, user, kind):
    if kind not in SCHEMAS:
        raise HTTPException(404, 'Unknown module.')
    if kind == 'employees' and user.role not in {'administrator', 'account_manager'}:
        raise HTTPException(403, 'Employee records are restricted.')
    query = select(Record).where(Record.agency_id == user.agency_id, Record.kind == kind)
    if user.role == 'client':
        if kind == 'clients':
            query = query.where(Record.id == user.client_id)
        elif kind in {'campaigns', 'creatives'}:
            query = query.where(Record.client_id == user.client_id)
        else:
            raise HTTPException(403, 'This module is internal.')
    return query


def accessible(db, user, record_id):
    record = db.get(Record, record_id)
    if not record or record.agency_id != user.agency_id:
        raise HTTPException(404, 'Record not found.')
    if user.role == 'client':
        if record.kind not in {'campaigns', 'creatives'} or record.client_id != user.client_id:
            raise HTTPException(404, 'Record not found.')
        if record.kind == 'creatives' and record.data['status'] in {'Draft', 'Draft — Generated'}:
            raise HTTPException(404, 'Record not found.')
    if record.kind == 'employees' and user.role not in {'administrator', 'account_manager'}:
        raise HTTPException(403, 'Employee records are restricted.')
    return record


def record_view(record):
    return {'id': record.id, **record.data, 'created_at': record.created_at.isoformat(), 'updated_at': record.updated_at.isoformat()}


def audit(db, user, action, record=None, detail=None):
    db.add(Activity(agency_id=user.agency_id, user_id=user.id, record_id=record.id if record else None, action=action, detail=detail or {}))


def validate_payload(kind, data):
    if kind not in SCHEMAS:
        raise HTTPException(404, 'Unknown module.')
    try:
        return SCHEMAS[kind].model_validate(data).model_dump(mode='json')
    except ValidationError as exc:
        raise HTTPException(422, [{'field': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in exc.errors()])


def references(db, user, data):
    client_id = data.get('client_id')
    if client_id:
        client = db.get(Record, client_id)
        if not client or client.agency_id != user.agency_id or client.kind != 'clients':
            raise HTTPException(422, 'Select a client from this agency.')
    for field, kind in [('order_id', 'orders'), ('campaign_id', 'campaigns'), ('previous_id', 'creatives')]:
        if data.get(field):
            record = db.get(Record, data[field])
            if not record or record.agency_id != user.agency_id or record.kind != kind or record.client_id != client_id:
                raise HTTPException(422, f'{field} must belong to the same client and agency.')
    for field in ['owner_id', 'user_id']:
        if data.get(field):
            owner = db.get(User, data[field])
            if not owner or owner.agency_id != user.agency_id or owner.role == 'client':
                raise HTTPException(422, f'{field} must identify an agency team member.')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/auth/login')
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    key = digest_token(f'{request.client.host if request.client else "local"}:{email}')
    attempt = db.get(LoginAttempt, key)
    if not attempt:
        attempt = LoginAttempt(key=key, count=0, window_start=now())
        db.add(attempt)
    if attempt.window_start.replace(tzinfo=timezone.utc) < now() - timedelta(minutes=15):
        attempt.count = 0
        attempt.window_start = now()
    if attempt.count >= 10:
        raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        attempt.count += 1
        db.commit()
        raise HTTPException(401, 'Email or password is incorrect.')
    attempt.count = 0
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=digest_token(token), user_id=user.id, expires_at=now() + timedelta(hours=8)))
    db.commit()
    response.set_cookie('pgm_session', token, httponly=True, secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', samesite='lax', max_age=28800, path='/')
    return user_view(user)


@app.post('/auth/logout')
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = db.get(LoginSession, digest_token(request.cookies.get('pgm_session', '')))
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie('pgm_session', path='/')
    return {'ok': True}


@app.get('/auth/me')
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    agency = db.get(Agency, user.agency_id)
    return {**user_view(user), 'agency': agency.name, 'demo': agency.demo, 'read_only': demo.read_only()}


@app.get('/team')
def team(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == 'client':
        raise HTTPException(403, 'Team directory is internal.')
    return [{'id': u.id, 'name': u.name, 'role': u.role} for u in db.scalars(select(User).where(User.agency_id == user.agency_id, User.role != 'client'))]


@app.get('/records/{kind}')
def list_records(kind: str, q: str = Query('', max_length=160), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = query_records(db, user, kind)
    if user.role == 'client' and kind == 'creatives':
        query = query.where(Record.data['status'].as_string().not_in(['Draft', 'Draft — Generated']))
    if q:
        field = 'name' if kind in {'clients', 'employees'} else 'title'
        query = query.where(Record.data[field].as_string().ilike(f'%{q}%'))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    records = db.scalars(query.order_by(Record.updated_at.desc(), Record.id.desc()).offset(offset).limit(limit))
    return {'items': [record_view(r) for r in records], 'total': total}


@app.post('/records/{kind}', status_code=201)
def create_record(kind: str, data: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in WRITE_ROLES.get(kind, set()):
        raise HTTPException(403, 'You cannot create records in this module.')
    clean = validate_payload(kind, data)
    references(db, user, clean)
    if kind == 'clients':
        for existing in db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.kind == kind)):
            if existing.data['name'].casefold() == clean['name'].casefold() or (clean['email'] and existing.data['email'].casefold() == clean['email'].casefold()):
                raise HTTPException(409, 'A matching client already exists.')
    if kind == 'orders' and clean['status'] != 'Draft':
        raise HTTPException(422, 'New orders must start as Draft.')
    if kind == 'creatives':
        if clean['context_pack_id'] or clean['claim_refs'] or clean['review_flags']:
            raise HTTPException(422, 'Use the grounded generation endpoint for traced drafts.')
        if clean['status'] != 'Draft':
            raise HTTPException(422, 'New creatives must start as Draft.')
        previous = db.get(Record, clean['previous_id']) if clean.get('previous_id') else None
        clean['version'] = previous.data['version'] + 1 if previous else 1
    record = Record(agency_id=user.agency_id, kind=kind, client_id=clean.get('client_id'), data=clean)
    db.add(record)
    db.flush()
    audit(db, user, f'{kind}.created', record)
    db.commit()
    return record_view(record)


@app.put('/records/{kind}/{record_id}')
def update_record(kind: str, record_id: int, data: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in WRITE_ROLES.get(kind, set()):
        raise HTTPException(403, 'You cannot edit records in this module.')
    record = accessible(db, user, record_id)
    if record.kind != kind:
        raise HTTPException(404, 'Record not found.')
    clean = validate_payload(kind, data)
    references(db, user, clean)
    if clean.get('client_id') != record.data.get('client_id'):
        raise HTTPException(422, 'Client ownership cannot be changed.')
    if kind == 'clients':
        for other in db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.kind == kind, Record.id != record.id)):
            if other.data['name'].casefold() == clean['name'].casefold() or (clean['email'] and other.data['email'].casefold() == clean['email'].casefold()):
                raise HTTPException(409, 'A matching client already exists.')
    if kind == 'orders' and clean['status'] != record.data['status'] and clean['status'] not in TRANSITIONS[record.data['status']]:
        raise HTTPException(422, 'Invalid order status transition.')
    if kind == 'creatives':
        if record.data['status'] in {'Submitted', 'Approved'}:
            raise HTTPException(409, 'Submitted or approved creative is locked. Create a new version.')
        if clean['status'] not in {'Draft', 'Draft — Generated', 'Submitted'}:
            raise HTTPException(422, 'Use the approval action for decisions.')
        if not record.data.get('context_pack_id') and (clean['context_pack_id'] or clean['claim_refs'] or clean['review_flags']):
            raise HTTPException(422, 'Claim metadata can only be set by grounded generation.')
        if record.data.get('context_pack_id'):
            if any(clean[k] != record.data[k] for k in ['copy', 'brief']):
                raise HTTPException(422, 'Regenerate traced copy to change its content.')
            clean['context_pack_id'] = record.data['context_pack_id']
            clean['claim_refs'] = record.data['claim_refs']
            from .context import check_claims
            pack = db.get(Record, clean['context_pack_id'])
            clean['review_flags'] = check_claims(pack.data, clean['copy'], clean['claim_refs'])
            if clean['status'] == 'Submitted' and clean['review_flags']:
                raise HTTPException(422, 'Resolve grounded-copy flags before submission: ' + '; '.join(clean['review_flags']))
        clean['version'] = record.data['version']
        clean['previous_id'] = record.data['previous_id']
    old_status = record.data.get('status')
    record.data = clean
    record.updated_at = now()
    audit(db, user, f'{kind}.updated', record, {'from': old_status, 'to': clean.get('status')})
    db.commit()
    return record_view(record)


@app.post('/creatives/{record_id}/decision')
def decide(record_id: int, payload: Decision, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in {'client', 'administrator', 'account_manager'}:
        raise HTTPException(403, 'You cannot approve creative.')
    record = accessible(db, user, record_id)
    if record.kind != 'creatives' or record.data['status'] != 'Submitted':
        raise HTTPException(409, 'Only submitted creative can receive a decision.')
    if payload.status == 'Approved' and record.data.get('context_pack_id'):
        from .context import check_claims
        pack = db.get(Record, record.data['context_pack_id'])
        flags = check_claims(pack.data, record.data['copy'], record.data['claim_refs'])
        if flags:
            raise HTTPException(422, 'Resolve claim flags before approval: ' + '; '.join(flags))
    record.data = {**record.data, 'status': payload.status}
    record.updated_at = now()
    audit(db, user, 'creative.decision', record, payload.model_dump())
    db.commit()
    return record_view(record)


@app.get('/activity')
def activity(record_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Activity).where(Activity.agency_id == user.agency_id)
    if record_id:
        accessible(db, user, record_id)
        query = query.where(Activity.record_id == record_id)
    if user.role == 'client':
        allowed = [r.id for r in db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.client_id == user.client_id, Record.kind.in_(['campaigns', 'creatives', 'narratives']))) if (r.kind != 'creatives' or r.data['status'] not in {'Draft', 'Draft — Generated'}) and (r.kind != 'narratives' or r.data['status'] in {'Account Approved', 'Client Approved'})]
        query = query.where(Activity.record_id.in_(allowed))
    elif user.role not in {'administrator', 'account_manager'}:
        restricted = select(Record.id).where(Record.kind == 'employees', Record.agency_id == user.agency_id)
        query = query.where((Activity.record_id.is_(None)) | (~Activity.record_id.in_(restricted)))
    return [{'id': a.id, 'record_id': a.record_id, 'action': a.action, 'detail': a.detail, 'created_at': a.created_at.isoformat()} for a in db.scalars(query.order_by(Activity.id.desc()).limit(100))]


@app.post('/comments', status_code=201)
def comment(payload: Comment, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = accessible(db, user, payload.record_id)
    for mention in payload.mention_ids:
        target = db.get(User, mention)
        if not target or target.agency_id != user.agency_id or (target.role == 'client' and (target.client_id != record.client_id or record.kind not in {'campaigns', 'creatives'} or (record.kind == 'creatives' and record.data['status'] == 'Draft'))):
            raise HTTPException(422, 'Mention must refer to an authorized participant.')
        if user.role == 'client' and target.role not in {'administrator', 'account_manager', 'client'}:
            raise HTTPException(422, 'Mention must refer to an account contact.')
    audit(db, user, 'comment', record, {'body': payload.body, 'author': user.name, 'mention_ids': payload.mention_ids})
    db.commit()
    return {'ok': True}


@app.get('/notifications')
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    events = activity(user=user, db=db)
    return [event for event in events if user.id in event['detail'].get('mention_ids', []) or event['action'] == 'creative.decision']


def ratios(data):
    def divide(numerator, denominator, multiplier=1):
        return round(numerator / denominator * multiplier, 4) if denominator else None
    return {'ctr': divide(data['clicks'], data['impressions'], 100), 'cpc': divide(data['spend'], data['clicks']), 'cpl': divide(data['spend'], data['leads']), 'cpa': divide(data['spend'], data['conversions']), 'roas': divide(data['revenue'], data['spend'])}


@app.get('/dashboard')
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaigns = list(db.scalars(query_records(db, user, 'campaigns')))
    groups = defaultdict(list)
    for record in campaigns:
        d = record.data
        key = tuple(d[k] for k in ['currency', 'timezone', 'attribution', 'source', 'start_date', 'end_date'])
        groups[key].append(d)
    summaries = []
    for key, values in groups.items():
        totals = {k: sum(v[k] for v in values) for k in ['budget', 'spend', 'impressions', 'clicks', 'leads', 'conversions', 'revenue']}
        summaries.append({**dict(zip(['currency', 'timezone', 'attribution', 'source', 'start_date', 'end_date'], key)), **totals, **ratios(totals), 'campaigns': len(values)})
    counts = {}
    for kind in SCHEMAS:
        if user.role == 'client' and kind not in {'clients', 'campaigns', 'creatives'}:
            continue
        if kind == 'employees' and user.role not in {'administrator', 'account_manager'}:
            continue
        query = query_records(db, user, kind)
        if user.role == 'client' and kind == 'creatives':
            query = query.where(Record.data['status'].as_string().not_in(['Draft', 'Draft — Generated']))
        counts[kind] = db.scalar(select(func.count()).select_from(query.subquery()))
    return {'counts': counts, 'groups': summaries, 'campaigns': [record_view(r) for r in campaigns], 'demo': db.get(Agency, user.agency_id).demo}


@app.get('/reports/campaigns.csv')
def export_csv(client_id: int | None = None, channel: str = '', user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = query_records(db, user, 'campaigns')
    if client_id:
        query = query.where(Record.client_id == client_id)
    if channel:
        query = query.where(Record.data['channel'].as_string() == channel)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(Campaign.model_fields))
    writer.writeheader()
    for record in db.scalars(query):
        safe = {k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v) for k, v in record.data.items()}
        writer.writerow(safe)
    return Response(buffer.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="campaigns.csv"'})


@app.post('/reports/import', status_code=201)
async def import_csv(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in WRITE_ROLES['campaigns']:
        raise HTTPException(403, 'You cannot import campaigns.')
    if not request.headers.get('content-type', '').startswith('text/csv'):
        raise HTTPException(415, 'Send a UTF-8 CSV file using text/csv.')
    try:
        text = (await request.body()).decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or set(reader.fieldnames) - set(Campaign.model_fields):
            raise HTTPException(422, 'CSV headers are missing, duplicated, or unknown.')
        rows = list(reader)
        if not 1 <= len(rows) <= 500:
            raise HTTPException(422, 'Import between 1 and 500 rows.')
        validated = []
        seen = set()
        for index, row in enumerate(rows, start=2):
            if None in row or any(v is None for v in row.values()):
                raise HTTPException(422, f'Row {index} has an invalid column count.')
            clean = validate_payload('campaigns', {k: (None if k == 'owner_id' and v == '' else v) for k, v in row.items() if v != '' or k == 'owner_id'})
            references(db, user, clean)
            key = (clean['client_id'], clean['title'].casefold(), clean['start_date'], clean['end_date'])
            if key in seen:
                raise HTTPException(422, f'Duplicate campaign in row {index}.')
            seen.add(key)
            validated.append(clean)
        for clean in validated:
            record = Record(agency_id=user.agency_id, kind='campaigns', client_id=clean['client_id'], data=clean)
            db.add(record)
            db.flush()
            audit(db, user, 'campaigns.imported', record)
        db.commit()
        return {'imported': len(validated)}
    except UnicodeDecodeError:
        raise HTTPException(422, 'CSV must use UTF-8 encoding.')
    except csv.Error:
        raise HTTPException(422, 'Malformed CSV.')


from .context import router as context_router
app.include_router(context_router)

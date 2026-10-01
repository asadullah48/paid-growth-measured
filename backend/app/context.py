"""Versioned context packs, deterministic copy generation, and metric narratives."""
import io
import re
from datetime import date, datetime
from typing import Literal, Protocol
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Record, User, now
from .schemas import Creative, StrictModel

router = APIRouter(prefix='/context', tags=['Context Writing & Presentation'])


def dependencies():
    from .main import current_user
    return current_user


class Fact(StrictModel):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,39}$')
    text: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=1000)
    expires: date


class Pack(StrictModel):
    client_id: int = Field(gt=0)
    brand_voice: str = Field(min_length=1, max_length=2000)
    audience_segments: list[str] = Field(min_length=1, max_length=20)
    offers: list[str] = Field(default_factory=list, max_length=20)
    facts: list[Fact] = Field(default_factory=list, max_length=100)
    prohibited_claims: list[str] = Field(default_factory=list, max_length=50)
    compliance_notes: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def unique_facts(self):
        if len({f.id for f in self.facts}) != len(self.facts):
            raise ValueError('Fact IDs must be unique within a version.')
        if any(len(v) > 1000 for v in self.audience_segments + self.offers + self.prohibited_claims):
            raise ValueError('Context list entries must not exceed 1000 characters.')
        return self


class FactApproval(StrictModel):
    fact_ids: list[str] = Field(min_length=1, max_length=100)


class Generate(StrictModel):
    pack_id: int = Field(gt=0)
    campaign_id: int = Field(gt=0)
    fact_ids: list[str] = Field(min_length=1, max_length=10)
    format: Literal['Headline', 'Primary Text', 'CTA', 'TV Script', 'Outdoor Script']


class ReportInput(StrictModel):
    pack_id: int = Field(gt=0)
    campaign_id: int = Field(gt=0)
    kind: Literal['Monthly Report', 'Client Review Summary'] = 'Monthly Report'


class Approval(StrictModel):
    decision: Literal['Approve', 'Request Changes']


def user_dependency(request, db):
    from .main import current_user
    return current_user(request, db)

# Dependency is imported after main defines it; main mounts this router at its end.
from .main import current_user, audit, record_view, references, ratios


def scoped(db, user, record_id, kind):
    record = db.get(Record, record_id)
    if not record or record.agency_id != user.agency_id or record.kind != kind:
        raise HTTPException(404, 'Record not found.')
    if user.role == 'client' and record.client_id != user.client_id:
        raise HTTPException(404, 'Record not found.')
    return record


def check_claims(pack, copy, refs, today=None):
    today = today or date.today()
    facts = {f['id']: f for f in pack['facts']}
    flags = []
    citations = set(re.findall(r'\[fact:([A-Za-z][A-Za-z0-9_-]*)\]', copy))
    if citations != set(refs):
        flags.append('Uncited or inconsistent claim references')
    for ref in set(refs):
        fact = facts.get(ref)
        if not fact:
            flags.append(f'Unknown fact: {ref}')
            continue
        if not fact.get('approved_by'):
            flags.append(f'Fact lacks client approval: {ref}')
        if date.fromisoformat(fact['expires']) < today:
            flags.append(f'Expired fact: {ref}')
        if f"{fact['text']} [fact:{ref}]" not in copy:
            flags.append(f'Claim text differs from approved fact: {ref}')
    for phrase in pack['prohibited_claims']:
        if phrase.strip() and phrase.casefold() in copy.casefold():
            flags.append(f'Prohibited wording: {phrase}')
    # Only exact cited factual passages and controlled, non-factual template text are allowed.
    remaining = copy
    for ref in refs:
        if ref in facts:
            remaining = remaining.replace(f"{facts[ref]['text']} [fact:{ref}]", '')
    allowed = {'Discover what comes next.', 'Explore your options.', 'Learn more.', 'Opening:', 'Voiceover:', 'Closing:', 'Your next chapter starts here.'}
    for line in remaining.splitlines():
        if line.strip() and line.strip() not in allowed:
            flags.append('Uncited claim or unsupported template text')
            break
    return list(dict.fromkeys(flags))


class CopyProvider(Protocol):
    def generate(self, pack: dict, campaign: dict, fact_ids: list[str], format: str) -> dict: ...


class TemplateProvider:
    LIMITS = {'Headline': 160, 'Primary Text': 2200, 'CTA': 80, 'TV Script': 4000, 'Outdoor Script': 300}

    def generate(self, pack, campaign, fact_ids, format):
        facts = {f['id']: f for f in pack['facts']}
        lines = [f"{facts[ref]['text']} [fact:{ref}]" for ref in fact_ids if ref in facts]
        if format == 'TV Script':
            copy = '\n'.join(['Opening:', 'Your next chapter starts here.', 'Voiceover:', *lines, 'Closing:', 'Learn more.'])
        elif format == 'CTA':
            copy = '\n'.join([*lines, 'Learn more.'])
        else:
            copy = '\n'.join(['Discover what comes next.', *lines, 'Explore your options.'])
        flags = check_claims(pack, copy, fact_ids)
        visible = re.sub(r'\s*\[fact:[^\]]+\]', '', copy)
        if len(visible) > self.LIMITS[format]:
            flags.append(f'{format} exceeds starter format limit of {self.LIMITS[format]} characters')
        return {'copy': copy, 'claim_refs': fact_ids, 'review_flags': flags, 'brief': f"Objective: {campaign['objective']}\nChannel: {campaign['channel']}\nFormat: {format}\nBrand voice: {pack['brand_voice']}\nAudience: {'; '.join(pack['audience_segments'])}\nCompliance: {pack['compliance_notes']}\nOffers are context only; promotional claims require approved facts."}


PROVIDER: CopyProvider = TemplateProvider()  # No LLM adapter or provider credentials configured.


@router.post('/packs', status_code=201)
def create_pack(payload: Pack, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != 'account_manager':
        raise HTTPException(403, 'Only Account Managers can edit Context Packs.')
    clean = payload.model_dump(mode='json')
    references(db, user, clean)
    prior = list(db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.kind == 'context_packs', Record.client_id == clean['client_id'])))
    clean['version'] = max((r.data['version'] for r in prior), default=0) + 1
    clean['facts'] = [{**f, 'approved_by': None, 'approved_at': None} for f in clean['facts']]
    record = Record(agency_id=user.agency_id, kind='context_packs', client_id=clean['client_id'], data=clean)
    db.add(record); db.flush(); audit(db, user, 'context_pack.version_created', record, {'version': clean['version']}); db.commit()
    return record_view(record)


@router.get('/packs')
def packs(client_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == 'client':
        raise HTTPException(403, 'Use approved facts in the client workspace.')
    query = select(Record).where(Record.agency_id == user.agency_id, Record.kind == 'context_packs')
    if client_id:
        query = query.where(Record.client_id == client_id)
    return [record_view(r) for r in db.scalars(query.order_by(Record.id.desc()).limit(100))]


@router.get('/approved-facts')
def approved_facts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != 'client':
        raise HTTPException(403, 'This view is for client-approved facts.')
    records = db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.kind == 'context_packs', Record.client_id == user.client_id))
    return [{'pack_id': r.id, 'version': r.data['version'], 'facts': [f for f in r.data['facts'] if f['approved_by'] == user.id]} for r in records]


@router.get('/fact-review')
def fact_review(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != 'client':
        raise HTTPException(403, 'This action is for clients.')
    records = db.scalars(select(Record).where(Record.agency_id == user.agency_id, Record.kind == 'context_packs', Record.client_id == user.client_id))
    return [{'pack_id': r.id, 'version': r.data['version'], 'facts': [f for f in r.data['facts'] if not f['approved_by']]} for r in records]


@router.post('/packs/{pack_id}/facts/approve')
def approve_facts(pack_id: int, payload: FactApproval, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != 'client':
        raise HTTPException(403, 'Only the client can approve their facts.')
    record = scoped(db, user, pack_id, 'context_packs')
    if set(payload.fact_ids) - {f['id'] for f in record.data['facts']}:
        raise HTTPException(422, 'Unknown fact reference.')
    if any(f['approved_by'] not in {None, user.id} for f in record.data['facts'] if f['id'] in payload.fact_ids):
        raise HTTPException(409, 'A fact is already approved by another client reviewer.')
    facts = [{**f, 'approved_by': user.id, 'approved_at': now().isoformat()} if f['id'] in payload.fact_ids else f for f in record.data['facts']]
    record.data = {**record.data, 'facts': facts};record.updated_at = now()
    audit(db, user, 'context_fact.approved', record, {'fact_ids': payload.fact_ids});db.commit()
    return {'approved': payload.fact_ids}


@router.post('/generate', status_code=201)
def generate(payload: Generate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in {'account_manager', 'creative'}:
        raise HTTPException(403, 'Only Account Managers and creative staff can generate drafts.')
    pack = scoped(db, user, payload.pack_id, 'context_packs')
    campaign = scoped(db, user, payload.campaign_id, 'campaigns')
    if pack.client_id != campaign.client_id:
        raise HTTPException(422, 'Campaign and Context Pack must belong to the same client.')
    result = PROVIDER.generate(pack.data, campaign.data, payload.fact_ids, payload.format)
    clean = Creative(title=f"{campaign.data['title']} · {payload.format}", client_id=pack.client_id, context_pack_id=pack.id, status='Draft — Generated', **result).model_dump(mode='json')
    record = Record(agency_id=user.agency_id, kind='creatives', client_id=pack.client_id, data=clean)
    db.add(record);db.flush();audit(db, user, 'creative.generated', record, {'pack_id': pack.id, 'provider': 'template'});db.commit()
    return record_view(record)


def metric_snapshot(campaign):
    fields = ['title', 'currency', 'timezone', 'source', 'attribution', 'start_date', 'end_date', 'budget', 'spend', 'impressions', 'clicks', 'leads', 'conversions', 'revenue']
    return {**{k: campaign.data[k] for k in fields}, **ratios(campaign.data), 'campaign_id': campaign.id, 'captured_at': now().isoformat()}


@router.post('/reports', status_code=201)
def create_report(payload: ReportInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in {'account_manager', 'campaign_specialist'}:
        raise HTTPException(403, 'Only Account Managers and campaign specialists can prepare reports.')
    pack = scoped(db, user, payload.pack_id, 'context_packs')
    campaign = scoped(db, user, payload.campaign_id, 'campaigns')
    if pack.client_id != campaign.client_id:
        raise HTTPException(422, 'Campaign and Context Pack must belong to the same client.')
    metric = metric_snapshot(campaign)
    if payload.kind == 'Monthly Report' and (metric['start_date'][:7] != metric['end_date'][:7]):
        raise HTTPException(422, 'Monthly reports require a campaign reporting period within one month.')
    # Numerical report claims must come from the measurement snapshot, not hand-entered context facts.
    approved = [f for f in pack.data['facts'] if f['approved_by'] and date.fromisoformat(f['expires']) >= date.today() and not re.search(r'\d', f['text'])]
    data = {'title': f"{payload.kind}: {campaign.data['title']}", 'kind': payload.kind, 'status': 'Draft', 'pack_id': pack.id, 'pack_version': pack.data['version'], 'brand_voice': pack.data['brand_voice'], 'approved_facts': approved, 'metrics': metric, 'interpretation': 'These are recorded outcomes under the stated attribution method. They do not establish that advertising caused the outcomes.', 'recommendations': 'Review tracking quality and creative relevance before changing the campaign plan.', 'open_questions': 'Are the recorded outcomes complete, and is the attribution method appropriate for the decision?'}
    record = Record(agency_id=user.agency_id, kind='narratives', client_id=pack.client_id, data=data)
    db.add(record);db.flush();audit(db,user,'report.prepared',record);db.commit()
    return record_view(record)


@router.get('/reports')
def reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Record).where(Record.agency_id == user.agency_id, Record.kind == 'narratives')
    if user.role == 'client':
        query = query.where(Record.client_id == user.client_id, Record.data['status'].as_string().in_(['Account Approved', 'Client Approved']))
    return [record_view(r) for r in db.scalars(query.order_by(Record.id.desc()).limit(100))]


@router.post('/reports/{report_id}/approve')
def approve_report(report_id: int, payload: Approval, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = scoped(db,user,report_id,'narratives')
    status = record.data['status']
    if user.role == 'account_manager' and status == 'Draft':
        status = 'Account Approved' if payload.decision == 'Approve' else 'Changes Requested'
    elif user.role == 'client' and status == 'Account Approved':
        status = 'Client Approved' if payload.decision == 'Approve' else 'Changes Requested'
    else:
        raise HTTPException(403, 'Reports require Account Manager approval before client approval.')
    record.data = {**record.data, 'status': status};record.updated_at = now();audit(db,user,'report.approval',record,{'to':status});db.commit()
    return record_view(record)


@router.get('/reports/{report_id}/pdf')
def report_pdf(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    record = scoped(db,user,report_id,'narratives')
    if user.role == 'client' and record.data['status'] not in {'Account Approved', 'Client Approved'}:
        raise HTTPException(404, 'Report not available.')
    d = record.data;m=d['metrics'];styles=getSampleStyleSheet();buffer=io.BytesIO();story=[]
    def paragraph(text, style='Normal'):
        story.append(Paragraph(escape(str(text)), styles[style]));story.append(Spacer(1,10))
    paragraph('Paid Growth, Measured', 'Title');paragraph(d['title'],'Heading1');paragraph(f"Approval: {d['status']} · Context version: {d['pack_version']}")
    paragraph('Results (facts)','Heading2');paragraph(f"Period: {m['start_date']} to {m['end_date']} | Currency: {m['currency']} | Source: {m['source']} | Attribution: {m['attribution']} | Timezone: {m['timezone']}")
    for key in ['budget','spend','impressions','clicks','leads','conversions','revenue','ctr','cpc','cpl','cpa','roas']:
        paragraph(f"{key.upper()}: {m[key] if m[key] is not None else 'Unavailable'}")
    paragraph(f"Metric snapshot captured: {m['captured_at']}; campaign record #{m['campaign_id']}. Subsequent metric edits require a new report.")
    for fact in d['approved_facts']:
        paragraph(f"{fact['text']} [fact:{fact['id']}] | Source: {fact['source']} | Expires: {fact['expires']}")
    for title,key in [('Interpretation','interpretation'),('Recommendations','recommendations'),('Open questions','open_questions')]:
        paragraph(title,'Heading2');paragraph(d[key])
    SimpleDocTemplate(buffer).build(story)
    return Response(buffer.getvalue(), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="report-{report_id}.pdf"'})

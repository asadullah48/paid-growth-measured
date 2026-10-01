import csv
import io
import os
from datetime import date

import pytest
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['FRONTEND_ORIGIN'] = 'http://localhost:3000'
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, ratios
from app.context import TemplateProvider, check_claims
from app.models import Agency, Record, User
from app.schemas import SCHEMAS
from app.security import hash_password

HEADERS = {'X-Requested-With': 'PaidGrowth', 'Origin': 'http://localhost:3000'}
PASSWORD = 'test-only-strong-password'


@pytest.fixture()
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        a=Agency(name='Agency A',demo=True);b=Agency(name='Agency B',demo=True);db.add_all([a,b]);db.flush()
        def record(kind,data,agency=a):
            clean=SCHEMAS[kind].model_validate(data).model_dump(mode='json');r=Record(agency_id=agency.id,kind=kind,client_id=clean.get('client_id'),data=clean);db.add(r);db.flush();return r
        client=record('clients',{'name':'Example Client'});other=record('clients',{'name':'Other Client'});foreign=record('clients',{'name':'Foreign Client'},b)
        campaign=record('campaigns',{'title':'Sample','client_id':client.id,'channel':'Paid Social','budget':1000,'spend':200,'impressions':1000,'clicks':100,'leads':20,'conversions':5,'revenue':600,'start_date':'2026-10-01','end_date':'2026-10-31'})
        for role in ['administrator','account_manager','campaign_specialist','creative','client']:
            db.add(User(agency_id=a.id,name=role,email=f'{role}@example.test',role=role,password_hash=hash_password(PASSWORD),client_id=client.id if role=='client' else None))
        db.add(User(agency_id=b.id,name='Foreign',email='foreign@example.test',role='administrator',password_hash=hash_password(PASSWORD)))
        db.commit();ids={'client':client.id,'other':other.id,'foreign':foreign.id,'campaign':campaign.id}
    def dependency():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=dependency
    yield ids,factory
    app.dependency_overrides.clear();engine.dispose()


def session(role='administrator'):
    client=TestClient(app);response=client.post('/auth/login',json={'email':f'{role}@example.test','password':PASSWORD},headers=HEADERS);assert response.status_code==200,response.text;return client


def pack_payload(client_id,**updates):
    return {'client_id':client_id,'brand_voice':'Clear and encouraging','audience_segments':['Local buyers'],'offers':[],'facts':[{'id':'area','text':'Service is available in Lahore.','source':'Approved service register','expires':'2099-12-31'}],'prohibited_claims':['guaranteed profit'],'compliance_notes':'Avoid causal claims.',**updates}


def approved_pack(ids):
    manager=session('account_manager');result=manager.post('/context/packs',json=pack_payload(ids['client']),headers=HEADERS);assert result.status_code==201,result.text;pack=result.json();client=session('client');assert client.post(f"/context/packs/{pack['id']}/facts/approve",json={'fact_ids':['area']},headers=HEADERS).status_code==200;return pack


def test_authentication_and_logout(env):
    client=TestClient(app);assert client.get('/dashboard').status_code==401
    assert client.post('/auth/login',json={'email':'administrator@example.test','password':'wrong'},headers=HEADERS).status_code==401
    client=session();assert client.get('/dashboard').status_code==200;assert client.post('/auth/logout',headers=HEADERS).status_code==200;assert client.get('/dashboard').status_code==401


def test_csrf_origin_and_header(env):
    client=session();assert client.post('/auth/logout').status_code==403
    assert client.post('/auth/logout',headers={**HEADERS,'Origin':'https://untrusted.test'}).status_code==403


def test_login_attempt_limit(env):
    client=TestClient(app)
    for _ in range(10):assert client.post('/auth/login',json={'email':'missing@example.test','password':'wrong'},headers=HEADERS).status_code==401
    assert client.post('/auth/login',json={'email':'missing@example.test','password':'wrong'},headers=HEADERS).status_code==429


def test_cross_agency_references_and_lists(env):
    ids,_=env;client=session();records=client.get('/records/clients').json()['items'];assert ids['foreign'] not in [r['id'] for r in records]
    payload={'title':'Bad','client_id':ids['foreign'],'channel':'Search','budget':10,'deadline':'2026-11-01'}
    assert client.post('/records/orders',json=payload,headers=HEADERS).status_code==422


@pytest.mark.parametrize('role',['campaign_specialist','creative','client'])
def test_employee_privacy(env,role):
    assert session(role).get('/records/employees').status_code==403


def test_client_scope(env):
    ids,_=env;client=session('client');assert [r['id'] for r in client.get('/records/clients').json()['items']]==[ids['client']]
    assert client.get('/records/orders').status_code==403
    assert client.post('/records/campaigns',json={},headers=HEADERS).status_code==403


def test_order_transitions_and_audit(env):
    ids,_=env;client=session();payload={'title':'Launch','client_id':ids['client'],'channel':'Search','budget':10,'deadline':'2026-11-01'}
    result=client.post('/records/orders',json=payload,headers=HEADERS);assert result.status_code==201;record=result.json();url=f"/records/orders/{record['id']}"
    assert client.put(url,json={**payload,'status':'Completed'},headers=HEADERS).status_code==422
    for status in ['Confirmed','In Progress','Awaiting Approval','Completed']:
        assert client.put(url,json={**payload,'status':status},headers=HEADERS).status_code==200
    assert len(client.get(f"/activity?record_id={record['id']}").json())==5


def test_duplicate_clients(env):
    assert session().post('/records/clients',json={'name':'example client'},headers=HEADERS).status_code==409


def test_ratios_zero_and_values():
    assert ratios({'clicks':0,'impressions':0,'spend':0,'leads':0,'conversions':0,'revenue':0})=={'ctr':None,'cpc':None,'cpl':None,'cpa':None,'roas':None}
    assert ratios({'clicks':100,'impressions':1000,'spend':200,'leads':20,'conversions':5,'revenue':600})=={'ctr':10,'cpc':2,'cpl':10,'cpa':40,'roas':3}


def test_csv_atomic_invalid_and_duplicate(env):
    ids,_=env;client=session();campaign=client.get('/records/campaigns').json()['items'][0];data={k:v for k,v in campaign.items() if k in SCHEMAS['campaigns'].model_fields}
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(data));writer.writeheader();writer.writerow(data);writer.writerow({**data,'budget':'invalid'})
    assert client.post('/reports/import',content=output.getvalue(),headers={**HEADERS,'Content-Type':'text/csv'}).status_code==422
    assert client.get('/records/campaigns').json()['total']==1
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(data));writer.writeheader();writer.writerow(data);writer.writerow(data)
    assert client.post('/reports/import',content=output.getvalue(),headers={**HEADERS,'Content-Type':'text/csv'}).status_code==422


def test_csv_valid(env):
    client=session();campaign=client.get('/records/campaigns').json()['items'][0];data={k:v for k,v in campaign.items() if k in SCHEMAS['campaigns'].model_fields};data['title']='Imported'
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(data));writer.writeheader();writer.writerow(data)
    response=client.post('/reports/import',content=output.getvalue(),headers={**HEADERS,'Content-Type':'text/csv'});assert response.status_code==201,response.text;assert response.json()['imported']==1


@pytest.mark.parametrize('role',['administrator','campaign_specialist','creative','client'])
def test_only_account_managers_edit_pack(env,role):
    ids,_=env;assert session(role).post('/context/packs',json=pack_payload(ids['client']),headers=HEADERS).status_code==403


def test_pack_versions_and_client_fact_view(env):
    ids,_=env;pack=approved_pack(ids);client=session('client');approved=client.get('/context/approved-facts').json();assert approved[0]['facts'][0]['id']=='area';assert client.get('/context/packs').status_code==403
    manager=session('account_manager');v2=manager.post('/context/packs',json=pack_payload(ids['client']),headers=HEADERS).json();assert v2['version']==2;assert v2['facts'][0]['approved_by'] is None
    foreign=manager.post('/context/packs',json=pack_payload(ids['other']),headers=HEADERS).json();assert client.post(f"/context/packs/{foreign['id']}/facts/approve",json={'fact_ids':['area']},headers=HEADERS).status_code==404


def test_claim_tracing_and_generated_draft(env):
    ids,_=env;pack=approved_pack(ids);manager=session('account_manager');result=manager.post('/context/generate',json={'pack_id':pack['id'],'campaign_id':ids['campaign'],'fact_ids':['area'],'format':'Primary Text'},headers=HEADERS);assert result.status_code==201,result.text
    draft=result.json();assert draft['status']=='Draft — Generated';assert '[fact:area]' in draft['copy'];assert draft['review_flags']==[]
    assert session('client').get('/records/creatives').json()['total']==0
    payload={k:v for k,v in draft.items() if k in SCHEMAS['creatives'].model_fields};payload['status']='Submitted'
    assert manager.put(f"/records/creatives/{draft['id']}",json=payload,headers=HEADERS).status_code==200
    assert session('client').post(f"/creatives/{draft['id']}/decision",json={'status':'Approved'},headers=HEADERS).status_code==200


def test_expired_prohibited_uncited_detection():
    pack={'facts':[{'id':'a','text':'Guaranteed profit.','expires':'2020-01-01','approved_by':1}],'prohibited_claims':['guaranteed profit']}
    flags=check_claims(pack,'Guaranteed profit. [fact:a]\nRevenue doubled.',['a'],date(2026,10,1))
    assert 'Expired fact: a' in flags;assert any('Prohibited' in flag for flag in flags);assert any('Uncited' in flag for flag in flags)
    assert 'Uncited or inconsistent claim references' in check_claims(pack,'Guaranteed profit.',['a'])


def test_unapproved_and_unknown_claims():
    pack={'facts':[{'id':'a','text':'Available locally.','expires':'2099-01-01','approved_by':None}],'prohibited_claims':[]}
    flags=check_claims(pack,'Available locally. [fact:a]',['a','missing']);assert 'Fact lacks client approval: a' in flags;assert 'Unknown fact: missing' in flags


def test_report_snapshot_permissions_pdf(env):
    ids,factory=env;pack=approved_pack(ids);manager=session('account_manager');response=manager.post('/context/reports',json={'pack_id':pack['id'],'campaign_id':ids['campaign']},headers=HEADERS);assert response.status_code==201,response.text;report=response.json();assert report['metrics']['spend']==200;assert report['metrics']['cpl']==10
    client=session('client');assert client.get('/context/reports').json()==[];assert client.get(f"/context/reports/{report['id']}/pdf").status_code==404
    assert client.post(f"/context/reports/{report['id']}/approve",json={'decision':'Approve'},headers=HEADERS).status_code==403
    assert session().post(f"/context/reports/{report['id']}/approve",json={'decision':'Approve'},headers=HEADERS).status_code==403
    assert manager.post(f"/context/reports/{report['id']}/approve",json={'decision':'Approve'},headers=HEADERS).status_code==200
    assert client.post(f"/context/reports/{report['id']}/approve",json={'decision':'Approve'},headers=HEADERS).status_code==200
    with factory() as db:
        campaign=db.get(Record,ids['campaign']);campaign.data={**campaign.data,'spend':999};db.commit()
    assert client.get('/context/reports').json()[0]['metrics']['spend']==200
    pdf=client.get(f"/context/reports/{report['id']}/pdf");assert pdf.status_code==200;assert pdf.content.startswith(b'%PDF')


def test_reports_numbers_match_stored_metrics(env):
    ids,factory=env;pack=approved_pack(ids);report=session('account_manager').post('/context/reports',json={'pack_id':pack['id'],'campaign_id':ids['campaign']},headers=HEADERS).json()
    with factory() as db:
        campaign=db.get(Record,ids['campaign'])
        for field in ['budget','spend','impressions','clicks','leads','conversions','revenue','currency','source','attribution','start_date','end_date','timezone']:
            assert report['metrics'][field]==campaign.data[field]


def test_format_limit_flags():
    pack={'brand_voice':'Clear','audience_segments':['Buyers'],'compliance_notes':'','facts':[{'id':'a','text':'a'*200,'expires':'2099-01-01','approved_by':1}],'prohibited_claims':[]}
    assert any('format limit' in f for f in TemplateProvider().generate(pack,{'objective':'Awareness','channel':'Outdoor'},['a'],'Headline')['review_flags'])


def test_reports_do_not_inject_numeric_context_claims(env):
    ids,_=env;manager=session('account_manager')
    payload=pack_payload(ids['client'],facts=[{'id':'history','text':'We have served 500 customers.','source':'Synthetic register','expires':'2099-12-31'}])
    pack=manager.post('/context/packs',json=payload,headers=HEADERS).json()
    assert session('client').post(f"/context/packs/{pack['id']}/facts/approve",json={'fact_ids':['history']},headers=HEADERS).status_code==200
    report=manager.post('/context/reports',json={'pack_id':pack['id'],'campaign_id':ids['campaign']},headers=HEADERS).json()
    assert report['approved_facts']==[]
    assert report['metrics']['spend']==200

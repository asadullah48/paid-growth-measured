"""Create synthetic local demo records after running migrations."""
import os
from sqlalchemy import select
from .database import SessionLocal
from .models import Agency, Record, User
from .schemas import SCHEMAS
from .security import hash_password


def seed():
    password = os.getenv('DEMO_PASSWORD', '')
    if len(password) < 12 or password.startswith('replace-'):
        raise SystemExit('Set DEMO_PASSWORD to a unique value of at least 12 characters in .env.')
    with SessionLocal() as db:
        # The second name is how earlier seeds stored the dash (double-encoded
        # UTF-8); matching it keeps a re-run on an existing database a no-op.
        if db.scalar(select(Agency).where(Agency.name.in_(['Northstar Studio — Demo', 'Northstar Studio \u00e2\u20ac\u201d Demo']))):
            print('Demo agency already exists; no records changed.')
            return
        agency = Agency(name='Northstar Studio — Demo', demo=True)
        db.add(agency)
        db.flush()
        def add(kind, data):
            clean = SCHEMAS[kind].model_validate(data).model_dump(mode='json')
            record = Record(agency_id=agency.id, kind=kind, client_id=clean.get('client_id'), data=clean)
            db.add(record)
            db.flush()
            return record
        client = add('clients', {'name': 'Meridian Homes — Sample', 'contact': 'Demo Client', 'email': 'client@example.test', 'notes': 'Synthetic demonstration organization.'})
        users = {}
        for role, name, email in [('administrator', 'Asadullah Shafique', 'admin@example.test'), ('account_manager', 'Sam Rivera', 'manager@example.test'), ('campaign_specialist', 'Taylor Lane', 'campaigns@example.test'), ('creative', 'Jordan Ellis', 'creative@example.test'), ('client', 'Demo Client', 'client@example.test')]:
            user = User(agency_id=agency.id, client_id=client.id if role == 'client' else None, name=name, email=email, role=role, password_hash=hash_password(password))
            db.add(user)
            db.flush()
            users[role] = user
        for role in ['account_manager', 'campaign_specialist', 'creative']:
            add('employees', {'name': users[role].name, 'role': role.replace('_', ' ').title(), 'user_id': users[role].id, 'responsibilities': 'Synthetic team member for the local walkthrough.'})
        order = add('orders', {'title': 'Autumn launch — Sample', 'client_id': client.id, 'channel': 'Paid Social', 'budget': 5000, 'deadline': '2026-10-31', 'status': 'In Progress', 'owner_id': users['account_manager'].id, 'deliverables': 'Campaign brief, two creative concepts, reporting summary.'})
        campaign = add('campaigns', {'title': 'Autumn homes — Sample', 'client_id': client.id, 'channel': 'Paid Social', 'budget': 5000, 'start_date': '2026-10-01', 'end_date': '2026-10-31', 'spend': 1250, 'impressions': 48000, 'clicks': 1440, 'leads': 96, 'conversions': 8, 'revenue': 4800, 'source': 'Synthetic demo', 'status': 'Active', 'owner_id': users['campaign_specialist'].id})
        add('tasks', {'title': 'Review launch copy — Sample', 'client_id': client.id, 'order_id': order.id, 'campaign_id': campaign.id, 'owner_id': users['creative'].id, 'deadline': '2026-10-08'})
        add('creatives', {'title': 'Autumn concept — Sample', 'client_id': client.id, 'order_id': order.id, 'brief': 'Demonstration only. No actual advertising offer.', 'copy': 'Find room for your next chapter.', 'status': 'Submitted'})
        db.commit()
        print('Synthetic demo created. Sign in with admin@example.test and your private DEMO_PASSWORD.')


if __name__ == '__main__':
    seed()

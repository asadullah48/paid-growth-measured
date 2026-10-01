"""Initial agency workspace schema."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agencies', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.String(160), nullable=False), sa.Column('demo', sa.Boolean(), nullable=False))
    op.create_table('records', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('agency_id', sa.Integer(), sa.ForeignKey('agencies.id'), nullable=False), sa.Column('kind', sa.String(30), nullable=False), sa.Column('client_id', sa.Integer(), sa.ForeignKey('records.id')), sa.Column('data', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    for field in ['agency_id', 'kind', 'client_id']:
        op.create_index(f'ix_records_{field}', 'records', [field])
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('agency_id', sa.Integer(), sa.ForeignKey('agencies.id'), nullable=False), sa.Column('client_id', sa.Integer(), sa.ForeignKey('records.id')), sa.Column('name', sa.String(120), nullable=False), sa.Column('email', sa.String(254), nullable=False, unique=True), sa.Column('role', sa.String(30), nullable=False), sa.Column('password_hash', sa.Text(), nullable=False))
    op.create_index('ix_users_agency_id', 'users', ['agency_id'])
    op.create_table('sessions', sa.Column('token_hash', sa.String(64), primary_key=True), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_table('login_attempts', sa.Column('key', sa.String(64), primary_key=True), sa.Column('count', sa.Integer(), nullable=False), sa.Column('window_start', sa.DateTime(timezone=True), nullable=False))
    op.create_table('activity', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('agency_id', sa.Integer(), sa.ForeignKey('agencies.id'), nullable=False), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False), sa.Column('record_id', sa.Integer(), sa.ForeignKey('records.id')), sa.Column('action', sa.String(120), nullable=False), sa.Column('detail', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_activity_agency_id', 'activity', ['agency_id'])


def downgrade():
    for name in ['activity', 'login_attempts', 'sessions', 'users', 'records', 'agencies']:
        op.drop_table(name)

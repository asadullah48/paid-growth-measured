from datetime import date
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROLES = {'administrator', 'account_manager', 'campaign_specialist', 'creative', 'client'}
CHANNELS = Literal['Paid Social', 'Search', 'Display', 'Television', 'Outdoor']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Client(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    contact: str = Field(default='', max_length=120)
    email: str = Field(default='', max_length=254)
    communication: str = Field(default='Email', max_length=80)
    owner_id: int | None = None
    opportunity: str = Field(default='', max_length=500)
    follow_up: date | None = None
    notes: str = Field(default='', max_length=3000)


class Employee(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=80)
    responsibilities: str = Field(default='', max_length=2000)
    user_id: int | None = None


class Order(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    client_id: int = Field(gt=0)
    channel: CHANNELS
    budget: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    currency: str = Field(default='USD', pattern=r'^[A-Z]{3}$')
    deadline: date
    owner_id: int | None = None
    deliverables: str = Field(default='', max_length=3000)
    notes: str = Field(default='', max_length=3000)
    status: Literal['Draft', 'Confirmed', 'In Progress', 'Awaiting Approval', 'Completed', 'Cancelled'] = 'Draft'


class Task(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    client_id: int = Field(gt=0)
    order_id: int | None = None
    campaign_id: int | None = None
    owner_id: int | None = None
    deadline: date
    status: Literal['To Do', 'In Progress', 'Done'] = 'To Do'


class Creative(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    client_id: int = Field(gt=0)
    order_id: int | None = None
    brief: str = Field(default='', max_length=4000)
    copy: str = Field(default='', max_length=8000)
    asset_url: str = Field(default='', max_length=2048)
    version: int = Field(default=1, ge=1)
    previous_id: int | None = None
    status: Literal['Draft', 'Draft — Generated', 'Submitted', 'Approved', 'Changes Requested'] = 'Draft'
    context_pack_id: int | None = None
    claim_refs: list[str] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def safe_url(self):
        if self.asset_url:
            parsed = urlsplit(self.asset_url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Asset references must be HTTPS URLs without embedded credentials.')
        return self


class Campaign(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    client_id: int = Field(gt=0)
    channel: CHANNELS
    objective: str = Field(default='Lead generation', max_length=160)
    owner_id: int | None = None
    start_date: date
    end_date: date
    currency: str = Field(default='USD', pattern=r'^[A-Z]{3}$')
    timezone: str = Field(default='Asia/Karachi', max_length=80)
    attribution: str = Field(default='7-day click', min_length=1, max_length=120)
    source: str = Field(default='Manual', min_length=1, max_length=120)
    budget: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    spend: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False)
    impressions: int = Field(default=0, ge=0, le=10**15)
    clicks: int = Field(default=0, ge=0, le=10**15)
    leads: int = Field(default=0, ge=0, le=10**15)
    conversions: int = Field(default=0, ge=0, le=10**15)
    revenue: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False)
    status: Literal['Planned', 'Active', 'Paused', 'Completed'] = 'Planned'

    @model_validator(mode='after')
    def valid_period(self):
        if self.end_date < self.start_date:
            raise ValueError('End date must be on or after start date.')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Unknown IANA timezone.')
        return self


class Comment(StrictModel):
    record_id: int = Field(gt=0)
    body: str = Field(min_length=1, max_length=2000)
    mention_ids: list[int] = Field(default_factory=list, max_length=20)


class Decision(StrictModel):
    status: Literal['Approved', 'Changes Requested']
    note: str = Field(default='', max_length=2000)


SCHEMAS = {'clients': Client, 'employees': Employee, 'orders': Order, 'tasks': Task, 'creatives': Creative, 'campaigns': Campaign}

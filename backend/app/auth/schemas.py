from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.accounts.model import AccountType


class RegistrationStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_type: AccountType
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=32)
    direction: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=300)


class RegistrationStarted(BaseModel):
    request_id: int
    deep_link: str
    expires_in: int
    resend_after: int


class LoginStarted(BaseModel):
    request_id: int
    deep_link: str
    code_sent: bool
    expires_in: int
    resend_after: int


class ChallengeResent(BaseModel):
    request_id: int
    code_version: int
    expires_in: int
    resend_after: int


class Authenticated(BaseModel):
    account_id: int
    account_type: AccountType
    session_token: str
    csrf_token: str
    expires_at: datetime
    login: str | None = None
    password: str | None = None


class SessionIdentity(BaseModel):
    account_id: int
    account_type: AccountType
    login: str
    csrf_token: str
    expires_at: datetime

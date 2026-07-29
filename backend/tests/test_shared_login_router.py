import pytest
from pydantic import ValidationError

from app.accounts.model import AccountType
from app.auth.shared_login_router import SharedLoginStartRequest


def test_shared_login_request_accepts_cabinet_type():
    request = SharedLoginStartRequest(
        login="shared_owner",
        password="secret-42",
        cabinet_type="business",
    )

    assert request.cabinet_type is AccountType.BUSINESS


def test_shared_login_request_keeps_account_type_forbidden():
    with pytest.raises(ValidationError):
        SharedLoginStartRequest.model_validate(
            {
                "login": "shared_owner",
                "password": "secret-42",
                "account_type": "business",
            }
        )

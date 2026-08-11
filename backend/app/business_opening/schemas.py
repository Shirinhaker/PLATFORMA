from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessOpeningWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=120)
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=32)
    address: str = Field(default="", max_length=300)

    @field_validator(
        "name",
        "direction",
        "activity_type",
        "phone",
        "address",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class BusinessOpeningRead(BaseModel):
    ok: bool = True
    business_account_id: int
    biz_login: str
    biz_password: str

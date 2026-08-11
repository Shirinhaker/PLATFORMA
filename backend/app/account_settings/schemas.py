from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessCredentialsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_login: str = Field(default="", max_length=20)
    new_password: str = Field(default="", max_length=128)

    @field_validator("new_login", mode="before")
    @classmethod
    def normalize_login(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("new_password", mode="before")
    @classmethod
    def clean_password(cls, value):
        return value.strip() if isinstance(value, str) else value


class BusinessCredentialsRead(BaseModel):
    ok: bool = True
    login: str

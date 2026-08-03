from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseEnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_item_public_id: str = Field(min_length=1, max_length=64)
    phone: str = Field(default="", max_length=30)
    note: str = Field(default="", max_length=300)

    @field_validator("course_item_public_id", "phone", "note", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class CourseEnrollmentCreated(BaseModel):
    ok: bool = True
    id: int = Field(gt=0)

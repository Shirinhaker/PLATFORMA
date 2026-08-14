from enum import Enum

from sqlalchemy import Enum as SqlEnum


class OwnerState(str, Enum):
    LINKED = "linked"
    UNLINKED = "unlinked"


class ReviewState(str, Enum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"


def enum_type(enum: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum,
        name=name,
        values_callable=lambda enum_class: [item.value for item in enum_class],
        validate_strings=True,
    )


OWNER_STATE_ENUM = enum_type(OwnerState, "owner_state")
REVIEW_STATE_ENUM = enum_type(ReviewState, "review_state")

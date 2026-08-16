"""Ta'lim resurslari: guruhlar va arizalar."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from app.business_online.payload.helpers import (
    action_forbidden,
    find_record,
    integer,
    missing_record_id,
    next_record_id,
    raw_payload_rows,
)
from app.core.errors import ApiError


def education_group_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {str(row.get("id")): row for row in raw_payload_rows(payload, "items")}
    students = raw_payload_rows(payload, "education_students")
    result = []
    for source in raw_payload_rows(payload, "education_groups"):
        if str(source.get("status") or "") != "active":
            continue
        row = deepcopy(source)
        course = items.get(str(row.get("course_item_id")), {})
        row["course_name"] = str(row.get("course_name") or course.get("name") or "")
        row["student_count"] = sum(
            str(student.get("group_id")) == str(row.get("id"))
            and str(student.get("status") or "") == "active"
            for student in students
        )
        result.append(row)
    result.sort(key=lambda row: integer(row.get("id")), reverse=True)
    return result


def education_enrollment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {str(row.get("id")): row for row in raw_payload_rows(payload, "items")}
    groups = {
        str(row.get("id")): row for row in raw_payload_rows(payload, "education_groups")
    }
    result = []
    for source in raw_payload_rows(payload, "education_enrollments"):
        row = deepcopy(source)
        course = items.get(str(row.get("course_item_id")), {})
        group = groups.get(str(row.get("group_id")), {})
        row["course_name"] = str(row.get("course_name") or course.get("name") or "")
        row["group_name"] = str(row.get("group_name") or group.get("name") or "")
        result.append(row)
    rank = {"new": 0, "accepted": 1}
    result.sort(
        key=lambda row: (
            rank.get(str(row.get("status") or ""), 2),
            -integer(row.get("id")),
        )
    )
    return result[:500]


def apply_education_enrollment_action(
    payload: dict[str, Any],
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
    now: int,
) -> dict[str, Any]:
    if record_id is None:
        raise missing_record_id()
    rows = raw_payload_rows(payload, "education_enrollments")
    try:
        enrollment = find_record(rows, record_id)
    except ApiError:
        raise ApiError(
            404, "new_education_enrollment_not_found", "Yangi ariza topilmadi."
        ) from None
    if str(enrollment.get("status") or "") != "new":
        raise ApiError(
            404, "new_education_enrollment_not_found", "Yangi ariza topilmadi."
        )

    if action == "accept":
        group_id = integer(data.get("group_id"))
        group = next(
            (
                row
                for row in raw_payload_rows(payload, "education_groups")
                if integer(row.get("id")) == group_id
                and str(row.get("status") or "") == "active"
            ),
            None,
        )
        if group is None:
            raise ApiError(400, "education_group_required", "Guruhni tanlang.")
        course_id = integer(enrollment.get("course_item_id"))
        group_course_id = integer(group.get("course_item_id"))
        if group_course_id and group_course_id != course_id:
            raise ApiError(
                400,
                "education_group_course_mismatch",
                "Tanlangan guruh boshqa kursga tegishli.",
            )

        students = raw_payload_rows(payload, "education_students")
        user_id = integer(enrollment.get("user_id"))
        user_account_id = integer(enrollment.get("user_account_id"))
        user_legacy_id = integer(enrollment.get("user_legacy_id"))
        student = next(
            (
                row
                for row in students
                if str(row.get("status") or "") == "active"
                and (
                    (
                        user_account_id
                        and integer(row.get("user_account_id")) == user_account_id
                    )
                    or (
                        user_account_id
                        and user_legacy_id
                        and integer(row.get("user_id")) == user_legacy_id
                    )
                    or (
                        not user_account_id
                        and user_id
                        and integer(row.get("user_id")) == user_id
                    )
                )
            ),
            None,
        )
        if student is None:
            student = {
                "id": next_record_id(students),
                "group_id": group_id,
                "user_id": enrollment.get("user_id"),
                "full_name": str(enrollment.get("customer_name") or ""),
                "phone": str(enrollment.get("phone") or ""),
                "joined_date": (datetime.now(UTC) + timedelta(hours=5)).strftime(
                    "%Y-%m-%d"
                ),
                "note": ("Kurs arizasi: " + str(enrollment.get("note") or ""))[:500],
                "monthly_fee": 0,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            if user_account_id:
                student["user_account_id"] = user_account_id
            students.append(student)
        else:
            student["group_id"] = group_id
            student["phone"] = str(enrollment.get("phone") or "")
            student["updated_at"] = now
        payload["education_students"] = students
        enrollment["status"] = "accepted"
        enrollment["group_id"] = group_id
        enrollment["student_id"] = student["id"]
    elif action == "reject":
        enrollment["status"] = "rejected"
    else:
        raise action_forbidden()

    enrollment["updated_at"] = now
    payload["education_enrollments"] = rows
    return find_record(education_enrollment_rows(payload), record_id)

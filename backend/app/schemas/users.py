from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models import AppUser, AuditEvent
from app.models.enums import AccessRole, Language
from app.schemas.common import Ref


class UserRow(BaseModel):
    id: int
    employee_id: str
    full_name: str
    branch: Ref | None
    region: Ref | None
    job_role: Ref | None
    access_role: AccessRole
    preferred_language: Language
    is_active: bool
    must_change_password: bool
    locked_until: datetime | None
    last_seen_at: datetime | None

    @classmethod
    def of(cls, user: AppUser) -> UserRow:
        branch = user.branch
        return cls(
            id=user.id,
            employee_id=user.employee_id,
            full_name=user.full_name,
            branch=Ref.model_validate(branch) if branch else None,
            region=Ref.model_validate(branch.region) if branch else None,
            job_role=Ref.model_validate(user.job_role) if user.job_role else None,
            access_role=user.access_role,
            preferred_language=user.preferred_language,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            locked_until=user.locked_until,
            last_seen_at=user.last_seen_at,
        )


class AuditOut(BaseModel):
    at: datetime
    action: str
    actor_id: int | None
    reason: str | None
    data: dict[str, Any]

    @classmethod
    def of(cls, event: AuditEvent) -> AuditOut:
        return cls(
            at=event.at,
            action=event.action,
            actor_id=event.actor_id,
            reason=event.reason,
            data=event.data,
        )


class UserDetail(UserRow):
    audit: list[AuditOut]


class UserPatchIn(BaseModel):
    access_role: AccessRole | None = None
    is_active: bool | None = None


class TempPasswordOut(BaseModel):
    temp_password: str


class ImportProblem(BaseModel):
    row: int
    employee_id: str | None
    code: str
    params: dict[str, Any]


class ImportReport(BaseModel):
    import_id: int
    filename: str
    total_rows: int
    valid_rows: int
    error_rows: int
    to_create: int
    to_update: int
    errors: list[ImportProblem]


class ImportCommitOut(BaseModel):
    import_id: int
    created: int
    updated: int
    unchanged: int
    skipped: list[ImportProblem]
    # One-time CSV of temporary passwords for the new users; not stored anywhere.
    temp_passwords_csv: str

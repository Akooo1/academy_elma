from __future__ import annotations

import itertools
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import passwords
from app.models import AppUser, Branch, JobRole, Module, Region
from app.models.enums import AccessRole, Language

PASSWORD = "Parol-2026!"
_ids = itertools.count(1)


@dataclass
class Reference:
    regions: dict[str, Region]
    roles: dict[str, JobRole]
    modules: dict[str, Module]
    tashkent: Branch  # 01-101, region 01
    samarqand: Branch  # 11-101, region 11

    @classmethod
    def load(cls, db: Session) -> Reference:
        regions = {r.code: r for r in db.scalars(select(Region))}
        tashkent = Branch(
            code="01-101", name_uz="Chilonzor BXM", name_ru="ЦБУ Чиланзар",
            region_id=regions["01"].id,
        )  # fmt: skip
        samarqand = Branch(
            code="11-101", name_uz="Samarqand BXM", name_ru="ЦБУ Самарканд",
            region_id=regions["11"].id,
        )  # fmt: skip
        db.add_all([tashkent, samarqand])
        db.flush()
        return cls(
            regions=regions,
            roles={r.code: r for r in db.scalars(select(JobRole))},
            modules={m.code: m for m in db.scalars(select(Module))},
            tashkent=tashkent,
            samarqand=samarqand,
        )


def make_user(
    db: Session,
    *,
    role: AccessRole = AccessRole.learner,
    employee_id: str | None = None,
    password: str = PASSWORD,
    must_change: bool = False,
    branch: Branch | None = None,
    job_role: JobRole | None = None,
    full_name: str = "Test Foydalanuvchi",
    is_active: bool = True,
) -> AppUser:
    user = AppUser(
        employee_id=employee_id or f"T-{next(_ids):06d}",
        full_name=full_name,
        access_role=role,
        preferred_language=Language.uz,
        password_hash=passwords.hash_password(password),
        must_change_password=must_change,
        branch_id=branch.id if branch else None,
        job_role_id=job_role.id if job_role else None,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def login(client, user_or_id, password: str = PASSWORD):
    employee_id = user_or_id if isinstance(user_or_id, str) else user_or_id.employee_id
    return client.post("/api/v1/auth/login", json={"username": employee_id, "password": password})


def error_code(response) -> str:
    return response.json()["error"]["code"]

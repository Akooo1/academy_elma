from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.auth import passwords
from app.models import (
    AppUser,
    Branch,
    Certificate,
    ElmaRelease,
    JobRole,
    Lesson,
    LessonVersion,
    Module,
    Region,
    VideoAsset,
    Wave,
    WaveBranch,
    WaveModuleRole,
)
from app.models.enums import (
    AccessRole,
    CertificateKind,
    Language,
    LessonVersionStatus,
    ReleaseStatus,
    VideoStatus,
)

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


# --- content -----------------------------------------------------------------------


def make_release(db: Session, code: str, status: ReleaseStatus = ReleaseStatus.published):
    release = ElmaRelease(code=code, status=status)
    if status == ReleaseStatus.published:
        release.published_at = clock.utcnow()
    db.add(release)
    db.flush()
    return release


def _staff(db: Session) -> AppUser:
    staff = db.scalar(select(AppUser).where(AppUser.employee_id == "STAFF-0001"))
    return staff or make_user(db, role=AccessRole.methodologist, employee_id="STAFF-0001")


def make_asset(
    db: Session, duration: float | None = 100.0, status=VideoStatus.ready
) -> VideoAsset:
    staff = _staff(db)
    asset = VideoAsset(
        id=uuid.uuid4(),
        original_filename="dars.mp4",
        size_bytes=1,
        status=status,
        duration_s=duration,
        synthetic_confirmed_by=staff.id,
        synthetic_confirmed_at=clock.utcnow(),
        uploaded_by=staff.id,
    )
    db.add(asset)
    db.flush()
    return asset


def make_live_lesson(
    db: Session,
    module: Module,
    *,
    duration: float = 100.0,
    release: ElmaRelease | None = None,
    title: str = "Dars",
    pdf: bool = False,
) -> tuple[Lesson, LessonVersion]:
    """A published lesson with a ready (fake) video; no files on disk."""
    release = release or db.scalar(select(ElmaRelease).where(ElmaRelease.code == "T-LIVE"))
    release = release or make_release(db, "T-LIVE")
    last = db.scalar(select(func.max(Lesson.sort)).where(Lesson.module_id == module.id)) or 0
    lesson = Lesson(module_id=module.id, sort=last + 1, title_uz=title, title_ru=f"{title} (ru)")
    db.add(lesson)
    db.flush()
    asset = make_asset(db, duration)
    version = LessonVersion(
        lesson_id=lesson.id,
        release_id=release.id,
        status=LessonVersionStatus.published,
        video_asset_id=asset.id,
        vtt_uz_path=f"vtt/{lesson.id}-uz.vtt",
        vtt_ru_path=f"vtt/{lesson.id}-ru.vtt",
        pdf_uz_path=f"pdf/{lesson.id}-uz.pdf" if pdf else None,
        pdf_ru_path=f"pdf/{lesson.id}-ru.pdf" if pdf else None,
        published_at=clock.utcnow(),
    )
    db.add(version)
    module.current_release_id = release.id
    db.flush()
    return lesson, version


def make_wave(
    db: Session, branches: list[Branch], assignments: dict[JobRole, list[Module]]
) -> Wave:
    today = clock.utcnow().date()
    wave = Wave(
        name_uz="Sinov toʻlqini", name_ru="Тестовая волна",
        training_start=today, deadline=today, go_live=today,
    )  # fmt: skip
    db.add(wave)
    db.flush()
    for branch in branches:
        db.add(WaveBranch(wave_id=wave.id, branch_id=branch.id))
    for role, modules in assignments.items():
        for module in modules:
            db.add(WaveModuleRole(wave_id=wave.id, module_id=module.id, job_role_id=role.id))
    db.flush()
    return wave


def make_learner(db: Session, ref: Reference, role_code: str = "menejer", branch=None) -> AppUser:
    return make_user(db, branch=branch or ref.tashkent, job_role=ref.roles[role_code])


def give_certificate(
    db: Session, user: AppUser, module: Module, *, recert_due_at=None, superseded: bool = False
) -> Certificate:
    now = clock.utcnow()
    cert = Certificate(
        number=f"YO-TEST-{next(_ids):06d}",
        verify_code="TESTCODE",
        kind=CertificateKind.module,
        user_id=user.id,
        module_id=module.id,
        issued_at=now,
        recert_due_at=recert_due_at,
        superseded_at=now if superseded else None,
        snapshot={},
    )
    db.add(cert)
    db.flush()
    return cert

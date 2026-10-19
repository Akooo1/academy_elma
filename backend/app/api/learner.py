"""Learner side of content: assigned modules, lessons, the player and heartbeats."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import get_db
from app.errors import AppError, not_found
from app.models import (
    AppUser,
    ElmaRelease,
    Lesson,
    LessonProgress,
    LessonVersion,
    Module,
    VideoAsset,
)
from app.models.enums import LessonVersionStatus, ModuleType
from app.schemas.learner import (
    HeartbeatIn,
    HeartbeatOut,
    LearnerLesson,
    LearnerModule,
    LearnerModuleDetail,
    PlayerOut,
    ProgressOut,
    TestInfo,
)
from app.services import access, content, media, progress

router = APIRouter(prefix="/me", tags=["learner"])


def _pct(watched_s: float, duration: float) -> int:
    return min(100, int(watched_s / duration * 100)) if duration > 0 else 0


def _release_code(db: Session, release_id: int | None) -> str | None:
    if release_id is None:
        return None
    return db.scalar(select(ElmaRelease.code).where(ElmaRelease.id == release_id))


def _lesson_rows(db: Session, user: AppUser, module_ids: list[int]):
    """(module_id, lesson, duration, progress or None) for every live lesson, in order."""
    return db.execute(
        select(Lesson, VideoAsset.duration_s, LessonProgress)
        .join(
            LessonVersion,
            and_(
                LessonVersion.lesson_id == Lesson.id,
                LessonVersion.status == LessonVersionStatus.published,
            ),
        )
        .join(VideoAsset, VideoAsset.id == LessonVersion.video_asset_id)
        .outerjoin(
            LessonProgress,
            and_(
                LessonProgress.lesson_version_id == LessonVersion.id,
                LessonProgress.user_id == user.id,
            ),
        )
        .where(Lesson.module_id.in_(module_ids))
        .order_by(Lesson.sort, Lesson.id)
    ).all()


def _module_out(
    db: Session, module: Module, rows: list, core_certified: bool
) -> LearnerModule:
    return LearnerModule(
        id=module.id,
        code=module.code,
        type=module.type,
        title_uz=module.title_uz,
        title_ru=module.title_ru,
        sort=module.sort,
        locked=access.is_locked(module, core_certified),
        release_code=_release_code(db, module.current_release_id),
        lessons_total=len(rows),
        lessons_completed=sum(1 for _, _, p in rows if p is not None and p.completed_at),
        duration_s=round(sum(d or 0 for _, d, _ in rows), 1),
    )


def _lesson_items(rows: list) -> list[LearnerLesson]:
    return [
        LearnerLesson(
            id=lesson.id,
            sort=lesson.sort,
            title_uz=lesson.title_uz,
            title_ru=lesson.title_ru,
            duration_s=duration or 0.0,
            completed=bool(p and p.completed_at),
            watched_pct=_pct(p.watched_s, duration or 0) if p else 0,
        )
        for lesson, duration, p in rows
    ]


@router.get("/modules", response_model=list[LearnerModule])
def my_modules(user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    modules = access.assigned_modules(db, user)
    rows_by_module: dict[int, list] = {m.id: [] for m in modules}
    for lesson, duration, p in _lesson_rows(db, user, list(rows_by_module)):
        rows_by_module[lesson.module_id].append((lesson, duration, p))
    core_certified = access.holds_core_certificate(db, user.id)
    return [
        _module_out(db, m, rows_by_module[m.id], core_certified)
        for m in modules
        if rows_by_module[m.id]  # modules without live lessons stay hidden
    ]


@router.get("/modules/{module_id}", response_model=LearnerModuleDetail)
def my_module(module_id: int, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    module = db.get(Module, module_id)
    assigned = {m.id for m in access.assigned_modules(db, user)}
    if module is None or (module.type != ModuleType.faq and module.id not in assigned):
        raise not_found("module")
    rows = [tuple(r) for r in _lesson_rows(db, user, [module.id])]
    if not rows:
        raise not_found("module")
    core_certified = access.holds_core_certificate(db, user.id)
    base = _module_out(db, module, rows, core_certified)
    test = None
    if module.type != ModuleType.faq:
        test = TestInfo(
            question_count=module.test_question_count,
            pass_pct=module.test_pass_pct,
            time_limit_min=module.test_time_limit_min,
            max_attempts=module.test_max_attempts,
            published=module.test_published_at is not None,
            lessons_complete=base.lessons_completed == base.lessons_total,
        )
    return LearnerModuleDetail(**base.model_dump(), lessons=_lesson_items(rows), test=test)


@router.get("/faq", response_model=list[LearnerLesson])
def faq(user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    faq_ids = list(db.scalars(select(Module.id).where(Module.type == ModuleType.faq)))
    return _lesson_items([tuple(r) for r in _lesson_rows(db, user, faq_ids)])


def _open_lesson(db: Session, user: AppUser, lesson_id: int):
    """Lesson, module, live version and whether watching is tracked; enforces access."""
    lesson = db.get(Lesson, lesson_id)
    version = content.published_version(db, lesson_id) if lesson else None
    if lesson is None or version is None:
        raise not_found("lesson")
    module = db.get(Module, lesson.module_id)
    if module.type == ModuleType.faq:
        return lesson, module, version, False
    if module.id not in {m.id for m in access.assigned_modules(db, user)}:
        raise not_found("lesson")
    if access.is_locked(module, access.holds_core_certificate(db, user.id)):
        raise AppError(403, "module.locked")
    return lesson, module, version, True


def _progress_out(p: LessonProgress | None, duration: float) -> ProgressOut:
    if p is None:
        return ProgressOut(
            watched_s=0, watched_pct=0, max_position_s=0, last_position_s=0, completed=False
        )
    return ProgressOut(
        watched_s=p.watched_s,
        watched_pct=_pct(p.watched_s, duration),
        max_position_s=p.max_position_s,
        last_position_s=p.last_position_s,
        completed=p.completed_at is not None,
    )


@router.get("/lessons/{lesson_id}", response_model=PlayerOut)
def open_lesson(
    lesson_id: int, user: AppUser = Depends(current_user), db: Session = Depends(get_db)
):
    lesson, module, version, tracking = _open_lesson(db, user, lesson_id)
    duration = content.duration_of(version) or 0.0
    record = (
        db.scalar(
            select(LessonProgress).where(
                LessonProgress.user_id == user.id, LessonProgress.lesson_version_id == version.id
            )
        )
        if tracking
        else None
    )
    prog = _progress_out(record, duration) if tracking else None
    completed = bool(prog and prog.completed)
    siblings = [lsn.id for lsn, _ in content.published_lessons(db, module.id)]
    index = siblings.index(lesson.id)
    pdf = (
        {"uz": media.url(version.pdf_uz_path), "ru": media.url(version.pdf_ru_path)}
        if version.pdf_uz_path and version.pdf_ru_path
        else None
    )
    return PlayerOut(
        lesson_id=lesson.id,
        module_id=module.id,
        module_type=module.type,
        title_uz=lesson.title_uz,
        title_ru=lesson.title_ru,
        version_id=version.id,
        release_code=_release_code(db, version.release_id) or "",
        duration_s=duration,
        hls_url=media.hls_url(version.video_asset_id),
        subtitles={"uz": media.url(version.vtt_uz_path), "ru": media.url(version.vtt_ru_path)},
        pdf=pdf,
        tracking=tracking,
        progress=prog,
        seek_limit_s=None if (not tracking or completed) else prog.max_position_s,
        speed_change_allowed=not tracking or completed,
        prev_lesson_id=siblings[index - 1] if index > 0 else None,
        next_lesson_id=siblings[index + 1] if index + 1 < len(siblings) else None,
    )


@router.post("/lessons/{lesson_id}/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    lesson_id: int,
    body: HeartbeatIn,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, _, version, tracking = _open_lesson(db, user, lesson_id)
    if not tracking:
        raise AppError(400, "lesson.not_tracked")
    if body.version_id != version.id:  # a release replaced the video meanwhile
        raise AppError(409, "lesson.version_changed", {"current_version_id": version.id})
    duration = content.duration_of(version) or 0.0
    record, _ = progress.record_heartbeat(
        db,
        user_id=user.id,
        lesson_version_id=version.id,
        duration=duration,
        ranges=body.ranges,
        position_s=body.position_s,
    )
    db.commit()
    return HeartbeatOut(**_progress_out(record, duration).model_dump(), duration_s=duration)


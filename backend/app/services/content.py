"""Lessons and their versions: lookups shared by the admin and learner APIs."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Lesson, LessonVersion, Question, VideoAsset
from app.models.enums import LessonVersionStatus
from app.services import media

FILE_COLUMNS = ("vtt_uz_path", "vtt_ru_path", "pdf_uz_path", "pdf_ru_path")


def versions_by_lesson(
    db: Session, lesson_ids: Iterable[int], status: LessonVersionStatus
) -> dict[int, LessonVersion]:
    ids = list(lesson_ids)
    if not ids:
        return {}
    rows = db.scalars(
        select(LessonVersion)
        .options(selectinload(LessonVersion.video_asset))
        .where(LessonVersion.lesson_id.in_(ids), LessonVersion.status == status)
    )
    return {v.lesson_id: v for v in rows}


def published_lessons(db: Session, module_id: int) -> list[tuple[Lesson, LessonVersion]]:
    """Lessons learners can see in a module, in order, with their live version."""
    rows = db.execute(
        select(Lesson, LessonVersion)
        .join(LessonVersion, LessonVersion.lesson_id == Lesson.id)
        .options(selectinload(LessonVersion.video_asset))
        .where(
            Lesson.module_id == module_id,
            LessonVersion.status == LessonVersionStatus.published,
        )
        .order_by(Lesson.sort, Lesson.id)
    ).all()
    return [(lesson, version) for lesson, version in rows]


def published_version(db: Session, lesson_id: int) -> LessonVersion | None:
    return db.scalar(
        select(LessonVersion)
        .options(selectinload(LessonVersion.video_asset))
        .where(
            LessonVersion.lesson_id == lesson_id,
            LessonVersion.status == LessonVersionStatus.published,
        )
    )


def duration_of(version: LessonVersion) -> float | None:
    asset = version.video_asset
    return asset.duration_s if asset is not None else None


def has_questions(db: Session, version_ids: Iterable[int]) -> bool:
    ids = list(version_ids)
    return bool(ids) and bool(
        db.scalar(select(exists().where(Question.lesson_version_id.in_(ids))))
    )


def drop_unreferenced_files(db: Session, paths: Iterable[str | None]) -> None:
    """Delete files no lesson version points to any more (draft PDFs can be shared)."""
    for path in {p for p in paths if p}:
        columns = [getattr(LessonVersion, c) == path for c in FILE_COLUMNS]
        if not db.scalar(select(exists().where(or_(*columns)))):
            media.delete_rel(path)


def drop_asset_if_unreferenced(db: Session, asset_id: uuid.UUID | None) -> None:
    if asset_id is None:
        return
    if db.scalar(select(exists().where(LessonVersion.video_asset_id == asset_id))):
        return
    asset = db.get(VideoAsset, asset_id)
    if asset is not None:
        db.delete(asset)
        db.flush()
    media.delete_asset_files(asset_id)


def delete_version(db: Session, version: LessonVersion) -> None:
    paths = [getattr(version, c) for c in FILE_COLUMNS]
    asset_id = version.video_asset_id
    db.delete(version)
    db.flush()
    drop_unreferenced_files(db, paths)
    drop_asset_if_unreferenced(db, asset_id)

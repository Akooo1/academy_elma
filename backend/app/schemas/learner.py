from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ModuleType

Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class LearnerLesson(BaseModel):
    id: int
    sort: int
    title_uz: str
    title_ru: str
    duration_s: float
    completed: bool
    watched_pct: int


class LearnerModule(BaseModel):
    id: int
    code: str
    type: ModuleType
    title_uz: str
    title_ru: str
    sort: int
    locked: bool  # product module before the Core certificate
    release_code: str | None
    lessons_total: int
    lessons_completed: int
    duration_s: float


class TestInfo(BaseModel):
    question_count: int
    pass_pct: int
    time_limit_min: int
    max_attempts: int
    published: bool
    lessons_complete: bool


class LearnerModuleDetail(LearnerModule):
    lessons: list[LearnerLesson]
    test: TestInfo | None  # None for FAQ


class ProgressOut(BaseModel):
    watched_s: float
    watched_pct: int
    max_position_s: float
    last_position_s: float
    completed: bool


class PlayerOut(BaseModel):
    lesson_id: int
    module_id: int
    module_type: ModuleType
    title_uz: str
    title_ru: str
    version_id: int
    release_code: str
    duration_s: float
    hls_url: str
    subtitles: dict[str, str]  # {"uz": url, "ru": url}
    pdf: dict[str, str] | None  # shown only when it exists in both languages
    tracking: bool  # False for FAQ: no heartbeats, free seeking
    progress: ProgressOut | None
    seek_limit_s: float | None  # first viewing: no seeking past this point
    speed_change_allowed: bool
    prev_lesson_id: int | None
    next_lesson_id: int | None


class HeartbeatIn(BaseModel):
    """What the player actually played since the last heartbeat. No completion flag exists."""

    model_config = ConfigDict(extra="forbid")

    version_id: int
    ranges: list[tuple[Seconds, Seconds]] = Field(default_factory=list, max_length=50)
    position_s: Seconds = 0.0


class HeartbeatOut(ProgressOut):
    duration_s: float

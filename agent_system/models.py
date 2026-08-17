"""Pydantic models.

Two groups:
  1. Raw record models — mirror `types.ts` / `schema.prisma` field-for-field so
     the JSON/CSV files in this repo validate directly. Fields that can be
     legitimately absent in real-world exports (a late-arriving webhook, a
     partial CSV) are Optional with a safe default rather than required —
     ingestion quarantines a row instead of crashing the whole pipeline.
  2. Pipeline models — the outputs each agent produces and the shared graph
     state that flows between them.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Lenient(BaseModel):
    """Base for records sourced from external files: unknown fields ignored,
    validation failures are caught by the ingestion layer (not here)."""

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- raw records

class Parent(Lenient):
    full_name: Optional[str] = None
    relation: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None
    preferred_contact: Literal["telegram", "phone", "sms"] = "telegram"


class Student(Lenient):
    id: int
    code: str
    full_name: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    course_code: Optional[str] = None
    mentor_id: Optional[int] = None
    tutor_id: Optional[int] = None
    curator_id: Optional[int] = None
    parent: Optional[Parent] = None
    status: str = "active"


class AttendanceStatus(str, Enum):
    present = "present"
    late = "late"
    absent_excused = "absent_excused"
    absent_unexcused = "absent_unexcused"


class AttendanceRecord(Lenient):
    id: int
    student_id: int
    lesson_id: int
    group_id: Optional[int] = None
    date: date
    status: AttendanceStatus
    minutes_late: int = 0
    note: Optional[str] = None


class LessonType(str, Enum):
    lecture = "lecture"
    practice = "practice"
    exam = "exam"


class Lesson(Lenient):
    id: int
    group_id: int
    lesson_number: Optional[int] = None
    date: date
    topic: str = "Noma'lum mavzu"
    module: Optional[int] = None
    type: LessonType = LessonType.lecture


class HomeworkStatus(str, Enum):
    submitted_on_time = "submitted_on_time"
    submitted_late = "submitted_late"
    not_submitted = "not_submitted"


class HomeworkSubmission(Lenient):
    id: int
    homework_id: int
    student_id: int
    group_id: Optional[int] = None
    status: HomeworkStatus = HomeworkStatus.not_submitted
    days_late: Optional[int] = None
    score: int = 0
    submitted_at: Optional[str] = None


class HomeworkAssignment(Lenient):
    id: int
    lesson_id: int
    group_id: Optional[int] = None
    title: Optional[str] = None
    due_date: Optional[date] = None
    max_score: int = 100
    difficulty: Optional[str] = None


class CoinTransaction(Lenient):
    id: int
    student_id: int
    date: date
    type: Literal["earn", "spend", "penalty"]
    reason: str
    amount: int
    balance_after: int


class CuratorContact(Lenient):
    id: int
    curator_id: int
    student_id: int
    date: date
    channel: Literal["telegram", "phone", "sms"] = "telegram"
    reason: str
    subject: Optional[str] = None
    summary: Optional[str] = None
    resolved: bool = False
    follow_up_needed: bool = False


class Group(Lenient):
    id: int
    name: str
    course_code: Optional[str] = None
    mentor_id: Optional[int] = None
    tutor_id: Optional[int] = None
    curator_id: Optional[int] = None


# -------------------------------------------------------------- data quality

class QuarantinedRow(BaseModel):
    source_file: str
    reason: str
    row_index: int
    raw: Any = None


class DataQualityReport(BaseModel):
    files_loaded: dict[str, int] = Field(default_factory=dict)
    files_missing: list[str] = Field(default_factory=list)
    quarantined: list[QuarantinedRow] = Field(default_factory=list)
    orphaned_fk_count: int = 0

    @property
    def is_degraded(self) -> bool:
        return bool(self.files_missing or self.quarantined)


class DataBundle(BaseModel):
    """Everything ingestion produced, ready for the agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    students: dict[int, Student] = Field(default_factory=dict)
    groups: dict[int, Group] = Field(default_factory=dict)
    lessons: dict[int, Lesson] = Field(default_factory=dict)
    attendance: list[AttendanceRecord] = Field(default_factory=list)
    homework_assignments: dict[int, HomeworkAssignment] = Field(default_factory=dict)
    homework_submissions: list[HomeworkSubmission] = Field(default_factory=list)
    coin_transactions: list[CoinTransaction] = Field(default_factory=list)
    curator_contacts: list[CuratorContact] = Field(default_factory=list)
    quality: DataQualityReport = Field(default_factory=DataQualityReport)


# ---------------------------------------------------------------- agent 1

class AbsenceReason(str, Enum):
    homework_avoidance = "homework_avoidance"   # ko'p qoldirgan darslarda ham vazifa topshirmagan
    documented_excused = "documented_excused"   # sababli, curator/parent tomonidan tasdiqlangan
    unexplained = "unexplained"                 # sabab aniqlanmagan — curator tekshirishi kerak


class MonthlyAttendanceFlag(BaseModel):
    student_id: int
    student_name: str
    group_id: Optional[int]
    period: str  # "2026-04"
    lessons_in_window: int
    present_count: int
    required_min: int
    below_threshold: bool
    consecutive_absences: int
    likely_reason: AbsenceReason
    reason_detail: str


class AttendanceAgentOutput(BaseModel):
    flagged: list[MonthlyAttendanceFlag] = Field(default_factory=list)
    ok_count: int = 0
    curator_alerts: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- agent 2

class WeakTopic(BaseModel):
    topic: str
    module: Optional[int] = None
    avg_score: float
    submissions: int


class StudentRecommendation(BaseModel):
    student_id: int
    student_name: str
    weak_topics: list[WeakTopic]
    strong_topics: list[WeakTopic]
    recommendation_text: str
    source: Literal["llm", "template"] = "template"


class RankingEntry(BaseModel):
    rank: int
    student_id: int
    student_name: str
    group_id: Optional[int]
    performance_score: float
    attendance_rate: float
    homework_rate: float
    avg_score: float
    trend: Literal["up", "down", "flat"] = "flat"


class PerformanceAgentOutput(BaseModel):
    leaderboard: list[RankingEntry] = Field(default_factory=list)
    bottom_list: list[RankingEntry] = Field(default_factory=list)
    recommendations: list[StudentRecommendation] = Field(default_factory=list)
    group_weak_topics: dict[int, list[WeakTopic]] = Field(default_factory=dict)


# ---------------------------------------------------------------- agent 3

class SyncResult(BaseModel):
    target: Literal["postgres", "sqlite_fallback"]
    ok: bool
    rows_written: int = 0
    error: Optional[str] = None


class NotificationResult(BaseModel):
    channel: Literal["telegram", "dry_run"]
    recipient: str
    ok: bool
    error: Optional[str] = None
    retries: int = 0


class IntegrationAgentOutput(BaseModel):
    sync: Optional[SyncResult] = None
    notifications: list[NotificationResult] = Field(default_factory=list)
    mcp_published: bool = False
    mcp_error: Optional[str] = None


# ---------------------------------------------------------------- pipeline

class PipelineState(BaseModel):
    """Shared state threaded through the LangGraph graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_source: str
    bundle: Optional[DataBundle] = None
    attendance_out: Optional[AttendanceAgentOutput] = None
    performance_out: Optional[PerformanceAgentOutput] = None
    integration_out: Optional[IntegrationAgentOutput] = None
    errors: list[str] = Field(default_factory=list)
    aborted: bool = False

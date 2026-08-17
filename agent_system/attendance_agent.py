"""Agent 1 — Davomat agenti.

Rule (as specified): a course runs ~13 lessons per month; if a student is
present for fewer than 7 of those 13, they go on the "kam kelganlar" list and
their ranking takes a hit. Windows are built from the student's own attendance
history in chunks of `attendance_window_lessons` lessons (not calendar
months) — this is robust to holidays, makeup weeks, and students who joined
mid-term, and it matches the literal "13 ta dars" framing better than a
wall-clock month would.

Reason classification for a flagged window is heuristic (no free-text NLP
model here — this is a deterministic signal-combination, cheap and
explainable):
  - documented_excused : majority of misses are `absent_excused` and/or a
                          curator already logged + resolved a contact
  - homework_avoidance  : majority `absent_unexcused` AND the student's
                          homework submission rate in the same window is low
                          (pattern: skipping class to dodge the assignment)
  - unexplained         : neither signal fires — curator needs to actually
                          call the parent, this is the highest-priority case

Fallback logic: a trailing window shorter than half the configured size is
too little evidence to judge, so it is skipped with a note instead of being
scored (avoids false "kam kelgan" flags for students who just enrolled).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .config import settings
from .models import (
    AbsenceReason,
    AttendanceAgentOutput,
    AttendanceRecord,
    AttendanceStatus,
    DataBundle,
    MonthlyAttendanceFlag,
)

_ATTENDED = {AttendanceStatus.present, AttendanceStatus.late}
_MISSED = {AttendanceStatus.absent_excused, AttendanceStatus.absent_unexcused}


def _chunks(seq: list[AttendanceRecord], size: int) -> list[list[AttendanceRecord]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _max_consecutive_absences(records: list[AttendanceRecord]) -> int:
    best = cur = 0
    for r in records:
        if r.status in _MISSED:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _homework_rate_in_window(
    student_id: int,
    window_start: date,
    window_end: date,
    bundle: DataBundle,
) -> float | None:
    assignment_ids_in_window = {
        a.id
        for a in bundle.homework_assignments.values()
        if a.due_date and window_start <= a.due_date <= window_end
    }
    if not assignment_ids_in_window:
        return None
    relevant = [
        s
        for s in bundle.homework_submissions
        if s.student_id == student_id and s.homework_id in assignment_ids_in_window
    ]
    if not relevant:
        return None
    submitted = sum(1 for s in relevant if s.status.value != "not_submitted")
    return submitted / len(relevant)


def _classify_reason(
    window: list[AttendanceRecord],
    student_id: int,
    bundle: DataBundle,
    has_resolved_contact: bool,
) -> tuple[AbsenceReason, str]:
    missed = [r for r in window if r.status in _MISSED]
    excused = sum(1 for r in missed if r.status == AttendanceStatus.absent_excused)
    unexcused = len(missed) - excused

    if missed and (excused / len(missed) >= 0.6 or has_resolved_contact):
        return (
            AbsenceReason.documented_excused,
            f"{excused}/{len(missed)} qoldirilgan dars sababli belgilangan"
            + (", curator allaqachon oila bilan bog'langan" if has_resolved_contact else ""),
        )

    hw_rate = _homework_rate_in_window(student_id, window[0].date, window[-1].date, bundle)
    if unexcused and hw_rate is not None and hw_rate < 0.5:
        return (
            AbsenceReason.homework_avoidance,
            f"{unexcused}/{len(missed)} sababsiz qoldirish, shu davrda vazifa "
            f"topshirish darajasi past ({hw_rate:.0%}) — vazifadan qochish ehtimoli",
        )

    return (
        AbsenceReason.unexplained,
        f"{unexcused}/{len(missed)} sababsiz qoldirish, sabab hujjatlashtirilmagan — "
        "curator ota-ona bilan bog'lanishi kerak",
    )


def run_attendance_agent(bundle: DataBundle) -> AttendanceAgentOutput:
    by_student: dict[int, list[AttendanceRecord]] = defaultdict(list)
    for rec in bundle.attendance:
        by_student[rec.student_id].append(rec)

    resolved_contacts_by_student: set[int] = {
        c.student_id
        for c in bundle.curator_contacts
        if c.reason == "absence_alert" and c.resolved
    }

    out = AttendanceAgentOutput()
    window_size = settings.attendance_window_lessons
    min_present = settings.attendance_min_present

    for student_id, records in by_student.items():
        student = bundle.students.get(student_id)
        student_name = student.full_name if student else f"#{student_id}"
        group_id = student.group_id if student else (records[0].group_id if records else None)

        records_sorted = sorted(records, key=lambda r: r.date)
        consecutive = _max_consecutive_absences(records_sorted)

        any_flag_for_student = False
        for window in _chunks(records_sorted, window_size):
            if len(window) < max(1, window_size // 2):
                out.notes.append(
                    f"{student_name}: oxirgi davr uchun yetarli dars yozuvi yo'q "
                    f"({len(window)} ta) — baholanmadi"
                )
                continue

            present_count = sum(1 for r in window if r.status in _ATTENDED)
            below = present_count < min_present
            if not below:
                continue

            any_flag_for_student = True
            reason, detail = _classify_reason(
                window, student_id, bundle, student_id in resolved_contacts_by_student
            )
            out.flagged.append(
                MonthlyAttendanceFlag(
                    student_id=student_id,
                    student_name=student_name,
                    group_id=group_id,
                    period=window[-1].date.strftime("%Y-%m"),
                    lessons_in_window=len(window),
                    present_count=present_count,
                    required_min=min_present,
                    below_threshold=True,
                    consecutive_absences=consecutive,
                    likely_reason=reason,
                    reason_detail=detail,
                )
            )

        if not any_flag_for_student:
            out.ok_count += 1

        if consecutive >= settings.behind_streak_threshold:
            out.curator_alerts.append(
                {
                    "student_id": student_id,
                    "student_name": student_name,
                    "group_id": group_id,
                    "curator_id": student.curator_id if student else None,
                    "consecutive_absences": consecutive,
                    "message": (
                        f"{student_name} {consecutive} ta ketma-ket darsni qoldirdi — "
                        "ota-ona bilan bog'lanish tavsiya etiladi."
                    ),
                }
            )

    return out

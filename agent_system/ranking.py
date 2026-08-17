"""Final ranking algorithm — combines Agent 1 (attendance) and Agent 2
(homework/score) signals into one `performance_score` per student and sorts.

performance_score = w_attendance * attendance_rate
                   + w_homework   * homework_submission_rate
                   + w_score      * avg_homework_score

All three inputs are normalized to a 0-100 scale before weighting, and the
weights are read from `Settings` (they default to 0.35/0.30/0.35, matching
the dataset's own precomputed `performance_score` formula documented in
README.md, so results are directly comparable to the source data).

A student flagged by Agent 1 (`below_threshold` in the current window) takes
an explicit ranking penalty on top of the raw formula — attendance is a gate,
not just one input among equals, per the stated business rule.
"""
from __future__ import annotations

from .config import settings
from .models import MonthlyAttendanceFlag, RankingEntry

ATTENDANCE_PENALTY_PER_FLAG = 5.0


def compute_performance_score(
    attendance_rate_pct: float,
    homework_rate_pct: float,
    avg_score: float,
    flags_for_student: int = 0,
) -> float:
    raw = (
        settings.weight_attendance * attendance_rate_pct
        + settings.weight_homework * homework_rate_pct
        + settings.weight_score * avg_score
    )
    penalty = ATTENDANCE_PENALTY_PER_FLAG * flags_for_student
    return round(max(0.0, raw - penalty), 2)


def build_leaderboard(entries: list[RankingEntry]) -> list[RankingEntry]:
    ranked = sorted(entries, key=lambda e: e.performance_score, reverse=True)
    return [e.model_copy(update={"rank": i + 1}) for i, e in enumerate(ranked)]


def bottom_n(ranked_entries: list[RankingEntry], n: int = 20) -> list[RankingEntry]:
    return sorted(ranked_entries, key=lambda e: e.performance_score)[:n]


def flags_by_student(flags: list[MonthlyAttendanceFlag]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for f in flags:
        counts[f.student_id] = counts.get(f.student_id, 0) + 1
    return counts

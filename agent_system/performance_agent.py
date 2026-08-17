"""Agent 2 — O'zlashtirish va reyting agenti.

For every student: attendance rate, homework submission rate and average
score are aggregated from the raw records (not read off any precomputed
field, so this keeps working even against a data export that lacks the
dataset's own cached `performance_score`). Submissions are joined through
`homework_assignments.lesson_id -> lessons.topic` to find which topics a
student (and, aggregated, a whole group) struggles with the most.

Recommendation text generation is pluggable: if `ANTHROPIC_API_KEY` is set,
a short personalized note is generated with Claude; on any error (no key,
network down, rate limit) it transparently falls back to a deterministic
template built from the same weak/strong topic data, so the pipeline's
output shape never depends on an LLM being reachable.
"""
from __future__ import annotations

from collections import defaultdict

from .config import settings
from .models import (
    AttendanceStatus,
    DataBundle,
    MonthlyAttendanceFlag,
    PerformanceAgentOutput,
    RankingEntry,
    StudentRecommendation,
    WeakTopic,
)
from .ranking import bottom_n, build_leaderboard, compute_performance_score, flags_by_student

_ATTENDED = {AttendanceStatus.present, AttendanceStatus.late}


def _attendance_rate(student_id: int, bundle: DataBundle) -> float:
    records = [r for r in bundle.attendance if r.student_id == student_id]
    if not records:
        return 0.0
    attended = sum(1 for r in records if r.status in _ATTENDED)
    return round(100 * attended / len(records), 2)


def _homework_stats(student_id: int, bundle: DataBundle) -> tuple[float, float]:
    subs = [s for s in bundle.homework_submissions if s.student_id == student_id]
    if not subs:
        return 0.0, 0.0
    submitted = [s for s in subs if s.status.value != "not_submitted"]
    rate = round(100 * len(submitted) / len(subs), 2)
    avg_score = round(sum(s.score for s in subs) / len(subs), 2)
    return rate, avg_score


def _topic_for_homework(homework_id: int, bundle: DataBundle) -> tuple[str, int | None] | None:
    assignment = bundle.homework_assignments.get(homework_id)
    if assignment is None:
        return None
    lesson = bundle.lessons.get(assignment.lesson_id)
    if lesson is None:
        return None
    return lesson.topic, lesson.module


def _student_topic_breakdown(student_id: int, bundle: DataBundle) -> list[WeakTopic]:
    scores_by_topic: dict[tuple[str, int | None], list[int]] = defaultdict(list)
    for s in bundle.homework_submissions:
        if s.student_id != student_id or s.status.value == "not_submitted":
            continue
        topic_key = _topic_for_homework(s.homework_id, bundle)
        if topic_key is None:
            continue
        scores_by_topic[topic_key].append(s.score)

    return [
        WeakTopic(
            topic=topic,
            module=module,
            avg_score=round(sum(scores) / len(scores), 2),
            submissions=len(scores),
        )
        for (topic, module), scores in scores_by_topic.items()
    ]


def _template_recommendation(name: str, weak: list[WeakTopic], strong: list[WeakTopic]) -> str:
    if not weak:
        return (
            f"{name} barcha mavzularda barqaror natija ko'rsatmoqda. "
            "Qiyinroq / qo'shimcha mashqlar bilan rivojlanishni davom ettirish tavsiya etiladi."
        )
    weakest = ", ".join(f"«{t.topic}» ({t.avg_score:.0f} ball)" for t in weak[:3])
    tip = (
        f"{name} uchun eng qiyin mavzular: {weakest}. "
        "Ushbu mavzular bo'yicha qo'shimcha tutor sessiyasi va video darslarni qayta ko'rib "
        "chiqish, so'ng shu mavzudagi qo'shimcha mashqlarni bajarish tavsiya etiladi."
    )
    if strong:
        tip += f" Kuchli tomoni — «{strong[0].topic}» ({strong[0].avg_score:.0f} ball)."
    return tip


def _llm_recommendation(name: str, weak: list[WeakTopic], strong: list[WeakTopic]) -> str | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        weak_desc = ", ".join(f"{t.topic} ({t.avg_score:.0f} ball)" for t in weak[:3]) or "yo'q"
        strong_desc = ", ".join(f"{t.topic} ({t.avg_score:.0f} ball)" for t in strong[:2]) or "yo'q"
        msg = client.messages.create(
            model=settings.llm_model,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "O'zbek tilida, 2-3 gapda, o'quvchiga (ismi: "
                        f"{name}) shaxsiy o'quv tavsiyasi yoz. Qiyin mavzular: {weak_desc}. "
                        f"Kuchli mavzular: {strong_desc}. Ohang do'stona va konkret bo'lsin, "
                        "aniq nima qilish kerakligini ayt."
                    ),
                }
            ],
        )
        return msg.content[0].text.strip()
    except Exception:
        # Network / auth / rate-limit / SDK errors must never break the pipeline.
        return None


def run_performance_agent(
    bundle: DataBundle, attendance_flags: list[MonthlyAttendanceFlag]
) -> PerformanceAgentOutput:
    flag_counts = flags_by_student(attendance_flags)
    entries: list[RankingEntry] = []
    recommendations: list[StudentRecommendation] = []
    group_topic_scores: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for student_id, student in bundle.students.items():
        attendance_rate = _attendance_rate(student_id, bundle)
        homework_rate, avg_score = _homework_stats(student_id, bundle)
        score = compute_performance_score(
            attendance_rate, homework_rate, avg_score, flag_counts.get(student_id, 0)
        )
        entries.append(
            RankingEntry(
                rank=0,
                student_id=student_id,
                student_name=student.full_name,
                group_id=student.group_id,
                performance_score=score,
                attendance_rate=attendance_rate,
                homework_rate=homework_rate,
                avg_score=avg_score,
            )
        )

        breakdown = sorted(_student_topic_breakdown(student_id, bundle), key=lambda t: t.avg_score)
        weak = [t for t in breakdown if t.avg_score < settings.weak_topic_score_threshold]
        strong = sorted(
            [t for t in breakdown if t.avg_score >= settings.weak_topic_score_threshold],
            key=lambda t: t.avg_score,
            reverse=True,
        )

        if student.group_id is not None:
            for t in breakdown:
                group_topic_scores[student.group_id][t.topic].extend([t.avg_score] * t.submissions)

        text = _llm_recommendation(student.full_name, weak, strong)
        source = "llm" if text else "template"
        text = text or _template_recommendation(student.full_name, weak, strong)

        recommendations.append(
            StudentRecommendation(
                student_id=student_id,
                student_name=student.full_name,
                weak_topics=weak[:5],
                strong_topics=strong[:5],
                recommendation_text=text,
                source=source,
            )
        )

    leaderboard = build_leaderboard(entries)
    bottom = bottom_n(leaderboard, n=20)

    group_weak_topics: dict[int, list[WeakTopic]] = {}
    for group_id, topics in group_topic_scores.items():
        ranked = sorted(
            (
                WeakTopic(topic=topic, avg_score=round(sum(vals) / len(vals), 2), submissions=len(vals))
                for topic, vals in topics.items()
            ),
            key=lambda t: t.avg_score,
        )
        group_weak_topics[group_id] = ranked[:5]

    return PerformanceAgentOutput(
        leaderboard=leaderboard,
        bottom_list=bottom,
        recommendations=recommendations,
        group_weak_topics=group_weak_topics,
    )

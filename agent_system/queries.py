"""Fast, single-fact answers over the LMS data.

Two consumers:
  - `bot_server.py`'s keyword router (fallback path, no LLM required)
  - `mcp_server.py`'s tools (the AI agent's grounding — every number Claude
    states in a reply comes from one of these functions, never from the
    model's own guess)

These deliberately skip Agent 3 (cloud sync + real Telegram sends) so a
question gets a quick reply — only ingestion + Agent 1 + Agent 2 run, which
is pure in-memory computation with no network calls. `/analyze` still runs
the full graph including Agent 3 for the "official" hourly-style report.

`get_cached_quick_analysis` memoizes the result for a few minutes so an AI
conversation that calls 3-4 tools in a row doesn't re-parse ~26MB of JSON on
every single one.
"""
from __future__ import annotations

import time

from .attendance_agent import run_attendance_agent
from .ingestion import load_data_bundle
from .models import DataBundle
from .performance_agent import run_performance_agent

_CACHE: dict[str, tuple[float, tuple]] = {}
_CACHE_TTL_SECONDS = 300


def load_quick_analysis(source: str):
    bundle = load_data_bundle(source)
    attendance_out = run_attendance_agent(bundle)
    performance_out = run_performance_agent(bundle, attendance_out.flagged)
    return bundle, attendance_out, performance_out


def get_cached_quick_analysis(source: str):
    now = time.monotonic()
    cached = _CACHE.get(source)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    result = load_quick_analysis(source)
    _CACHE[source] = (now, result)
    return result


def _current_coin_balance(bundle: DataBundle) -> dict[int, int]:
    latest_tx: dict[int, tuple] = {}
    for tx in bundle.coin_transactions:
        key = (tx.date, tx.id)
        if tx.student_id not in latest_tx or key >= latest_tx[tx.student_id][0]:
            latest_tx[tx.student_id] = (key, tx.balance_after)
    return {sid: bal for sid, (_, bal) in latest_tx.items()}


def top_coin_holders(bundle: DataBundle, n: int = 5) -> str:
    balances = _current_coin_balance(bundle)
    if not balances:
        return "Coin tranzaksiyalari topilmadi."
    ranked = sorted(balances.items(), key=lambda kv: kv[1], reverse=True)[:n]
    lines = ["Eng ko'p coin to'plagan o'quvchilar:"]
    for i, (student_id, balance) in enumerate(ranked, start=1):
        student = bundle.students.get(student_id)
        name = student.full_name if student else f"#{student_id}"
        group = f" ({student.group_name})" if student and student.group_name else ""
        lines.append(f"{i}. {name}{group} — {balance} coin")
    return "\n".join(lines)


def bottom_coin_holders(bundle: DataBundle, n: int = 5) -> str:
    balances = _current_coin_balance(bundle)
    if not balances:
        return "Coin tranzaksiyalari topilmadi."
    ranked = sorted(balances.items(), key=lambda kv: kv[1])[:n]
    lines = ["Eng kam coin to'plagan o'quvchilar:"]
    for i, (student_id, balance) in enumerate(ranked, start=1):
        student = bundle.students.get(student_id)
        name = student.full_name if student else f"#{student_id}"
        lines.append(f"{i}. {name} — {balance} coin")
    return "\n".join(lines)


def top_performance(performance_out, n: int = 5) -> str:
    lines = ["Eng yaxshi o'zlashtirgan o'quvchilar:"]
    for e in performance_out.leaderboard[:n]:
        lines.append(f"{e.rank}. {e.student_name} — {e.performance_score} ball")
    return "\n".join(lines)


def bottom_performance(performance_out, n: int = 5) -> str:
    lines = ["Eng past o'zlashtirgan o'quvchilar (yordam kerak):"]
    for e in performance_out.bottom_list[:n]:
        lines.append(f"{e.rank}. {e.student_name} — {e.performance_score} ball")
    return "\n".join(lines)


def attendance_summary(attendance_out) -> str:
    lines = [
        f"Kam kelganlar (bayroqlangan davrlar): {len(attendance_out.flagged)}",
        f"Muammosiz o'quvchilar: {attendance_out.ok_count}",
        f"Curator ogohlantirishlari (2+ ketma-ket qoldirish): {len(attendance_out.curator_alerts)}",
        "",
        "Eng ko'p qoldirganlar:",
    ]
    worst = sorted(
        attendance_out.flagged, key=lambda f: f.present_count - f.required_min
    )[:5]
    for f in worst:
        lines.append(
            f"- {f.student_name} [{f.period}]: {f.present_count}/{f.lessons_in_window} kelgan"
        )
    return "\n".join(lines)


def find_students_by_name(performance_out, name: str, limit: int = 10):
    needle = name.strip().lower()
    return [
        e for e in performance_out.leaderboard if needle in e.student_name.lower()
    ][:limit]


def student_report(bundle: DataBundle, attendance_out, performance_out, name: str) -> str:
    matches = find_students_by_name(performance_out, name)
    if not matches:
        return f"'{name}' ismli o'quvchi topilmadi."
    if len(matches) > 1:
        listing = "\n".join(f"- {m.student_name} ({m.group_id})" for m in matches)
        return f"Bir nechta o'quvchi topildi, aniqroq ism yozing:\n{listing}"

    entry = matches[0]
    balances = _current_coin_balance(bundle)
    coin_balance = balances.get(entry.student_id, 0)
    rec = next(
        (r for r in performance_out.recommendations if r.student_id == entry.student_id), None
    )
    flags = [f for f in attendance_out.flagged if f.student_id == entry.student_id]

    lines = [
        f"{entry.student_name} — reyting #{entry.rank}",
        f"Performance score: {entry.performance_score}",
        f"Davomat: {entry.attendance_rate}%, uy vazifasi topshirish: {entry.homework_rate}%, "
        f"o'rtacha ball: {entry.avg_score}",
        f"Coin balansi: {coin_balance}",
    ]
    if flags:
        lines.append(f"Diqqat: {len(flags)} davrda davomat me'yordan past bo'lgan.")
    if rec:
        lines.append(f"Tavsiya: {rec.recommendation_text}")
    return "\n".join(lines)


def group_report(bundle: DataBundle, performance_out, group_query: str) -> str:
    needle = group_query.strip().lower()
    matched_group_id = None
    for gid, g in bundle.groups.items():
        if needle in g.name.lower():
            matched_group_id = gid
            break
    if matched_group_id is None:
        return f"'{group_query}' nomli guruh topilmadi."

    members = [e for e in performance_out.leaderboard if e.group_id == matched_group_id]
    if not members:
        return f"'{group_query}' guruhida o'quvchi topilmadi."

    avg_score = round(sum(m.performance_score for m in members) / len(members), 2)
    avg_attendance = round(sum(m.attendance_rate for m in members) / len(members), 2)
    weak_topics = performance_out.group_weak_topics.get(matched_group_id, [])

    lines = [
        f"Guruh: {bundle.groups[matched_group_id].name}",
        f"O'quvchilar soni: {len(members)}",
        f"O'rtacha performance score: {avg_score}",
        f"O'rtacha davomat: {avg_attendance}%",
    ]
    if weak_topics:
        lines.append("Eng qiyin mavzular: " + ", ".join(f"{t.topic} ({t.avg_score:.0f})" for t in weak_topics[:3]))
    return "\n".join(lines)

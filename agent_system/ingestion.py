"""Ingestion agent (pipeline entry step, not a graph-visible "agent" per se).

Accepts a directory OR a .zip archive containing the LMS export files. This is
the layer where "the data is messy" stops being everyone else's problem:

  - missing file            -> recorded in `quality.files_missing`, that
                                dataset is simply empty downstream (agents are
                                written to tolerate empty collections)
  - malformed row            -> quarantined with a reason, the rest of the
                                file still loads
  - dangling foreign key      -> row dropped, counted in `orphaned_fk_count`
  - corrupt / unreadable zip  -> raised as IngestionFatalError; this is the
                                only case that aborts the whole pipeline,
                                because there is nothing safe left to analyze
"""
from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from .models import (
    AttendanceRecord,
    CoinTransaction,
    CuratorContact,
    DataBundle,
    DataQualityReport,
    Group,
    HomeworkAssignment,
    HomeworkSubmission,
    Lesson,
    QuarantinedRow,
    Student,
)

T = TypeVar("T", bound=BaseModel)


class IngestionFatalError(Exception):
    """Raised only when no usable data can be recovered at all."""


def _resolve_source_dir(source: str) -> Path:
    path = Path(source)
    if path.is_dir():
        return path
    if path.is_file() and path.suffix.lower() == ".zip":
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="lms_ingest_"))
            with zipfile.ZipFile(path) as zf:
                zf.extractall(tmp_dir)
        except (zipfile.BadZipFile, OSError) as exc:
            raise IngestionFatalError(f"ZIP fayl o'qib bo'lmadi: {exc}") from exc
        # data may sit at the archive root or one level deep in a single folder
        nested = [p for p in tmp_dir.iterdir() if p.is_dir()]
        if not any(tmp_dir.glob("*.json")) and len(nested) == 1:
            return nested[0]
        return tmp_dir
    raise IngestionFatalError(
        f"Data manba topilmadi yoki noto'g'ri format: {source} "
        "(katalog yoki .zip bo'lishi kerak)"
    )


def _load_json_array(dir_path: Path, filename: str, quality: DataQualityReport) -> list[dict]:
    file_path = dir_path / filename
    if not file_path.exists():
        quality.files_missing.append(filename)
        return []
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        quality.files_missing.append(filename)
        quality.quarantined.append(
            QuarantinedRow(source_file=filename, reason=f"fayl parse xatosi: {exc}", row_index=-1)
        )
        return []
    if not isinstance(raw, list):
        quality.quarantined.append(
            QuarantinedRow(source_file=filename, reason="kutilgan JSON array emas", row_index=-1)
        )
        return []
    quality.files_loaded[filename] = len(raw)
    return raw


def _validate_rows(
    rows: list[dict], model: Type[T], filename: str, quality: DataQualityReport
) -> list[T]:
    out: list[T] = []
    for i, row in enumerate(rows):
        try:
            out.append(model.model_validate(row))
        except ValidationError as exc:
            quality.quarantined.append(
                QuarantinedRow(
                    source_file=filename,
                    reason=exc.errors()[0].get("msg", "validation error"),
                    row_index=i,
                    raw=row.get("id") if isinstance(row, dict) else None,
                )
            )
    return out


def load_data_bundle(source: str) -> DataBundle:
    dir_path = _resolve_source_dir(source)
    quality = DataQualityReport()

    students_raw = _load_json_array(dir_path, "students.json", quality)
    groups_raw = _load_json_array(dir_path, "groups.json", quality)
    lessons_raw = _load_json_array(dir_path, "lessons.json", quality)
    attendance_raw = _load_json_array(dir_path, "attendance.json", quality)
    hw_assign_raw = _load_json_array(dir_path, "homework_assignments.json", quality)
    hw_submit_raw = _load_json_array(dir_path, "homework_submissions.json", quality)
    coins_raw = _load_json_array(dir_path, "coin_transactions.json", quality)
    contacts_raw = _load_json_array(dir_path, "curator_contacts.json", quality)

    if not students_raw and not attendance_raw:
        raise IngestionFatalError(
            "Na students.json, na attendance.json topildi — tahlil qilish uchun "
            "hech qanday ma'lumot yo'q."
        )

    students = {
        s.id: s for s in _validate_rows(students_raw, Student, "students.json", quality)
    }
    groups = {g.id: g for g in _validate_rows(groups_raw, Group, "groups.json", quality)}
    lessons = {l.id: l for l in _validate_rows(lessons_raw, Lesson, "lessons.json", quality)}

    homework_assignments = {
        h.id: h
        for h in _validate_rows(hw_assign_raw, HomeworkAssignment, "homework_assignments.json", quality)
    }

    attendance: list[AttendanceRecord] = []
    for rec in _validate_rows(attendance_raw, AttendanceRecord, "attendance.json", quality):
        if students and rec.student_id not in students:
            quality.orphaned_fk_count += 1
            continue
        attendance.append(rec)

    homework_submissions: list[HomeworkSubmission] = []
    for sub in _validate_rows(hw_submit_raw, HomeworkSubmission, "homework_submissions.json", quality):
        if students and sub.student_id not in students:
            quality.orphaned_fk_count += 1
            continue
        homework_submissions.append(sub)

    coin_transactions: list[CoinTransaction] = []
    for tx in _validate_rows(coins_raw, CoinTransaction, "coin_transactions.json", quality):
        if students and tx.student_id not in students:
            quality.orphaned_fk_count += 1
            continue
        coin_transactions.append(tx)

    curator_contacts = _validate_rows(
        contacts_raw, CuratorContact, "curator_contacts.json", quality
    )

    return DataBundle(
        students=students,
        groups=groups,
        lessons=lessons,
        attendance=attendance,
        homework_assignments=homework_assignments,
        homework_submissions=homework_submissions,
        coin_transactions=coin_transactions,
        curator_contacts=curator_contacts,
        quality=quality,
    )

"""Import a CD-format mock (Section → Part → QuestionGroup → Question) from JSON.

The test content lives in data files (``apps/tests/fixtures/mocks/<name>/``),
not in code:

    python manage.py import_cd_mock record_mock_1 --dry-run
    python manage.py import_cd_mock record_mock_1 --audio-dir /path/to/audio --publish

Idempotent by ``mock_code``: an existing test is rebuilt only with
``--replace`` and only while nobody has attempted it (attempts are never
deleted). Listening audio is optional: ``part-<n>.mp3|wav|m4a|ogg`` files in
``--audio-dir`` are attached to the matching Listening part.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Course
from apps.tests.models import (
    Choice,
    ExamPart,
    ExamSection,
    GapBlank,
    Question,
    QuestionGroup,
    ReadingPassage,
    Test,
)

MOCKS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "mocks"
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHOICE_TYPES = {"MULTIPLE_CHOICE", "MATCHING", "MAP_LABELING", "HEADING_MATCHING", "TRUE_FALSE_NOT_GIVEN"}


class DryRun(Exception):
    """Raised inside the transaction to roll a --dry-run back."""


def load_mock(name: str) -> tuple[dict[str, Any], Path]:
    folder = MOCKS_DIR / name
    path = folder / "mock.json"
    if not path.exists():
        raise CommandError(f"Mock topilmadi: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh), folder


def iter_questions(data: dict[str, Any]):
    """(section_code, question dict, group dict) for every question."""
    for section in data["sections"]:
        for part in section["parts"]:
            for group in part["groups"]:
                for q in group["questions"]:
                    yield section["code"], q, group


def answer_key(data: dict[str, Any]) -> dict[str, dict[int, Any]]:
    """{section_code: {number: answer}} for objective questions (used by tests)."""
    keys: dict[str, dict[int, Any]] = {}
    for code, q, _group in iter_questions(data):
        if "answer" in q:
            keys.setdefault(code, {})[q["number"]] = q["answer"]
    return keys


class Command(BaseCommand):
    help = "CD-format mock testni JSON fayldan bazaga import qilish."

    def add_arguments(self, parser):
        parser.add_argument("mock", help="apps/tests/fixtures/mocks ichidagi papka nomi, masalan record_mock_1")
        parser.add_argument("--dry-run", action="store_true", help="Faqat tekshirish, bazaga yozmaydi.")
        parser.add_argument("--replace", action="store_true", help="Urinishlari yo'q mavjud testni qayta qurish.")
        parser.add_argument("--publish", action="store_true", help="Testni e'lon qilingan holatda yaratish.")
        parser.add_argument("--audio-dir", help="Listening audio fayllari papkasi (part-1.mp3 ... part-6.mp3).")
        parser.add_argument("--course-slug", default="cefr-multilevel-record-course")
        parser.add_argument("--teacher-email", help="Kurs yo'q bo'lsa, shu ustoz nomidan yaratiladi.")

    def handle(self, *args, **opts):
        data, folder = load_mock(opts["mock"])
        audio_dir = Path(opts["audio_dir"]) if opts.get("audio_dir") else None
        if audio_dir and not audio_dir.is_dir():
            raise CommandError(f"Audio papka topilmadi: {audio_dir}")
        try:
            with transaction.atomic():
                test, stats = self._import(data, folder, audio_dir, opts)
                if opts["dry_run"]:
                    raise DryRun
        except DryRun:
            self.stdout.write(self.style.WARNING("Dry-run: hech narsa yozilmadi."))
        self.stdout.write(
            f"{data['mock_code']}: " + ", ".join(f"{k}={v}" for k, v in stats.items())
        )
        if not opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Test #{test.id} tayyor: {test.title}"))

    # ------------------------------------------------------------------
    def _import(self, data, folder: Path, audio_dir: Path | None, opts) -> tuple[Test, dict[str, int]]:
        existing = Test.objects.filter(mock_code=data["mock_code"]).first()
        if existing:
            if not opts["replace"]:
                raise CommandError(f"{data['mock_code']} allaqachon bor (test #{existing.id}). --replace bilan qayta quring.")
            if existing.attempts.exists():
                raise CommandError(f"Test #{existing.id} da urinishlar bor — o'chirilmaydi. Yangi mock_code bilan import qiling.")
            existing.delete()

        test = Test.objects.create(
            course=self._course(opts),
            mock_code=data["mock_code"],
            title=data["title"],
            description=data.get("description", ""),
            subject=data["subject"],
            exam_type=data["exam_type"],
            time_limit_minutes=sum(s.get("minutes", 0) for s in data["sections"]),
            max_attempts=0,
            status=Test.Status.PUBLISHED if opts["publish"] else Test.Status.DRAFT,
        )
        stats = {"sections": 0, "parts": 0, "groups": 0, "questions": 0, "audio": 0, "images": 0}
        for s_order, sdata in enumerate(data["sections"], start=1):
            section = ExamSection.objects.create(
                test=test, code=sdata["code"], name=sdata["name"], order=s_order,
                duration_minutes=sdata.get("minutes", 0),
            )
            stats["sections"] += 1
            for p_order, pdata in enumerate(sdata["parts"], start=1):
                part = ExamPart.objects.create(
                    section=section, number=pdata["number"], title=pdata.get("title", ""),
                    instructions=pdata.get("instructions", ""), order=p_order,
                )
                stats["parts"] += 1
                if audio_dir and sdata["code"] == "LISTENING" and self._attach_audio(part, audio_dir, opts["dry_run"]):
                    stats["audio"] += 1
                part_passage = self._passage(test, section, pdata.get("passage"), p_order * 100)
                for g_order, gdata in enumerate(pdata["groups"], start=1):
                    group = QuestionGroup.objects.create(
                        part=part, title=gdata.get("title", ""), instructions=gdata.get("instructions", ""),
                        answer_rule=gdata.get("answer_rule", ""),
                        passage=self._passage(test, section, gdata.get("passage"), p_order * 100 + g_order)
                        or part_passage,
                        options_label=gdata.get("options_label", ""),
                        each_option_once=bool(gdata.get("each_option_once")), order=g_order,
                    )
                    stats["groups"] += 1
                    if gdata.get("image"):
                        image_path = folder / gdata["image"]
                        if not image_path.exists():
                            raise CommandError(f"Rasm topilmadi: {image_path}")
                        if not opts["dry_run"]:  # rollback can't undo files on disk
                            with image_path.open("rb") as fh:
                                group.image.save(f"{data['mock_code'].lower()}-{image_path.name}", File(fh), save=True)
                        stats["images"] += 1
                    for qdata in gdata["questions"]:
                        self._question(test, section, group, gdata, qdata)
                        stats["questions"] += 1
        return test, stats

    def _course(self, opts) -> Course:
        course = Course.objects.filter(slug=opts["course_slug"]).first()
        if course:
            return course
        User = get_user_model()
        teacher = (
            User.objects.filter(email=opts["teacher_email"]).first()
            if opts.get("teacher_email")
            else User.objects.filter(is_superuser=True).order_by("id").first()
        )
        if not teacher:
            raise CommandError("Kurs uchun ustoz topilmadi: --teacher-email bering.")
        return Course.objects.create(
            slug=opts["course_slug"], title="CEFR Multi-level mock testlari", teacher=teacher, status="published"
        )

    @staticmethod
    def _passage(test, section, pdata, order) -> ReadingPassage | None:
        if not pdata:
            return None
        return ReadingPassage.objects.create(
            test=test, section=section, title=pdata.get("title", ""), content=pdata["content"], order=order
        )

    @staticmethod
    def _attach_audio(part: ExamPart, audio_dir: Path, dry_run: bool) -> bool:
        for ext in AUDIO_EXTS:
            path = audio_dir / f"part-{part.number}{ext}"
            if path.exists():
                if dry_run:
                    return True
                with path.open("rb") as fh:
                    part.audio.save(f"{part.section.test.mock_code.lower()}-listening-{path.name}", File(fh), save=True)
                return True
        return False

    @staticmethod
    def _question(test, section, group, gdata, qdata) -> Question:
        qtype = qdata["type"]
        question = Question.objects.create(
            test=test, section=section, group=group, reading_passage=group.passage,
            text=qdata["text"], question_type=qtype, points=0 if qtype == "SPEAKING_PROMPT" else 1,
            position=section.order * 1000 + qdata["number"],
            config={"number": qdata["number"], **qdata.get("config", {})},
        )
        if qtype in CHOICE_TYPES:
            options = qdata.get("options") or gdata.get("options") or []
            answer = qdata["answer"]
            if len(answer) == 1 and answer in LETTERS:
                correct_index = LETTERS.index(answer)
            else:  # True / False / No Information
                correct_index = options.index(answer)
            if not 0 <= correct_index < len(options):
                raise CommandError(f"{section.code} {qdata['number']}: kalit {answer!r} variantlarda yo'q")
            Choice.objects.bulk_create(
                Choice(question=question, text=text, is_correct=i == correct_index, position=i + 1)
                for i, text in enumerate(options)
            )
        elif qtype == "INLINE_GAP_FILL":
            GapBlank.objects.bulk_create(
                GapBlank(question=question, position=0, answer_text=alt) for alt in qdata["answer"]
            )
        return question

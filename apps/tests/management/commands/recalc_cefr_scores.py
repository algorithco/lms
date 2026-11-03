"""Recalculate CEFR Multi-level attempts with the estimated 0–75 scale.

Before this scale existed, Multi-level attempts were scored as one pool of
answers stretched to a 40-question IELTS table (band_score) and a 75-point
CEFR table with the wrong B1 threshold. This command rebuilds
``section_scores`` / ``cefr_level`` and clears ``band_score`` from the
answers already stored — it never re-grades answers or touches timestamps.

    python manage.py recalc_cefr_scores --dry-run      # report only
    python manage.py recalc_cefr_scores                # write changes
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tests import cefr_multilevel as cm
from apps.tests.models import ExamWrittenBridge, Question, StudentAnswer, Test, TestAttempt
from apps.tests.scoring import QuestionScore
from apps.tests.services import ExamBridgeService

FINISHED = (
    TestAttempt.Status.COMPLETED,
    TestAttempt.Status.TIMEOUT,
    TestAttempt.Status.PENDING_GRADING,
)


def rebuild_question_scores(attempt: TestAttempt) -> list[QuestionScore]:
    """QuestionScores from stored answers (is_correct as graded at submit)."""
    questions = Question.objects.filter(test=attempt.test).select_related("section")
    answers = {a.question_id: a for a in StudentAnswer.objects.filter(attempt=attempt)}
    bridges = {
        b.question_id: b
        for b in ExamWrittenBridge.objects.select_related("essay_submission").filter(attempt=attempt)
    }
    scores = []
    for q in questions:
        code = (q.section.code if q.section_id else "").upper()
        qmax = Decimal(str(q.points or 1))
        ans = answers.get(q.id)
        base = {"question_id": q.id, "maximum": qmax, "section_code": code, "section_id": q.section_id}
        if q.question_type == Question.QuestionType.WRITTEN:
            if ans is None or not (ans.written_text or "").strip():
                scores.append(QuestionScore(**base, is_correct=False, answered=False, kind="written"))
                continue
            bridge = bridges.get(q.id)
            earned = ExamBridgeService.written_points(q, bridge.essay_submission if bridge else None)
            scores.append(
                QuestionScore(
                    **base,
                    earned=earned or Decimal("0"),
                    is_correct=None if earned is None else earned >= qmax,
                    kind="written",
                )
            )
            continue
        if ans is None:
            scores.append(QuestionScore(**base, is_correct=False, answered=False))
            continue
        scores.append(QuestionScore(**base, earned=qmax if ans.is_correct else Decimal("0"), is_correct=bool(ans.is_correct)))
    return scores


class Command(BaseCommand):
    help = "CEFR Multi-level urinishlarini taxminiy 0–75 shkala bo'yicha qayta hisoblash."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Faqat hisobot, bazaga yozmaydi.")
        parser.add_argument("--test-id", type=int, help="Faqat shu test.")

    def handle(self, *args, dry_run: bool = False, test_id: int | None = None, **options):
        attempts = TestAttempt.objects.filter(
            test__exam_type=Test.ExamType.CEFR_MULTILEVEL, status__in=FINISHED
        ).select_related("test")
        if test_id:
            attempts = attempts.filter(test_id=test_id)

        changed = 0
        total = attempts.count()
        for attempt in attempts.order_by("id"):
            names = dict(
                attempt.test.sections.values_list("code", "name")
            )
            names = {k.upper(): v for k, v in names.items()}
            section_map = cm.score_sections(rebuild_question_scores(attempt), names)
            overall = cm.summarize(section_map)["overall"]
            new_level = overall["level"] if overall else ""
            new_sections = cm.to_json(section_map)
            if (
                attempt.band_score is None
                and attempt.cefr_level == new_level
                and attempt.section_scores == new_sections
            ):
                continue
            changed += 1
            per_section = ", ".join(
                f"{code[:1]}={s['score'] if s['score'] is not None else s['status']}"
                for code, s in new_sections.items()
            )
            new_text = f"{new_level} ({overall['score']})" if overall else "umumiy yo'q"
            self.stdout.write(
                f"#{attempt.id} test={attempt.test_id} raw={attempt.raw_score}: "
                f"band {attempt.band_score} / {attempt.cefr_level or '-'} -> {new_text} [{per_section}]"
            )
            if not dry_run:
                with transaction.atomic():
                    TestAttempt.objects.filter(id=attempt.id).update(
                        band_score=None, cefr_level=new_level, section_scores=new_sections
                    )

        verb = "o'zgaradi" if dry_run else "yangilandi"
        self.stdout.write(
            self.style.SUCCESS(
                f"CEFR Multi-level urinishlar: {total}, {verb}: {changed}"
                + (" (dry-run, bazaga yozilmadi)" if dry_run else "")
            )
        )
        other = TestAttempt.objects.filter(
            test__subject="english", status__in=FINISHED
        ).exclude(test__exam_type=Test.ExamType.CEFR_MULTILEVEL).count()
        self.stdout.write(f"Boshqa ingliz tili urinishlari (IELTS va h.k., tegilmadi): {other}")

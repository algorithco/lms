# Data cleanup before uniq_essay_active_draft (one active DRAFT per
# student+topic). Keeps the most advanced draft per group, deletes the rest.
#
# Deterministic keep rule per (student, topic):
#   1. password_verified_at NOT NULL first (started timer wins),
#   2. then longest essay_text,
#   3. then latest updated_at, then max id.
# Only DRAFT rows with a non-null topic are touched (the constraint scope).
from django.db import migrations
from django.db.models import Count


def dedupe_active_drafts(apps, schema_editor):
    EssaySubmission = apps.get_model("essays", "EssaySubmission")
    dup_groups = (
        EssaySubmission.objects.filter(status="draft", topic__isnull=False)
        .values("student_id", "topic_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    removed = 0
    for group in dup_groups.iterator():
        rows = list(
            EssaySubmission.objects.filter(
                status="draft",
                student_id=group["student_id"],
                topic_id=group["topic_id"],
            ).order_by("id")
        )
        if len(rows) < 2:
            continue

        def rank(row):
            text = row.essay_text or ""
            return (
                1 if row.password_verified_at else 0,
                len(text),
                row.updated_at,
                row.id,
            )

        keep = max(rows, key=rank)
        drop_ids = [r.id for r in rows if r.id != keep.id]
        # Criteria/criterion rows are never attached to DRAFTs (created only
        # on grading), reviews target graded rows — safe to delete drafts.
        EssaySubmission.objects.filter(id__in=drop_ids).delete()
        removed += len(drop_ids)
    if removed:
        print(f"dedupe_active_drafts: removed {removed} duplicate DRAFT rows")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("essays", "0011_essaysubmission_improved_at_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_active_drafts, noop),
    ]

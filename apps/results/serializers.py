"""
Results serializers — Result list, detail, and analytics.

Read-only serializers for the analytics dashboard and student result views.
"""

from __future__ import annotations

from typing import Any

from urllib.parse import quote

from rest_framework import serializers

from .models import Certificate, Result


# ---------------------------------------------------------------------------
# Result Serializers
# ---------------------------------------------------------------------------


class ResultListSerializer(serializers.ModelSerializer):
    """
    Natija list serializer — tez yuklash uchun lightweight.
    Dashboard'da ishlatiladi.
    """

    attempt_id = serializers.IntegerField(
        source="attempt.id", read_only=True, default=None
    )
    test_title = serializers.CharField(source="test.title", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    test_subject = serializers.CharField(source="test.subject", read_only=True, default="uzbek")
    exam_type = serializers.CharField(source="test.exam_type", read_only=True, default="general")
    student_name = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    bmb_grade = serializers.CharField(read_only=True)
    bmb_info = serializers.DictField(read_only=True)

    class Meta:
        model = Result
        fields = [
            "id",
            "attempt_id",
            "test",
            "test_title",
            "test_subject",
            "exam_type",
            "course",
            "course_title",
            "student_name",
            "score",
            "max_score",
            "percentage",
            "is_passed",
            "time_taken_seconds",
            "calculated_at",
            "grading_status",
            "certificate_status",
            "bmb_grade",
            "bmb_info",
            "rasch_score",
            "max_rasch_score",
            "rasch_grade",
            "rasch_explanation",
        ]

    def get_certificate_status(self, obj: Result) -> str:
        from apps.certificates.services.generation import (
            certificate_status,
            resolve_profile,
        )

        is_milliy = getattr(obj, "is_milliy", None)
        profile = None
        if is_milliy:
            profile = getattr(obj.test, "scoring_profile", None)
            if profile is None:
                # Resolve the shared fallback once per page, not once per row.
                profile = self.context.get("default_scoring_profile")
                if profile is None:
                    profile = resolve_profile(obj.test)
                    self.context["default_scoring_profile"] = profile
        return certificate_status(obj, is_milliy=is_milliy, profile=profile)

    def get_student_name(self, obj: Result) -> str:
        return obj.student.get_full_name()


class ResultDetailSerializer(serializers.ModelSerializer):
    """
    Natija detail serializer — to'liq tafsilotlar.
    Qaysi savollarda xato qilganini ko'rsatadi.
    """

    attempt_id = serializers.IntegerField(
        source="attempt.id", read_only=True, default=None
    )
    test_title = serializers.CharField(source="test.title", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.SerializerMethodField()
    question_details = serializers.SerializerMethodField()
    certificate_info = serializers.SerializerMethodField()
    section_scores = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    bmb_grade = serializers.CharField(read_only=True)
    bmb_info = serializers.DictField(read_only=True)
    test_subject = serializers.CharField(source="test.subject", read_only=True, default="uzbek")
    exam_type = serializers.CharField(source="test.exam_type", read_only=True, default="general")
    cefr_summary = serializers.SerializerMethodField()
    trial_part = serializers.SerializerMethodField()
    show_estimate_notice = serializers.SerializerMethodField()
    subject_analysis = serializers.SerializerMethodField()
    branch_info = serializers.SerializerMethodField()
    share_data = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            "id",
            "attempt_id",
            "show_estimate_notice",
            "test",
            "test_title",
            "test_subject",
            "exam_type",
            "cefr_summary",
            "trial_part",
            "course",
            "course_title",
            "student_name",
            "total_questions",
            "correct_answers",
            "wrong_answers",
            "unanswered",
            "score",
            "max_score",
            "percentage",
            "is_passed",
            "time_taken_seconds",
            "grading_status",
            "objective_score",
            "writing_score",
            "scoring_version",
            "rubric_version",
            "question_details",
            "section_scores",
            "certificate_status",
            "certificate_info",
            "calculated_at",
            "bmb_grade",
            "bmb_info",
            "subject_analysis",
            "branch_info",
            "share_data",
        ]

    def get_student_name(self, obj: Result) -> str:
        return obj.student.get_full_name()

    def get_section_scores(self, obj: Result) -> list[dict[str, Any]]:
        """Bo'lim kesimidagi ballar (obyektiv + yozma)."""
        return [
            {
                "section_code": s.section_code,
                "section_name": s.section_name,
                "earned": str(s.earned),
                "maximum": str(s.maximum),
                "weight": str(s.weight),
            }
            for s in obj.section_scores.order_by("id")
        ]

    def get_cefr_summary(self, obj: Result) -> dict[str, Any] | None:
        """CEFR Multi-level 0–75 estimate — same source as certificate-card."""
        if obj.test.exam_type != "cefr_multilevel" or not obj.attempt_id:
            return None
        if obj.attempt.trial_part_id:
            return None  # one part is not a section score
        from apps.tests import cefr_multilevel

        return cefr_multilevel.to_json(
            cefr_multilevel.summarize(obj.attempt.section_scores or {})
        )

    def get_show_estimate_notice(self, obj: Result) -> bool:
        from django.conf import settings

        return bool(getattr(settings, "SHOW_ESTIMATE_NOTICE", False))

    def get_trial_part(self, obj: Result) -> dict[str, Any] | None:
        part = obj.attempt.trial_part if obj.attempt_id and obj.attempt.trial_part_id else None
        if part is None:
            return None
        return {"section_code": part.section.code, "section_name": part.section.name, "part": part.number}

    def get_certificate_status(self, obj: Result) -> str:
        """Canonical eligibility state (eligible only with verified rules)."""
        from apps.certificates.services.generation import certificate_status

        return certificate_status(obj)

    def get_question_details(self, obj: Result) -> list[dict[str, Any]]:
        from apps.tests import question_review
        from apps.tests.ai_tutor import _detect_question_topic
        """
        Har bir savol uchun batafsil ma'lumot:
        - Savol matni
        - Student tanlagan variantlar
        - To'g'ri javoblar
        - Ball olinganmi?
        """
        attempt = obj.attempt
        request = self.context.get("request")
        user = getattr(request, "user", None)
        reveal_answers = bool(obj.test.show_results_immediately)
        if not reveal_answers and user:
            from apps.accounts.access import is_platform_admin

            reveal_answers = is_platform_admin(user) or (
                getattr(user, "role", None) == "teacher"
                and obj.course.teacher_id == user.pk
            )

        # Barcha savollarni olish
        questions = (
            obj.test.questions.select_related(
                "section",
                "test",
                "group",
                "group__part",
                "group__passage",
                "reading_passage",
            )
            .prefetch_related(
                "choices",
                "student_answers",
                "student_answers__selected_choices",
                "gap_blanks",
                "matching_prompts__correct_pair",
                "matching_prompts__correct_pair__correct_option",
                "matching_options",
            )
            .order_by("position")
        )

        # Student javoblari xaritasi
        answers_map: dict[int, Any] = {}
        for answer in attempt.answers.select_related("question").prefetch_related(
            "selected_choices",
            "gap_responses",
            "matching_responses",
        ):
            answers_map[answer.question_id] = answer

        from apps.tests.numbering import number_map

        if attempt.trial_part_id:
            questions = questions.filter(group__part_id=attempt.trial_part_id)
        questions = list(questions)
        numbers = number_map(obj.test, questions)

        result = []
        for q in questions:
            answer = answers_map.get(q.id)

            # Respect the instructor's answer-release setting. Students and
            # parents must not infer answer keys or per-question correctness
            # while feedback is withheld; authorized course staff can review.
            correct_choices = (
                list(q.choices.filter(is_correct=True).values("id", "text"))
                if reveal_answers
                else []
            )

            # Student tanlangan
            selected = []
            is_correct = None
            gap_review: list[dict[str, Any]] = []
            matching_review: list[dict[str, Any]] = []
            written_review: dict[str, Any] | None = None
            student_text_answer = ""
            correct_text_answer = ""

            accepted_keys: list[str] = []
            if reveal_answers:
                accepted_keys = [k.strip() for k in q.correct_text.split("|") if k.strip()]
                if not accepted_keys and q.question_type != "gap_fill":
                    # CD gap-fills keep their key in the blanks, not in correct_text.
                    accepted_keys = [
                        b.answer_text.strip() for b in q.gap_blanks.all() if (b.answer_text or "").strip()
                    ]
            if accepted_keys:
                correct_text_answer = accepted_keys[0]
                if not correct_choices:
                    correct_choices = [{"id": 0, "text": correct_text_answer}]

            if answer:
                student_text_answer = (answer.text_answer or "").strip()
                selected = list(answer.selected_choices.values("id", "text"))
                if not selected and student_text_answer:
                    selected = [{"id": 0, "text": student_text_answer}]

                is_correct = answer.is_correct if reveal_answers else None
                if q.question_type == "matching":
                    option_text = {o.id: o.text for o in q.matching_options.all()}
                    for prompt in q.matching_prompts.all().order_by("position"):
                        pair = getattr(prompt, "correct_pair", None)
                        correct_id = pair.correct_option_id if pair else None
                        chosen = None
                        try:
                            mr = answer.matching_responses.get(prompt=prompt)
                            chosen = mr.selected_option_id
                        except Exception:
                            chosen = None
                        matching_review.append(
                            {
                                "prompt_id": prompt.id,
                                "prompt_text": prompt.text,
                                "selected_option_id": chosen,
                                "selected_text": option_text.get(chosen, "")
                                if chosen
                                else "",
                                "correct_option_id": correct_id
                                if reveal_answers
                                else None,
                                "correct_text": (
                                    option_text.get(correct_id, "")
                                    if reveal_answers and correct_id
                                    else ""
                                ),
                            }
                        )
                elif q.question_type == "gap_fill":
                    accepted: dict[int, list[str]] = {}
                    for blank in q.gap_blanks.all():
                        accepted.setdefault(blank.position, []).append(
                            blank.answer_text
                        )
                    given = {
                        gr.blank_position: gr.response_text
                        for gr in answer.gap_responses.all()
                    }
                    for pos in sorted(accepted):
                        gap_review.append(
                            {
                                "position": pos,
                                "response": given.get(pos, ""),
                                "accepted": accepted[pos] if reveal_answers else [],
                            }
                        )
                elif q.question_type == "written":
                    written_review = {
                        "text": answer.written_text,
                        "word_count": answer.written_word_count,
                    }

            sec_code = getattr(q.section, "code", "") if q.section else ""
            sec_name = getattr(q.section, "name", "") if q.section else ""

            written = q.question_type in ("written", "SPEAKING_PROMPT")
            has_answer = bool(
                answer
                and (
                    selected
                    or student_text_answer
                    or (written and (answer.written_text or "").strip())
                    or (gap_review and any(g["response"] for g in gap_review))
                    or (matching_review and any(m["selected_option_id"] for m in matching_review))
                )
            )
            status = question_review.answer_status(
                revealed=reveal_answers,
                has_answer=has_answer,
                is_correct=is_correct,
                written=written,
            )
            group = q.group
            hint = (
                question_review.build_hint(
                    question_type=q.question_type,
                    status=status,
                    given_text=student_text_answer,
                    accepted_keys=accepted_keys,
                    answer_rule=getattr(group, "answer_rule", "") or "",
                    source_text=question_review.source_text_for(q),
                )
                if reveal_answers
                else None
            )
            show_explanation = reveal_answers and status in ("wrong", "blank")
            for c in selected:
                c["letter"] = question_review.choice_letter(q, c["id"]) if c.get("id") else ""
            for c in correct_choices:
                c["letter"] = question_review.choice_letter(q, c["id"]) if c.get("id") else ""
            q_topic = _detect_question_topic(
                q.text,
                q.explanation or "",
                subject=getattr(obj.test, "subject", "uzbek"),
                section_code=sec_code,
                section_name=sec_name,
            )
            earned_points = 0.0
            qmax = float(q.points or 1.0)
            if is_correct:
                earned_points = qmax
            elif q.question_type == "dual_open_calc" and student_text_answer:
                corr_parts = [p.strip() for p in (q.correct_text or "").split("|", 1)]
                stud_parts = [p.strip() for p in student_text_answer.split("|", 1)]
                a_ok = bool(len(stud_parts) > 0 and len(corr_parts) > 0 and stud_parts[0].replace(",", ".").lower() == corr_parts[0].replace(",", ".").lower())
                b_ok = bool(len(stud_parts) > 1 and len(corr_parts) > 1 and stud_parts[1].replace(",", ".").lower() == corr_parts[1].replace(",", ".").lower())
                if a_ok:
                    earned_points += qmax / 2.0
                if b_ok:
                    earned_points += qmax / 2.0
            elif q.question_type == "matching_matrix" and student_text_answer:
                corr_items = [it.strip().lower() for it in (q.correct_text or "").replace("|", ",").split(",") if it.strip()]
                stud_items = [it.strip().lower() for it in student_text_answer.replace("|", ",").split(",") if it.strip()]
                corr_dict = dict(it.split("-", 1) if "-" in it else (str(idx+1), it) for idx, it in enumerate(corr_items))
                stud_dict = dict(it.split("-", 1) if "-" in it else (str(idx+1), it) for idx, it in enumerate(stud_items))
                if corr_dict:
                    matched = sum(1 for k, v in corr_dict.items() if stud_dict.get(k) == v)
                    earned_points = (matched / len(corr_dict)) * qmax

            result.append(
                {
                    "question_id": q.id,
                    # Number shown to students (never the internal position).
                    "number": numbers[q.id].number if q.id in numbers else None,
                    "number_key": numbers[q.id].key if q.id in numbers else "",
                    "section_name": sec_name,
                    "section_code": sec_code,
                    "topic": q_topic,
                    "question_text": q.text,
                    "question_type": q.question_type,
                    "points": q.points,
                    "earned_points": round(earned_points, 2),
                    "section_id": q.section_id,
                    "current_rasch_weight": float(q.current_rasch_weight or 2.0),
                    "difficulty_logit": float(q.difficulty_logit or 0.0),
                    "total_attempts": int(q.total_attempts or 0),
                    "correct_attempts": int(q.correct_attempts or 0),
                    "correct_choices": correct_choices,
                    "selected_choices": selected,
                    "student_answer_text": student_text_answer,
                    "correct_text": correct_text_answer,
                    "gap_review": gap_review,
                    "matching_review": matching_review,
                    "written_review": written_review,
                    "is_correct": is_correct,
                    "status": status,
                    "hint": hint,
                    "explanation": q.explanation if show_explanation else "",
                    "evidence": q.evidence if show_explanation else "",
                    "explanation_status": q.explanation_status if show_explanation and q.explanation else "",
                    "part_id": group.part_id if group else None,
                    "part_number": group.part.number if group else "",
                    "part_title": group.part.title if group else "",
                    "group_title": group.title if group else "",
                    "can_ai_explain": bool(
                        reveal_answers
                        and status in ("wrong", "blank")
                        and (
                            question_review.source_text_for(q)
                            or question_review.is_self_contained(q)
                        )
                    ),
                }
            )

        return result

    def get_certificate_info(self, obj: Result) -> dict[str, Any] | None:
        """Agar sertifikat bo'lsa, uning ma'lumotlarini qaytarish."""
        try:
            cert = obj.certificate
            return {
                "certificate_number": cert.certificate_number,
                "status": cert.status,
                "issued_at": cert.issued_at,
                "file_url": cert.file.url if cert.file else None,
            }
        except Certificate.DoesNotExist:
            return None



    def get_branch_info(self, obj: Result) -> dict[str, Any]:
        student = obj.student
        branch = getattr(student, "branch", None)
        group_name = None
        try:
            if not branch:
                group = student.student_groups.filter(branch__isnull=False).first()
                if group:
                    branch = group.branch
                    group_name = group.name
            else:
                group = student.student_groups.first()
                if group:
                    group_name = group.name
        except Exception:
            pass

        return {
            "branch_id": branch.id if branch else None,
            "branch_name": branch.name if branch else "Grand Education Bosh Filiali",
            "branch_code": getattr(branch, "branch_code", "SAM-01") if branch else "SAM-01",
            "region": getattr(branch, "region", "Samarqand viloyati") if branch else "Samarqand viloyati",
            "group_name": group_name,
        }

    def get_share_data(self, obj: Result) -> dict[str, Any]:
        student = obj.student
        ref_code = getattr(student, "referral_code", "") or "GRAND"
        subject = getattr(obj.test, "subject", "uzbek")
        subj_names = {
            "biology": "Biologiya",
            "chemistry": "Kimyo",
            "law": "Huquqshunoslik",
            "uzbek": "Ona tili va Adabiyot",
            "english": "Ingliz tili",
        }
        subj_title = subj_names.get(subject, "Fan")
        score_val = f"{float(obj.score):g}" if obj.score is not None else "0"
        grade_val = obj.bmb_grade or (f"{round(float(obj.percentage or 0))}%")
        branch_name = getattr(getattr(student, "branch", None), "name", "Grand Education")

        text = f"Men Grand Education'da {subj_title} fanidan {score_val} ball ({grade_val}) oldim! Sen ham o'z bilimingni sinab ko'r:"
        ref_url = f"https://grandec.uz/join?ref={ref_code}"
        tg_url = f"https://t.me/share/url?url={quote(ref_url)}&text={quote(text)}"

        return {
            "subject": subj_title,
            "score": score_val,
            "max_score": f"{float(obj.max_score):g}" if obj.max_score else "100",
            "percentage": round(float(obj.percentage or 0), 1),
            "grade": grade_val,
            "branch_name": branch_name,
            "referral_code": ref_code,
            "referral_url": ref_url,
            "share_text": text,
            "telegram_share_url": tg_url,
            "pdf_download_url": f"/api/results/{obj.id}/pdf/",
        }

    def get_subject_analysis(self, obj: Result) -> dict[str, Any] | None:
        subject = getattr(obj.test, "subject", "uzbek")
        attempt = getattr(obj, "attempt", None)
        if not attempt:
            return None

        answers_map = {ans.question_id: ans for ans in attempt.answers.all()}
        questions = list(obj.test.questions.all().order_by("position"))

        pct = float(obj.percentage or 0)
        from apps.tests.bmb_grading import calculate_bmb_grade
        bmb_calc = calculate_bmb_grade(pct)

        if subject in ("biology", "chemistry"):
            closed_earned = 0.0
            closed_max = 0.0
            closed_correct = 0
            closed_total = 0

            matching_earned = 0.0
            matching_max = 0.0
            matching_correct = 0
            matching_total = 0

            open_earned = 0.0
            open_max = 0.0
            open_correct = 0
            open_total = 0

            for idx, q in enumerate(questions, 1):
                ans = answers_map.get(q.id)
                qmax = float(q.points or 1.0)
                qtype = str(q.question_type or "").lower()
                is_corr = bool(ans and ans.is_correct)

                if qtype in ("matching_matrix", "matching") or (33 <= idx <= 35 and qtype != "dual_open_calc"):
                    matching_total += 1
                    matching_max += qmax
                    if is_corr:
                        matching_correct += 1
                        matching_earned += qmax
                    elif ans and ans.text_answer:
                        corr_items = [it.strip().lower() for it in (q.correct_text or "").replace("|", ",").split(",") if it.strip()]
                        stud_items = [it.strip().lower() for it in ans.text_answer.replace("|", ",").split(",") if it.strip()]
                        corr_dict = dict(it.split("-", 1) if "-" in it else (str(i+1), it) for i, it in enumerate(corr_items))
                        stud_dict = dict(it.split("-", 1) if "-" in it else (str(i+1), it) for i, it in enumerate(stud_items))
                        if corr_dict:
                            matched = sum(1 for k, v in corr_dict.items() if stud_dict.get(k) == v)
                            part_e = (matched / len(corr_dict)) * qmax
                            matching_earned += part_e
                            if matched == len(corr_dict):
                                matching_correct += 1
                elif qtype in ("dual_open_calc", "text", "gap_fill") or (idx >= 36 and qtype != "single"):
                    open_total += 1
                    open_max += qmax
                    if is_corr:
                        open_correct += 1
                        open_earned += qmax
                    elif ans and ans.text_answer:
                        corr_parts = [p.strip() for p in (q.correct_text or "").split("|", 1)]
                        stud_parts = [p.strip() for p in ans.text_answer.split("|", 1)]
                        a_ok = bool(len(stud_parts) > 0 and len(corr_parts) > 0 and stud_parts[0].replace(",", ".").lower() == corr_parts[0].replace(",", ".").lower())
                        b_ok = bool(len(stud_parts) > 1 and len(corr_parts) > 1 and stud_parts[1].replace(",", ".").lower() == corr_parts[1].replace(",", ".").lower())
                        if a_ok:
                            open_earned += qmax / 2.0
                        if b_ok:
                            open_earned += qmax / 2.0
                        if a_ok and b_ok:
                            open_correct += 1
                else:
                    closed_total += 1
                    closed_max += qmax
                    if is_corr:
                        closed_correct += 1
                        closed_earned += qmax

            return {
                "kind": "science_bmb",
                "subject": subject,
                "subject_title": "Biologiya" if subject == "biology" else "Kimyo",
                "closed_questions": {
                    "label": "1–32 Yopiq testlar",
                    "correct_count": closed_correct,
                    "total_count": closed_total,
                    "earned_score": round(closed_earned, 1),
                    "max_score": round(closed_max, 1),
                    "percentage": round((closed_earned / closed_max * 100), 1) if closed_max else 0.0,
                },
                "matching_questions": {
                    "label": "33–35 Moslashtirish matritsasi",
                    "correct_count": matching_correct,
                    "total_count": matching_total,
                    "earned_score": round(matching_earned, 1),
                    "max_score": round(matching_max, 1),
                    "percentage": round((matching_earned / matching_max * 100), 1) if matching_max else 0.0,
                },
                "open_calc_questions": {
                    "label": "36–45 Ikki qismli ochiq masalalar (a/b)",
                    "correct_count": open_correct,
                    "total_count": open_total,
                    "earned_score": round(open_earned, 1),
                    "max_score": round(open_max, 1),
                    "percentage": round((open_earned / open_max * 100), 1) if open_max else 0.0,
                },
                "bmb_grade": bmb_calc["grade"],
                "bmb_description": bmb_calc.get("title", ""),
                "bmb_color": bmb_calc["color"],
                "is_passed": bmb_calc["is_passed"],
            }

        elif subject == "law":
            from apps.tests.ai_tutor import _detect_question_topic
            theory_correct = 0
            theory_total = 0
            theory_earned = 0.0
            theory_max = 0.0

            case_correct = 0
            case_total = 0
            case_earned = 0.0
            case_max = 0.0

            mistakes_by_topic: dict[str, int] = {}

            for idx, q in enumerate(questions, 1):
                ans = answers_map.get(q.id)
                qmax = float(q.points or 1.0)
                qtype = str(q.question_type or "").lower()
                is_corr = bool(ans and ans.is_correct)

                is_case = bool(qtype in ("legal_case_study", "case_study") or idx >= 36)
                if is_case:
                    case_total += 1
                    case_max += qmax
                    if is_corr:
                        case_correct += 1
                        case_earned += qmax
                else:
                    theory_total += 1
                    theory_max += qmax
                    if is_corr:
                        theory_correct += 1
                        theory_earned += qmax

                if not is_corr:
                    t_name = _detect_question_topic(
                        q.text,
                        q.explanation or "",
                        subject="law",
                        section_code=getattr(q.section, "code", "") if q.section else "",
                        section_name=getattr(q.section, "name", "") if q.section else "",
                    )
                    mistakes_by_topic[t_name] = mistakes_by_topic.get(t_name, 0) + 1

            mistake_list = [
                {"topic": k, "count": v}
                for k, v in sorted(mistakes_by_topic.items(), key=lambda x: x[1], reverse=True)
            ]

            return {
                "kind": "law_jurisprudence",
                "subject": "law",
                "subject_title": "Huquqshunoslik",
                "theory_questions": {
                    "label": "Nazariy savollar (1–35)",
                    "correct_count": theory_correct,
                    "total_count": theory_total,
                    "earned_score": round(theory_earned, 1),
                    "max_score": round(theory_max, 1),
                    "percentage": round((theory_earned / theory_max * 100), 1) if theory_max else 0.0,
                },
                "case_study_questions": {
                    "label": "Huquqiy kazus va amaliy situatsion tahlil (36–45)",
                    "correct_count": case_correct,
                    "total_count": case_total,
                    "earned_score": round(case_earned, 1),
                    "max_score": round(case_max, 1),
                    "percentage": round((case_earned / case_max * 100), 1) if case_max else 0.0,
                },
                "mistake_topics": mistake_list,
                "bmb_grade": bmb_calc["grade"],
                "bmb_description": bmb_calc.get("title", ""),
                "bmb_color": bmb_calc["color"],
                "is_passed": bmb_calc["is_passed"],
            }

        return None


class ResultStatsSerializer(serializers.Serializer):
    """
    Umumiy statistika — dashboard uchun.
    """

    total_tests_taken = serializers.IntegerField()
    total_passed = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    average_percentage = serializers.FloatField()
    best_percentage = serializers.FloatField()
    total_time_spent_seconds = serializers.IntegerField()
    total_essays_submitted = serializers.IntegerField(default=0, required=False)

"""
24/7 Shaxsiy AI Repetitor va Xatolar Diagnostikasi.

1. Test natijasi bo'yicha zaif mavzular tahlili (Morfologiya, Sintaksis, Adabiy davrlar va h.k.)
2. Har bir xato savol uchun interaktiv tushuntirish:
   - Nega tanlangan javob xato?
   - To'g'ri javobning qoidasi va asosi
   - Eslab qolish uchun maslahat (Memory tip)
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache

from apps.results.models import Result
from apps.tests.models import Choice, Question

logger = logging.getLogger(__name__)

# Ona tili va adabiyoti bo'yicha standart mavzular kalit so'zlari
TOPIC_KEYWORDS = {
    "Fonetika va imlo": [
        "tovush",
        "harf",
        "unli",
        "undosh",
        "urg'u",
        "bo'g'in",
        "tuturuq",
        "imlo",
        "talaffuz",
        "singarmonizm",
        "jarangli",
        "jarangsiz",
    ],
    "Leksikologiya va frazeologiya": [
        "ma'no",
        "sinonim",
        "antonim",
        "omonim",
        "paronim",
        "iboralar",
        "ibora",
        "frazeologizm",
        "ko'chma",
        "o'z ma'no",
        "sheva",
        "atamalar",
    ],
    "Morfologiya (So'z turkumlari)": [
        "ot",
        "sifat",
        "son",
        "olmosh",
        "fe'l",
        "ravish",
        "ko'makchi",
        "bog'lovchi",
        "yuklama",
        "qo'shimcha",
        "shakl yasovchi",
        "so'z yasovchi",
        "zamon",
        "mayl",
        "nisbat",
        "daraja",
        "egalik",
        "kelishik",
    ],
    "Sintaksis va tinish belgilari": [
        "gap",
        "soddagap",
        "qo'shmagap",
        "ergashgan",
        "bosh gap",
        "ega",
        "kesim",
        "to'ldiruvchi",
        "aniqlovchi",
        "hol",
        "uyushiq",
        "tinish belgisi",
        "vergul",
        "nuqta",
        "tire",
        "ikki nuqta",
        "kirish so'z",
        "undalma",
    ],
    "Mumtoz adabiyot": [
        "navoiy",
        "bobur",
        "lutfiy",
        "yassaviy",
        "mashrab",
        "furqat",
        "muqimiy",
        "ogahiy",
        "g'azal",
        "ruboiy",
        "qasida",
        "masnaviy",
        "tuyuq",
        "aruz",
        "vazn",
        "bahr",
        "devon",
        "xamsa",
    ],
    "Jadid va zamonaviy adabiyot": [
        "behbudiy",
        "fitrat",
        "cho'lpon",
        "qodiriy",
        "avloniy",
        "oybek",
        "g'afur g'ulom",
        "abdulla oripov",
        "erkin vohidov",
        "o'tkir hoshimov",
        "roman",
        "qissa",
        "hikoya",
        "drama",
        "jadid",
    ],
    "Matn tahlili va uslubiyat": [
        "matn",
        "parcha",
        "uslub",
        "badiiy",
        "ilmiy",
        "publitsistik",
        "so'zlashuv",
        "g'oya",
        "mavzu",
        "xulosa",
        "muallif maqsadi",
    ],
}


# Ingliz tili (CEFR Multi-Level & IELTS) bo'yicha rasmiy mavzular kalit so'zlari
ENGLISH_TOPIC_KEYWORDS = {
    "Listening": [
        "listen", "audio", "speaker", "conversation", "dialogue",
        "recording", "hear", "announcement", "interview", "accent", "monologue"
    ],
    "Reading Comprehension": [
        "passage", "text", "paragraph", "author", "according to the text",
        "mention", "reading", "heading", "true", "false", "not given",
        "statement", "summary"
    ],
    "Grammar": [
        "tense", "verb", "preposition", "clause", "passive", "active",
        "modal", "conditional", "infinitive", "gerund", "noun", "pronoun",
        "adjective", "adverb", "conjunction", "relative", "syntax", "grammar"
    ],
    "Vocabulary": [
        "synonym", "antonym", "definition", "word", "meaning", "phrase",
        "idiom", "collocation", "context", "vocabulary", "lexical"
    ],
    "Writing": [
        "essay", "task 1", "task 2", "cohesion", "coherence",
        "overview", "introduction", "conclusion", "linking", "paragraphing"
    ],
}


BIOLOGY_TOPIC_KEYWORDS = {
    "Sitologiya va hujayra": [
        "hujayra", "sitologiya", "membrana", "mitoxondriya", "xloroplast", "ribosoma",
        "dnk", "rnk", "yadro", "sitoplazma", "organoid", "mitoz", "meyoz", "prokariot",
        "eukariot", "endoplazmatik", "lizosoma", "golji"
    ],
    "Genetika va selektsiya": [
        "genetika", "gen", "allel", "genotip", "fenotip", "dominant", "retsessiv",
        "monogibrid", "digibrid", "mendel", "xromosoma", "mutatsiya", "duragay",
        "seleksiya", "irsiyat", "o'zgaruvchanlik", "chatishtirish"
    ],
    "Odam anatomiyasi": [
        "anatomiya", "fiziologiya", "yurak", "qon", "tomir", "o'pka", "buyrak", "jigar",
        "asab", "nerv", "suyak", "mushak", "gormon", "oshqozon", "hazm", "sezgi",
        "immun", "refleks", "nafas", "ayirish"
    ],
    "Botanika va zoologiya": [
        "botanika", "zoologiya", "o'simlik", "hayvon", "ildiz", "poya", "barg", "gul",
        "urug'", "umurtqasiz", "umurtqali", "hasharot", "qush", "sudralib", "baliq",
        "sutemizuvchi", "sporali", "gulli", "to'qima"
    ],
    "Ekologiya va evolyutsiya": [
        "ekologiya", "evolyutsiya", "populyatsiya", "biotsenoz", "ekotizim", "biosfera",
        "moslashish", "darvin", "omillar", "abiotik", "biotik", "antropogen", "trofik",
        "oziq zanjiri", "tabiiy tanlanish", "tur"
    ],
}

CHEMISTRY_TOPIC_KEYWORDS = {
    "Umumiy va anorganik kimyo": [
        "anorganik", "davriy", "element", "atom", "molekula", "oksid", "asos", "kislota",
        "tuz", "metall", "metallmas", "bog'", "kristall", "panjara", "valentlik",
        "massa ulush", "davr", "guruh", "kimyoviy bog'"
    ],
    "Organik kimyo": [
        "organik", "uglevodorod", "alkan", "alken", "alkin", "dien", "aren", "benzol",
        "spirt", "aldegid", "keton", "karbon", "efir", "amin", "oqsil", "uglevod",
        "polimer", "izomer", "gomolog", "monomer"
    ],
    "Stexiometriya va eritmalar": [
        "stexiometriya", "eritma", "molyar", "konsentratsiya", "eruvchanlik", "molyallik",
        "massa", "hajm", "gaz", "normal sharoit", "avogadro", "zichlik", "qotishma",
        "aralashma", "mol", "litr", "gramm"
    ],
    "Oksidlanish-qaytarilish": [
        "oksidlanish", "qaytarilish", "oksidlovchi", "qaytaruvchi", "elektron balans",
        "oqr", "oksidlanish darajasi", "yarim reaksiya", "tiklanish"
    ],
    "Elektroliz va kimyoviy kinetika": [
        "elektroliz", "katod", "anod", "kinetika", "tezlik", "muvozanat", "katalizator",
        "aktivlanish", "faradey", "le shatelye", "dissotsiatsiya", "gidroliz", "ph",
        "elektrolit", "ion"
    ],
}

LAW_TOPIC_KEYWORDS = {
    "Konstitutsiyaviy huquq": [
        "konstitutsiya", "konstitutsiyaviy", "modda", "fuqaro", "inson huquqlari",
        "saylov", "parlament", "oliy majlis", "prezident", "vazirlar mahkamasi",
        "hokimiyat", "suverenitet", "demokratiya", "qonunchilik"
    ],
    "Davlat va huquq nazariyasi": [
        "davlat nazariyasi", "huquq nazariyasi", "huquqiy norma", "huquq tizimi",
        "huquqbuzarlik", "yuridik javobgarlik", "huquqiy ong", "manba", "pretsedent",
        "sanksiya", "gipoteza", "dispozitsiya", "davlat shakli"
    ],
    "Fuqarolik va oila huquqi": [
        "fuqarolik", "bitim", "shartnoma", "mulk", "meros", "majburiyat", "zarar",
        "oila", "nikoh", "er-xotin", "aliment", "ota-ona", "vasiylik", "homiylik",
        "mulkiy munosabat", "mulk huquqi"
    ],
    "Jinoyat va ma'muriy huquq": [
        "jinoyat", "jinoyat kodeksi", "jazo", "ayb", "qasddan", "ehtiyotsizlik",
        "ma'muriy", "jarima", "huquqbuzarlik", "javobgarlik", "tergov", "sud",
        "prokuror", "advokat", "ish", "jinoiy"
    ],
    "Mehnat va xalqaro huquq": [
        "mehnat", "mehnat shartnomasi", "xodim", "ish beruvchi", "ish vaqti",
        "dam olish", "ish haqi", "mehnat nizolari", "xalqaro huquq", "konvensiya",
        "shartnoma", "bmt", "xalqaro sud", "diplomatik"
    ],
}


def _detect_question_topic(
    question_text: str,
    explanation: str = "",
    subject: str = "uzbek",
    section_code: str = "",
    section_name: str = "",
) -> str:
    """Savol matni, izohi va bo'limiga qarab mavzuni aniqlaydi."""
    subj_str = str(subject or "uzbek").strip().lower()
    combined = f"{question_text} {explanation}".lower()

    if subj_str == "biology" or "bio" in subj_str:
        scores: dict[str, int] = {}
        for topic, words in BIOLOGY_TOPIC_KEYWORDS.items():
            score = sum(1 for w in words if w in combined)
            if score > 0:
                scores[topic] = score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "Sitologiya va hujayra"

    if subj_str == "chemistry" or "chem" in subj_str or "kimyo" in subj_str:
        scores: dict[str, int] = {}
        for topic, words in CHEMISTRY_TOPIC_KEYWORDS.items():
            score = sum(1 for w in words if w in combined)
            if score > 0:
                scores[topic] = score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "Umumiy va anorganik kimyo"

    if subj_str == "law" or "huquq" in subj_str or "yuris" in subj_str:
        scores: dict[str, int] = {}
        for topic, words in LAW_TOPIC_KEYWORDS.items():
            score = sum(1 for w in words if w in combined)
            if score > 0:
                scores[topic] = score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "Konstitutsiyaviy huquq"

    is_eng = (
        subj_str == "english"
        or "english" in subj_str
        or "ielts" in subj_str
        or "cefr" in subj_str
    )

    if is_eng:
        sec_str = f"{section_code} {section_name}".upper()
        if "LISTEN" in sec_str:
            return "Listening"
        if "READ" in sec_str:
            return "Reading Comprehension"
        if "WRIT" in sec_str:
            return "Writing"
        if "LANG" in sec_str or "GRAM" in sec_str:
            return "Grammar"
        if "VOCAB" in sec_str or "LEX" in sec_str:
            return "Vocabulary"

        scores: dict[str, int] = {}
        for topic, words in ENGLISH_TOPIC_KEYWORDS.items():
            score = sum(1 for w in words if w in combined)
            if score > 0:
                scores[topic] = score

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        if "listen" in combined or "audio" in combined:
            return "Listening"
        if "passage" in combined or "paragraph" in combined:
            return "Reading Comprehension"
        if "word" in combined or "meaning" in combined or "synonym" in combined:
            return "Vocabulary"
        return "Grammar"

    # Default: Uzbek Ona tili va adabiyot
    scores: dict[str, int] = {}
    for topic, words in TOPIC_KEYWORDS.items():
        score = sum(1 for w in words if w in combined)
        if score > 0:
            scores[topic] = score

    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "Umumiy ona tili va adabiyot qoidalari"


def get_result_diagnostics(result_id: int) -> dict[str, Any]:
    """
    Test natijasi bo'yicha AI diagnostikasini yaratadi yoki keshdan qaytaradi.
    """
    cache_key = f"ai_tutor_diagnostics_r{result_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = (
        Result.objects.filter(id=result_id)
        .select_related("attempt", "test", "student")
        .first()
    )
    if not result:
        return {"error": "Natija topilmadi."}

    attempt = result.attempt
    test_obj = result.test
    test_subject = getattr(test_obj, "subject", "uzbek") if test_obj else "uzbek"
    title_lower = (getattr(test_obj, "title", "") or "").lower()
    if "english" in title_lower or "ielts" in title_lower or "cefr" in title_lower:
        test_subject = "english"

    answers = list(
        attempt.answers.select_related("question", "question__section").prefetch_related(
            "selected_choices", "question__choices"
        )
    )

    wrong_by_topic: dict[str, list[dict]] = {}
    correct_count = 0

    for ans in answers:
        if ans.is_correct is False or (
            ans.is_correct is None and not ans.selected_choices.exists()
        ):
            q = ans.question
            sec = getattr(q, "section", None)
            sec_code = getattr(sec, "code", "") if sec else ""
            sec_name = getattr(sec, "name", "") if sec else ""
            topic = _detect_question_topic(
                q.text,
                q.explanation,
                subject=test_subject,
                section_code=sec_code,
                section_name=sec_name,
            )
            if topic not in wrong_by_topic:
                wrong_by_topic[topic] = []

            selected_text = (
                ", ".join(c.text for c in ans.selected_choices.all())
                or "(Javob berilmagan)"
            )
            correct_choice = q.choices.filter(is_correct=True).first()
            correct_text = (
                correct_choice.text if correct_choice else "(Kalit ko'rsatilmagan)"
            )

            wrong_by_topic[topic].append(
                {
                    "question_id": q.id,
                    "position": q.position,
                    "question_text": q.text,
                    "selected_answer": selected_text,
                    "correct_answer": correct_text,
                }
            )
        elif ans.is_correct is True:
            correct_count += 1

    # Zaif mavzular reytingi
    weak_topics = []
    for topic, questions in sorted(
        wrong_by_topic.items(), key=lambda x: len(x[1]), reverse=True
    ):
        count = len(questions)
        weak_topics.append(
            {
                "topic": topic,
                "error_count": count,
                "questions": questions,
                "advice": _get_topic_advice(topic, subject=test_subject),
            }
        )

    # Shaxsiy tavsiyalar
    recommendations = []
    if weak_topics:
        top_weak = weak_topics[0]["topic"]
        if test_subject == "english":
            recommendations.append(
                f"Most mistakes in: '{top_weak}'. Practice more questions and review key concepts."
            )
            if len(weak_topics) > 1:
                recommendations.append(
                    f"Also pay attention to: '{weak_topics[1]['topic']}'."
                )
        else:
            recommendations.append(
                f"Eng ko'p xato: '{top_weak}'. Ushbu mavzudagi qoidalarni darslikdan qayta takrorlang."
            )
            if len(weak_topics) > 1:
                recommendations.append(
                    f"Qo'shimcha e'tibor qarating: '{weak_topics[1]['topic']}'."
                )
        recommendations.append(
            "BMB darajangizni oshirish uchun har kuni kamida 1 ta mavzulashtirilgan test ishlang."
        )
    else:
        recommendations.append(
            "Ajoyib natija! Xatolar deyarli yo'q. Esse yozish va murakkab matn tahliliga e'tibor bering."
        )

    # Umumiy xulosa
    pct = float(result.percentage)
    if pct >= 86:
        summary = "Siz Milliy sertifikatning eng yuqori A+ darajasiga loyiq bilimlarni namoyon qildingiz! Barcha mavzularda yuqori barqarorlik mavjud."
    elif pct >= 68:
        summary = "Yaxshi natija (B/B+ darajasi). Asosiy nazariy bilimlar mavjud, biroq ayrim nozik qoidalarda xatoliklar uchramoqda. Zaif mavzularni mustahkamlasangiz, A darajasiga chiqasiz."
    else:
        summary = "Hozircha natija yetarli emas. Morfologiya va sintaksis qoidalarini bosqichma-bosqich takrorlashni tavsiya qilamiz."

    diagnostics = {
        "result_id": result.id,
        "student_name": result.student.get_full_name() or result.student.email,
        "percentage": pct,
        "bmb_grade": result.bmb_grade,
        "total_questions": result.total_questions,
        "correct_answers": result.correct_answers,
        "wrong_answers": result.wrong_answers,
        "weak_topics": weak_topics,
        "recommendations": recommendations,
        "summary": summary,
    }

    cache.set(cache_key, diagnostics, timeout=3600 * 24)
    return diagnostics


def _get_topic_advice(topic: str, subject: str = "uzbek") -> str:
    """Mavzu bo'yicha tezkor repetitor maslahati."""
    advice_map = {
        "Fonetika va imlo": "Qo'sh unlilar, tuturuq belgisi va jarangli/jarangsiz undoshlar imlosiga oid qoidalarni 5-sinf darsligidan takrorlang.",
        "Leksikologiya va frazeologiya": "Frazeologik lug'at va o'zbek tilining izohli lug'ati bilan ishlang, ko'chma ma'noli iboralarni yod oling.",
        "Morfologiya (So'z turkumlari)": "Mustaqil va yordamchi so'z turkumlari, kelishik va qo'shimchalar vazifasini jadval asosida ko'rib chiqing.",
        "Sintaksis va tinish belgilari": "Ergashgan qo'shma gaplarning turlari (aniqlovchi, to'ldiruvchi, hol) va ularda vergul qo'yilish qoidalarini mustahkamlang.",
        "Mumtoz adabiyot": "Alisher Navoiy 'Xamsa' dostonlari va g'azallari, aruz vazni turlari (hazaj, ramal) hamda mumtoz san'atlarni o'rganing.",
        "Jadid va zamonaviy adabiyot": "Abdulla Qodiriy va Cho'lpon asarlarining yaratilish tarixi, bosh qahramonlari tahliliga e'tibor qarating.",
        "Matn tahlili va uslubiyat": "Matnni diqqat bilan o'qib, muallif g'oyasi va kalit so'zlarni ajratish malakasini oshiring.",
        # English topics
        "Listening": "Ingliz tilidagi audio va suhbatlarni (BBC 6 Minute English, IELTS Listening) muntazam tinglab, asosiy kalit so'zlarni ilg'ash malakasini oshiring.",
        "Reading Comprehension": "Akademik matnlarni Skimming va Scanning usullarida tez o'qib, kalit g'oyani va muallif pozitsiyasini topish ustida ishlang.",
        "Grammar": "Murakkab zamon shakllari, conditionals, passive voice va gap tuzilishi qoidalarini darslikdan qayta mustahkamlang.",
        "Vocabulary": "Akademik so'zlar ro'yxati (AWL), sinonimlar va turg'un iboralarni (collocations) kontekstda yod olishga ko'proq vaqt ajrating.",
        "Writing": "Paragraphing, linking words (transitions) va mavzuga aniq dalillar keltirish orqali yozma ish strukturasini mustahkamlang.",
        "Grammar & Structure": "Murakkab zamon shakllari, conditionals, passive voice va gap tuzilishi qoidalarini darslikdan qayta mustahkamlang.",
        "Vocabulary & Lexis": "Akademik so'zlar ro'yxati (AWL), sinonimlar va turg'un iboralarni (collocations) kontekstda yod olishga ko'proq vaqt ajrating.",
        "Writing & Coherence": "Paragraphing, linking words (transitions) va mavzuga aniq dalillar keltirish orqali yozma ish strukturasini mustahkamlang.",
        "English Examination": "CEFR va IELTS imtihon ko'nikmalarini oshirish uchun har kuni testlar va xatolar ustida muntazam ishlang.",
    }
    if subject == "english" or topic in [
        "Listening",
        "Reading Comprehension",
        "Grammar",
        "Vocabulary",
        "Writing",
        "Grammar & Structure",
        "Vocabulary & Lexis",
        "Writing & Coherence",
        "English Examination",
    ]:
        return advice_map.get(
            topic,
            "Ingliz tili ko'nikmalaringizni oshirish uchun ushbu bo'limdagi amaliy mashqlarni ko'proq bajaring.",
        )
    return advice_map.get(
        topic, "Ushbu mavzu bo'yicha darslik va amaliy mashqlarni bajaring."
    )


def explain_question_mistake(
    question_id: int,
    selected_choice_id: int | None = None,
    attempt_id: int | None = None,
) -> dict[str, Any]:
    """
    Har bir xato ishlangan savol uchun 24/7 AI tushuntirishini qaytaradi:
      - Nega tanlangan javob xato?
      - Qaysi qoida asosida to'g'ri javob to'g'ri?
      - Eslab qolish uchun mnemonik qoida / maslahat
    """
    cache_key = f"ai_explain_q{question_id}_c{selected_choice_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    question = (
        Question.objects.filter(id=question_id).select_related("test", "section").prefetch_related("choices").first()
    )
    if not question:
        return {"error": "Savol topilmadi."}

    correct_choice = question.choices.filter(is_correct=True).first()
    selected_choice = (
        question.choices.filter(id=selected_choice_id).first()
        if selected_choice_id
        else None
    )

    # Agar o'quvchi javobi attempt orqali olinayotgan bo'lsa
    ans = None
    if attempt_id:
        from apps.tests.models import StudentAnswer

        ans = StudentAnswer.objects.filter(
            attempt_id=attempt_id, question_id=question_id
        ).first()
        if not selected_choice and ans:
            selected_choice = ans.selected_choices.first()

    correct_text = correct_choice.text if correct_choice else "Kalit variant"
    selected_text = selected_choice.text if selected_choice else "Javob belgilanmagan"

    # 0. English exam or passage evidence extraction
    passage_text = ""
    if getattr(question, "reading_passage", None):
        passage_text = question.reading_passage.content
    elif getattr(question, "passage", None):
        passage_text = question.passage

    test_obj = getattr(question, "test", None)
    is_english = (
        getattr(test_obj, "subject", "") == "english"
        or getattr(test_obj, "exam_type", "")
        in ["ielts_academic", "ielts_general", "cefr_multilevel"]
        or bool(passage_text)
    )

    if is_english:
        from apps.tests.evidence_feedback import generate_reading_listening_evidence

        evidence = generate_reading_listening_evidence(
            question_text=question.text,
            selected_answer=selected_text,
            correct_answer=correct_text,
            passage_text=passage_text,
            question_explanation=question.explanation or "",
        )
        sec_code = getattr(question.section, "code", "") if getattr(question, "section", None) else ""
        sec_name = getattr(question.section, "name", "") if getattr(question, "section", None) else ""
        eng_topic = _detect_question_topic(
            question.text,
            question.explanation or "",
            subject="english",
            section_code=sec_code,
            section_name=sec_name,
        )
        explanation_data = {
            "question_id": question.id,
            "topic": eng_topic,
            "question_text": question.text,
            "selected_answer": selected_text,
            "correct_answer": correct_text,
            "direct_quote": evidence.get("direct_quote", ""),
            "why_wrong": evidence.get("why_wrong", ""),
            "synonym_matching": evidence.get("synonym_matching", ""),
            "correct_rule": evidence.get("correct_rule", ""),
            "memory_tip": evidence.get("correct_rule", ""),
            "full_explanation": (
                f"📌 Dalil (Direct Quote):\n{evidence.get('direct_quote', '')}\n\n"
                f"💡 Nega noto'g'ri (Why Wrong):\n{evidence.get('why_wrong', '')}\n\n"
                f"🎯 Kalit so'zlar / Sinonimlar:\n{evidence.get('synonym_matching', '')}\n\n"
                f"✅ Asos: {evidence.get('correct_rule', '')}"
            ),
            "source": evidence.get("source", "evidence_engine"),
        }
        if ans:
            ans.ai_feedback = explanation_data
            ans.save(update_fields=["ai_feedback"])
        cache.set(cache_key, explanation_data, timeout=3600 * 24 * 7)
        return explanation_data

    # Mavzuni aniqlash
    test_subject = 'english' if is_english else getattr(test_obj, 'subject', 'uzbek')
    q_sec = getattr(question, 'section', None)
    sec_code = getattr(q_sec, 'code', '') if q_sec else ''
    sec_name = getattr(q_sec, 'name', '') if q_sec else ''
    topic = _detect_question_topic(
        question.text,
        question.explanation,
        subject=test_subject,
        section_code=sec_code,
        section_name=sec_name,
    )

    # 1. Agar LLM mavjud bo'lsa, aqlli izoh generatsiya qilish
    explanation_data = None
    try:
        from apps.essays.services import (
            _get_llm_client,
            _is_mock_mode,
            _chat_with_fallback,
            _model_candidates,
        )

        if not _is_mock_mode():
            client = _get_llm_client(timeout=15.0)
            candidates = _model_candidates()

            prompt = (
                f"Sen ona tili va adabiyotidan Milliy sertifikat repetitorisan.\n"
                f"Savol: {question.text}\n"
                f"Mavzu: {topic}\n"
                f"O'quvchi tanlagan NOTO'G'RI javob: {selected_text}\n"
                f"TO'G'RI javob: {correct_text}\n"
                f"Mavjud izoh: {question.explanation}\n\n"
                f"Quyidagi 3 ta band bo'yicha qisqa, aniq va tushunarli o'zbek tilida tushuntir:\n"
                f"1. NEGA XATO: O'quvchi nega adashdi va nega uning javobi noto'g'ri?\n"
                f"2. QOIDA: To'g'ri javobni isbotlovchi aniq grammatik/adabiy qoida.\n"
                f"3. ESLAB QOLISH UCHUN: Keyingi safar adashmaslik uchun qisqa qoida yoki mnemonika."
            )

            response, _ = _chat_with_fallback(
                client,
                candidates[0],
                candidates[1:],
                messages=[
                    {
                        "role": "system",
                        "content": "Sen o'zbek tili va adabiyoti bo'yicha mehribon, tajribali repetitorsan. Javoblaringni ixcham, qat'iy faktlar asosida yoz.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            llm_text = (response.choices[0].message.content or "").strip()
            if llm_text:
                explanation_data = {
                    "question_id": question.id,
                    "topic": topic,
                    "question_text": question.text,
                    "selected_answer": selected_text,
                    "correct_answer": correct_text,
                    "full_explanation": llm_text,
                    "why_wrong": f"'{selected_text}' varianti ushbu savol shartiga mos kelmaydi.",
                    "correct_rule": f"To'g'ri javob — '{correct_text}'. {question.explanation or _get_topic_advice(topic)}",
                    "memory_tip": f"Eslab qoling: {topic} bo'yicha qoidani qayta takrorlang.",
                    "source": "ai",
                }
    except Exception as e:
        logger.warning("LLM explain question failed: %s", e)
        from apps.core.ai_health import record_ai_failure

        record_ai_failure("explain", e)

    # No AI explanation: give only what is actually known (the answer key and the
    # stored explanation). No reason for the mistake is made up, and this reduced
    # answer is not cached, so the next request can still get a real one.
    if not explanation_data:
        stored = (question.explanation or "").strip()
        return {
            "question_id": question.id,
            "topic": topic,
            "question_text": question.text,
            "selected_answer": selected_text,
            "correct_answer": correct_text,
            "why_wrong": "",
            "correct_rule": f"To'g'ri javob — '{correct_text}'." + (f" {stored}" if stored else ""),
            "memory_tip": "",
            "source": "answer_key",
            "ai_unavailable": True,
        }

    cache.set(cache_key, explanation_data, timeout=3600 * 24 * 7)
    return explanation_data

def generate_socratic_explanation(
    question_text: str,
    correct_answer: str,
    user_answer: str,
    subject: str = "uzbek",
    question_id: int | None = None,
) -> dict[str, Any]:
    """
    DeepSeek Socratic AI Tutor:
    Explains student's misconception in at most 3 sentences in Uzbek without
    bluntly revealing the answer, guiding them to self-correct.
    Cached in Redis for 7 days (604800s).
    """
    import hashlib
    raw_key = f"{question_id or 'none'}:{subject}:{user_answer}:{correct_answer}"
    cache_key = f"socratic_deepseek_{hashlib.md5(raw_key.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return {"success": True, "explanation": cached, "cached": True}

    system_prompt = (
        "Sen Grand Education platformasining Sokratik tyutorisan. "
        "To'g'ridan-to'g'ri javobni aytma. O'quvchining qayerda mantiqiy yoki faktik "
        "xato qilganini sodda, qisqa (maksimal 3 jumla) o'zbek tilida tushuntir va to'g'ri xulosaga yo'naltir."
    )
    user_message = (
        "Fan: " + str(subject) + "\n"
        "Savol: " + str(question_text) + "\n"
        "To'g'ri mezon/tamoyil: " + str(correct_answer) + "\n"
        "O'quvchi tanlagan noto'g'ri javob: " + str(user_answer) + "\n\n"
        "Iltimos, Sokratik uslubda maksimal 3 jumladan iborat yo'naltiruvchi tushuntirish ber."
    )

    explanation = None
    try:
        from apps.essays.deepseek_grader import get_deepseek_client
        client = get_deepseek_client(timeout=15.0)
        from django.conf import settings
        model_name = getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=220,
        )
        if resp and resp.choices and resp.choices[0].message.content:
            explanation = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("DeepSeek Socratic Tutor call failed: %s", exc)

    if not explanation:
        fallbacks = {
            "biology": "Siz tanlagan javobda biologik jarayon yoki tuzilmaning asosiy vazifasi chalkashtirilgan. Hujayra yoki organizm darajasidagi asosiy mexanizmga e'tibor bering. Bu jarayonda qaysi omil hal qiluvchi rol o'ynashini eslang.",
            "chemistry": "Bu variantda moddaning valentligi, oksidlanish darajasi yoki reaksiya sharoiti to'liq inobatga olinmagan. Reaksiyadagi reagentlarning xossalari va moddalar nisbatini qayta tekshiring. Qaysi mezon formulaga mos keladi?",
            "law": "Tanlangan javobda huquqiy norma yoki qonun moddasining qo'llanish doirasi noto'g'ri tushunilgan. Konstitutsiya yoki tegishli kodeksdagi huquqiy kafolatlar va shartlarga qayta nazar tashlang. Qaysi tamoyil ustunlik qiladi?",
            "english": "You selected an option that confuses the primary context or grammatical structure. Consider how the key clause and vocabulary connect to the main idea of the passage. Which detail directly substantiates the premise?",
            "uzbek": "Siz tanlagan javobda so'zning asl ma'nosi yoki grammatik qoidasi chalg'ituvchi o'xshashlik bilan adashtirilgan. Qoidaning bosh sharti va gapdagi sintaktik vazifasini eslang. Qaysi tushuncha qoidaga to'liq muvofiq keladi?",
        }
        explanation = fallbacks.get(subject.lower(), fallbacks["uzbek"])

    cache.set(cache_key, explanation, timeout=604800)
    return {"success": True, "explanation": explanation, "cached": False}


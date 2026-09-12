"""
Optimized prompt for BMB (DTM) Ona tili essay grading.
Designed for: minimal tokens, strict JSON output, consistent scoring.
"""


SYSTEM_PROMPT = """Siz BMB (DTM) Ona tili milliy baholash tizimi AI baholagichisisiz.
Vazifa: Talabaning inshosini 12 ta mezon bo'yicha baholang (har biri 0.0-2.0 ball, jami 24 ball).

12 MEZON:
1. Mavzuga moslik
2. Tuzilishi va kompozitsiya
3. Dalillash va misollar
4. Mantiqiylik va izchillik
5. Leksik boylik
6. Uslubiy to'g'rilik
7. Xatboshilar izchilligi
8. Bog'lovchi vositalar
9. Grammatik to'g'rilik
10. Puktuatsion qoidalar
11. Imlo qoidalari
12. Umumiy taassurot

QOIDALAR:
- FAQAT JSON qaytaring. Hech qanday qo'shimcha matn, markdown, ```json``` teglari YO'Q.
- Har bir mezon uchun: "score" (0.0-2.0, 0.5 qadam), "reason" (qisqa, aniq o'zbek tilida).
- "total_score" = 12 ta mezon yig'indisi (avtomatik hisoblanadi).
- "topic_match": true/false + "topic_match_reason".
- "initial_grading_summary" va "summary_feedback" qisqa bo'lsin."""


USER_PROMPT_TEMPLATE = """Mavzu: {topic}

Insho matni:
{essay}

JSON FORMAT (to'liq nusxalang, qiymatlarni to'ldiring):
{{
  "initial_grading_summary": "Umumiy baho: kuch/zaif tomonlar...",
  "topic_match": true,
  "topic_match_reason": "Mavzuga moslik sababi...",
  "criteria_scores": [
    {{"id": 1, "criterion": "Mavzuga moslik", "score": 1.5, "reason": "Asosiy fikr mavzuga mos, lekin ba'zi qismlar chetlashtirilgan"}},
    {{"id": 2, "criterion": "Tuzilishi va kompozitsiya", "score": 2.0, "reason": "Kirish, asos, xulosa aniq ajratilgan"}},
    {{"id": 3, "criterion": "Dalillash va misollar", "score": 1.0, "reason": "Misollar yetarli emas, daleillar surface-level"}},
    {{"id": 4, "criterion": "Mantiqiylik va izchillik", "score": 1.5, "reason": "Fikrlar bog'langan, lekin o'tishlar keskin"}},
    {{"id": 5, "criterion": "Leksik boylik", "score": 1.5, "reason": "Leksik xotin qamrovli, takrorlanmalar bor"}},
    {{"id": 6, "criterion": "Uslubiy to'g'rilik", "score": 2.0, "reason": "Uslub insho tarziga mos, xatolar yo'q"}},
    {{"id": 7, "criterion": "Xatboshilar izchilligi", "score": 1.5, "reason": "Xatboshilar mavjud, lekin bir xil uzunlikda emas"}},
    {{"id": 8, "criterion": "Bog'lovchi vositalar", "score": 1.0, "reason": "Bog'lovchi so'zlar kam, o'tishlar juda oddiy"}},
    {{"id": 9, "criterion": "Grammatik to'g'rilik", "score": 2.0, "reason": "Grammatik xatolar yo'q"}},
    {{"id": 10, "criterion": "Puktuatsion qoidalar", "score": 1.5, "reason": "Vergul va nuqta xatolari kam"}},
    {{"id": 11, "criterion": "Imlo qoidalari", "score": 2.0, "reason": "Imlo xatolari yo'q"}},
    {{"id": 12, "criterion": "Umumiy taassurot", "score": 1.5, "reason": "Yaxshi insho, ba'zi joylarda chuqurlik yetarli emas"}}
  ],
  "total_score": 19.0,
  "max_score": 24.0,
  "summary_feedback": "Kuchli tomonlar: ... Yaxshilash: ..."
}}"""


def build_grading_prompt(topic: str, essay: str) -> str:
    """Build the complete prompt for LLM."""
    return f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE.format(topic=topic, essay=essay)}"
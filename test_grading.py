"""
Test script for essay grading pipeline.
Run: python test_grading.py
"""
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from essays.utils.llm_parser import extract_json, parse_llm_json, parse_and_validate_grading, _validate_grading_result
from essays.utils.prompts import build_grading_prompt
from essays.views import grade_essay_async


# Test essays
TEST_ESSAYS = [
    {
        "topic": "Oila va uning jamiyatdagi o'rni",
        "essay": """Oila - bu jamiyatning kichik nusxasi, uning asosidir. Oila bo'lmasdan jamiyat ham bo'lmaydi. 
        Oila odamga yengil tun ochadi, g'amlarda qo'llab-quvvatlaydi. Ota-ona bolalarni tarbiya qiladi, 
        ularga hayot yo'lini ko'rsatadi. Hozirgi kunda oilalar uzilib ketmoqda, bu yomon. 
        Bolalar ota-onasiz qolmoqda, ular yomon yo'lga kirishi mumkin. 
        Shu sababli oilani himoya qilish, uni mustahkam qilish lozim. 
        Davlat oilaga yordam bermoqchi, lekin hali kam. Ko'proq ishlar qilishi kerak."""
    },
    {
        "topic": "Ta'lim va uning inson hayotidagi ahamiyati",
        "essay": """Ta'lim - bu insonning eng katta boyidir. Bilimsiz inson chaqaloqdek, qayerga borsa shu yo'l. 
        Ta'lim olgan odam ish topa oladi, oila quradi, jamiyatga foyda yetkazadi. 
        Davlat ta'limga e'tibor bermoqda, yangi maktablar, universitetlar ochilmoqda. 
        Lekin hali ba'zi joylarda ta'lim sifati past. O'qituvchilar ish haqi kam, 
        shu sababli ular yana ish qidiradi. Bu hal qilinishi kerak. 
        Ta'lim bepul va sifatli bo'lishi kerak, bu inson haqqidir."""
    },
]


def test_json_extraction():
    """Test JSON extraction from various LLM response formats."""
    print("=" * 60)
    print("TEST: JSON Extraction")
    print("=" * 60)
    
    test_cases = [
        # Case 1: Markdown code block
        ('```json\n{"key": "value"}\n```', '{"key": "value"}'),
        # Case 2: Markdown without language
        ('```\n{"key": "value"}\n```', '{"key": "value"}'),
        # Case 3: Bare JSON
        ('{"key": "value"}', '{"key": "value"}'),
        # Case 4: With extra text
        ('Here is the result:\n```json\n{"score": 1.5}\n```\nDone.', '{"score": 1.5}'),
        # Case 5: Multiple blocks - should get first valid
        ('```json\n{"wrong": true}\n```\n```json\n{"criteria_scores": [], "total_score": 0}\n```', '{"criteria_scores": [], "total_score": 0}'),
    ]
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = extract_json(input_text)
        status = "✓" if result == expected else "✗"
        print(f"  Test {i}: {status} - Got: {result[:50]}...")
        if result != expected:
            print(f"    Expected: {expected}")


def test_validation():
    """Test validation with incomplete/malformed LLM output."""
    print("\n" + "=" * 60)
    print("TEST: Validation & Normalization")
    print("=" * 60)
    
    # Simulate LLM output missing some criteria
    partial_llm_output = {
        "initial_grading_summary": "Test",
        "topic_match": True,
        "topic_match_reason": "Ok",
        "criteria_scores": [
            {"id": 1, "criterion": "Mavzuga moslik", "score": 2.0, "reason": "Good"},
            {"id": 2, "criterion": "Tuzilishi va kompozitsiya", "score": 1.5, "reason": "Ok"},
            # Missing 10 criteria
        ],
        "total_score": 3.5,
        "max_score": 24.0,
        "summary_feedback": "Needs work",
    }
    
    validated = _validate_grading_result(partial_llm_output)
    
    print(f"  Input criteria count: {len(partial_llm_output['criteria_scores'])}")
    print(f"  Output criteria count: {len(validated['criteria_scores'])}")
    print(f"  All 12 present: {len(validated['criteria_scores']) == 12}")
    print(f"  Total score recalculated: {validated['total_score']}")
    print(f"  Scores clamped 0-2: {all(0 <= c['score'] <= 2 for c in validated['criteria_scores'])}")
    
    # Check specific criteria names
    names = [c['criterion'] for c in validated['criteria_scores']]
    expected_names = [
        "Mavzuga moslik", "Tuzilishi va kompozitsiya", "Dalillash va misollar",
        "Mantiqiylik va izchillik", "Leksik boylik", "Uslubiy to'g'rilik",
        "Xatboshilar izchilligi", "Bog'lovchi vositalar", "Grammatik to'g'rilik",
        "Puktuatsion qoidalar", "Imlo qoidalari", "Umumiy taassurot"
    ]
    print(f"  Criteria names match: {names == expected_names}")


async def test_full_pipeline():
    """Test the full async grading pipeline (uses mock LLM)."""
    print("\n" + "=" * 60)
    print("TEST: Full Async Grading Pipeline")
    print("=" * 60)
    
    for i, test in enumerate(TEST_ESSAYS, 1):
        print(f"\n  Essay {i}: {test['topic'][:40]}...")
        prompt = build_grading_prompt(test['topic'], test['essay'])
        
        try:
            result = await grade_essay_async(prompt)
            
            # Validate structure
            assert "criteria_scores" in result
            assert len(result["criteria_scores"]) == 12
            assert "total_score" in result
            assert 0 <= result["total_score"] <= 24
            assert result["max_score"] == 24.0
            assert isinstance(result["topic_match"], bool)
            
            print(f"    ✓ Success - Total: {result['total_score']}/24")
            print(f"    ✓ Topic match: {result['topic_match']}")
            print(f"    ✓ Criteria count: {len(result['criteria_scores'])}")
            
            # Print first few criteria
            for c in result["criteria_scores"][:3]:
                print(f"      - {c['criterion']}: {c['score']} ({c['reason'][:40]}...)")
                
        except Exception as e:
            print(f"    ✗ Failed: {e}")


def test_prompt_building():
    """Test prompt template."""
    print("\n" + "=" * 60)
    print("TEST: Prompt Building")
    print("=" * 60)
    
    prompt = build_grading_prompt("Test mavzu", "Test insho matni")
    
    checks = [
        ("SYSTEM_PROMPT present", "BMB (DTM)" in prompt),
        ("USER_PROMPT present", "Test mavzu" in prompt),
        ("JSON template present", "criteria_scores" in prompt),
        ("No markdown in template", "```json" not in prompt),
        ("All 12 criteria listed", prompt.count("criterion") >= 12),
    ]
    
    for name, passed in checks:
        print(f"  {name}: {'✓' if passed else '✗'}")


async def main():
    print("ESSAY GRADING PIPELINE TESTS")
    print("=" * 60)
    
    test_json_extraction()
    test_validation()
    test_prompt_building()
    await test_full_pipeline()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
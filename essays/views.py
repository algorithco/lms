"""
Essay Grading Views - Async, robust, with graceful shutdown support.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .utils.llm_parser import parse_and_validate_grading
from .utils.prompts import build_grading_prompt

logger = logging.getLogger(__name__)

# --- Global resources (cleaned up on shutdown) ---
_executor: Optional[ThreadPoolExecutor] = None
_background_tasks: set[asyncio.Task] = set()
_llm_client = None  # Will be initialized lazily


def get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool for blocking LLM calls."""
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(
            max_workers=getattr(settings, 'LLM_MAX_WORKERS', 2),
            thread_name_prefix="llm-grader"
        )
    return _executor


def get_llm_client():
    """Lazy initialization of LLM client (OpenAI, local, etc.)."""
    global _llm_client
    if _llm_client is None:
        # Replace with your actual LLM client initialization
        # Example: from openai import OpenAI; _llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # For now, a mock function is used in _sync_grade()
        pass
    return _llm_client


async def lifespan_manager():
    """ASGI lifespan context manager for startup/shutdown."""
    global _executor, _background_tasks
    try:
        yield
    finally:
        logger.info("Shutting down essay grading resources...")
        # Cancel background tasks
        for task in _background_tasks:
            if not task.done():
                task.cancel()
        if _background_tasks:
            await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()

        # Shutdown thread pool
        if _executor and not _executor._shutdown:
            _executor.shutdown(wait=True, cancel_futures=True)
        _executor = None
        logger.info("Essay grading resources cleaned up.")


def _sync_grade_essay(prompt: str) -> str:
    """
    Synchronous blocking call to LLM.
    Replace this with your actual LLM API call.
    MUST return raw string response from LLM.
    """
    client = get_llm_client()
    if client is None:
        # MOCK for development - replace with real call
        import time
        time.sleep(1.5)  # Simulate API latency
        return json.dumps({
            "initial_grading_summary": "Mock baholash: insho o'rtacha darajada",
            "topic_match": True,
            "topic_match_reason": "Mavzuga mos keladi",
            "criteria_scores": [
                {"id": i, "criterion": c, "score": 1.5, "reason": "Mock sabab"}
                for i, c in enumerate([
                    "Mavzuga moslik", "Tuzilishi va kompozitsiya", "Dalillash va misollar",
                    "Mantiqiylik va izchillik", "Leksik boylik", "Uslubiy to'g'rilik",
                    "Xatboshilar izchilligi", "Bog'lovchi vositalar", "Grammatik to'g'rilik",
                    "Puktuatsion qoidalar", "Imlo qoidalari", "Umumiy taassurot"
                ], 1)
            ],
            "total_score": 18.0,
            "max_score": 24.0,
            "summary_feedback": "Mock maslahat: haqiqiy LLM ulanishi kerak"
        }, ensure_ascii=False)

    # --- REAL LLM CALL EXAMPLE (OpenAI) ---
    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[{"role": "user", "content": prompt}],
    #     temperature=0.1,
    #     max_tokens=1500,
    #     response_format={"type": "json_object"}  # Forces JSON if supported
    # )
    # return response.choices[0].message.content

    raise NotImplementedError("LLM client not configured. Implement _sync_grade_essay().")


async def grade_essay_async(prompt: str) -> dict:
    """Run LLM grading in thread pool, parse & validate result."""
    loop = asyncio.get_running_loop()
    executor = get_executor()

    try:
        raw_response = await loop.run_in_executor(executor, _sync_grade_essay, prompt)
        logger.debug(f"LLM raw response (first 200): {raw_response[:200]}")
        return parse_and_validate_grading(raw_response)
    except Exception as e:
        logger.exception("LLM grading failed")
        # Return a valid error structure instead of raising
        return {
            "initial_grading_summary": "Baholash amalga oshmadi",
            "topic_match": False,
            "topic_match_reason": f"Xatolik: {str(e)[:100]}",
            "criteria_scores": [
                {"id": i, "criterion": c, "score": 0.0, "reason": "Baholanmadi"}
                for i, c in enumerate([
                    "Mavzuga moslik", "Tuzilishi va kompozitsiya", "Dalillash va misollar",
                    "Mantiqiylik va izchillik", "Leksik boylik", "Uslubiy to'g'rilik",
                    "Xatboshilar izchilligi", "Bog'lovchi vositalar", "Grammatik to'g'rilik",
                    "Puktuatsion qoidalar", "Imlo qoidalari", "Umumiy taassurot"
                ], 1)
            ],
            "total_score": 0.0,
            "max_score": 24.0,
            "summary_feedback": f"Texnik xatolik yuz berdi: {str(e)[:200]}"
        }


@method_decorator(csrf_exempt, name='dispatch')
class EssaySubmitView(View):
    """
    POST /essays/submit/
    Body: {"essay_text": "...", "topic": "..."}
    Returns: Full validated grading JSON.
    """

    async def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Noto\'g\'ri JSON format'}, status=400)

        essay_text = data.get('essay_text', '').strip()
        topic = data.get('topic', '').strip()

        if not essay_text:
            return JsonResponse({'error': 'Essay matni kiritilmagan'}, status=400)
        if not topic:
            return JsonResponse({'error': 'Mavzu kiritilmagan'}, status=400)

        # Length check (optional)
        if len(essay_text) < 50:
            return JsonResponse({'error': 'Insho juda qisqa (kamida 50 belgi)'}, status=400)

        prompt = build_grading_prompt(topic, essay_text)

        # Create background task for tracking
        task = asyncio.create_task(self._process_with_timeout(prompt))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        try:
            result = await asyncio.wait_for(task, timeout=45.0)
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        except asyncio.TimeoutError:
            logger.warning("Grading timeout for essay")
            return JsonResponse({'error': 'Baholash vaqti tugadi (45s)'}, status=504)
        except Exception as e:
            logger.exception("Unexpected error in essay submit")
            return JsonResponse({'error': 'Server ichki xatosi'}, status=500)

    async def _process_with_timeout(self, prompt: str) -> dict:
        """Wrapper to ensure we always return a valid dict."""
        return await grade_essay_async(prompt)
# Django + Channels + AI Integration - Setup & Run Guide

## 1. Install Dependencies

```bash
pip install django channels daphne uvicorn[standard] python-dotenv
# For production Redis:
# pip install channels_redis
```

## 2. Project Structure

```
project/
├── asgi.py                    # ASGI entry point with lifespan
├── settings.py                # Add CHANNEL_LAYERS, DATABASES opts
├── settings_additions.py      # Reference settings (copy to settings.py)
essays/
├── views.py                   # EssaySubmitView (async, robust)
├── utils/
│   ├── llm_parser.py          # JSON extract + validate (12 criteria)
│   └── prompts.py             # Optimized BMB/DTM prompt
quiz/
├── models.py                  # QuizRoom, QuizQuestion, QuizAnswer, QuizResult
├── consumers.py               # QuizArenaConsumer (SQLite-safe)
└── routing.py                 # WebSocket URL routing
```

## 3. Register URLs

```python
# project/urls.py
from django.urls import path, include
from essays.views import EssaySubmitView

urlpatterns = [
    path('essays/submit/', EssaySubmitView.as_view(), name='essay-submit'),
    # ... other urls
]
```

## 4. Run Development Server (Uvicorn with reload)

```bash
# Option 1: Uvicorn directly (recommended for ASGI)
uvicorn project.asgi:application --reload --host 0.0.0.0 --port 8000 --log-level info

# Option 2: Daphne (older, less lifespan support)
daphne -p 8000 project.asgi:application
```

## 5. Production (Gunicorn + Uvicorn workers)

```bash
gunicorn project.asgi:application \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --graceful-timeout 30 \
  --worker-tmp-dir /dev/shm
```

## 6. WebSocket Client Example (JS)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/quiz/arena/');

ws.onopen = () => {
  // Join room
  ws.send(JSON.stringify({ type: 'join', room_id: 'uuid-from-create-api' }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'quiz.joined':
      console.log('Joined room', msg.room);
      break;
    case 'quiz.question':
      renderQuestion(msg);
      break;
    case 'quiz.answer_result':
      showAnswerResult(msg);
      break;
    case 'quiz.result':
      showFinalResults(msg.results);
      break;
    case 'quiz.error':
      alert(msg.message);
      break;
  }
};

// Submit answer
function submitAnswer(questionIndex, option) {
  ws.send(JSON.stringify({ type: 'answer', question_index: questionIndex, answer: option }));
}

// Creator starts game
function startGame() {
  ws.send(JSON.stringify({ type: 'start' }));
}
```

## 7. Key Design Decisions

### Essay Grading (`essays/views.py`)
| Feature | Implementation |
|---------|----------------|
| **Async LLM call** | `run_in_executor` with `ThreadPoolExecutor` (non-blocking) |
| **JSON parsing** | `extract_json()` handles markdown, bare JSON, multiple blocks |
| **Validation** | `_validate_grading_result()` enforces 12 criteria, clamps 0-2, recalculates total |
| **Graceful shutdown** | `lifespan_manager` cancels tasks, shuts down executor |
| **Timeout** | 45s per request, returns 504 if exceeded |
| **Error handling** | Always returns valid JSON structure, never 500 to client |

### Quiz Arena (`quiz/consumers.py`)
| Feature | Implementation |
|---------|----------------|
| **SQLite locks** | All DB ops in `@database_sync_to_async`, short transactions |
| **Race conditions** | `select_for_update()` in `_save_answer`, atomic transactions |
| **Duplicate prevention** | Unique constraint `(room, user, question)` + explicit check |
| **Group messaging** | `channel_layer.group_send` to `quiz_<room_id>` |
| **State machine** | Join → Start → Question → Answer(s) → Next/Finish → Result |
| **Auto-join** | Empty opponent slot auto-filled on join |

## 8. LLM Client Integration

Replace `_sync_grade_essay()` in `essays/views.py`:

```python
def _sync_grade_essay(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content
```

## 9. Testing Checklist

- [ ] Essay submit returns valid JSON with all 12 criteria
- [ ] Reload (code change) doesn't crash pending requests
- [ ] WebSocket connects, joins room, receives questions
- [ ] Two clients in same room both answer → advances automatically
- [ ] Final results calculated correctly
- [ ] SQLite "database is locked" never appears under load

## 10. Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `RuntimeError: cannot schedule new futures after interpreter shutdown` | Ensure `lifespan_manager` in `asgi.py`, run with Uvicorn |
| `database is locked` | Use `@database_sync_to_async`, keep transactions short, enable WAL mode |
| LLM returns markdown | `extract_json()` handles ```json``` blocks automatically |
| WebSocket 403 | Check `AllowedHostsOriginValidator`, add origin to `CSRF_TRUSTED_ORIGINS` |
| Auto-reload kills requests | Uvicorn `--reload` + lifespan = graceful, use `gunicorn` for prod |
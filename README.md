# LMS Platform — Uzbek Language & Literature

> Modern learning platform for Uzbek language and literature exam preparation. Timed tests, AI essay grading, gamification, 1v1 quiz arena, certificates, and Telegram integration.

[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-GPLv3-blue)](./LICENSE)

---

## Features

| Area | What you get |
| ---- | ------------ |
| **Tests** | Timed exams, single / multiple / text answers, shuffling, auto-grading, attempt limits |
| **AI Essays** | 12-criteria grading (24 pts → 75 scale), off-topic detection, improved-version generator, teacher review queue |
| **Games** | Spelling Mines, Ghazal Puzzle, Dictionary Match — XP, coins, badges, streaks, weekly challenges |
| **Arena** | Real-time 1v1 quiz duels over WebSockets, matchmaking, ELO rating, bot fallback |
| **Certificates** | PDF with QR verification and HMAC anti-fraud (`LMS-YYYY-XXXXXX`) |
| **Telegram** | Bot (`/start`, `/results`, `/leaderboard`, `/streak`), Mini App, login, push notifications |
| **Roles** | Student, teacher, parent, admin — dashboards, groups, analytics (Chart.js), CSV import |

Auth: email + password, Google OAuth, Telegram login. API: REST (JWT) + Swagger.

---

## Tech Stack

**Backend:** Django 5.2, DRF + SimpleJWT, Channels + Daphne, Celery + Redis
**Data:** PostgreSQL 16 (prod) / SQLite (dev), Redis 7
**Frontend:** Server-rendered Django templates + Tailwind, HTMX, Alpine.js — no build step
**AI:** OpenRouter / Groq via OpenAI-compatible client with fallback chain
**Infra:** Docker Compose, Nginx, GHCR, GitHub Actions (CI → Build → Deploy)

---

## Quickstart

```bash
git clone https://github.com/algorithco/lms.git
cd lms

python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

pip install -r requirements/development.txt
cp .env.example .env   # fill SECRET_KEY, GROQ_API_KEY / OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN

python manage.py migrate
python manage.py createsuperuser
python manage.py loaddata apps/games/fixtures/initial_data.json  # optional
python manage.py runserver
```

Bot (separate terminal):

```bash
python manage.py run_bot
```

Docker (full stack: web + db + redis + celery + bot + nginx):

```bash
docker compose up --build
```

Open: `http://localhost:8000` · Swagger: `/api/docs/` · ReDoc: `/api/schema/redoc/`

---

## Configuration

| Key | Purpose |
| --- | ------- |
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django core |
| `DATABASE_URL` / `DB_*` | SQLite (dev) or Postgres (prod) |
| `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `ESSAY_AI_PROVIDER` | AI essay grading |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_NAME` | Bot + Mini App |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google login |
| `CELERY_BROKER_URL`, `REDIS_URL` | Background jobs, channels, cache |

See `.env.example` and `.env.prod.example` for the full list.

---

## Project Structure

```
├── apps/            # accounts, courses, tests, results, essays, games,
│                    # arena, notifications, telegram_app, payments, panel, web, core
├── config/          # settings, urls, asgi/wsgi, celery
├── templates/       # server-rendered HTML
├── static/          # css, js, img (no bundler)
├── requirements/    # base / development / production
├── tests/           # integration suite (300+ tests)
├── deploy/          # nginx, entrypoint, backup, preflight scripts
└── .github/workflows/  # ci.yml, build.yml, deploy.yml
```

---

## Testing & Quality

```bash
python manage.py test tests --verbosity=2
python manage.py check && python manage.py check --deploy
ruff check .
```

---

## Deployment

Production: `grandec.uz` + `admin.grandec.uz` via GHCR image `ghcr.io/algorithco/lms`.

```bash
# push main → CI green → Build (GHCR sha + latest) → Deploy (SSH pull, no build on VPS)
curl -fsS https://grandec.uz/healthz/
```

Details: [`DEPLOYMENT.md`](./DEPLOYMENT.md) · Changes: [`RELEASE_NOTES.md`](./RELEASE_NOTES.md)

---

## Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Commit (`git commit -m 'Add my feature'`)
4. Push and open a Pull Request

---

## License

GPL-3.0 — free software, derivatives must stay open source. See [`LICENSE`](./LICENSE).

**Author:** Komiljon Roziyev · **Telegram:** @grandEducationBot

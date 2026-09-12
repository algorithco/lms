# 🚀 Production Deploy — VPS / Linux

Ona tili va adabiyot LMS platformasini production VPS'ga joylashtirish bo'yicha
to'liq yo'riqnoma.

**Stack:** Django 5 (ASGI/Daphne) · PostgreSQL 16 · Redis 7 · Celery Worker + Beat ·
Telegram Bot · Nginx + Let's Encrypt SSL

---

## 📁 Tayyor fayllar ro'yxati

| Fayl | Vazifasi |
|---|---|
| `Dockerfile` | Multi-stage production image (daphne ASGI, non-root, healthcheck) |
| `docker-compose.prod.yml` | 8 xizmat: web, db, redis, celery-worker, celery-beat, bot, nginx, certbot |
| `deploy/docker-entrypoint.sh` | DB kutish → migrate → collectstatic → daphne/celery/bot |
| `deploy/nginx/nginx.conf` | Aktiv nginx konfiguratsiyasi (init skript uni boshqaradi) |
| `deploy/nginx/nginx-http.conf` | SSL'siz boshlang'ich konfig (ACME challenge uchun) |
| `deploy/nginx/nginx-ssl.conf` | Production HTTPS konfig (`__DOMAIN__` placeholder bilan) |
| `deploy/init-letsencrypt.sh` | SSL sertifikat olish skripti |
| `.env.prod.example` | Production muhit o'zgaruvchilari shabloni |

> **Muhim:** mavjud `docker-compose.yml` (dev) va `nginx.conf` (katalog ildizidagi)
> faqat mahalliy ishlab chiqish uchun — production'da `docker-compose.prod.yml`
> va `deploy/nginx/` ishlatiladi.

---

## 🧭 1. Tayyorgarlik (VPS)

```bash
# 1.1. System paketlari
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates gnupg

# 1.2. Docker + Compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Qayta kirish (logout/login) yoki: newgrp docker

# 1.3. DNS sozlash (VPS panelida)
#   A record:  example.com  →  VPS_IP
#   A record:  www.example.com →  VPS_IP
#   (DNS tarqalishini tekshiring: dig +short example.com)

# 1.4. Firewall (faqat 80/443 ochiq)
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 📦 2. Loyihani ko'chirish

```bash
cd /opt
sudo git clone <REPO_URL> lms_platform
cd lms_platform

# Production env faylini yaratish
cp .env.prod.example .env.prod
nano .env.prod     # ⚠️ BARCHA qiymatlarni to'ldiring (quyida ko'ring)
```

### `.env.prod` — majburiy qiymatlar

| O'zgaruvchi | Tavsif | Misol |
|---|---|---|
| `DJANGO_SECRET_KEY` | Uzun tasodifiy kalit | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | Domenlar (vergul bilan) | `example.com,www.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS originlar | `https://example.com,https://www.example.com` |
| `DB_PASSWORD` | PostgreSQL paroli | kuchli parol |
| `EMAIL_HOST_USER/PASSWORD` | SMTP (parolni tiklash uchun) | Gmail app-parol |
| `TELEGRAM_BOT_TOKEN` | @BotFather tokeni | `123456789:AA...` |
| `OPENROUTER_API_KEY` | AI esse baholash (OpenRouter) | `sk-or-v1-...` |
| `GROQ_API_KEY` | AI esse baholash (Groq) — yoki OpenRouter | `gsk_...` |
| `ESSAY_AI_PROVIDER` | `auto` \| `openrouter` \| `groq` | `auto` |
| `OPENROUTER_FALLBACK_MODELS` | Vergul bilan ajratilgan model zanjiri (ixtiyoriy) | `liquid/lfm-2.5-2.6b:free,nvidia/nemotron-3-super-120b-a12b:free` |
| `SITE_URL` | Public sayt URL | `https://example.com` |

> **AI model zanjiri (default, `config/settings/base.py`):**
> 1) `nvidia/nemotron-3.5-lightning:free` (asosiy) → 2) `liquid/lfm-2.5-2.6b:free`
> → 3) `nvidia/nemotron-3-super-120b-a12b:free` (katalogdagi togri ID).
> Eski `nvidia/nemotron-3-super:free` (va `:free`siz qisqa varianti) OpenRouter'da yo'q — 400 "is not a valid
> model ID" berardi; endi bunday xato bo'lsa ham task o'lmaydi, zanjirdagi
> keyingi modelga o'tiladi (`services.py: _is_invalid_model_error`).
>
> **Deploy'dan keyin tekshirish:**
>
> ```bash
> python manage.py ai_smoke_test                    # konfiguratsiya hisoboti (API so'roqsiz)
> python manage.py ai_smoke_test --validate-models  # IDlarni katalog bilan solishtirish
> python manage.py ai_smoke_test --validate-models --live  # katalog + bitta arzon live so'rov, birinchi OK modelgacha
> ```
>
> `--live` da har bir model uchun `OK model — vaqt — javob` yoki
> `FAIL model — sabab` chop etiladi: `400 ... is not a valid model ID`
> ko'rsangiz, `OPENROUTER_FALLBACK_MODELS` dagi ID'ni OpenRouter dashboard
> bilan solishtiring.

> **Xavfsizlik:** `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
> `DJANGO_CSRF_TRUSTED_ORIGINS` sozlanmagan bo'lsa — Django *ataylab* ishga
> tushmaydi (fail-loud safety net). Bu production xatosini oldini oladi.

## 🔐 3. SSL sertifikat olish (Let's Encrypt)

```bash
cd /opt/lms_platform

# Domen + email bilan skriptni ishga tushiring
./deploy/init-letsencrypt.sh example.com admin@example.com

# (Ishonch hosil qilish uchun avval STAGING rejimda sinab ko'ring:
#  ./deploy/init-letsencrypt.sh example.com admin@example.com --staging
#  Keyin real rejimda qayta ishga tushiring.)
```

Skript nima qiladi:

1. HTTP (SSL'siz) nginx konfigini o'rnatadi va `web` + `nginx` xizmatlarini ishga tushiradi.
2. Certbot orqali `example.com` va `www.example.com` uchun sertifikat so'raydi (webroot usuli).
3. `deploy/nginx/nginx-ssl.conf` dagi `__DOMAIN__` larni haqiqiy domen bilan almashtirib, nginx'ni HTTPS'ga o'tkazadi.
4. Qolgan barcha xizmatlarni (`celery-worker`, `celery-beat`, `bot`) ishga tushiradi.

> Sertifikat avtomatik yangilanadi: `certbot` xizmati compose ichida har 12 soatda
> `certbot renew` ishga tushiradi. Nginx `nginx.conf` dagi `location /.well-known/acme-challenge/`
> orqali challenge'ni qabul qiladi.

## ▶️ 4. Stackni boshqarish

```bash
cd /opt/lms_platform

# Holat
docker compose -f docker-compose.prod.yml ps

# Loglar
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f celery-worker
docker compose -f docker-compose.prod.yml logs -f bot

# Yangilash (kod o'zgargandan keyin)
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Restart
docker compose -f docker-compose.prod.yml restart

# To'xtatish
docker compose -f docker-compose.prod.yml down        # konteynerlarni to'xtatadi (data saqlanadi)
docker compose -f docker-compose.prod.yml down -v     # ⚠️ VOLUMESNI HAM O'CHIRADI (data yo'qoladi!)
```

## 🧪 5. Tekshirish

```bash
# Healthcheck (web konteyneri ichidan, DB aloqasini tekshiradi)
curl -fsS https://example.com/healthz/
# → {"status": "ok", "db": true}

# Admin panel
# https://example.com/admin/  (avval superuser yarating:)
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Celery ishlayotganini tekshirish
docker compose -f docker-compose.prod.yml exec web python -c "
from config.celery import app
i = app.control.inspect()
print('Workers:', list(i.ping() or {}))
"

# WebSocket (Arena) — browser konsolida:
# new WebSocket('wss://example.com/ws/arena/')
```

## 💾 6. Zaxiralash (backup)

```bash
# PostgreSQL backup
docker compose -f docker-compose.prod.yml exec db pg_dump -U lms_user lms_platform \
    | gzip > /opt/backups/lms_$(date +%F).sql.gz

# Media fayllar
docker run --rm -v lms-platform-prod_media_volume:/media -v /opt/backups:/backup \
    alpine tar czf /backup/media_$(date +%F).tar.gz -C /media .

# Cron'ga qo'shish (har kuni soat 4:00):
# 0 4 * * * cd /opt/lms_platform && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U lms_user lms_platform | gzip > /opt/backups/lms_$(date +\%F).sql.gz
```

## 🛠️ 7. Muammolar (troubleshooting)

| Alomat | Yechim |
|---|---|
| `SECRET_KEY must be set...` | `.env.prod` da `DJANGO_SECRET_KEY` to'ldirilganligini tekshiring |
| `ALLOWED_HOSTS must be set...` | `DJANGO_ALLOWED_HOSTS` ni vergul bilan yozing |
| `CSRF_TRUSTED_ORIGINS must be set...` | `DJANGO_CSRF_TRUSTED_ORIGINS` ga `https://domen` qo'shing |
| CSRF 403 (form POST) | `DJANGO_CSRF_TRUSTED_ORIGINS` da domen borligini tekshiring |
| `DB_PASSWORD must be set...` | Compose `.env.prod` da `DB_PASSWORD` yo'q |
| 502 Bad Gateway | `docker compose logs web` — daphne ishga tushganini tekshiring |
| WebSocket ulanmayapti | Nginx `Upgrade` headerlari `nginx.conf` da borligini tekshiring |
| Bot ishlamayapti | `TELEGRAM_BOT_TOKEN` to'g'riligi; `docker compose logs bot` |
| Sertifikat muddati | `certbot` xizmati har 12 soatda yangilaydi; nginx config'da `renew` joyi bor |

## 🔍 8. Xavfsizlik eslatmalari

- `SECURE_PROXY_SSL_HEADER` o'rnatilgan — Django Nginx orqasida HTTPS'ni to'g'ri biladi.
- `SECURE_SSL_REDIRECT` o'chirilgan, chunki **Nginx** HTTP→HTTPS qayta yo'naltirishni
  o'zi qiladi (Django darajasidagi redirect konteyner ichidagi healthcheck'ni buzardi).
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `HSTS` — yoqilgan.
- Konteyner **non-root** (`app` user) sifatida ishlaydi.
- `PORT` o'zgaruvchisi orqali daphne porti boshqariladi.
- PostgreSQL va Redis portlari tashqariga **ochilmaydi** (faqat `expose` — ichki tarmoq).

## ⚙️ 9. Telegram bot: webhook rejim (ixtiyoriy)

Compose'da bot **long polling** rejimda ishlaydi (`python manage.py run_bot`) —
bu eng sodda va ishonchli variant va **tavsiya etiladi**. Xohlasangiz webhook'ga
o'tishingiz mumkin (webhook → Nginx → Django `telegram_webhook_view`):

```bash
# 9.1. Bot polling konteynerini to'xtatish (webhook bilan birga ishlamaydi!)
docker compose -f docker-compose.prod.yml up -d --scale bot=0

# 9.2. .env.prod da TELEGRAM_WEBHOOK_MODE=true va kuchli
#      TELEGRAM_WEBHOOK_SECRET ni o'rnating, web konteynerini qayta ishga tushiring.
#      Secret yo'q bo'lsa webhook 503 qaytaradi va deploy check xato beradi.

# 9.3. Telegram'ga webhook URL'ni ro'yxatdan o'tkazish
#     (Django URL'ni avtomatik oladi: /api/notifications/telegram/webhook/)
docker compose -f docker-compose.prod.yml exec web \
    python manage.py setup_bot_webhook --domain example.com
```

Telegram identifikatorlarini yangilashda eski `telegram_chat_id` qiymatlari
o'chirilmaydi. Ular tasdiqlanmaguncha TMA 409 qaytaradi va bot hisobga
kiritmaydi. **Deploydan oldin** quyidagini bajaring:

```bash
python manage.py migrate
python manage.py reconcile_telegram_identity --list
```

Parolli veb hisob egasi `/api/auth/telegram/connect/` orqali 10 daqiqalik
bot havolasini oladi va o'z Telegram chatida `/start link_...` bilan
tasdiqlaydi. Veb paroli yo'q eski bot hisoblari uchun administrator mustaqil
egalik dalilini tekshiradi; faqat shundan keyin mavjud **aynan shu** juftlikni
`python manage.py reconcile_telegram_identity --user-id ID --telegram-id TG_ID --evidence TICKET`
bilan tasdiqlaydi. Eski username yoki faqat bazadagi ID egalik dalili emas.
Qayta `--list` bo'sh chiqmaguncha Telegramga bog'langan eski hisoblar uchun
o'tishni tugallangan deb hisoblamang.

> ℹ️ **AI esse baholash async ishlaydi**: web-sahifadagi submit va vaqt-tugash
> yo'llari LLM chaqiruvini Celery worker'ga yuklaydi (`essays.grade_submission`),
> web thread hech qachon bloklanmaydi. Worker ishlamasa, broker-down fallback
> tufayli baholash background thread'da bajariladi (Cloudflare Tunnel ortida
> Celery/Redis ishlamaganda ham request hech qachon LLM'ni KUTMAYDI — bu
> `502 Bad Gateway`'ning ildiz sababi edi).
> Redis pool'lari chegaralangan (Channels `capacity=100`, Celery
> `CELERY_REDIS_MAX_CONNECTIONS=20`, cache `max_connections=100`) — yuqori
> trafik botning Redis ulanishlarini quritib qo'ya olmaydi.
>
> **Cloudflare Tunnel + daphne loglari haqida:**
> - `failed to accept QUIC stream: timeout: no recent network activity` —
>   bu daphne xatosi EMAS, `cloudflared` tunnel'ning QUIC (HTTP/3) ulanishi
>   vaqtinchalik uzilishi. Tunnel o'zi qayta ulanadi. Dohni kamaytirish uchun
>   tunnel'ni `--protocol http2` bilan ishga tushirish mumkin.
> - `Application instance ... took too long to shut down and was killed` —
>   daphne restart bo'lganda in-flight request'lar 10s (default) ichida
>   tugamay qolgan. `--application-close-timeout 60` bilan hal qilindi
>   (`docker-compose.prod.yml`), submit endpoint'lari asinxron bo'lgani
>   uchun endi request'lar o'zi ham tez.
>
> **Asinxron shartnoma (frontend/TMA uchun):**
> - Web: submit → `submit_result_partial.html` spinner → redirect
>   `/essays/result/<id>/` → sahifa `/essays/api/<id>/status/` endpointini
>   poll qiladi (3s) va `status` o'zgarganda reload qiladi.
> - TMA API: `POST /api/telegram/essays/<id>/submit/` → darhol
>   `202 {"status": "processing", "poll_after": 3}` → client
>   `GET /api/telegram/essays/<id>/result/` ni `poll_after` sekunddan keyin
>   tekshirib turadi (`status == "pending"` bo'lsa hali ishlanmoqda).
> - Celery/Redis ishlamasa: baholash avtomatik background thread'ga tushadi
>   (`start_thread_grading`), retry backoff `ESSAY_THREAD_RETRY_BACKOFF`
>   bilan sozlanadi (default 5/10/15s, 3 urinish).

> ⚠️ Bir vaqtning o'zida polling VA webhook ishlamasligi kerak — Telegram faqat
> bitta manbadan update qabul qiladi. Webhook'ga qaytish uchun: `up -d --scale bot=1`
> va webhook'ni o'chiring (`setup_bot_webhook --remove`).

---

✅ **Tayyor!** Sayt `https://example.com` da ochiq, Arena WebSocket'lari ishlaydi,
Celery periodic vazifalari (test timeout'lari, kunlik maintenance, esse auto-submit)
ishlaydi, Telegram bot ishga tushgan.

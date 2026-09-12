# 📚 ONA TILI & ADABIYOT LMS — TO'LIQ FOYDALANISH YO'RIQNOMASI

> **Platforma**: AI-powered o'qish platformasi (Web + Telegram Bot + Real-time Arena)
> **Versiya**: v1.1.1 | **Muallif**: Komiljon Roziyev
> **Repo**: https://github.com/rozievkomiljon/ona-tili

---

## 📖 MUNDARIJA

1. [Tizim talablari](#1-tizim-talablari)
2. [Loyihani yuklab olish](#2-loyihani-yuklab-olish)
3. [Muhit sozlamalari (.env.prod)](#3-muhit-sozlamalari-envprod)
4. [Ubuntu VPS'da deploy qilish](#4-ubuntu-vpsda-deploy-qilish)
5. [SSL sertifikat o'rnatish](#5-ssl-sertifikat-ornatish)
6. [Deploy'dan keyingi tekshiruvlar](#6-deploydan-keyingi-tekshiruvlar)
7. [Admin yaratish va boshqaruv](#7-admin-yaratish-va-boshqaruv)
8. [Platformaning barcha bo'limlari](#8-platformaning-barcha-bolimlari)
9. [Telegram Bot sozlash](#9-telegram-bot-sozlash)
10. [Kundalik boshqaruv buyruqlari](#10-kundalik-boshqaruv-buyruqlari)
11. [Zaxira nusxa (backup)](#11-zaxira-nusxa-backup)
12. [Yangilash (update) tartibi](#12-yangilash-update-tartibi)
13. [Muammolar va yechimlar (troubleshooting)](#13-muammolar-va-yechimlar-troubleshooting)
14. [Xavfsizlik qoidalari](#14-xavfsizlik-qoidalari)

---

## 1. Tizim talablari

### VPS server (tavsiya etiladi):
| Resurs | Minimal | Tavsiya etilgan |
|---|---|---|
| OS | Ubuntu 22.04 / 24.04 | Ubuntu 24.04 LTS |
| CPU | 2 yadro | 4 yadro |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| Trafik | 1 TB | cheksiz |

> Platforma 7 xil konteyner ishlatadi (web, bot, celery ×2, redis, postgres, nginx) — shuning uchun 2 GB'dan kam RAM yetmaydi.

### Domain:
- Domeningiz bo'lishi kerak (masalan: `onatili.uz`)
- Domenning **A yozuvi (A record)** server IP manzilingizga yo'naltirilgan bo'lishi shart
- `www` subdomen uchun ham **CNAME yoki A yozuvi** kerak (SSL ikkalasiga beriladi)

### Dasturiy ta'minot (serverga o'rnatiladi):
- Docker + Docker Compose v2 — barcha qolgan narsalar konteynerlarda

---

## 2. Loyihani yuklab olish

### 2.1. Serverga ulanish:
```bash
ssh root@SERVER_IP
```

### 2.2. Docker o'rnatish (agar bo'lmasa):
```bash
# Docker
curl -fsSL https://get.docker.com | sh

# Ishga tushirish va avtomatik start
sudo systemctl enable --now docker

# Docker versiyasini tekshirish
docker --version          # 24+ bo'lishi kerak
docker compose version    # v2.x bo'lishi kerak
```

### 2.3. Oddiy foydalanuvchi yaratish (xavfsizlik uchun root emas):
```bash
adduser deploy
usermod -aG docker deploy
su - deploy
```

### 2.4. Loyihani klonlash:
```bash
cd /opt
sudo git clone https://github.com/rozievkomiljon/ona-tili.git lms
sudo chown -R deploy:deploy /opt/lms
cd /opt/lms
```

> Repo **private** bo'lsa: GitHub'da `Settings → Developer settings → Personal access tokens → Fine-grained tokens` orqali token yarating va clone paytida undan foydalaning:
> ```bash
> git clone https://TOKEN@github.com/rozievkomiljon/ona-tili.git lms
> ```

### 2.5. Kerakli papkalar va ruxsatlar:
```bash
mkdir -p deploy/logs
chmod +x deploy/init-letsencrypt.sh deploy/docker-entrypoint.sh
```

---

## 3. Muhit sozlamalari (.env.prod)

### 3.1. Fayl yaratish:
```bash
cp .env.prod.example .env.prod
nano .env.prod
```

### 3.2. Quyidagi maydonlarni ALBATTA o'zgartiring:

| O'zgaruvchi | Nima qilish kerak |
|---|---|
| `DJANGO_SECRET_KEY` | Yangi tasodifiy kalit (quyida generatsiya buyrug'i) |
| `DB_PASSWORD` | Kuchli PostgreSQL paroli |
| `TELEGRAM_BOT_TOKEN` | @BotFather'dan olingan haqiqiy token |
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys dan olingan kalit |
| `EMAIL_HOST_PASSWORD` | Gmail "App Password" (oddiy parol ishlamaydi!) |
| `CERTIFICATE_SECRET_KEY` | Sertifikat imzosi uchun alohida kalit |
| `DJANGO_ALLOWED_HOSTS` | Domeningiz: `onatili.uz,www.onatili.uz` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://onatili.uz,https://www.onatili.uz` |
| `SITE_URL` | `https://onatili.uz` |
| `CORS_ALLOWED_ORIGINS` | `https://onatili.uz` |

### 3.3. Kuchli kalit generatsiya qilish:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# yoki
openssl rand -base64 48
```

> ⚠️ **MUHIM (v1.1.1 dan boshlab)**: `DJANGO_SECRET_KEY` kamida 32 belgidan iborat bo'lishi va "change-me", "your-" kabi so'zlarni o'z ichiga olmasligi kerak. Aks holda server **umuman ishga tushmaydi** (bu xavfsizlik uchun ataylab qilingan).

### 3.4. Gmail "App Password" olish:
1. https://myaccount.google.com/security ga kiring
2. "2-Step Verification" ni yoqing (bo'lmasa)
3. https://myaccount.google.com/apppasswords ga o'ting
4. "Mail" uchun yangi parol yarating
5. Shu 16 belgili parolni `EMAIL_HOST_PASSWORD` ga qo'ying

### 3.5. Telegram bot token olish:
1. Telegram'da @BotFather ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomi va username'ini kiriting
4. Token'ni nusxalab `TELEGRAM_BOT_TOKEN` ga qo'ying
5. `TELEGRAM_BOT_NAME` ga bot username'ini (">@sizning_bot" ko'rinishida) yozing

### 3.6. .env.prod faylini himoyalash:
```bash
chmod 600 .env.prod
```

---

## 4. Ubuntu VPS'da deploy qilish

### 4.1. Birinchi ishga tushirish (SSL'siz, faqat tekshirish uchun):
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d db redis
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```
> `db` va `redis` "healthy" holatga o'tishini kutib turing (30 soniya).

### 4.2. Barcha xizmatlarni ishga tushirish:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

Bu buyruq quyidagi 7 ta konteynerni ishga tushiradi:
| Konteyner | Vazifasi |
|---|---|
| `web` | Django + Daphne (HTTP + WebSocket) |
| `db` | PostgreSQL 16 ma'lumotlar bazasi |
| `redis` | Cache + Celery broker + Channels |
| `celery-worker` | Fon vazifalari (AI tekshirish, PDF, xabarlar) |
| `celery-beat` | Davriy vazifalar (timeout, avto-yuborish) |
| `bot` | Telegram bot (polling) |
| `nginx` | Reverse proxy + SSL + static fayllar |

### 4.3. Loglarni kuzatish:
```bash
# Barcha loglar
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f

# Faqat web
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f web

# Faqat bot
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f bot
```

### 4.4. Qisqa alias yaratish (ixtiyoriy, qulaylik uchun):
```bash
echo 'alias lms="docker compose --env-file /opt/lms/.env.prod -f /opt/lms/docker-compose.prod.yml"' >> ~/.bashrc
source ~/.bashrc
# Endi shunday ishlatish mumkin:
lms ps
lms logs -f web
lms restart bot
```

---

## 5. SSL sertifikat o'rnatish

> ⚠️ SSL'dan OLDIN domen A yozuvi server IP'siga yo'naltirilgan bo'lishi SHART.

### 5.1. Avtomatik o'rnatish (tavsiya etiladi):
```bash
cd /opt/lms

# Birinchi marta: TEST rejimida sinash (cheklangan, lekin xavfsiz)
./deploy/init-letsencrypt.sh onatili.uz siz@email.com --staging

# Agar muvaffaqiyatli bo'lsa — HAQIQIY sertifikat:
./deploy/init-letsencrypt.sh onatili.uz siz@email.com
```

Bu skript avtomatik:
1. HTTP nginx konfiguratsiyasini o'rnatadi
2. Let's Encrypt'dan sertifikat so'raydi
3. HTTPS konfiguratsiyasini o'rnatadi
4. Nginx'ni qayta yuklaydi
5. Butun stack'ni ishga tushiradi

### 5.2. Sertifikat yangilanishi — AVTOMATIK:
- `certbot` konteyneri har 12 soatda `certbot renew` ishga tushiradi
- Hech qanday qo'lda aralashuv kerak emas

### 5.3. SSL ishlashini tekshirish:
```bash
curl -I https://onatili.uz
# HTTP/2 200 va ssl_certificate ko'rinishi kerak

# SSL rating: https://www.ssllabs.com/ssltest/
```

---

## 6. Deploy'dan keyingi tekshiruvlar

### 6.1. Barcha konteynerlar holati:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```
Har bir konteyner `Up (healthy)` holatida bo'lishi kerak.

### 6.2. Asosiy endpoint'lar:
```bash
# Sog'liq tekshiruvi
curl https://onatili.uz/healthz/
# Natija: {"status": "ok", "db": true}

# Bosh sahifa
curl -I https://onatili.uz/

# Admin panel
curl -I https://onatili.uz/admin/
```

### 6.3. WebSocket (Arena) tekshiruvi:
Brauzerda `https://onatili.uz/arena/` oching → F12 → Console:
```
WebSocket connection to 'wss://onatili.uz/ws/...' established
```
ko'rinishidagi xato BO'Lmasligi kerak.

### 6.4. Telegram bot javob berishini tekshirish:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs bot | tail -20
```
Xatolar yo'q bo'lishi kerak. Bot'ga Telegram'da `/start` yuborib ko'ring.

### 6.5. Ma'lumotlar bazasi migratsiyalari:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py migrate --check
```
"Migrations to apply" xabari chiqmasligi kerak.

---

## 7. Admin yaratish va boshqaruv

### 7.1. Superuser yaratish:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Username, email va parol so'raydi.

### 7.2. Obuna planlarini yuklash (ALBATTA birinchi marta):
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py setup_plans
```
4 ta plan yaratiladi: Bepul / Starter / Pro / Premium.

### 7.3. Admin panelga kirish:
- Django admin: `https://onatili.uz/admin/`
- In-app admin panel: `https://onatili.uz/control-panel/` (faqat `is_staff=True` yoki `role=admin` foydalanuvchilar uchun)

### 7.4. Test ma'lumotlar yaratish (ixtiyoriy):
Admin panelda:
1. **Tests** bo'limida test yarating
2. Har bir testga savollar qo'shing (MCQ, open answer, passage)
3. **Essay Topics** bo'limida esse mavzulari yarating
4. **Users** bo'limida foydalanuvchilarni boshqaring

---

## 8. Platformaning barcha bo'limlari

### 🌐 Ommaviy sahifalar:
| URL | Tavsif |
|---|---|
| `/` | Bosh sahifa (landing, 3 tilli) |
| `/login/` | Kirish |
| `/register/` | Ro'yxatdan o'tish |
| `/password-reset/` | Parolni tiklash |
| `/subscribe/` | Obuna planlari |
| `/healthz/` | Healthcheck (JSON) |

### 👨‍🎓 O'quvchi paneli:
| URL | Tavsif |
|---|---|
| `/dashboard/` | Asosiy dashboard |
| `/tests/` | Testlar ro'yxati |
| `/tests/<id>/take/` | Testni ishlash |
| `/results/` | Natijalarim |
| `/results/<id>/` | Natija tafsiloti |
| `/certificates/` | Sertifikatlarim |
| `/games/` | O'yinlar (Imlo Minolari, Gazal Puzzle, Lug'at Match) |
| `/arena/` | 1v1 Arena lobbisi |
| `/arena/<room>/` | Jonli duel xonasi |
| `/essay-leaderboard/` | Esse reytingi |

### 👨‍🏫 O'qituvchi paneli:
| URL | Tavsif |
|---|---|
| `/teacher/dashboard/` | O'qituvchi dashboard |
| `/teacher/analytics/` | Statistika va grafiklar |
| `/manage-teachers/` | O'qituvchilarni boshqarish |
| `/groups/` | Guruhlar ro'yxati |
| `/groups/create/` | Guruh yaratish |

### 💳 To'lovlar:
| URL | Tavsif |
|---|---|
| `/subscribe/` | 4 ta plan ko'rish |
| `/subscribe/<id>/subscribe/` | To'lov ko'rsatmalari (karta + Telegram) |
| `/subscribe/my/` | Mening obunam |
| `/api/notifications/telegram/webhook/` | Bot webhook (agar webhook rejimida) |

### 🛡 Admin:
| URL | Tavsif |
|---|---|
| `/admin/` | Django admin (to'liq boshqaruv) |
| `/control-panel/` | In-app admin panel (test/esse/foydalanuvchi CRUD) |
| `/api/docs/` | Swagger API hujjatlari |

### 📱 Telegram Mini App:
| URL | Tavsif |
|---|---|
| `/tma/` | Bot ichidan ochiladigan mini ilova |

---

## 9. Telegram Bot sozlash

### 9.1. Bot rejimini tanlash:

**A) Polling rejimi (standart, tavsiya etiladi):**
- `docker-compose.prod.yml` dagi `bot` xizmati avtomatik ishlaydi
- Hech qanday qo'shimcha sozlama kerak emas
- Domen kerak emas, bot mustaqil ishlaydi

**B) Webhook rejimi (kengaroq, HTTPS kerak):**
```bash
# Webhook o'rnatish
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web \
    python manage.py setup_bot_webhook --url https://onatili.uz/api/notifications/telegram/webhook/

# Webhook'ni o'chirish (polling'ga qaytish uchun)
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web \
    python manage.py setup_bot_webhook --remove
```
> Webhook ishlatilsa, `bot` konteynerini to'xtatib qo'yish kerak (ikkalasi bir vaqtda ishlamaydi):
> ```bash
> docker compose --env-file .env.prod -f docker-compose.prod.yml stop bot
> ```

### 9.2. Bot foydalanuvchilari bilan sinxronizatsiya:
- Bot orqali ro'yxatdan o'tgan foydalanuvchilar `apps.accounts` ga yoziladi
- Web'da `/login/` sahifasida "Telegram orqali kirish" tugmasi bor
- Ikkalasi bir xil ma'lumotlar bazasidan foydalanadi

### 9.3. Bot buyruqlari:
- `/start` — botni ishga tushirish
- `/help` — yordam
- Test ishlash, esse yuborish, reyting — bot menyusidan

---

## 10. Kundalik boshqaruv buyruqlari

Quyidagi buyruqlar `/opt/lms` papkasida bajariladi (`lms` alias o'rnatilgan bo'lsa qisqaroq):

### Konteynerlarni boshqarish:
```bash
# Holat
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# To'xtatish / ishga tushirish / qayta ishga tushirish
docker compose --env-file .env.prod -f docker-compose.prod.yml stop
docker compose --env-file .env.prod -f docker-compose.prod.yml start
docker compose --env-file .env.prod -f docker-compose.prod.yml restart

# Bitta xizmatni qayta ishga tushirish
docker compose --env-file .env.prod -f docker-compose.prod.yml restart web
docker compose --env-file .env.prod -f docker-compose.prod.yml restart bot

# Butunlay o'chirish (ma'lumotlar SAQLANADI - volume'larda)
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# Ma'lumotlar bilan birga o'chirish (DIQQAT! BAZANI O'CHIRADI)
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v
```

### Loglar:
```bash
# Oxirgi 100 qator
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail 100 web

# Real vaqtda kuzatish
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f web
```

### Konteyner ichida buyruq bajarish:
```bash
# Django shell
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py shell

# Bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web bash

# PostgreSQL
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db psql -U lms_user -d lms_platform
```

### Kerakli management buyruqlar:
```bash
# Migratsiyalar
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py migrate

# Statik fayllar
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py collectstatic

# Obuna planlarini yangilash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py setup_plans

# Sertifikatlarni generatsiya qilish
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py generate_missing_certificates

# Muddati o'tgan essalarni avto-yuborish (celery-beat avtomatik qiladi)
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py auto_submit_expired_essays
```

---

## 11. Zaxira nusxa (backup)

### 11.1. Ma'lumotlar bazasini zaxiralash:
```bash
# Backup yaratish
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
    pg_dump -U lms_user lms_platform > backup_$(date +%Y%m%d_%H%M%S).sql

# Tiklash (DIQQAT: mavjud ma'lumotlarni almashtiradi)
cat backup_20260909.sql | docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
    psql -U lms_user lms_platform
```

### 11.2. Media fayllarni zaxiralash:
```bash
docker run --rm -v lms-platform-prod_media_volume:/data -v $(pwd):/backup \
    alpine tar czf /backup/media_backup_$(date +%Y%m%d).tar.gz -C /data .
```

### 11.3. Avtomatik kunlik backup (cron):
```bash
crontab -e
# Quyidagi qatorni qo'shing (har kuni 03:00 da):
0 3 * * * cd /opt/lms && docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_dump -U lms_user lms_platform > /opt/backups/db_$(date +\%Y\%m\%d).sql 2>>/opt/backups/backup.log
```

```bash
# Backup papkasi yaratish
mkdir -p /opt/backups
chmod 700 /opt/backups
```

### 11.4. Zaxiralarni serverdan tashqariga ko'chirish:
```bash
scp root@SERVER_IP:/opt/backups/db_20260909.sql ./
# yoki boshqa serverga
rsync -avz /opt/backups/ user@backup-server:/backups/lms/
```

---

## 12. Yangilash (update) tartibi

Kod o'zgarganda yangi versiyani deploy qilish:

```bash
cd /opt/lms

# 1. Eng yangi kodni olish
git pull origin main

# 2. Agar .env.prod.example yangilangan bo'lsa, farqlarni solishtirish
diff .env.prod.example .env.prod

# 3. Qayta build va restart (zero-downtime'ga yaqin)
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 4. Migratsiyalar (web konteyner entrypoint'da avtomatik bajaradi,
#    lekin qo'lda tekshirish mumkin)
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py migrate

# 5. Loglarni tekshirish
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f --tail 50
```

### Muayyan versiyaga qaytish (rollback):
```bash
git fetch --tags
git checkout v1.1.1    # yoki boshqa versiya
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

---

## 13. Muammolar va yechimlar (troubleshooting)

### ❌ Konteyner ishga tushmaydi
```bash
# Logini ko'rish
docker compose --env-file .env.prod -f docker-compose.prod.yml logs web

# Ko'p uchraydigan sabablar:
# 1. .env.prod'da majburiy maydon to'ldirilmagan (SECRET_KEY, DB_PASSWORD, ...)
#    Yechim: Xato xabaridagi o'zgaruvchini to'ldiring
# 2. DB hali tayyor emas — 30 soniya kuting
# 3. Port band — `sudo ss -tlnp | grep -E ":80|:443"` bilan tekshiring
```

### ❌ `SECRET_KEY must be a long random value...` xatosi
- `.env.prod` dagi `DJANGO_SECRET_KEY` zaif yoki placeholder
- Yechim: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` bilan yangi kalit yarating

### ❌ Sayt ochilmaydi (connection refused)
```bash
# Nginx holatini tekshirish
docker compose --env-file .env.prod -f docker-compose.prod.yml logs nginx

# Firewall
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Domen to'g'ri IP'ga ishora qilayotganini tekshirish
dig +short onatili.uz   # server IP'ni qaytarishi kerak
```

### ❌ SSL sertifikat chiqmayapti
- Domen hali yangi bo'lsa DNS tarqalishini kutib turing (1-24 soat)
- `--staging` rejimida sinab ko'ring
- Rate limit: Let's Encrypt haftada 5 tadan ko'p sertifikat bermaydi — staging rejimida mashq qiling
- 80-port ochiq va nginx ishlayotganini tekshiring

### ❌ WebSocket (Arena) ishlamayapti
```bash
# Nginx konfiguratsiyasida upgrade sarlavhalari borligini tekshirish
grep -A 3 "Upgrade" deploy/nginx/nginx-ssl.conf
# Natijada quyidagilar bo'lishi kerak:
# proxy_set_header Upgrade $http_upgrade;
# proxy_set_header Connection $connection_upgrade;
```

### ❌ Telegram bot javob bermayapti
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs bot | tail -30
# Token to'g'riligini tekshirish:
curl https://api.telegram.org/bot<SIZNING_TOKEN>/getMe
```

### ❌ AI esse tekshirilmayapti
```bash
# OPENROUTER_API_KEY to'g'riligini tekshirish
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web \
    python -c "from django.conf import settings; print(settings.ESSAY_AI_PROVIDER, bool(settings.OPENROUTER_API_KEY))"
```

### ❌ Disk to'la
```bash
df -h
# Docker zaxiralarni tozalash
docker system prune -af --volumes   # DIQQAT: ishlatilmayotgan hamma narsani o'chiradi
```

### ❌ Web sayt sekin ishlayapti
```bash
# Resurslarni kuzatish
docker stats
# RAM kam bo'lsa — swap qo'shish:
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 14. Xavfsizlik qoidalari

1. ✅ **`.env.prod` hech qachon gitga qo'shilmaydi** — `.gitignore`da turibdi
2. ✅ SSH kalit orqali ulaning, parolni o'chirib qo'ying:
   ```bash
   sudo nano /etc/ssh/sshd_config
   # PasswordAuthentication no
   sudo systemctl restart sshd
   ```
3. ✅ Firewall yoqing:
   ```bash
   sudo ufw default deny incoming
   sudo ufw allow ssh
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
4. ✅ Fail2ban o'rnating (brute-force himoyasi):
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable --now fail2ban
   ```
5. ✅ Docker va tizimni muntazam yangilab turing:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
6. ✅ Backup'ni har kuni tekshiring va bir marta oyda tiklashni sinab ko'ring
7. ✅ Server loglarini kuzatib turing:
   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail 100 web | grep -i error
   ```

---

## 📞 Qo'llab-quvvatlash

- **Telegram**: @rozievkomiljon
- **Instagram**: https://www.instagram.com/rozievkomiljon/
- **Email**: kruziyev0@gmail.com
- **Repo**: https://github.com/rozievkomiljon/ona-tili

---

*Yo'riqnoma v1.1.1 versiyasi uchun tayyorlandi — 2026-yil sentyabr.*

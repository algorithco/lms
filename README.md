# 🎓 LMS Platform — Ona Tili va Adabiyot Ta'lim Platformasi

> O'zbek tili va adabiyoti bo'yicha zamonaviy ta'lim platformasi. Testlar, o'yinlar, AI-asosidagi esse baholash, Telegram bot va boshqa ko'plab imkoniyatlar.

![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-0088cc?style=flat&logo=telegram)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Imkoniyatlar

### 📝 Test Tizimi
- Avtomatik baholash
- Taymer bilan test topshirish
- Savollarni aralashtirish
- Natijalar tahlili

### ✍️ Esse Baholash (AI)
- **Groq API** orqali AI baholash
- **12 mezonli** batafsil baholash
- **75 ballik** shkalaga konvertatsiya
- Mavzuga moslikni tekshirish
- O'qituvchi qo'lda tekshirish imkoniyati

### 🎮 O'yinlar (Gamification)
- **Imlo Minalari** — imlo xatolarini topish
- **G'azal Puzzle** — she'rlarni tartibga solish
- **Lug'at Match** — eski-zamonaviy so'zlarni match qilish
- **XP, tanga, badgelar** tizimi
- **Kunlik streak** — har kuni kirish mukofoti
- **Haftalik challenge'lar**

### 🤖 Telegram Bot
- `/start` — Botni ishga tushirish
- `/results` — Barcha natijalar (test + esse)
- `/leaderboard` — Reyting
- `/streak` — Kunlik streak
- `/daily` — Kunlik vazifalar
- `/tests` — Mavjud testlar
- `/essays` — Esse mavzulari

### 👨‍🏫 O'qituvchi Paneli
- Dashboard (Chart.js grafiklar)
- Talabalar guruhlari
- Esse tekshirish navbati
- Batafsil statistika

### 🔐 Kirish
- Email + Parol
- Telegram orqali kirish

## 🚀 O'rnatish

### 1. Repo'ni clone qilish

```bash
git clone https://github.com/USERNAME/lms-platform.git
cd lms-platform
```

### 2. Virtual environment yaratish

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements/development.txt
```

### 4. .env faylini yaratish

```bash
cp .env.example .env
```

Keyin `.env` faylini oching va quyidagilarni to'ldiring:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# Groq API (esse baholash uchun)
GROQ_API_KEY=gsk_your-groq-key-here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

### 5. Migratsiyalarni ishga tushirish

```bash
python manage.py migrate
```

### 6. Superuser yaratish

```bash
python manage.py createsuperuser
```

### 7. Fixture'larni yuklash (ixtiyoriy)

```bash
python manage.py loaddata apps/games/fixtures/initial_data.json
```

### 8. Serverni ishga tushirish

```bash
python manage.py runserver
```

### 9. Telegram botni ishga tushirish (alohida terminalda)

```bash
python manage.py run_bot
```

## 🐳 Docker bilan ishga tushirish

```bash
docker-compose up --build
```

## 📁 Loyiha tuzilishi

```
lms_platform/
├── apps/
│   ├── accounts/       # Foydalanuvchilar, auth
│   ├── courses/        # Kurslar, guruhlar
│   ├── tests/          # Testlar, savollar
│   ├── results/        # Natijalar, sertifikatlar
│   ├── essays/         # Esse baholash (AI)
│   ├── games/          # O'yinlar, gamification
│   ├── notifications/  # Telegram bot, email
│   ├── arena/          # Quiz Arena (1v1)
│   └── telegram_app/   # Telegram Mini App
├── config/             # Django sozlamalari
├── templates/          # HTML shablonlar
├── static/             # CSS, JS fayllar
├── requirements/       # Python kutubxonalari
├── manage.py
└── .env.example
```

## 🔧 Sozlamalar

### Groq API (Esse Baholash)

1. **https://console.groq.com** → kirib kiring
2. API key yarating
3. `.env` fayliga qo'shing: `GROQ_API_KEY=gsk_...`

### Telegram Bot

1. **@BotFather** ga `/newbot` yuboring
2. Bot nomini kiriting
3. Berilgan token'ni `.env` ga qo'shing: `TELEGRAM_BOT_TOKEN=...`

## 🧪 Testlar

```bash
python manage.py test
```

## 📊 API Documentation

Server ishga tushgandan keyin:
- **Swagger UI:** http://localhost:8000/api/docs/
- **ReDoc:** http://localhost:8000/api/schema/redoc/

## 🤝 Hissa qo'shish

1. Fork qiling
2. Branch yarating (`git checkout -b feature/amazing-feature`)
3. Commit qiling (`git commit -m 'Add amazing feature'`)
4. Push qiling (`git push origin feature/amazing-feature`)
5. Pull Request oching

## 📄 Litsenziya

MIT License — bepul ishlatish mumkin.

---

**Muallif:** Komiljon Roziyev
**Telegram:** @grandEducationBot

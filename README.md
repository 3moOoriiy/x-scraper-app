# 🐦 X Posts Scraper

استخراج وتحليل البوستات من حسابات X (Twitter) عبر اسم الحساب، الكلمات المفتاحية، أو الهاشتاجات.

A web app for extracting and analyzing posts from X (Twitter) — by username, keyword, or hashtag.

---

## ✨ المميزات

- 🔍 **3 أنواع بحث**: اسم الحساب · كلمة مفتاحية · هاشتاج
- 📅 **فلتر تاريخ مرن** (Date range picker)
- 📊 **بيانات مكتملة**: caption · likes · retweets · comments · views · صور · فيديوهات
- 💾 **تصدير CSV / Excel**
- 🌗 **Light + Dark themes**
- 🌐 **عربي + English**
- 🔐 **تسجيل دخول** بـ email/password
- ⚡ **Cache 2 دقيقة** للنتائج المتكررة (فوري)

---

## 🛠️ Stack

| Layer | Technology |
|------|-----------|
| Frontend | React 18, Vite 6, recharts, Three.js |
| Backend  | FastAPI, Selenium, requests, pandas |
| Deploy   | Render (Docker for backend, Static for frontend) |

---

## 🚀 التشغيل محلياً (Local development)

### 1. Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python main.py
```
يشتغل على `http://127.0.0.1:8000`

### 2. Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
يشتغل على `http://localhost:3000`

### 3. الكوكيز
عدّل `backend/scraper.py` أو حط `X_AUTH_TOKEN` و `X_CT0` كـ env vars.

---

## 🌐 النشر على Render

المشروع جاهز للنشر عبر `render.yaml`:

1. ارفع المشروع لـ GitHub
2. اربط الـ repo بـ Render → اختار **"Blueprint"**
3. حدّد قيم الـ secrets في الـ dashboard:
   - `X_AUTH_TOKEN` — auth_token cookie من x.com
   - `X_CT0` — ct0 cookie من x.com
   - `VITE_API_URL` — URL الـ backend بعد الـ deploy

كيفية الحصول على الكوكيز:
1. افتح x.com في المتصفح وسجّل دخولك
2. F12 → Application → Cookies → x.com
3. انسخ قيمتي `auth_token` و `ct0`

---

## 📁 Structure

```
x-scraper-app/
├── backend/
│   ├── main.py            # FastAPI app
│   ├── scraper.py         # X scraping logic (GraphQL + Selenium)
│   ├── requirements.txt
│   └── Dockerfile         # Includes Chromium for Selenium
├── frontend/
│   ├── src/               # React app
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
├── render.yaml            # Render Blueprint (one-click deploy)
├── .gitignore
└── README.md
```

---

## ⚖️ License

MIT

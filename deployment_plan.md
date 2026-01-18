# خطة تجهيز مشروع FastAPI للرفع على Render

تهدف هذه الخطة إلى تحويل قاعدة البيانات من SQLite إلى PostgreSQL (لتجنب فقدان البيانات) وتجهيز إعدادات السيرفر للعمل في بيئة الإنتاج (Production).

## المرحلة الأولى: تعديل الكود البرمجي (Code Preparation)

### 1.1 تحديث الاتصال بقاعدة البيانات
*   تعديل `app/database.py` ليدعم المتغير البيئي `DATABASE_URL`.
*   إضافة معالجة لرابط PostgreSQL (تحويل `postgres://` إلى `postgresql://`).

### 1.2 تحديث ملف الاعتماديات `requirements.txt`
*   إضافة `psycopg2-binary` للاتصال بقاعدة PostgreSQL.
*   إضافة `gunicorn` كـ Process Manager للإنتاج.

### 1.3 تحديث إعدادات CORS
*   تحديث `app/main.py` للسماح بطلبات من الدومين الخاص بالفرونت آند المستقبلي أو استخدام `*` مؤقتاً.

---

## المرحلة الثانية: إعدادات Render (Dashboard Setup)

### 2.1 إنشاء قاعدة البيانات (Render PostgreSQL)
1.  من لوحة تحكم Render، اختر **New** ثم **PostgreSQL**.
2.  قم بتسمية قاعدة البيانات (مثلاً `legal_db`).
3.  بعد الإنشاء، سيقوم Render بإعطائك رابط "Internal Database URL" (سيتم ربطه آلياً بالخدمة).

### 2.2 إنشاء خدمة الويب (Render Web Service)
1.  اختر **New** ثم **Web Service**.
2.  اربط حساب GitHub/GitLab الخاص بك واختر المستودع (Repository).
3.  الإعدادات الأساسية:
    *   **Environment**: `Python`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app`

---

## المرحلة الثالثة: المتغيرات البيئية (Environment Variables)

يجب إضافة المفاتيح التالية في قسم **Environment** في Render:
*   `DATABASE_URL`: (يتم ربطه تلقائياً عند ربط قاعدة البيانات بالخدمة).
*   `GEMINI_API_KEY`: مفتاح جوجل.
*   `OPENROUTER_API_KEY`: مفتاح OpenRouter.
*   `PYTHON_VERSION`: `3.10.0` (أو النسخة التي تفضلها).

---

## المرحلة الرابعة: التحقق والاختبار

*   التأكد من أن الجداول يتم إنشاؤها تلقائياً عند التشغيل الأول.
*   اختبار رفع ملف PDF والتأكد من حفظ البيانات في PostgreSQL.

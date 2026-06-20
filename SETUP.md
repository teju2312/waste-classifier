# Waste Classifier — Django Setup Guide

## Project Structure
```
waste_classifier/
├── .env                          ← your secrets (never commit this)
├── .env.example                  ← template to share with team
├── requirements.txt
├── manage.py
├── models/
│   └── waste_classifier_final.keras   ← paste your downloaded model here
├── media/                        ← uploaded images saved here (auto-created)
├── waste_classification/
│   ├── settings.py
│   └── urls.py
└── classifier/
    ├── ml_model.py               ← WasteClassifier class (Singleton)
    ├── models.py                 ← PredictionLog, ModelInfo (Inheritance)
    ├── views.py                  ← HomeView, PredictView, HistoryView (CBVs)
    ├── forms.py                  ← ImageUploadForm (Inheritance + Encapsulation)
    ├── urls.py
    └── admin.py
```

---

## Step 1 — Create MySQL Database

Open MySQL and run:
```sql
CREATE DATABASE waste_classifier_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'waste_user'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON waste_classifier_db.* TO 'waste_user'@'localhost';
FLUSH PRIVILEGES;
```

---

## Step 2 — Create .env file

Copy .env.example to .env and fill in your values:
```bash
cp .env.example .env
```

Edit .env:
```
DJANGO_SECRET_KEY=paste-a-long-random-string-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=waste_classifier_db
DB_USER=waste_user
DB_PASSWORD=your_strong_password
DB_HOST=localhost
DB_PORT=3306

MODEL_PATH=models/waste_classifier_final.keras
MAX_UPLOAD_SIZE_MB=10
MEDIA_ROOT=media
```

Generate a Django secret key with:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4 — Place your model file

```bash
mkdir models
# Copy your downloaded waste_classifier_final.keras into the models/ folder
```

---

## Step 5 — Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Step 6 — Create admin user

```bash
python manage.py createsuperuser
```

---

## Step 7 — Run the server

```bash
python manage.py runserver
```

Open: http://127.0.0.1:8000

---

## OOP Concepts Summary

| Concept | Where used |
|---|---|
| Inheritance | All views inherit from Django base views; Models inherit from models.Model; Form inherits from forms.Form |
| Encapsulation | WasteClassifier hides all TF/numpy logic; Form hides file size validation; Views hide IP extraction |
| Abstraction | Views call classifier.predict(image) without knowing TF internals |
| Singleton Pattern | WasteClassifier._instance ensures model loads only once in memory |
| Polymorphism | get() and post() methods behave differently in each view class |
| Single Responsibility | Each class has exactly one job |

---

## .gitignore (important — never commit secrets)

```
.env
*.keras
*.h5
media/
__pycache__/
*.pyc
db.sqlite3
staticfiles/
```

# Playto Payout Engine

A minimal payout engine built using Django, DRF, PostgreSQL, and Celery that simulates how real-world payment systems manage merchant balances, payouts, and concurrency safely.

---

## 🚀 Overview

Playto Pay helps merchants receive international payments and withdraw funds to their bank accounts.

This project focuses on the **hardest part of such systems**:

- Maintaining correct balances
- Preventing double spending
- Handling concurrent requests
- Ensuring idempotent APIs
- Managing payout lifecycle asynchronously

---

## 🧱 Tech Stack

- Backend: Django + Django REST Framework
- Database: PostgreSQL
- Background Worker: Celery
- Broker: Redis
- Language: Python 3.12

---

## ⚙️ Setup Instructions

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd Playto-Payout-Engine
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

Create .env file:

```
DATABASE_URL=<your_postgres_url>
```

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Seed Data (Create Merchant + Balance)

```bash
python manage.py shell
from payouts.models import Merchant, LedgerEntry

m = Merchant.objects.create(name="Demo Merchant")

LedgerEntry.objects.create(
    merchant=m,
    amount_paise=100000,
    entry_type="credit"
)
```

## ▶️ Running the Application

### Start Redis

```bash
redis-server
```

### Start Django Server

```bash
python manage.py runserver 0.0.0.0:8000
```

### Start Celery Worker

```bash
celery -A playto_engine worker -l info
```

## 📡 API Endpoints

1. Get Balance

   GET /api/v1/merchant/<merchant_id>/balance

   Response

   ```json
   {
     "total_balance": 100000,
     "held_balance": 20000,
     "available_balance": 80000
   }
   ```

2. Create Payout

   POST /api/v1/payouts

   Headers

   Content-Type: application/json

   Idempotency-Key: unique-key-123

   Body

   ```json
   {
     "amount_paise": 50000,
     "bank_account_id": 1
   }
   ```

   Response

   ```json
   {
     "payout_id": 1,
     "status": "pending",
     "amount": 50000
   }
   ```

## 🔄 Payout Lifecycle

pending → processing → completed

pending → processing → failed

Success: payout marked completed

Failure: funds returned to merchant (credit entry)

Stuck (>30 sec): retried with exponential backoff
🧠 Key Design Decisions
1. Ledger-Based System
No stored balance

Balance derived from:

credits - debits
Ensures consistency and auditability
2. Concurrency Control
Used select_for_update() to lock merchant row
Prevents double spending
3. Idempotency
Each request includes Idempotency-Key
Duplicate requests return same response
Keys expire after 24 hours
4. Async Processing
Payout processing handled by Celery
Triggered only after DB commit using:
transaction.on_commit(...)
5. Retry Logic
Retries if payout stuck in processing > 30 sec
Exponential backoff
Max 3 retries
🧪 Running Tests
python manage.py test --keepdb
Includes:
Idempotency test
Concurrency test
❗ Notes
Celery is disabled during tests to avoid Redis dependency
All money is stored in paise (integer) — no floats used
Database-level aggregation ensures correctness
🚀 Future Improvements
React dashboard (balance + payouts)
Deployment on Render/Railway
Webhook notifications
Audit logs
📌 What This Project Demonstrates
Safe money movement logic
Database-level concurrency control
Real-world API reliability patterns
Understanding of distributed system failures
📎 Additional File
See EXPLAINER.md for deep technical reasoning and design explanations
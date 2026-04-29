# Playto Payout Engine – Explainer

This document explains the key backend decisions in my implementation. The focus is on correctness of money movement, handling concurrency safely, and ensuring API reliability.

---

## 1. The Ledger

   ### Balance Calculation Query

   ```python
   total_balance = LedgerEntry.objects.filter(merchant=merchant).aggregate(
       total=Sum(
           Case(
               When(entry_type="credit", then=F("amount_paise")),
               When(entry_type="debit", then=-F("amount_paise")),
               output_field=BigIntegerField()
           )
       )
   )["total"] or 0
   ```

   Why I modeled it this way

   I used a ledger-based model instead of storing balance as a field.

   Each transaction is recorded as:

   credit → money coming in

   debit → money going out

   The balance is always derived as:

   balance = sum(credits) - sum(debits)

   Why this is important

   - Prevents inconsistencies from partial updates
   - Makes the system auditable (every change is recorded)
   - Avoids race conditions from updating a shared balance field
   - Matches how real financial systems work

   Important decision

   The balance is calculated using database aggregation, not Python loops. This ensures:

   - correctness under concurrency
   - no stale reads
   - better performance

## 2. The Lock

   Code that prevents double spending

   ```python
   with transaction.atomic():
       merchant = Merchant.objects.select_for_update().get(id=merchant.id)
   ```

   What this does

   transaction.atomic() ensures all operations run as a single database transaction

   select_for_update() acquires a row-level lock on the merchant row

   What problem this solves

   Example:

   Balance = 100

   Two payout requests = 60 each

   Without locking:

   Both read 100

   Both succeed → system overdraws → incorrect

   With locking:

   First request locks the row

   Second request waits

   First completes and updates ledger

   Second resumes and sees updated balance → fails

   Database primitive used

   PostgreSQL row-level locking via SELECT ... FOR UPDATE

   This is database-level synchronization, not Python-level

## 3. The Idempotency

   Code

   ```python
   expiry_time = timezone.now() - timedelta(hours=24)

   existing = IdempotencyKey.objects.filter(
       merchant=merchant,
       key=idempotency_key,
       created_at__gte=expiry_time
   ).first()

   if existing:
       return Response(existing.response)
   ```

   How the system knows it has seen a key before

   Each request includes an Idempotency-Key

   We store:

   merchant

   key

   response

   timestamp

   If the same key is seen again within 24 hours:

   we return the stored response

   no new payout is created

   What happens if two requests arrive at the same time

   Both enter the transaction

   One creates the payout and saves the key

   The other finds the existing key and returns immediately

This ensures:

no duplicate payouts
consistent API behavior
4. The State Machine
Allowed transitions
pending → processing → completed
pending → processing → failed
Code that blocks invalid transitions
if payout.status not in ["pending", "processing"]:
    return
Why this matters

This prevents illegal transitions such as:

completed → pending
failed → completed
Failure handling (atomic)
with transaction.atomic():
    payout.status = "failed"
    payout.save()

    LedgerEntry.objects.create(
        merchant=payout.merchant,
        amount_paise=payout.amount_paise,
        entry_type="credit",
        payout=payout
    )
Important guarantee
Status change and refund happen in the same transaction
This ensures:
no money is lost
no partial updates occur
5. Retry Logic
Code
if payout.status == "processing":
    if timezone.now() - payout.updated_at > timedelta(seconds=30):
        raise Exception("Retry due to timeout")
Behavior
If a payout is stuck in processing for more than 30 seconds
It is retried using Celery
Retry strategy

Exponential backoff:

2^retry_count
Maximum 3 retries
After that → mark as failed and refund
Why this is needed

Simulates real-world scenarios:

bank delays
network timeouts
uncertain external systems
6. The AI Audit
Example of incorrect AI suggestion

AI initially suggested:

available_balance = total_balance - held_balance
Why this is wrong
I already create a debit ledger entry when payout is created
That means funds are already deducted from balance
Subtracting held balance again results in double deduction
Correct implementation
available_balance = total_balance
Another issue AI missed

AI suggested triggering Celery directly:

process_payout.delay(payout.id)
Why this is incorrect
The database transaction may not be committed yet
Worker may not see the payout record
Leads to inconsistent behavior
Correct fix
transaction.on_commit(lambda: process_payout.delay(payout.id))
Why this works
Task is triggered only after DB commit
Worker always sees consistent data
Final Notes

This system focuses on correctness and safety:

All money stored as integers (paise)
No floating point usage
No race conditions
No duplicate payouts
No invalid state transitions
from celery import shared_task
from django.db import transaction
import random
from .models import Payout, LedgerEntry


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    try:
        payout = Payout.objects.get(id=payout_id)

        # ❌ Prevent illegal transitions
        if payout.status not in ["pending", "processing"]:
            return

        # 🔄 Move to processing
        if payout.status == "pending":
            payout.status = "processing"
            payout.save()

        # 🎲 Simulate bank response
        rand = random.random()

        if rand < 0.7:
            # ✅ SUCCESS
            payout.status = "completed"
            payout.save()

        elif rand < 0.9:
            # ❌ FAILURE → refund (atomic)
            with transaction.atomic():
                payout.status = "failed"
                payout.save()

                # 💰 Refund money
                LedgerEntry.objects.create(
                    merchant=payout.merchant,
                    amount_paise=payout.amount_paise,
                    entry_type="credit",
                    payout=payout
                )

        else:
            # ⏳ STUCK → retry
            raise Exception("Bank timeout")

    except Exception as e:
        if self.request.retries < 3:
            raise self.retry(countdown=2 ** self.request.retries)
        else:
            # ❌ Final failure after retries → refund
            payout = Payout.objects.get(id=payout_id)

            if payout.status != "completed":
                with transaction.atomic():
                    payout.status = "failed"
                    payout.save()

                    LedgerEntry.objects.create(
                        merchant=payout.merchant,
                        amount_paise=payout.amount_paise,
                        entry_type="credit",
                        payout=payout
                    )
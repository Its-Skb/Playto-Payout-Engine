from celery import shared_task
import random
from django.db import transaction
from .models import Payout, LedgerEntry


@shared_task
def process_payout(payout_id):
    payout = Payout.objects.get(id=payout_id)

    if payout.status != "pending":
        return

    payout.status = "processing"
    payout.save()

    rand = random.random()

    if rand < 0.7:
        payout.status = "completed"
        payout.save()

    elif rand < 0.9:
        with transaction.atomic():
            payout.status = "failed"
            payout.save()

            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount_paise=payout.amount_paise,
                entry_type="credit",
                payout=payout
            )
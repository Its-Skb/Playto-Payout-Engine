from django.shortcuts import render
from django.db import transaction
from django.db.models import Sum, Case, When, F, BigIntegerField
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Merchant, LedgerEntry, Payout, IdempotencyKey
from .serializers import PayoutCreateSerializer
from .tasks import process_payout


# -------------------------------
# ✅ Balance API (already done)
# -------------------------------
@api_view(["GET"])
def get_balance(request, merchant_id):
    # 🔹 Total balance (credits - debits)
    total_balance = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        total=Sum(
            Case(
                When(entry_type="credit", then=F("amount_paise")),
                When(entry_type="debit", then=-F("amount_paise")),
                output_field=BigIntegerField()
            )
        )
    )["total"] or 0

    # 🔹 Held balance (pending + processing payouts)
    held_balance = Payout.objects.filter(
        merchant_id=merchant_id,
        status__in=["pending", "processing"]
    ).aggregate(
        total=Sum("amount_paise")
    )["total"] or 0

    # 🔹 Available balance
    available_balance = total_balance - held_balance

    return Response({
        "total_balance": total_balance,
        "held_balance": held_balance,
        "available_balance": available_balance
    })


# -------------------------------
# 🚀 Payout API (CRITICAL LOGIC)
# -------------------------------
@api_view(["POST"])
def create_payout(request):
    merchant_id = 1
    idempotency_key = request.headers.get("Idempotency-Key")

    if not idempotency_key:
        return Response(
            {"error": "Idempotency-Key header required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = PayoutCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    amount = serializer.validated_data["amount_paise"]

    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        # ✅ Idempotency (safe)
        idempotency_obj, created = IdempotencyKey.objects.get_or_create(
            merchant=merchant,
            key=idempotency_key,
            defaults={"response": {}}
        )

        if not created:
            return Response(idempotency_obj.response)

        # 💰 Balance
        total_balance = LedgerEntry.objects.filter(merchant=merchant).aggregate(
            total=Sum(
                Case(
                    When(entry_type="credit", then=F("amount_paise")),
                    When(entry_type="debit", then=-F("amount_paise")),
                    output_field=BigIntegerField()
                )
            )
        )["total"] or 0

        if total_balance < amount:
            return Response(
                {"error": "Insufficient balance"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Create payout
        payout = Payout.objects.create(
            merchant=merchant,
            amount_paise=amount,
            status="pending",
            idempotency_key=idempotency_key
        )

        # 💳 Hold funds
        LedgerEntry.objects.create(
            merchant=merchant,
            amount_paise=amount,
            entry_type="debit",
            payout=payout
        )

        response_data = {
            "payout_id": payout.id,
            "status": payout.status,
            "amount": payout.amount_paise
        }

        # 💾 Save idempotent response
        idempotency_obj.response = response_data
        idempotency_obj.save()

    # 🚀 Async trigger AFTER commit
    print("🔥 Sending task to Celery:", payout.id)
    process_payout.delay(payout.id)

    return Response(response_data, status=status.HTTP_201_CREATED)
from django.shortcuts import render
from django.db import transaction
from django.conf import settings
from django.db.models import Sum, Case, When, F, BigIntegerField
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

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
    available_balance = total_balance

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
    merchant_id = Merchant.objects.first()
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
        merchant = Merchant.objects.select_for_update().first()

        if not merchant:
            return Response({"error": "Merchant not found"}, status=404)

        expiry_time = timezone.now() - timedelta(hours=24)

        existing = IdempotencyKey.objects.filter(
            merchant=merchant,
            key=idempotency_key,
            created_at__gte=expiry_time
        ).first()

        if existing:
            return Response(existing.response)

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
        IdempotencyKey.objects.create(
            merchant=merchant,
            key=idempotency_key,
            response=response_data
        )


    if not settings.TESTING:
        transaction.on_commit(lambda: process_payout.delay(payout.id))

    return Response(response_data, status=status.HTTP_201_CREATED)
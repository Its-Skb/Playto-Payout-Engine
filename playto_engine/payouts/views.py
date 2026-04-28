from django.shortcuts import render
from django.db.models import Sum, Case, When, F, BigIntegerField
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import LedgerEntry, Payout


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

# Create your views here.

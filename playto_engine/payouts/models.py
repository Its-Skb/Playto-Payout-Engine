from django.db import models

# Create your models here.

#Merchant - A business receiving money
class Merchant(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name



#Payout - Money Going Out
class Payout(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    idempotency_key = models.CharField(max_length=255)
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)



#LedgerEntry
class LedgerEntry(models.Model):
    CREDIT = "credit"
    DEBIT = "debit"

    ENTRY_CHOICES = [
        (CREDIT, "Credit"),
        (DEBIT, "Debit"),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_CHOICES)
    payout = models.ForeignKey(Payout, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)



#IdempotencyKey - duplicate payout requests
class IdempotencyKey(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("merchant", "key")

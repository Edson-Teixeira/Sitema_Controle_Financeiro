from rest_framework import serializers
from .models import (
    Account, CreditCard, Category, Transaction, CreditCardInvoice,
    TransactionType, TransactionStatus
)
from .services import get_credit_card_info

class AccountSerializer(serializers.ModelSerializer):
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'institution', 'account_type', 'account_type_display',
            'initial_balance', 'current_balance', 'color', 'icon', 'created_at', 'updated_at'
        ]
        read_only_fields = ['current_balance', 'created_at', 'updated_at']


class CreditCardSerializer(serializers.ModelSerializer):
    used_limit = serializers.SerializerMethodField()
    available_limit = serializers.SerializerMethodField()

    class Meta:
        model = CreditCard
        fields = [
            'id', 'name', 'total_limit', 'used_limit', 'available_limit',
            'closing_day', 'due_day', 'color', 'created_at', 'updated_at'
        ]

    def get_used_limit(self, obj):
        return get_credit_card_info(obj)['used_limit']

    def get_available_limit(self, obj):
        return get_credit_card_info(obj)['available_limit']


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'icon', 'color', 'parent']


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategorySerializer(many=True, read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'type_display', 'icon', 'color', 'parent', 'subcategories']


class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_institution = serializers.CharField(source='account.institution', read_only=True)
    credit_card_name = serializers.CharField(source='credit_card.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    destination_account_name = serializers.CharField(source='destination_account.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'description', 'amount', 'date', 'type', 'type_display',
            'status', 'status_display', 'account', 'account_name', 'account_institution',
            'credit_card', 'credit_card_name', 'category', 'category_name',
            'category_color', 'category_icon', 'destination_account', 'destination_account_name',
            'installment_number', 'total_installments', 'invoice_month', 'invoice_year',
            'created_at', 'updated_at'
        ]


class TransferSerializer(serializers.Serializer):
    source_account_id = serializers.IntegerField()
    destination_account_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateField()
    description = serializers.CharField(max_length=255, required=False, default="Transferência entre contas")


class CreditCardInvoiceSerializer(serializers.ModelSerializer):
    card_name = serializers.CharField(source='credit_card.name', read_only=True)
    paid_from_account_name = serializers.CharField(source='paid_from_account.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_amount = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()

    class Meta:
        model = CreditCardInvoice
        fields = [
            'id', 'credit_card', 'card_name', 'month', 'year', 'status', 'status_display',
            'paid_at', 'paid_from_account', 'paid_from_account_name', 'paid_amount',
            'total_amount', 'transactions'
        ]

    def get_total_amount(self, obj):
        txs = Transaction.objects.filter(
            credit_card=obj.credit_card,
            invoice_month=obj.month,
            invoice_year=obj.year
        )
        return sum(t.amount for t in txs)

    def get_transactions(self, obj):
        txs = Transaction.objects.filter(
            credit_card=obj.credit_card,
            invoice_month=obj.month,
            invoice_year=obj.year
        )
        return TransactionSerializer(txs, many=True).data


class PayInvoiceSerializer(serializers.Serializer):
    account_id = serializers.IntegerField()
    month = serializers.IntegerField()
    year = serializers.IntegerField()


from django.contrib import admin
from .models import Account, CreditCard, Category, Transaction, CreditCardInvoice

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'account_type', 'initial_balance', 'current_balance', 'updated_at')
    list_filter = ('account_type', 'institution')
    search_fields = ('name', 'institution')

@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_limit', 'closing_day', 'due_day')
    search_fields = ('name',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'parent', 'icon', 'color')
    list_filter = ('type',)
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'date', 'type', 'status', 'account', 'credit_card', 'category')
    list_filter = ('type', 'status', 'date', 'account', 'credit_card')
    search_fields = ('description',)
    date_hierarchy = 'date'

@admin.register(CreditCardInvoice)
class CreditCardInvoiceAdmin(admin.ModelAdmin):
    list_display = ('credit_card', 'month', 'year', 'status', 'paid_amount', 'paid_at')
    list_filter = ('status', 'year', 'month', 'credit_card')


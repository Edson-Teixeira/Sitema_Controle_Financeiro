from decimal import Decimal
from datetime import date
from django.db import transaction as db_transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import (
    Account, CreditCard, Category, Transaction, CreditCardInvoice,
    TransactionType, TransactionStatus, InvoiceStatus, CategoryType
)

def recalculate_account_balances():
    """
    Recalculates the current balance for all accounts based on initial balance
    and COMPLETED transactions. PENDING transactions are ignored.
    """
    accounts = Account.objects.all()
    for acc in accounts:
        balance = acc.initial_balance

        # 1. Income (+)
        incomes = Transaction.objects.filter(
            account=acc,
            type=TransactionType.INCOME,
            status=TransactionStatus.COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 2. Expense (-)
        expenses = Transaction.objects.filter(
            account=acc,
            type=TransactionType.EXPENSE,
            status=TransactionStatus.COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 3. Outgoing Transfer (-)
        transfers_out = Transaction.objects.filter(
            account=acc,
            type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 4. Incoming Transfer (+)
        transfers_in = Transaction.objects.filter(
            destination_account=acc,
            type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        acc.current_balance = balance + incomes - expenses - transfers_out + transfers_in
        acc.save(update_fields=['current_balance'])


def get_credit_card_info(card):
    """
    Returns available limit, used limit, and invoice summary for a credit card.
    Used limit is calculated from transactions in unpaid (OPEN) invoices or unbilled transactions.
    """
    # Find all transactions on this card that belong to OPEN invoices or have no paid invoice
    paid_invoice_keys = set(
        CreditCardInvoice.objects.filter(
            credit_card=card,
            status=InvoiceStatus.PAID
        ).values_list('month', 'year')
    )

    card_txs = Transaction.objects.filter(credit_card=card)
    used_limit = Decimal('0.00')
    
    for tx in card_txs:
        # Check if transaction invoice is already paid
        if (tx.invoice_month, tx.invoice_year) not in paid_invoice_keys:
            used_limit += tx.amount

    available_limit = card.total_limit - used_limit
    return {
        'total_limit': card.total_limit,
        'used_limit': used_limit,
        'available_limit': available_limit if available_limit >= Decimal('0.00') else Decimal('0.00')
    }


def calculate_invoice_month_year(tx_date, closing_day):
    """
    Determines invoice month and year based on transaction date and card closing day.
    If transaction date day >= closing_day, it goes to next month's invoice.
    """
    year = tx_date.year
    month = tx_date.month

    if tx_date.day >= closing_day:
        month += 1
        if month > 12:
            month = 1
            year += 1

    return month, year


def add_months_to_date(source_date, months_to_add):
    """Utility to add N months to a date."""
    new_month = source_date.month + months_to_add
    new_year = source_date.year + (new_month - 1) // 12
    new_month = (new_month - 1) % 12 + 1
    # Adjust day if out of range for new month
    import calendar
    max_days = calendar.monthrange(new_year, new_month)[1]
    new_day = min(source_date.day, max_days)
    return date(new_year, new_month, new_day)


@db_transaction.atomic
def create_transaction(data):
    """
    Creates single or installment transactions and recalculates balances.
    """
    description = data.get('description')
    amount = Decimal(str(data.get('amount')))
    tx_date = data.get('date')
    if isinstance(tx_date, str):
        tx_date = date.fromisoformat(tx_date)
        
    tx_type = data.get('type')
    status = data.get('status', TransactionStatus.COMPLETED)
    account = data.get('account')
    credit_card = data.get('credit_card')
    category = data.get('category')
    destination_account = data.get('destination_account')
    total_installments = int(data.get('total_installments', 1))

    # Credit card transaction with installments
    if credit_card and total_installments > 1 and tx_type == TransactionType.EXPENSE:
        installment_amount = round(amount / Decimal(total_installments), 2)
        # Fix rounding difference on first installment
        first_installment_amount = amount - (installment_amount * Decimal(total_installments - 1))
        
        created_transactions = []
        parent_tx = None

        for i in range(1, total_installments + 1):
            curr_amount = first_installment_amount if i == 1 else installment_amount
            curr_date = add_months_to_date(tx_date, i - 1)
            inv_month, inv_year = calculate_invoice_month_year(curr_date, credit_card.closing_day)
            
            desc = f"{description} ({i}/{total_installments})"

            tx = Transaction.objects.create(
                description=desc,
                amount=curr_amount,
                date=curr_date,
                type=tx_type,
                status=status,
                credit_card=credit_card,
                category=category,
                installment_number=i,
                total_installments=total_installments,
                parent_transaction=parent_tx,
                invoice_month=inv_month,
                invoice_year=inv_year
            )
            if i == 1:
                parent_tx = tx
            created_transactions.append(tx)
        
        recalculate_account_balances()
        return created_transactions[0]

    # Standard transaction
    inv_month, inv_year = None, None
    if credit_card:
        inv_month, inv_year = calculate_invoice_month_year(tx_date, credit_card.closing_day)

    tx = Transaction.objects.create(
        description=description,
        amount=amount,
        date=tx_date,
        type=tx_type,
        status=status,
        account=account,
        credit_card=credit_card,
        category=category,
        destination_account=destination_account,
        installment_number=1,
        total_installments=1,
        invoice_month=inv_month,
        invoice_year=inv_year
    )

    recalculate_account_balances()
    return tx


@db_transaction.atomic
def pay_invoice(credit_card_id, month, year, account_id):
    """
    Pays a credit card invoice:
    1. Finds all transactions for card in month/year.
    2. Sums total amount.
    3. Creates COMPLETED EXPENSE transaction on specified account for the total amount.
    4. Creates or updates CreditCardInvoice to status PAID.
    5. Recalculates account balances.
    """
    card = CreditCard.objects.get(id=credit_card_id)
    account = Account.objects.get(id=account_id)

    txs = Transaction.objects.filter(
        credit_card=card,
        invoice_month=month,
        invoice_year=year
    )

    total_invoice_amount = txs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Get or create invoice
    invoice, _ = CreditCardInvoice.objects.get_or_create(
        credit_card=card,
        month=month,
        year=year,
        defaults={'status': InvoiceStatus.OPEN}
    )

    if invoice.status == InvoiceStatus.PAID:
        raise ValueError("Esta fatura já está paga.")

    # Create debit transaction on selected bank account
    category_pagamento, _ = Category.objects.get_or_create(
        name="Pagamento de Fatura",
        type=CategoryType.EXPENSE,
        defaults={'icon': 'credit-card', 'color': '#ef4444'}
    )

    tx_payment = Transaction.objects.create(
        description=f"Pagamento Fatura {card.name} - {month:02d}/{year}",
        amount=total_invoice_amount,
        date=timezone.now().date(),
        type=TransactionType.EXPENSE,
        status=TransactionStatus.COMPLETED,
        account=account,
        category=category_pagamento
    )

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = timezone.now()
    invoice.paid_from_account = account
    invoice.paid_amount = total_invoice_amount
    invoice.save()

    recalculate_account_balances()
    return invoice


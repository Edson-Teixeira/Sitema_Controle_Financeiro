from decimal import Decimal
from datetime import date, timedelta
from django.shortcuts import render
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Account, CreditCard, Category, Transaction, CreditCardInvoice,
    TransactionType, TransactionStatus, InvoiceStatus, CategoryType
)
from .serializers import (
    AccountSerializer, CreditCardSerializer, CategorySerializer,
    TransactionSerializer, TransferSerializer, CreditCardInvoiceSerializer,
    PayInvoiceSerializer
)
from .services import (
    recalculate_account_balances, create_transaction, pay_invoice,
    get_credit_card_info, calculate_invoice_month_year
)


def index_view(request):
    """Renders the Single Page Application."""
    return render(request, 'index.html')


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('name')
    serializer_class = AccountSerializer

    def perform_create(self, serializer):
        account = serializer.save()
        account.current_balance = account.initial_balance
        account.save()
        recalculate_account_balances()

    def perform_update(self, serializer):
        serializer.save()
        recalculate_account_balances()

    def perform_destroy(self, instance):
        instance.delete()
        recalculate_account_balances()

    @action(detail=False, methods=['post'])
    def transfer(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source = Account.objects.get(id=serializer.validated_data['source_account_id'])
        dest = Account.objects.get(id=serializer.validated_data['destination_account_id'])
        amt = serializer.validated_data['amount']
        dt = serializer.validated_data['date']
        desc = serializer.validated_data.get('description', 'Transferência entre contas')

        tx_data = {
            'description': f"{desc} ({source.name} ➔ {dest.name})",
            'amount': amt,
            'date': dt,
            'type': TransactionType.TRANSFER,
            'status': TransactionStatus.COMPLETED,
            'account': source,
            'destination_account': dest,
        }

        tx = create_transaction(tx_data)
        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class CreditCardViewSet(viewsets.ModelViewSet):
    queryset = CreditCard.objects.all().order_by('name')
    serializer_class = CreditCardSerializer

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        card = self.get_object()
        now = timezone.now().date()

        # Find distinct invoice months from transactions on this card
        invoice_dates = Transaction.objects.filter(
            credit_card=card,
            invoice_month__isnull=False,
            invoice_year__isnull=False
        ).values('invoice_month', 'invoice_year').distinct()

        months_set = {(t['invoice_month'], t['invoice_year']) for t in invoice_dates}

        # Include past 12 months and future 12 months for cycle navigation
        for offset in range(-12, 13):
            total_m = now.month + offset
            y = now.year + (total_m - 1) // 12
            m = (total_m - 1) % 12 + 1
            months_set.add((m, y))

        result = []
        for m, y in sorted(months_set, key=lambda x: (x[1], x[0])):
            inv, _ = CreditCardInvoice.objects.get_or_create(
                credit_card=card,
                month=m,
                year=y,
                defaults={'status': InvoiceStatus.OPEN}
            )
            result.append(CreditCardInvoiceSerializer(inv).data)

        return Response(result)

    @action(detail=True, methods=['post'])
    def pay_invoice(self, request, pk=None):
        card = self.get_object()
        serializer = PayInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        m = serializer.validated_data['month']
        y = serializer.validated_data['year']
        acc_id = serializer.validated_data['account_id']

        try:
            invoice = pay_invoice(card.id, m, y, acc_id)
            return Response(CreditCardInvoiceSerializer(invoice).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(parent__isnull=True).order_by('name')
    serializer_class = CategorySerializer

    def get_queryset(self):
        qs = Category.objects.filter(parent__isnull=True).order_by('name')
        cat_type = self.request.query_params.get('type')
        if cat_type:
            qs = qs.filter(type=cat_type)
        return qs


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by('-date', '-id')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = Transaction.objects.all().order_by('-date', '-id')
        status_param = self.request.query_params.get('status')
        type_param = self.request.query_params.get('type')
        month_param = self.request.query_params.get('month')
        year_param = self.request.query_params.get('year')
        account_param = self.request.query_params.get('account')
        card_param = self.request.query_params.get('credit_card')
        pending_only = self.request.query_params.get('pending')

        if status_param:
            qs = qs.filter(status=status_param)
        if pending_only == 'true':
            qs = qs.filter(status=TransactionStatus.PENDING)
        if type_param:
            qs = qs.filter(type=type_param)
        if month_param:
            qs = qs.filter(date__month=int(month_param))
        if year_param:
            qs = qs.filter(date__year=int(year_param))
        if account_param:
            qs = qs.filter(account_id=int(account_param))
        if card_param:
            qs = qs.filter(credit_card_id=int(card_param))

        return qs

    def create(self, request, *args, **kwargs):
        tx_data = request.data.copy()
        
        # Convert IDs to object references if passed
        if tx_data.get('account'):
            tx_data['account'] = Account.objects.get(id=tx_data['account'])
        if tx_data.get('credit_card'):
            tx_data['credit_card'] = CreditCard.objects.get(id=tx_data['credit_card'])
        if tx_data.get('category'):
            tx_data['category'] = Category.objects.get(id=tx_data['category'])
        if tx_data.get('destination_account'):
            tx_data['destination_account'] = Account.objects.get(id=tx_data['destination_account'])

        tx = create_transaction(tx_data)
        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        tx = serializer.save()
        if tx.credit_card and tx.date:
            inv_month, inv_year = calculate_invoice_month_year(tx.date, tx.credit_card.closing_day)
            tx.invoice_month = inv_month
            tx.invoice_year = inv_year
            tx.save(update_fields=['invoice_month', 'invoice_year'])
        recalculate_account_balances()

    def perform_destroy(self, instance):
        instance.delete()
        recalculate_account_balances()

    @action(detail=True, methods=['patch'])
    def toggle_status(self, request, pk=None):
        tx = self.get_object()
        if tx.status == TransactionStatus.PENDING:
            tx.status = TransactionStatus.COMPLETED
        else:
            tx.status = TransactionStatus.PENDING
        tx.save()

        recalculate_account_balances()
        return Response(TransactionSerializer(tx).data)


class DashboardView(APIView):
    def get(self, request):
        today = timezone.now().date()
        month_param = request.query_params.get('month')
        year_param = request.query_params.get('year')

        current_month = int(month_param) if month_param else today.month
        current_year = int(year_param) if year_param else today.year

        recalculate_account_balances()

        # 1. Consolidated Account Balance across all accounts (Global)
        accounts = Account.objects.all()
        consolidated_balance = sum(acc.current_balance for acc in accounts)

        # 2. Cycle Incomes (Entradas do Ciclo)
        month_incomes = Transaction.objects.filter(
            type=TransactionType.INCOME,
            date__month=current_month,
            date__year=current_year
        )
        realized_income = month_incomes.filter(status=TransactionStatus.COMPLETED).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        pending_income = month_incomes.filter(status=TransactionStatus.PENDING).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        total_entradas = realized_income + pending_income

        # 3. Cycle Expenses (Saídas do Ciclo em Contas)
        month_expenses = Transaction.objects.filter(
            type=TransactionType.EXPENSE,
            date__month=current_month,
            date__year=current_year,
            account__isnull=False
        )
        realized_expenses = month_expenses.filter(status=TransactionStatus.COMPLETED).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        pending_expenses = month_expenses.filter(status=TransactionStatus.PENDING).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        # 4. Credit Card Invoices for Cycle
        cards = CreditCard.objects.all()
        month_invoices_total = Decimal('0.00')
        paid_invoices_total = Decimal('0.00')
        for card in cards:
            card_month_txs = Transaction.objects.filter(
                credit_card=card,
                invoice_month=current_month,
                invoice_year=current_year
            )
            invoice_sum = sum(t.amount for t in card_month_txs)
            month_invoices_total += invoice_sum

            is_paid = CreditCardInvoice.objects.filter(
                credit_card=card,
                month=current_month,
                year=current_year,
                status=InvoiceStatus.PAID
            ).exists()
            if is_paid:
                paid_invoices_total += invoice_sum

        total_saidas = realized_expenses + pending_expenses + month_invoices_total

        # Saldo do Ciclo (Saldo já realizado no ciclo)
        saldo_ciclo = realized_income - (realized_expenses + paid_invoices_total)

        # Previsto do Ciclo (Balanço final previsto do ciclo após pagar todas as saídas)
        previsto_ciclo = total_entradas - total_saidas

        # Expenses by Category (for selected cycle)
        category_data = []
        category_sums = Transaction.objects.filter(
            type=TransactionType.EXPENSE,
            date__month=current_month,
            date__year=current_year,
            category__isnull=False
        ).values('category__name', 'category__color').annotate(total=Sum('amount')).order_by('-total')

        for item in category_sums:
            category_data.append({
                'category_name': item['category__name'],
                'category_color': item['category__color'] or '#3b82f6',
                'total': float(item['total'])
            })

        # Next 7 Days Upcoming Due Dates
        next_7_days = today + timedelta(days=7)
        upcoming_pending_txs = Transaction.objects.filter(
            status=TransactionStatus.PENDING,
            date__gte=today,
            date__lte=next_7_days
        ).order_by('date')

        upcoming_list = []
        for tx in upcoming_pending_txs:
            upcoming_list.append({
                'id': tx.id,
                'title': tx.description,
                'amount': float(tx.amount),
                'date': tx.date.isoformat(),
                'type': tx.get_type_display(),
                'status': tx.get_status_display(),
                'is_pending_tx': True
            })

        for card in cards:
            try:
                due_date = date(today.year, today.month, card.due_day)
            except ValueError:
                due_date = date(today.year, today.month, 28)

            if today <= due_date <= next_7_days:
                inv_txs = Transaction.objects.filter(
                    credit_card=card,
                    invoice_month=today.month,
                    invoice_year=today.year
                )
                amt = sum(t.amount for t in inv_txs)
                if amt > 0:
                    is_paid = CreditCardInvoice.objects.filter(
                        credit_card=card,
                        month=today.month,
                        year=today.year,
                        status=InvoiceStatus.PAID
                    ).exists()

                    if not is_paid:
                        upcoming_list.append({
                            'id': f"card-{card.id}",
                            'title': f"Fatura {card.name}",
                            'amount': float(amt),
                            'date': due_date.isoformat(),
                            'type': 'Fatura de Cartão',
                            'status': 'Aberta',
                            'is_card_invoice': True,
                            'card_id': card.id,
                            'month': today.month,
                            'year': today.year
                        })

        upcoming_list.sort(key=lambda x: x['date'])
        recent_txs = Transaction.objects.all().order_by('-date', '-id')[:10]

        return Response({
            'cycle_month': current_month,
            'cycle_year': current_year,
            'consolidated_balance': float(consolidated_balance),
            'month_realized_income': float(realized_income),
            'month_pending_income': float(pending_income),
            'total_entradas': float(total_entradas),
            'month_realized_expenses': float(realized_expenses),
            'month_pending_expenses': float(pending_expenses),
            'total_saidas': float(total_saidas),
            'month_invoices_total': float(month_invoices_total),
            'saldo': float(saldo_ciclo),
            'previsto': float(previsto_ciclo),
            'expenses_by_category': category_data,
            'upcoming_due_dates': upcoming_list,
            'recent_transactions': TransactionSerializer(recent_txs, many=True).data
        })


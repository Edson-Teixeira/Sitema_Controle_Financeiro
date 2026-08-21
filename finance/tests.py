from decimal import Decimal
from datetime import date
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from finance.models import (
    Account, CreditCard, Category, Transaction, CreditCardInvoice,
    AccountType, CategoryType, TransactionType, TransactionStatus, InvoiceStatus
)
from finance.services import (
    recalculate_account_balances, create_transaction, pay_invoice, get_credit_card_info
)

class PersonalFinanceTestCase(TestCase):
    def setUp(self):
        # 1. Accounts
        self.acc_corrente = Account.objects.create(
            name="Conta Corrente",
            institution="Nubank",
            account_type=AccountType.CHECKING,
            initial_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00")
        )
        self.acc_poupanca = Account.objects.create(
            name="Poupança",
            institution="Itaú",
            account_type=AccountType.SAVINGS,
            initial_balance=Decimal("500.00"),
            current_balance=Decimal("500.00")
        )

        # 2. Credit Card
        self.card = CreditCard.objects.create(
            name="Cartão Crédito",
            total_limit=Decimal("5000.00"),
            closing_day=25,
            due_day=5
        )

        # 3. Categories
        self.cat_salario = Category.objects.create(name="Salário", type=CategoryType.INCOME)
        self.cat_mercado = Category.objects.create(name="Mercado", type=CategoryType.EXPENSE)

    def test_pending_transaction_does_not_affect_balance(self):
        """Rule 1: Pending transactions must NOT change account balance until COMPLETED."""
        create_transaction({
            'description': 'Salário Pendente',
            'amount': Decimal('2000.00'),
            'date': date.today(),
            'type': TransactionType.INCOME,
            'status': TransactionStatus.PENDING,
            'account': self.acc_corrente,
            'category': self.cat_salario
        })

        self.acc_corrente.refresh_from_db()
        self.assertEqual(self.acc_corrente.current_balance, Decimal('1000.00'))

        # Now complete the transaction
        tx = Transaction.objects.get(description='Salário Pendente')
        tx.status = TransactionStatus.COMPLETED
        tx.save()
        recalculate_account_balances()

        self.acc_corrente.refresh_from_db()
        self.assertEqual(self.acc_corrente.current_balance, Decimal('3000.00'))

    def test_internal_transfer_between_accounts(self):
        """Rule 2: Internal transfers adjust balances of both accounts without being income/expense."""
        create_transaction({
            'description': 'Transferência para Poupança',
            'amount': Decimal('300.00'),
            'date': date.today(),
            'type': TransactionType.TRANSFER,
            'status': TransactionStatus.COMPLETED,
            'account': self.acc_corrente,
            'destination_account': self.acc_poupanca
        })

        self.acc_corrente.refresh_from_db()
        self.acc_poupanca.refresh_from_db()

        self.assertEqual(self.acc_corrente.current_balance, Decimal('700.00'))
        self.assertEqual(self.acc_poupanca.current_balance, Decimal('800.00'))

    def test_credit_card_installments_and_limit(self):
        """Rule 3: Credit card purchases reduce limit without affecting bank account until paid."""
        create_transaction({
            'description': 'Compra Notebook',
            'amount': Decimal('1200.00'),
            'date': date(2026, 8, 10),
            'type': TransactionType.EXPENSE,
            'status': TransactionStatus.COMPLETED,
            'credit_card': self.card,
            'category': self.cat_mercado,
            'total_installments': 3
        })

        # Should generate 3 installments of R$ 400.00
        txs = Transaction.objects.filter(credit_card=self.card)
        self.assertEqual(txs.count(), 3)
        for tx in txs:
            self.assertEqual(tx.amount, Decimal('400.00'))

        # Bank account balance should be unchanged
        self.acc_corrente.refresh_from_db()
        self.assertEqual(self.acc_corrente.current_balance, Decimal('1000.00'))

        # Limit used should be R$ 1200.00
        info = get_credit_card_info(self.card)
        self.assertEqual(info['used_limit'], Decimal('1200.00'))
        self.assertEqual(info['available_limit'], Decimal('3800.00'))

    def test_pay_credit_card_invoice(self):
        """Rule 4: Paying invoice debits selected bank account and marks invoice PAID."""
        create_transaction({
            'description': 'Supermercado',
            'amount': Decimal('500.00'),
            'date': date(2026, 8, 10),
            'type': TransactionType.EXPENSE,
            'status': TransactionStatus.COMPLETED,
            'credit_card': self.card,
            'category': self.cat_mercado
        })

        # Payment for invoice month 8, year 2026
        invoice = pay_invoice(self.card.id, 8, 2026, self.acc_corrente.id)
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

        # Bank account balance should now be 1000 - 500 = 500
        self.acc_corrente.refresh_from_db()
        self.assertEqual(self.acc_corrente.current_balance, Decimal('500.00'))


class APIEndpointsTestCase(APITestCase):
    def setUp(self):
        self.acc1 = Account.objects.create(
            name="Conta 1", institution="Banco A", initial_balance=Decimal("2000.00"), current_balance=Decimal("2000.00")
        )
        self.acc2 = Account.objects.create(
            name="Conta 2", institution="Banco B", initial_balance=Decimal("500.00"), current_balance=Decimal("500.00")
        )
        self.card = CreditCard.objects.create(
            name="Cartão Gold", total_limit=Decimal("3000.00"), closing_day=20, due_day=5
        )
        self.cat = Category.objects.create(name="Alimentação", type=CategoryType.EXPENSE)

    def test_dashboard_api(self):
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('consolidated_balance', response.data)
        self.assertEqual(response.data['consolidated_balance'], 2500.0)

    def test_account_api(self):
        response = self.client.get('/api/accounts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_transfer_api(self):
        payload = {
            'source_account_id': self.acc1.id,
            'destination_account_id': self.acc2.id,
            'amount': '500.00',
            'date': '2026-08-20',
            'description': 'Transferência via API'
        }
        response = self.client.post('/api/accounts/transfer/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.acc1.refresh_from_db()
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1500.00'))
        self.assertEqual(self.acc2.current_balance, Decimal('1000.00'))

    def test_category_crud_api(self):
        # Create
        res = self.client.post('/api/categories/', {'name': 'Transporte Uber', 'type': 'EXPENSE', 'icon': 'truck', 'color': '#3b82f6'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        cat_id = res.data['id']

        # Update
        res_edit = self.client.put(f'/api/categories/{cat_id}/', {'name': 'Transporte & Táxi', 'type': 'EXPENSE', 'icon': 'truck', 'color': '#2563eb'})
        self.assertEqual(res_edit.status_code, status.HTTP_200_OK)
        self.assertEqual(res_edit.data['name'], 'Transporte & Táxi')

        # Delete
        res_del = self.client.delete(f'/api/categories/{cat_id}/')
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)

    def test_transaction_edit_api(self):
        tx = Transaction.objects.create(
            description='Supermercado Semanal',
            amount=Decimal('200.00'),
            date=date.today(),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.COMPLETED,
            account=self.acc1,
            category=self.cat
        )
        recalculate_account_balances()
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1800.00'))

        # Edit transaction amount to R$ 300.00
        payload = {
            'description': 'Supermercado Grande',
            'amount': '300.00',
            'date': date.today().isoformat(),
            'type': 'EXPENSE',
            'status': 'COMPLETED',
            'account': self.acc1.id,
            'category': self.cat.id
        }
        res_put = self.client.put(f'/api/transactions/{tx.id}/', payload)
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)

        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, Decimal('1700.00'))



from django.core.management.base import BaseCommand
from finance.models import Category, CategoryType, Account, AccountType, CreditCard

class Command(BaseCommand):
    help = 'Seeds initial categories and sample account/card data'

    def handle(self, *args, **options):
        # 1. Income Categories
        incomes = [
            ('Salário', 'wallet', '#10b981'),
            ('Freelance', 'laptop', '#059669'),
            ('Investimentos', 'trending-up', '#047857'),
            ('Outras Receitas', 'plus-circle', '#10b981'),
        ]
        for name, icon, color in incomes:
            Category.objects.get_or_create(
                name=name,
                type=CategoryType.INCOME,
                defaults={'icon': icon, 'color': color}
            )

        # 2. Expense Categories
        expenses = [
            ('Alimentação', 'shopping-cart', '#ef4444'),
            ('Moradia', 'home', '#f59e0b'),
            ('Transporte', 'truck', '#3b82f6'),
            ('Lazer', 'smile', '#ec4899'),
            ('Saúde', 'activity', '#8b5cf6'),
            ('Educação', 'book', '#6366f1'),
            ('Pagamento de Fatura', 'credit-card', '#dc2626'),
            ('Outras Despesas', 'minus-circle', '#6b7280'),
        ]
        for name, icon, color in expenses:
            Category.objects.get_or_create(
                name=name,
                type=CategoryType.EXPENSE,
                defaults={'icon': icon, 'color': color}
            )

        # 3. Sample Accounts
        acc1, created1 = Account.objects.get_or_create(
            name="Conta Corrente",
            institution="Nubank",
            defaults={
                'account_type': AccountType.CHECKING,
                'initial_balance': 3500.00,
                'current_balance': 3500.00,
                'color': '#8b5cf6',
                'icon': 'wallet'
            }
        )

        acc2, created2 = Account.objects.get_or_create(
            name="Reserva de Emergência",
            institution="Banco do Brasil",
            defaults={
                'account_type': AccountType.SAVINGS,
                'initial_balance': 10000.00,
                'current_balance': 10000.00,
                'color': '#3b82f6',
                'icon': 'building-2'
            }
        )

        # 4. Sample Credit Card
        card, card_created = CreditCard.objects.get_or_create(
            name="Nubank Roxo",
            defaults={
                'total_limit': 8000.00,
                'closing_day': 25,
                'due_day': 5,
                'color': '#7c3aed'
            }
        )

        self.stdout.write(self.style.SUCCESS('Dados iniciais semeados com sucesso!'))


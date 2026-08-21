from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class AccountType(models.TextChoices):
    CHECKING = 'CHECKING', 'Conta Corrente'
    SAVINGS = 'SAVINGS', 'Poupança'
    INVESTMENT = 'INVESTMENT', 'Investimento'
    CASH = 'CASH', 'Carteira Física'
    OTHER = 'OTHER', 'Outros'

class CategoryType(models.TextChoices):
    INCOME = 'INCOME', 'Receita'
    EXPENSE = 'EXPENSE', 'Despesa'

class TransactionType(models.TextChoices):
    INCOME = 'INCOME', 'Entrada'
    EXPENSE = 'EXPENSE', 'Saída'
    TRANSFER = 'TRANSFER', 'Transferência'

class TransactionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendente'
    COMPLETED = 'COMPLETED', 'Realizada'

class InvoiceStatus(models.TextChoices):
    OPEN = 'OPEN', 'Aberta'
    PAID = 'PAID', 'Paga'


class Account(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome da Conta")
    institution = models.CharField(max_length=100, verbose_name="Instituição")
    account_type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.CHECKING, verbose_name="Tipo")
    initial_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Saldo Inicial")
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Saldo Atual")
    color = models.CharField(max_length=20, default="#3b82f6", verbose_name="Cor da UI")
    icon = models.CharField(max_length=50, default="landmark", verbose_name="Ícone/Logo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.institution})"


class CreditCard(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome do Cartão")
    total_limit = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Limite Total")
    closing_day = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], verbose_name="Dia de Fechamento")
    due_day = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], verbose_name="Dia de Vencimento")
    color = models.CharField(max_length=20, default="#8b5cf6", verbose_name="Cor da UI")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome da Categoria")
    type = models.CharField(max_length=20, choices=CategoryType.choices, default=CategoryType.EXPENSE, verbose_name="Tipo")
    icon = models.CharField(max_length=50, default="tag", verbose_name="Ícone")
    color = models.CharField(max_length=20, default="#6b7280", verbose_name="Cor")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories', verbose_name="Categoria Pai")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class Transaction(models.Model):
    description = models.CharField(max_length=255, verbose_name="Descrição")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    date = models.DateField(verbose_name="Data")
    type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name="Tipo")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.COMPLETED, verbose_name="Status")
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions', verbose_name="Conta Origem/Destino")
    credit_card = models.ForeignKey(CreditCard, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions', verbose_name="Cartão de Crédito")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', verbose_name="Categoria")
    
    destination_account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='incoming_transfers', verbose_name="Conta de Destino (Transferências)")
    
    installment_number = models.IntegerField(default=1, verbose_name="Número da Parcela")
    total_installments = models.IntegerField(default=1, verbose_name="Total de Parcelas")
    parent_transaction = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='installments')
    
    invoice_month = models.IntegerField(null=True, blank=True, verbose_name="Mês da Fatura")
    invoice_year = models.IntegerField(null=True, blank=True, verbose_name="Ano da Fatura")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} - R$ {self.amount} ({self.get_status_display()})"


class CreditCardInvoice(models.Model):
    credit_card = models.ForeignKey(CreditCard, on_delete=models.CASCADE, related_name='invoices', verbose_name="Cartão")
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)], verbose_name="Mês")
    year = models.IntegerField(verbose_name="Ano")
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.OPEN, verbose_name="Status")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Data do Pagamento")
    paid_from_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='paid_invoices', verbose_name="Pago com a Conta")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Pago")

    class Meta:
        unique_together = ('credit_card', 'month', 'year')

    def __str__(self):
        return f"Fatura {self.credit_card.name} - {self.month:02d}/{self.year} ({self.get_status_display()})"


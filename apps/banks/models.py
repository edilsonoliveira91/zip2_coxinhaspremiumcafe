from django.db import models
from django.conf import settings
from django.utils import timezone


class Bank(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome do Banco")
    numero_conta = models.CharField(max_length=50, blank=True, verbose_name="Número da Conta")
    agencia = models.CharField(max_length=20, blank=True, verbose_name="Agência")
    valor_inicial = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name="Valor Inicial"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='banks_criados',
    )

    class Meta:
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class BankTransaction(models.Model):
    TIPO_CHOICES = [
        ('deposito', 'Depósito'),
        ('pagamento', 'Pagamento'),
        ('transferencia', 'Transferência'),
    ]

    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='transactions')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    is_entrada = models.BooleanField(default=True, verbose_name="É entrada")
    data = models.DateTimeField(default=timezone.now, verbose_name="Data")
    observacao = models.TextField(blank=True, verbose_name="Observação")
    banco_destino = models.ForeignKey(
        Bank, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions_recebidas',
        verbose_name="Banco Destino",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='bank_transactions'
    )

    class Meta:
        verbose_name = "Transação"
        verbose_name_plural = "Transações"
        ordering = ['-data', '-id']

    @property
    def valor_signed(self):
        return self.valor if self.is_entrada else -self.valor

    def __str__(self):
        return f"{self.get_tipo_display()} - R$ {self.valor} ({self.bank.nome})"


class UserBankAccess(models.Model):
    """Controla quais bancos específicos cada usuário pode acessar e com quais ações."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_accesses',
        verbose_name='Usuário',
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='user_accesses',
        verbose_name='Banco',
    )
    can_view               = models.BooleanField(default=False, verbose_name='Visualizar')
    can_change             = models.BooleanField(default=False, verbose_name='Editar')
    can_add_transaction    = models.BooleanField(default=False, verbose_name='Adicionar depósito')
    can_pay_transaction    = models.BooleanField(default=False, verbose_name='Registrar pagamento')
    can_transfer_transaction = models.BooleanField(default=False, verbose_name='Transferir')
    can_delete_transaction = models.BooleanField(default=False, verbose_name='Remover transações')

    class Meta:
        verbose_name = 'Acesso ao Banco'
        verbose_name_plural = 'Acessos a Bancos'
        unique_together = ('user', 'bank')

    def __str__(self):
        return f'{self.user.username} → {self.bank.nome}'

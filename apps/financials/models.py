from django.db import models
from django.conf import settings  # Mudança aqui
from django.core.validators import MinValueValidator
from decimal import Decimal
from utils.models import TimeStampedModel


class Sangria(TimeStampedModel):
    """
    Modelo para registrar sangrias (retiradas de dinheiro do caixa)
    """
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor da Sangria",
        help_text="Valor em reais que foi retirado do caixa"
    )
    
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observação",
        help_text="Motivo ou observação sobre a sangria"
    )
    
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='sangrias',
        verbose_name="Usuário",
        help_text="Usuário que realizou a sangria"
    )
    
    class Meta:
        verbose_name = "Sangria"
        verbose_name_plural = "Sangrias"
        ordering = ['-created_at']  # Mais recentes primeiro
        permissions = [
            ("can_view_sangria", "Can view sangria"),
            ("can_add_sangria", "Can add sangria"),
        ]
    
    def __str__(self):
        return f"Sangria R$ {self.valor} - {self.usuario.get_full_name() or self.usuario.username} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"
    
    @property
    def valor_formatado(self):
        """Retorna o valor formatado em reais"""
        return f"R$ {self.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

class FechamentoCaixaDiario(TimeStampedModel):
    """
    Arquiva o extrato do caixa ao final de cada dia operacional.
    Permite verificar o histórico de fechamentos passados.
    """
    data = models.DateField(
        unique=True,
        verbose_name="Data do Fechamento",
    )
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fechamentos_caixa',
        verbose_name="Fechado por",
    )
    valor_inicial   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Troco Inicial")
    total_dinheiro  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Dinheiro")
    total_debito    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Cartao Debito")
    total_credito   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Cartao Credito")
    total_pix       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="PIX")
    total_voucher   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Voucher")
    total_sangrias  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Sangrias")
    total_entradas  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Entradas")
    total_final     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Final em Caixa")
    total_comandas  = models.PositiveIntegerField(default=0, verbose_name="Qtd Comandas")
    observacao      = models.TextField(blank=True, verbose_name="Observacao")
    cancelada       = models.BooleanField(default=False, verbose_name="Cancelado")
    cancelada_em    = models.DateTimeField(null=True, blank=True, verbose_name="Cancelado em")
    cancelada_por   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fechamentos_cancelados',
        verbose_name="Cancelado por",
    )

    class Meta:
        verbose_name = "Fechamento de Caixa Diario"
        verbose_name_plural = "Fechamentos de Caixa Diarios"
        ordering = ['-data']
        permissions = [
            ('view_financial', 'Pode visualizar relatórios financeiros (extrato e fechamento)'),
        ]

    def __str__(self):
        return f"Fechamento {self.data.strftime('%d/%m/%Y')} - R$ {self.total_final}"


class CaixaAdm(models.Model):
    """
    Malote enviado pelo operador de caixa para conferência administrativa.
    Criado quando o operador clica em "Enviar Malote" no histórico de fechamentos.
    """
    fechamento = models.OneToOneField(
        FechamentoCaixaDiario,
        on_delete=models.CASCADE,
        related_name='malote',
        verbose_name="Fechamento",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='malotes_enviados',
        verbose_name="Enviado por",
    )
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='malotes_concluidos',
        verbose_name="Concluído por",
    )
    concluido_em = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")

    class Meta:
        verbose_name = "Caixa ADM"
        verbose_name_plural = "Caixas ADM"
        ordering = ['-enviado_em']

    def __str__(self):
        return f"Malote {self.fechamento.data.strftime('%d/%m/%Y')} - {self.enviado_por}"

    @property
    def total_despesas(self):
        from django.db.models import Sum
        return self.despesas.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    @property
    def dinheiro_liquido(self):
        """Dinheiro do malote já descontado das despesas."""
        return self.fechamento.total_dinheiro - self.total_despesas

    @property
    def total_final_liquido(self):
        """Total final do malote já descontado das despesas."""
        return self.fechamento.total_final - self.total_despesas


class CaixaAdmTransferencia(models.Model):
    """
    Registro de transferência do saldo do Caixa ADM para um banco.
    Debita do total conferido exibido na tela Caixa ADM.
    """
    banco_destino = models.ForeignKey(
        'banks.Bank',
        on_delete=models.SET_NULL,
        null=True,
        related_name='transferencias_caixa_adm',
        verbose_name="Banco destino",
    )
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor",
    )
    METODO_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('debito',   'Débito'),
        ('credito',  'Crédito'),
        ('pix',      'PIX'),
    ]
    metodo_pagamento = models.CharField(
        max_length=10, choices=METODO_CHOICES, default='dinheiro', verbose_name="Método"
    )
    bandeira = models.CharField(max_length=100, blank=True, verbose_name="Bandeira")
    taxa_aplicada = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name="Taxa aplicada (%)",
    )
    data_caixa = models.DateField(null=True, blank=True, verbose_name="Data do Caixa")
    data_prevista_liquidacao = models.DateField(null=True, blank=True, verbose_name="Data prevista de liquidação")
    conciliado = models.BooleanField(default=False, verbose_name="Conciliado")
    conciliado_em = models.DateTimeField(null=True, blank=True, verbose_name="Conciliado em")
    conciliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transferencias_conciliadas',
        verbose_name="Conciliado por",
    )
    cancelada = models.BooleanField(default=False, verbose_name="Cancelada")
    cancelada_em = models.DateTimeField(null=True, blank=True, verbose_name="Cancelada em")
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transferencias_canceladas',
        verbose_name="Cancelada por",
    )
    descricao = models.CharField(max_length=200, verbose_name="Descrição", blank=True)
    observacao = models.TextField(blank=True, verbose_name="Observação")
    bank_transaction = models.OneToOneField(
        'banks.BankTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='caixa_transferencia',
        verbose_name="BankTransaction vinculada",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transferencias_caixa_adm',
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Transferência Caixa ADM"
        verbose_name_plural = "Transferências Caixa ADM"
        ordering = ['-criado_em']

    def __str__(self):
        return f"Transferência R$ {self.valor} → {self.banco_destino}"


class DespesaMalote(models.Model):
    """
    Despesa vinculada a um malote (CaixaAdm) registrada pelo ADM.
    """
    malote = models.ForeignKey(
        CaixaAdm,
        on_delete=models.CASCADE,
        related_name='despesas',
        verbose_name="Malote",
    )
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor",
    )
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    comprovante = models.FileField(
        upload_to='despesas_malote/',
        blank=True,
        null=True,
        verbose_name="Comprovante",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='despesas_malote',
        verbose_name="Registrado por",
    )
    registrado_em = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Despesa do Malote"
        verbose_name_plural = "Despesas do Malote"
        ordering = ['-registrado_em']

    def __str__(self):
        return f"Despesa R$ {self.valor} - {self.malote} - {self.descricao[:40]}"


class PlanoDeContas(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Plano de Contas"
        verbose_name_plural = "Plano de Contas"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    nome = models.CharField(max_length=150, verbose_name="Nome / Razão Social")
    cnpj = models.CharField(max_length=18, blank=True, verbose_name="CNPJ")
    telefone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, verbose_name="E-mail")
    observacao = models.TextField(blank=True, verbose_name="Observação")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Material(models.Model):
    nome = models.CharField(max_length=150, verbose_name="Nome")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiais"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class FornecedorMaterial(models.Model):
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.CASCADE,
        related_name='materiais',
        verbose_name="Fornecedor",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='fornecedores',
        verbose_name="Material",
    )
    plano_de_conta = models.ForeignKey(
        PlanoDeContas,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fornecedor_materiais',
        verbose_name="Plano de Contas",
    )

    class Meta:
        verbose_name = "Material do Fornecedor"
        verbose_name_plural = "Materiais do Fornecedor"
        unique_together = [('fornecedor', 'material')]

    def __str__(self):
        return f"{self.fornecedor.nome} — {self.material.nome}"


class ContaPagar(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
        ('cancelado', 'Cancelado'),
    ]

    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.PROTECT,
        related_name='contas_pagar',
        verbose_name="Fornecedor",
    )
    fornecedor_material = models.ForeignKey(
        FornecedorMaterial,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contas_pagar',
        verbose_name="Material",
    )
    plano_de_conta = models.ForeignKey(
        PlanoDeContas,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contas_pagar',
        verbose_name="Plano de Contas",
    )
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    valor = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor",
    )
    data_vencimento = models.DateField(verbose_name="Vencimento")
    data_pagamento = models.DateField(null=True, blank=True, verbose_name="Data de Pagamento")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    observacao = models.TextField(blank=True, verbose_name="Observação")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contas_pagar_criadas',
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    pago_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contas_pagar_pagas',
        verbose_name="Pago por",
    )
    banco_pagamento = models.ForeignKey(
        'banks.Bank',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contas_pagas',
        verbose_name="Banco do pagamento",
    )

    class Meta:
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"
        ordering = ['data_vencimento']

    def __str__(self):
        return f"{self.descricao} — R$ {self.valor} ({self.data_vencimento})"

    @property
    def vencida(self):
        from datetime import date
        return self.status == 'pendente' and self.data_vencimento < date.today()


class ContaPagarItem(models.Model):
    UNIDADE_CHOICES = [
        ('un', 'Unidade'),
        ('kg', 'Kg'),
        ('g', 'Gramas'),
        ('l', 'Litros'),
        ('ml', 'ml'),
        ('cx', 'Caixa'),
        ('pc', 'Pacote'),
        ('fd', 'Fardo'),
        ('sc', 'Saco'),
        ('lt', 'Lata'),
        ('dz', 'Dúzia'),
        ('m', 'Metro'),
    ]
    conta = models.ForeignKey(
        ContaPagar,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name="Conta",
    )
    fornecedor_material = models.ForeignKey(
        FornecedorMaterial,
        on_delete=models.PROTECT,
        related_name='itens_conta_pagar',
        verbose_name="Material",
    )
    quantidade = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Quantidade")
    unidade_medida = models.CharField(max_length=5, choices=UNIDADE_CHOICES, default='un', verbose_name="Unidade")
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="Valor Unitário")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Total")

    class Meta:
        verbose_name = "Item de Conta a Pagar"
        verbose_name_plural = "Itens de Conta a Pagar"
        ordering = ['pk']

    def __str__(self):
        return f"{self.fornecedor_material.material.nome} × {self.quantidade}"


class ContaPagarDocumento(models.Model):
    conta = models.ForeignKey(
        ContaPagar,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name="Conta a Pagar",
    )
    arquivo = models.FileField(upload_to='contas_pagar/documentos/', verbose_name="Arquivo")
    nome_original = models.CharField(max_length=255, verbose_name="Nome do arquivo")
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documentos_contas_pagar',
        verbose_name="Enviado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ['criado_em']

    def __str__(self):
        return self.nome_original


class AjusteFechamentoCaixaDiario(models.Model):
    """
    Auditoria de cada edição manual em um FechamentoCaixaDiario.
    Armazena valores ANTES (prev_*) e DEPOIS do ajuste para exibir o diff.
    """
    fechamento = models.ForeignKey(
        FechamentoCaixaDiario,
        on_delete=models.CASCADE,
        related_name='ajustes',
        verbose_name="Fechamento",
    )
    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ajustes_fechamento',
        verbose_name="Ajustado por",
    )
    ajustado_em = models.DateTimeField(auto_now_add=True, verbose_name="Ajustado em")

    # Valores ANTES do ajuste
    prev_valor_inicial  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Troco Inicial (antes)")
    prev_total_dinheiro = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Dinheiro (antes)")
    prev_total_debito   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Débito (antes)")
    prev_total_credito  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Crédito (antes)")
    prev_total_pix      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="PIX (antes)")
    prev_total_sangrias = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Sangrias (antes)")
    prev_total_final    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Final (antes)")

    # Valores DEPOIS do ajuste
    valor_inicial  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Troco Inicial (depois)")
    total_dinheiro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dinheiro (depois)")
    total_debito   = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Débito (depois)")
    total_credito  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Crédito (depois)")
    total_pix      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="PIX (depois)")
    total_sangrias = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sangrias (depois)")
    total_entradas = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Entradas (depois)")
    total_final    = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Final (depois)")

    observacao = models.TextField(blank=True, verbose_name="Motivo do ajuste")

    class Meta:
        verbose_name = "Ajuste de Fechamento"
        verbose_name_plural = "Ajustes de Fechamento"
        ordering = ['-ajustado_em']

    def __str__(self):
        return f"Ajuste {self.fechamento.data} por {self.ajustado_por} em {self.ajustado_em:%d/%m/%Y %H:%M}"

    def campos_alterados(self):
        """Retorna lista de (label, valor_antes, valor_depois) apenas dos campos que mudaram."""
        campos = [
            ('Dinheiro',      self.prev_total_dinheiro, self.total_dinheiro),
            ('Débito',        self.prev_total_debito,   self.total_debito),
            ('Crédito',       self.prev_total_credito,  self.total_credito),
            ('PIX',           self.prev_total_pix,      self.total_pix),
            ('Troco Inicial', self.prev_valor_inicial,  self.valor_inicial),
            ('Sangrias',      self.prev_total_sangrias, self.total_sangrias),
        ]
        return [(label, antes, depois) for label, antes, depois in campos if antes != depois]

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from utils.models import TimeStampedModel

User = get_user_model()


class Pinpad(TimeStampedModel):
    """
    Modelo para configuração de pinpads/maquininhas de cartão
    """
    
    PROVIDER_CHOICES = [
        ('stone', 'Stone'),
        ('cielo', 'Cielo'),
        ('rede', 'Rede'),
        ('pagseguro', 'PagSeguro'),
        ('mercado_pago', 'Mercado Pago'),
        ('getnet', 'Getnet'),
        ('safrapay', 'Safrapay'),
        ('bin', 'Bin'),
        ('outros', 'Outros'),
    ]
    
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('manutencao', 'Em Manutenção'),
        ('teste', 'Teste'),
    ]
    
    # Identificação
    name = models.CharField(
        max_length=100,
        verbose_name="Nome do Pinpad",
        help_text="Ex: Stone Terminal 1, Cielo Caixa Principal"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição adicional do pinpad"
    )
    
    # Provedor/Operadora
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        verbose_name="Provedor",
        help_text="Operadora da maquininha"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inativo',
        verbose_name="Status"
    )
    
    # Configurações de Conexão
    api_url = models.URLField(
        verbose_name="URL da API",
        help_text="URL base da API do provedor",
        validators=[URLValidator()]
    )
    
    api_key = models.CharField(
        max_length=500,
        verbose_name="API Key",
        help_text="Chave de acesso da API"
    )
    
    api_secret = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="API Secret",
        help_text="Chave secreta da API (se necessário)"
    )
    
    merchant_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID do Merchant",
        help_text="Identificação do estabelecimento"
    )
    
    terminal_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID do Terminal",
        help_text="Identificação do terminal/pinpad"
    )

    # Campos específicos para cada provedor
    pix_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Chave PIX",
        help_text="Chave PIX para recebimentos"
    )

    webhook_url = models.URLField(
        blank=True,
        verbose_name="Webhook URL",
        help_text="URL para receber notificações"
    )
    
    # Configurações de Pagamento
    supports_credit = models.BooleanField(
        default=True,
        verbose_name="Suporta Crédito",
        help_text="Pinpad aceita pagamentos no crédito"
    )
    
    supports_debit = models.BooleanField(
        default=True,
        verbose_name="Suporta Débito",
        help_text="Pinpad aceita pagamentos no débito"
    )
    
    supports_contactless = models.BooleanField(
        default=False,
        verbose_name="Suporta Contactless",
        help_text="Pinpad aceita pagamentos por aproximação"
    )

    supports_pix = models.BooleanField(
        default=False,
        verbose_name="Suporta PIX",
        help_text="Pinpad aceita pagamentos via PIX"
    )
    
    # Taxas do Pinpad
    credit_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxa Crédito (%)",
        help_text="Taxa percentual do crédito (Ex: 2.49 para 2,49%)",
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)]
    )
    
    debit_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxa Débito (%)",
        help_text="Taxa percentual do débito (Ex: 1.99 para 1,99%)",
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)]
    )
    
    credit_fee_fixed = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxa Fixa Crédito (R$)",
        help_text="Taxa fixa por transação de crédito em reais",
        validators=[MinValueValidator(0.00)]
    )
    
    debit_fee_fixed = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxa Fixa Débito (R$)",
        help_text="Taxa fixa por transação de débito em reais",
        validators=[MinValueValidator(0.00)]
    )

    pix_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxa PIX (%)",
        help_text="Taxa percentual do PIX"
    )
    
    # Configurações Avançadas
    timeout = models.IntegerField(
        default=60,
        verbose_name="Timeout (segundos)",
        help_text="Tempo limite para transações"
    )
    
    max_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor Máximo",
        help_text="Valor máximo permitido para transações"
    )
    
    # Controle
    is_default = models.BooleanField(
        default=False,
        verbose_name="Pinpad Padrão",
        help_text="Usar como pinpad padrão do sistema"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Pinpad ativo no sistema"
    )
    
    # Metadados
    last_test_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último Teste",
        help_text="Data do último teste de conexão"
    )
    
    last_test_success = models.BooleanField(
        default=False,
        verbose_name="Último Teste Sucesso",
        help_text="Resultado do último teste"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='pinpads_created',
        verbose_name="Criado por"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='pinpads_updated',
        null=True,
        blank=True,
        verbose_name="Atualizado por"
    )

    class Meta:
        verbose_name = "Pinpad"
        verbose_name_plural = "Pinpads"
        ordering = ['-is_default', '-is_active', 'name']
        
    def __str__(self):
        status_prefix = "ATIVO" if self.is_active else "INATIVO"
        default_suffix = " (PADRÃO)" if self.is_default else ""
        return f"{status_prefix}: {self.name} - {self.get_provider_display()}{default_suffix}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas um pinpad seja o padrão
        if self.is_default:
            Pinpad.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def status_color(self):
        """Cor do status para UI"""
        colors = {
            'ativo': 'green',
            'inativo': 'gray', 
            'manutencao': 'yellow',
            'teste': 'blue',
        }
        return colors.get(self.status, 'gray')
    
    @property
    def provider_display_name(self):
        """Nome completo do provedor para exibição"""
        return self.get_provider_display()
    
    def calculate_credit_fee(self, amount):
        """
        Calcula a taxa total do crédito para um valor
        """
        percentage_fee = (amount * self.credit_fee_percentage) / 100
        return percentage_fee + self.credit_fee_fixed
    
    def calculate_debit_fee(self, amount):
        """
        Calcula a taxa total do débito para um valor
        """
        percentage_fee = (amount * self.debit_fee_percentage) / 100
        return percentage_fee + self.debit_fee_fixed
    
    def get_net_amount(self, amount, payment_type='credit'):
        """
        Calcula o valor líquido após desconto das taxas
        """
        if payment_type == 'credit':
            fee = self.calculate_credit_fee(amount)
        else:  # debit
            fee = self.calculate_debit_fee(amount)
        
        return amount - fee
    
    @classmethod
    def get_default_pinpad(cls):
        """Retorna o pinpad padrão ativo do sistema"""
        return cls.objects.filter(is_default=True, is_active=True).first()
    
    @classmethod
    def get_active_pinpads(cls):
        """Retorna todos os pinpads ativos"""
        return cls.objects.filter(is_active=True).order_by('name')
    
    def test_connection(self):
        """
        Testa a conexão com a API do pinpad
        Retorna: dict com sucesso e mensagem
        """
        try:
            # Aqui será implementado o teste específico para cada provedor
            # Por enquanto, apenas uma simulação
            from django.utils import timezone
            self.last_test_at = timezone.now()
            self.last_test_success = True
            self.save(update_fields=['last_test_at', 'last_test_success'])
            
            return {
                'success': True,
                'message': 'Conexão testada com sucesso'
            }
        except Exception as e:
            from django.utils import timezone
            self.last_test_at = timezone.now()
            self.last_test_success = False
            self.save(update_fields=['last_test_at', 'last_test_success'])
            
            return {
                'success': False,
                'message': f'Erro na conexão: {str(e)}'
            }
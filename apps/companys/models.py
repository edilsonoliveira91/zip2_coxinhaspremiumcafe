from django.db import models
from django.core.validators import RegexValidator
from utils.models import TimeStampedModel

class Company(TimeStampedModel):
    """Modelo para dados da empresa para emissão de NFCe"""
    
    # Dados Básicos
    cnpj = models.CharField(
        max_length=18,
        unique=True,
        validators=[RegexValidator(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')],
        verbose_name="CNPJ",
        help_text="Formato: 00.000.000/0000-00"
    )
    
    razao_social = models.CharField(
        max_length=200,
        verbose_name="Razão Social"
    )
    
    nome_fantasia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nome Fantasia"
    )
    
    inscricao_estadual = models.CharField(
        max_length=20,
        verbose_name="Inscrição Estadual"
    )
    
    inscricao_municipal = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Inscrição Municipal"
    )
    
    # Endereço
    logradouro = models.CharField(max_length=100, verbose_name="Logradouro")
    numero = models.CharField(max_length=10, verbose_name="Número")
    complemento = models.CharField(max_length=50, blank=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=50, verbose_name="Bairro")
    cidade = models.CharField(max_length=50, verbose_name="Cidade")
    uf = models.CharField(
        max_length=2,
        choices=[
            ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
            ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
            ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
            ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'),
            ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'), ('PE', 'Pernambuco'),
            ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
            ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'),
            ('SC', 'Santa Catarina'), ('SP', 'São Paulo'), ('SE', 'Sergipe'),
            ('TO', 'Tocantins')
        ],
        verbose_name="UF"
    )
    cep = models.CharField(
        max_length=9,
        validators=[RegexValidator(r'^\d{5}-\d{3}$')],
        verbose_name="CEP",
        help_text="Formato: 00000-000"
    )
    
    # Contato
    telefone = models.CharField(max_length=15, blank=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, verbose_name="E-mail")
    
    # Configurações Fiscais
    REGIME_CHOICES = [
        ('1', 'Simples Nacional'),
        ('2', 'Simples Nacional - Excesso de Sublimite'),
        ('3', 'Regime Normal'),
    ]
    
    regime_tributario = models.CharField(
        max_length=1,
        choices=REGIME_CHOICES,
        default='1',
        verbose_name="Regime Tributário"
    )
    
    # NFCe Settings
    serie_nfce = models.PositiveIntegerField(
        default=1,
        verbose_name="Série NFCe",
        help_text="Série padrão para emissão de NFCe"
    )
    
    proximo_numero_nfce = models.PositiveIntegerField(
        default=1,
        verbose_name="Próximo Número NFCe",
        help_text="Próximo número sequencial da NFCe"
    )
    
    # CSC (Código de Segurança do Contribuinte)
    csc_id = models.PositiveIntegerField(
        verbose_name="CSC ID",
        help_text="ID do Token CSC cadastrado na SEFAZ"
    )
    
    csc_codigo = models.CharField(
        max_length=36,
        verbose_name="Código CSC",
        help_text="Código de Segurança do Contribuinte"
    )
    
    # Ambiente
    ambiente_nfce = models.CharField(
        max_length=1,
        choices=[
            ('1', 'Produção'),
            ('2', 'Homologação')
        ],
        default='2',
        verbose_name="Ambiente NFCe"
    )
    
    # Status
    ativa = models.BooleanField(
        default=True,
        verbose_name="Empresa Ativa"
    )
    
    # CFOP Padrão
    cfop_padrao = models.CharField(
        max_length=4,
        default='5102',
        verbose_name="CFOP Padrão",
        help_text="CFOP padrão para vendas (5102 - Venda no Estado)"
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['razao_social']

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"
    
    def get_proximo_numero_nfce(self):
        """Retorna e incrementa o próximo número da NFCe"""
        numero_atual = self.proximo_numero_nfce
        self.proximo_numero_nfce += 1
        self.save()
        return numero_atual
    
    @property
    def endereco_completo(self):
        """Retorna endereço formatado"""
        endereco = f"{self.logradouro}, {self.numero}"
        if self.complemento:
            endereco += f", {self.complemento}"
        endereco += f" - {self.bairro}, {self.cidade}/{self.uf} - {self.cep}"
        return endereco


class CertificadoDigital(TimeStampedModel):
    """Modelo para armazenar dados do certificado digital"""
    
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='certificado'
    )
    
    # Arquivo do certificado A1 (.pfx)
    arquivo_pfx = models.FileField(
        upload_to='certificados/',
        verbose_name="Arquivo Certificado (.pfx)",
        help_text="Arquivo do certificado digital A1"
    )
    
    senha_pfx = models.CharField(
        max_length=100,
        verbose_name="Senha do Certificado",
        help_text="Senha para acessar o certificado .pfx"
    )
    
    # Informações do certificado
    numero_serie = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Número de Série"
    )
    
    valido_ate = models.DateTimeField(
        verbose_name="Válido até",
        help_text="Data de expiração do certificado",
        blank=True,
        null=True
    )
    
    emissor = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Emissor"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Certificado Ativo"
    )

    class Meta:
        verbose_name = "Certificado Digital"
        verbose_name_plural = "Certificados Digitais"

    def __str__(self):
        validade = f" - Válido até {self.valido_ate.strftime('%d/%m/%Y')}" if self.valido_ate else ""
        return f"Certificado {self.company.razao_social}{validade}"
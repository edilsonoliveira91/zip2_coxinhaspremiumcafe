from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Company, CertificadoDigital

class CertificadoDigitalInline(admin.StackedInline):
    """Inline para certificado digital dentro da empresa"""
    model = CertificadoDigital
    extra = 0
    fields = ('arquivo_pfx', 'senha_pfx', 'numero_serie', 'valido_ate')

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin para empresa com certificado inline"""
    list_display = ('razao_social', 'nome_fantasia', 'cnpj', 'ativa', 'tem_certificado')
    list_filter = ('ativa', 'uf', 'ambiente_nfce')
    search_fields = ('razao_social', 'nome_fantasia', 'cnpj')
    
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('razao_social', 'nome_fantasia', 'cnpj', 'ativa')
        }),
        ('Endereço', {
            'fields': ('logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'cep')
        }),
        ('Dados Fiscais', {
            'fields': ('inscricao_estadual', 'inscricao_municipal', 'telefone', 'email')
        }),
        ('Configurações NFCe', {
            'fields': ('serie_nfce', 'proximo_numero_nfce', 'ambiente_nfce', 'csc_id', 'csc_codigo')
        })
    )
    
    inlines = [CertificadoDigitalInline]
    
    def tem_certificado(self, obj):
        """Mostra se tem certificado configurado"""
        try:
            return "✓ Sim" if obj.certificado else "✗ Não"
        except:
            return "✗ Não"
    tem_certificado.short_description = 'Certificado'

@admin.register(CertificadoDigital) 
class CertificadoDigitalAdmin(admin.ModelAdmin):
    """Admin independente para certificados"""
    list_display = ('company', 'numero_serie', 'valido_ate', 'tem_arquivo')
    list_filter = ('company',)
    fields = ('company', 'arquivo_pfx', 'senha_pfx', 'numero_serie', 'valido_ate')
    
    def tem_arquivo(self, obj):
        return "✓ Sim" if obj.arquivo_pfx else "✗ Não"
    tem_arquivo.short_description = 'Arquivo PFX'
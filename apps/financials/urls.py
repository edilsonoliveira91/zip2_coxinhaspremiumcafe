from django.urls import path
from . import views

app_name = 'financials'

urlpatterns = [
    # Dashboard financeiro
    path('', views.FinancialDashboardView.as_view(), name='dashboard'),
    
    # Sangrias
    path('sangria/', views.SangriaView.as_view(), name='sangria'),
    path('api/sangria/criar/', views.CriarSangriaView.as_view(), name='criar_sangria'),
    path('api/sangria/listar/', views.ListarSangriasView.as_view(), name='listar_sangrias'),
    path('api/sangria/<int:sangria_id>/excluir/', views.ExcluirSangriaView.as_view(), name='excluir_sangria'),
    path('extrato/', views.ExtratoView.as_view(), name='extrato'),
    path('fechamento-diario/', views.FechamentoCaixaDiarioView.as_view(), name='fechamento_diario'),
    path('fechamento-diario/realizar/', views.RealizarFechamentoCaixaView.as_view(), name='realizar_fechamento'),
    path('api/extrato-abertos/', views.ExtratoAbertosAPIView.as_view(), name='extrato_abertos'),
    path('comissao/', views.CommissionView.as_view(), name='comissao'),
    path('api/comissao/salvar/', views.SalvarComissaoView.as_view(), name='salvar_comissao'),
    path('caixa-adm/', views.CaixaAdmView.as_view(), name='caixa_adm'),
    path('api/malote/enviar/', views.EnviarMaloteView.as_view(), name='enviar_malote'),
    path('api/malote/despesa/', views.RegistrarDespesaMaloteView.as_view(), name='registrar_despesa_malote'),
    path('api/malote/concluir/', views.ConcluirMaloteView.as_view(), name='concluir_malote'),
    path('api/caixa-adm/transferir-banco/', views.TransferirCaixaAdmParaBancoView.as_view(), name='transferir_caixaadm_banco'),
    path('api/transferencia/<int:pk>/conciliar/', views.ConciliarTransferenciaView.as_view(), name='conciliar_transferencia'),
    path('conferencia-caixa/', views.ConferenciaCaixaView.as_view(), name='conferencia_caixa'),
    path('api/fechamento/atualizar/', views.AtualizarFechamentoCaixaView.as_view(), name='atualizar_fechamento_caixa'),
    path('api/fechamento/<int:pk>/despesa/', views.RegistrarDespesaFechamentoView.as_view(), name='registrar_despesa_fechamento'),
    path('api/despesa-dia/', views.RegistrarDespesaDiaView.as_view(), name='registrar_despesa_dia'),
]
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
    path('comissao/', views.CommissionView.as_view(), name='comissao'),
    path('api/comissao/salvar/', views.SalvarComissaoView.as_view(), name='salvar_comissao'),
]
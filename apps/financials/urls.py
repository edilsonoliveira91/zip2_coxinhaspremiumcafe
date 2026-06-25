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
    path('api/transferencia/<int:pk>/cancelar/', views.CancelarTransferenciaView.as_view(), name='cancelar_transferencia'),
    path('api/fechamento/<int:pk>/cancelar/', views.CancelarFechamentoView.as_view(), name='cancelar_fechamento'),
    path('conferencia-caixa/', views.ConferenciaCaixaView.as_view(), name='conferencia_caixa'),
    path('api/fechamento/atualizar/', views.AtualizarFechamentoCaixaView.as_view(), name='atualizar_fechamento_caixa'),
    path('api/fechamento/<int:pk>/despesa/', views.RegistrarDespesaFechamentoView.as_view(), name='registrar_despesa_fechamento'),
    path('api/despesa-dia/', views.RegistrarDespesaDiaView.as_view(), name='registrar_despesa_dia'),

    # Contas a Pagar
    path('contas-pagar/', views.ContasPagarListView.as_view(), name='contas_pagar'),
    path('relatorio/contas-pagas/', views.ContasPagasReportView.as_view(), name='relatorio_contas_pagas'),
    path('api/contas-pagar/criar/', views.ContasPagarCreateView.as_view(), name='contas_pagar_criar'),
    path('api/contas-pagar/<int:pk>/pagar/', views.ContasPagarMarcarPagoView.as_view(), name='contas_pagar_pagar'),
    path('api/contas-pagar/<int:pk>/pagar-banco/', views.ContasPagarPagarComBancoView.as_view(), name='contas_pagar_pagar_banco'),
    path('api/contas-pagar/<int:pk>/cancelar/', views.ContasPagarCancelarView.as_view(), name='contas_pagar_cancelar'),
    path('api/contas-pagar/<int:pk>/detalhe/', views.ContasPagarDetalheView.as_view(), name='contas_pagar_detalhe'),
    path('api/contas-pagar/<int:pk>/editar/', views.ContasPagarUpdateView.as_view(), name='contas_pagar_editar'),
    path('api/contas-pagar/<int:pk>/documentos/lista/', views.ContaPagarDocumentosListView.as_view(), name='contas_pagar_lista_docs'),
    path('api/contas-pagar/<int:pk>/documentos/upload/', views.ContaPagarUploadDocumentoView.as_view(), name='contas_pagar_upload_doc'),
    path('api/contas-pagar/documentos/<int:doc_pk>/excluir/', views.ContaPagarDocumentoDeleteView.as_view(), name='contas_pagar_excluir_doc'),
    path('api/fornecedor/<int:fornecedor_pk>/materiais/', views.FornecedorMateriaisAPIView.as_view(), name='fornecedor_materiais'),

    # Cadastro — Fornecedores
    path('cadastro/fornecedores/', views.FornecedorListView.as_view(), name='fornecedores'),
    path('cadastro/fornecedores/novo/', views.FornecedorFormPageView.as_view(), name='fornecedor_novo'),
    path('cadastro/fornecedores/<int:pk>/editar/', views.FornecedorFormPageView.as_view(), name='fornecedor_editar'),
    path('api/fornecedores/salvar/', views.FornecedorSalvarView.as_view(), name='fornecedor_salvar'),
    path('api/fornecedores/<int:pk>/salvar/', views.FornecedorSalvarView.as_view(), name='fornecedor_salvar_pk'),
    path('api/fornecedores/<int:pk>/excluir/', views.FornecedorDeleteView.as_view(), name='fornecedor_excluir'),
    path('api/fornecedores/<int:pk>/materiais/', views.FornecedorMateriaisListAPIView.as_view(), name='fornecedor_materiais_list'),
    path('api/fornecedor-material/<int:vinculo_pk>/remover/', views.FornecedorMaterialRemoverView.as_view(), name='fornecedor_material_remover'),

    # Cadastro — Materiais
    path('cadastro/materiais/', views.MaterialListView.as_view(), name='materiais'),
    path('api/materiais/criar/', views.MaterialCreateView.as_view(), name='material_criar'),
    path('api/materiais/<int:pk>/editar/', views.MaterialUpdateView.as_view(), name='material_editar'),
    path('api/materiais/<int:pk>/excluir/', views.MaterialDeleteView.as_view(), name='material_excluir'),

    # Cadastro — Plano de Contas
    path('cadastro/plano-de-contas/', views.PlanoDeContasListView.as_view(), name='plano_de_contas'),
    path('api/plano-de-contas/criar/', views.PlanoDeContasCreateView.as_view(), name='plano_de_contas_criar'),
    path('api/plano-de-contas/<int:pk>/editar/', views.PlanoDeContasUpdateView.as_view(), name='plano_de_contas_editar'),
    path('api/plano-de-contas/<int:pk>/excluir/', views.PlanoDeContasDeleteView.as_view(), name='plano_de_contas_excluir'),
]
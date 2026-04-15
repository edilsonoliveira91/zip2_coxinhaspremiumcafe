from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Dashboard de comandas
    path('', views.OrderDashboardView.as_view(), name='dashboard'),
    
    # ----- NOVAS ROTAS (Comanda -> Pedido) -----
    # Devem vir ANTES das rotas genéricas como '<str:code>/'
    path('nova-comanda/', views.NovaComandaView.as_view(), name='nova_comanda'),
    path('comanda/<str:numero>/', views.ComandaDetailView.as_view(), name='comanda_detail'),
    path('comanda/<str:numero>/novo-pedido/', views.NovoPedidoView.as_view(), name='novo_pedido'),
    path('api/comanda/<str:numero>/create-pedido/', views.ApiCreatePedidoView.as_view(), name='api_create_pedido'),
    path('api/comanda/<str:numero>/check/', views.ApiCheckComandaView.as_view(), name='api_check_comanda'),
    path('api/pedido/<int:pk>/update/', views.ApiUpdatePedidoView.as_view(), name='api_update_pedido'),

    path('pedido/<int:pk>/marcar-entregue/', views.MarcarPedidoEntregueView.as_view(), name='marcar_entregue'),
    path('pedido/<int:pk>/imprimir/', views.ImprimirPedidoView.as_view(), name='imprimir_pedido'),
    
    # CRUD de comandas
    path('list/', views.OrderListView.as_view(), name='list'),
    path('create/', views.OrderCreateView.as_view(), name='create'),

    # Comandas finalizadas
    path('finalizadas/', views.ClosedOrdersListView.as_view(), name='closed_orders'),
    path('<str:code>/emitir-nfce/', views.EmitirNFCeView.as_view(), name='emitir_nfce'),
    path('finalizadas/<str:code>/', views.ClosedOrderDetailView.as_view(), name='closed_order_detail'),

    # Rotas baseadas no código do objeto
    path('<str:code>/', views.OrderDetailView.as_view(), name='detail'),
    path('<str:code>/edit/', views.OrderUpdateView.as_view(), name='edit'),
    path('<str:code>/delete/', views.OrderDeleteView.as_view(), name='delete'),
    
    # Status da comanda
    path('<str:code>/status/', views.OrderStatusUpdateView.as_view(), name='status_update'),
    path('<str:code>/start/', views.OrderStartView.as_view(), name='start'),
    path('<str:code>/finish/', views.OrderFinishView.as_view(), name='finish'),
    path('<str:code>/deliver/', views.OrderDeliverView.as_view(), name='deliver'),
    path('<str:code>/cancel/', views.OrderCancelView.as_view(), name='cancel'),
    
    # Scanner de código de barras
    path('scanner/', views.ScannerView.as_view(), name='scanner'),
    path('scan/<str:code>/', views.ScanResultView.as_view(), name='scan_result'),
    
    # API para o modal (AJAX)
    path('api/create/', views.OrderCreateAPIView.as_view(), name='api_create'),
    path('api/<str:code>/', views.OrderDetailAPIView.as_view(), name='api_detail'),
    path('api/<str:code>/update/', views.OrderUpdateAPIView.as_view(), name='api_update'),
    path('api/<str:code>/status/', views.OrderStatusUpdateAPIView.as_view(), name='api_status_update'),
    path('api/<str:code>/finalize/', views.OrderFinalizeAPIView.as_view(), name='api_finalize'),
    
    # Relatórios
    path('reports/', views.OrderReportsView.as_view(), name='reports'),
    path('reports/daily/', views.DailyReportView.as_view(), name='daily_report'),
    
    # Impressão
    path('<str:code>/print/', views.OrderPrintView.as_view(), name='print'),
    path('<str:code>/barcode/', views.OrderBarcodeView.as_view(), name='barcode'),
    
    # Filtros úteis
    path('status/<str:status>/', views.OrdersByStatusView.as_view(), name='by_status'),
    path('today/', views.TodayOrdersView.as_view(), name='today'),
    path('active/', views.ActiveOrdersView.as_view(), name='active'),

    path('<str:code>/print-direct/', views.CheckoutDirectPrintView.as_view(), name='print_direct'),

    path('<str:code>/cupom-fiscal/', views.CupomFiscalPrintView.as_view(), name='cupom_fiscal'),
    path('<str:code>/cupom-fiscal-direto/', views.CupomFiscalDirectPrintView.as_view(), name='cupom_fiscal_direto'),
    path('teste-impressao-automatica/', views.TesteImpressaoAutomaticaView.as_view(), name='teste_impressao_automatica'),
    path('<str:code>/cupom-content/', views.OrderCupomContentView.as_view(), name='cupom_content'),
]
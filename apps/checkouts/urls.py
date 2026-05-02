from django.urls import path
from . import views

app_name = 'checkouts'

urlpatterns = [
    # Listagem principal de comandas para checkout
    path('', views.CheckoutOrderListView.as_view(), name='order_list'),

    # Fechamento de Caixa
    path('fechamento/', views.FechamentoCaixaView.as_view(), name='fechamento_caixa'),
    path('fechamento/fechar/', views.FechamentoCaixaFecharView.as_view(), name='fechar_caixa'),
    path('fechamento/<int:pk>/detalhe/', views.FechamentoCaixaDetalheView.as_view(), name='detalhe_sessao'),

    # Impressão de comanda
    path('orders/<str:code>/print/', views.CheckoutOrderPrintView.as_view(), name='order_print'),
    
    # API de finalização - DESCOMENTADO e CORRIGIDO
    path('finalize/<str:code>/', views.CheckoutFinalizeView.as_view(), name='finalize'),
    path('alterar-pagamento/<str:code>/', views.AlterarMetodoPagamentoView.as_view(), name='alterar_pagamento'),
    
    # URLs futuras para funcionalidades do checkout
    # path('orders/<str:code>/details/', views.CheckoutOrderDetailView.as_view(), name='order_detail'),
    # path('orders/<str:code>/finalize/', views.CheckoutOrderFinalizeView.as_view(), name='order_finalize'),
    
    # APIs futuras para checkout
    # path('api/orders/<str:code>/finalize/', views.CheckoutOrderFinalizeAPIView.as_view(), name='api_order_finalize'),
    # path('api/orders/refresh/', views.CheckoutOrderRefreshAPIView.as_view(), name='api_orders_refresh'),
]
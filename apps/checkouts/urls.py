from django.urls import path
from . import views

app_name = 'checkouts'

urlpatterns = [
    # Listagem principal de comandas para checkout
    path('', views.CheckoutOrderListView.as_view(), name='order_list'),

    path('orders/<str:code>/print/', views.CheckoutOrderPrintView.as_view(), name='order_print'),
    
    # URLs futuras para funcionalidades do checkout
    # path('orders/<str:code>/details/', views.CheckoutOrderDetailView.as_view(), name='order_detail'),
    # path('orders/<str:code>/print/', views.CheckoutOrderPrintView.as_view(), name='order_print'),
    # path('orders/<str:code>/finalize/', views.CheckoutOrderFinalizeView.as_view(), name='order_finalize'),
    
    # APIs futuras para checkout
    # path('api/orders/<str:code>/finalize/', views.CheckoutOrderFinalizeAPIView.as_view(), name='api_order_finalize'),
    # path('api/orders/refresh/', views.CheckoutOrderRefreshAPIView.as_view(), name='api_orders_refresh'),
]
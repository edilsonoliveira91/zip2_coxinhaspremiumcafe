from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.HomeView.as_view(), name='dashboard'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Gerenciamento de usuários e permissões
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),

    # API para verificar mudanças nas comandas
    path('api/check-orders-changes/', views.CheckOrderChangesView.as_view(), name='check_orders_changes'),

    # Impressão de comandas
    path('comandas/<str:comanda_code>/imprimir/', views.imprimir_comanda_view, name='imprimir_comanda'),
    path('comandas/<str:comanda_code>/imprimir-cupom/', views.imprimir_cupom_view, name='imprimir_cupom'),
]

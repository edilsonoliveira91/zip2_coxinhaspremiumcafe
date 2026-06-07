from django.urls import path
from . import views

app_name = 'banks'

urlpatterns = [
    path('', views.BankListView.as_view(), name='bank_list'),
    path('novo/', views.BankCreateView.as_view(), name='bank_create'),
    path('<int:pk>/editar/', views.BankUpdateView.as_view(), name='bank_edit'),
    path('<int:pk>/excluir/', views.BankDeleteView.as_view(), name='bank_delete'),
    path('<int:pk>/extrato/', views.BankStatementView.as_view(), name='bank_statement'),
    path('<int:pk>/adicionar/', views.BankAdicionarView.as_view(), name='bank_adicionar'),
    path('<int:pk>/pagar/', views.BankPagarView.as_view(), name='bank_pagar'),
    path('<int:pk>/transferir/', views.BankTransferirView.as_view(), name='bank_transferir'),
]

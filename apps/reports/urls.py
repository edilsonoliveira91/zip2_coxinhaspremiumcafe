from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('nfce/', views.NFCeReportView.as_view(), name='nfce_report'),
    path('vendas/', views.SalesReportView.as_view(), name='sales_report'),
]
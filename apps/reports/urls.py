from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('nfce/', views.NFCeReportView.as_view(), name='nfce_report'),
    path('nfce/emitir-lote/', views.EmitirLoteView.as_view(), name='emitir_lote'),
    path('nfce/emitir-lote/status/', views.EmitirLoteStatusView.as_view(), name='emitir_lote_status'),
    path('nfce/download-xml/', views.DownloadXMLZipView.as_view(), name='download_xml_zip'),
    path('vendas/', views.SalesReportView.as_view(), name='sales_report'),
    path('vendas/produtos/', views.SellsReportView.as_view(), name='sells_report'),
    path('cozinha/', views.CozinhaReportView.as_view(), name='cozinha_report'),
]
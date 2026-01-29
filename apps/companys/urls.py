from django.urls import path
from . import views

app_name = 'companys'

urlpatterns = [
    # Listar empresas
    path('', views.CompanyListView.as_view(), name='company_list'),
    
    # Criar empresa
    path('criar/', views.CompanyCreateView.as_view(), name='company_create'),
    
    # Visualizar empresa
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),
    
    # Editar empresa
    path('<int:pk>/editar/', views.CompanyUpdateView.as_view(), name='company_update'),
    
    # Deletar empresa
    path('<int:pk>/deletar/', views.company_delete, name='company_delete'),
    
    # Certificado Digital
    path('<int:company_id>/certificado/', views.CertificadoCreateView.as_view(), name='certificado_create'),
    path('<int:company_id>/certificado/editar/', views.CertificadoUpdateView.as_view(), name='certificado_update'),
    path('<int:company_id>/certificado/deletar/', views.CertificadoDeleteView.as_view(), name='certificado_delete'),
    
    # Testar certificado
    path('<int:company_id>/testar-certificado/', views.testar_certificado, name='testar_certificado'),
    
    # Consultar status SEFAZ
    path('<int:company_id>/status-sefaz/', views.consultar_status_sefaz, name='status_sefaz'),
    
    # Ativar/Desativar empresa
    path('<int:pk>/toggle-status/', views.toggle_company_status, name='toggle_status'),
]
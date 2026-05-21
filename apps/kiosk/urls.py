from django.urls import path
from . import views

app_name = 'kiosk'

urlpatterns = [
    path('', views.entrada, name='entrada'),
    path('mesa/<str:numero>/', views.cardapio, name='cardapio'),
    path('mesa/<str:numero>/enviar/', views.enviar_pedido, name='enviar_pedido'),
    path('mesa/<str:numero>/conta/', views.ver_conta, name='ver_conta'),
    path('mesa/<str:numero>/fechar/', views.fechar_mesa, name='fechar_mesa'),
    path('mesa/<str:numero>/status/', views.status_mesa, name='status_mesa'),
    path('confirmacao/<int:pedido_id>/', views.confirmacao, name='confirmacao'),
    path('manifest.json', views.manifest, name='manifest'),

    # Display Mesa — slides do carrossel
    path('display/imagens/', views.slide_list, name='slide_list'),
    path('display/imagens/novo/', views.slide_create, name='slide_create'),
    path('display/imagens/<int:pk>/editar/', views.slide_update, name='slide_update'),
    path('display/imagens/<int:pk>/excluir/', views.slide_delete, name='slide_delete'),

    # Versão do catálogo — usada pelo polling do kiosk
    path('api/catalog-version/', views.catalog_version, name='catalog_version'),
]

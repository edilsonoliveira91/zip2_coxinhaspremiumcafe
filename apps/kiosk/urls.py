from django.urls import path
from . import views

app_name = 'kiosk'

urlpatterns = [
    path('', views.entrada, name='entrada'),
    path('mesa/<str:numero>/', views.cardapio, name='cardapio'),
    path('mesa/<str:numero>/enviar/', views.enviar_pedido, name='enviar_pedido'),
    path('confirmacao/<int:pedido_id>/', views.confirmacao, name='confirmacao'),
    path('manifest.json', views.manifest, name='manifest'),
]

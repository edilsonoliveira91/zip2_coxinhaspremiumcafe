from django.urls import path
from . import views

app_name = 'config'

urlpatterns = [
    path('time_config', views.TimeConfigView.as_view(), name='time_config'),
    path('troco-inicial/', views.TrocoInicialView.as_view(), name='troco_inicial'),
    path('quebra-caixa/', views.QuebraCaixaView.as_view(), name='quebra_caixa'),
    path('garcom/', views.GarcomView.as_view(), name='cadastro_garcom'),
    path('kiosk-pin/', views.KioskPinView.as_view(), name='kiosk_pin'),
]

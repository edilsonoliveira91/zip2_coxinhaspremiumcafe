from django.urls import path
from . import views

app_name = 'config'

urlpatterns = [
    path('time_config', views.TimeConfigView.as_view(), name='time_config'),
    path('troco-inicial/', views.TrocoInicialView.as_view(), name='troco_inicial'),
]

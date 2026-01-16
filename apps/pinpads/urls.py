from django.urls import path
from . import views

app_name = 'pinpads'

urlpatterns = [
    # Listagem e CRUD
    path('', views.PinpadListView.as_view(), name='pinpad_list'),
    path('create/', views.PinpadCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.PinpadUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.PinpadDeleteView.as_view(), name='delete'),
    
    # APIs/AJAX Originais
    path('<int:pk>/test/', views.PinpadTestConnectionView.as_view(), name='test_connection'),
    path('<int:pk>/set-default/', views.PinpadSetDefaultView.as_view(), name='set_default'),
    path('<int:pk>/toggle-status/', views.PinpadToggleStatusView.as_view(), name='toggle_status'),
    path('stats/', views.PinpadStatsView.as_view(), name='stats'),
    
    # APIs Point - NOVAS
    path('<int:pinpad_id>/devices/', views.PointDevicesView.as_view(), name='point_devices'),
    path('<int:pinpad_id>/payment/', views.PointPaymentView.as_view(), name='point_payment'),
    path('<int:pinpad_id>/payment/<str:payment_intent_id>/status/', views.PointPaymentStatusView.as_view(), name='point_payment_status'),

    # Adicione esta linha junto com as outras URLs
    path('point-test/', views.PointTestView.as_view(), name='point_test'),
]
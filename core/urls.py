from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),  # Nova rota para healthcheck
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('', RedirectView.as_view(pattern_name='accounts:login'), name='home'),

    path('products/', include('products.urls', namespace='products')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('checkouts/', include('checkouts.urls', namespace='checkouts')),
]
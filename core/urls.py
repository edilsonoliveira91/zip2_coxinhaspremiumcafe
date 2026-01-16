from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from pinpads.views import mercadopago_webhook
from django.conf import settings
from django.conf.urls.static import static

@csrf_exempt
def health_check(request):
    return HttpResponse("OK", content_type="text/plain", status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('', RedirectView.as_view(pattern_name='accounts:login'), name='home'),

    path('products/', include('products.urls', namespace='products')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('checkouts/', include('checkouts.urls', namespace='checkouts')),
    path('pinpads/', include('pinpads.urls', namespace='pinpads')),
    path('financials/', include('financials.urls', namespace='financials')),
    
    # Webhook Mercado Pago - APENAS ESTA LINHA
    path('webhook/mercadopago/payment/', mercadopago_webhook, name='mercadopago_webhook'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from pinpads.views import mercadopago_webhook
from django.conf import settings
from django.views.static import serve
from django.views.decorators.http import require_GET


@require_GET
def service_worker_view(request):
    """Serve o SW na raiz para que o escopo cubra todas as URLs."""
    import os
    sw_path = os.path.join(settings.BASE_DIR, 'templates', 'static', 'sw.js')
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response

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
    path('companys/', include('companys.urls', namespace='companys')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('config/', include('config.urls', namespace='config')),
    path('kiosk/', include('kiosk.urls', namespace='kiosk')),
    
    # Service Worker na raiz (escopo cobre todas as URLs)
    path('sw.js', service_worker_view, name='service_worker'),

    # Webhook Mercado Pago - APENAS ESTA LINHA
    path('webhook/mercadopago/payment/', mercadopago_webhook, name='mercadopago_webhook'),
]

# Serve media files in both development and production.
# NOTE: django.conf.urls.static.static() returns [] when DEBUG=False,
# so we use re_path + serve directly to bypass that restriction.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
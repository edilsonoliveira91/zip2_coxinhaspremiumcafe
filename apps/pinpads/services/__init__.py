from .mercadopago import MercadoPagoPointService
from .rede import RedeItauService 
from .base import PaymentProviderService

PROVIDER_SERVICES = {
    'mercadopago': MercadoPagoPointService,
    'rede': RedeItauService,
    # 'stone': StoneService,  # Futuro
}

def get_payment_service(pinpad) -> PaymentProviderService:
    """Factory para criar serviço baseado no tipo do pinpad"""
    provider = pinpad.provider.lower() if pinpad.provider else 'mercadopago'
    service_class = PROVIDER_SERVICES.get(provider)
    
    if not service_class:
        raise ValueError(f"Provedor '{provider}' não suportado")
    
    return service_class(pinpad)
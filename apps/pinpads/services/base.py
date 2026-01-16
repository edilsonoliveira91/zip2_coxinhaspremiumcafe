from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from ..models import Pinpad

class PaymentProviderService(ABC):
    """Classe base abstrata para todos os provedores de pagamento"""
    
    def __init__(self, pinpad: Pinpad):
        self.pinpad = pinpad
        
    @abstractmethod
    def get_devices(self) -> Dict:
        """Lista dispositivos disponíveis"""
        pass
        
    @abstractmethod
    def create_payment_intent(self, device_id: str, amount: float, **kwargs) -> Dict:
        """Cria intenção de pagamento"""
        pass
        
    @abstractmethod
    def get_payment_intent(self, payment_intent_id: str) -> Dict:
        """Consulta status de intenção de pagamento"""
        pass
        
    @abstractmethod
    def create_pix_payment(self, amount: float, description: str) -> Dict:
        """Cria pagamento PIX"""
        pass
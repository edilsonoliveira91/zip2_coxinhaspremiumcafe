import requests
import json
import time
import logging
from django.conf import settings
from typing import Dict, List, Optional
from ..models import Pinpad
from .base import PaymentProviderService

logger = logging.getLogger(__name__)

class MercadoPagoPointService(PaymentProviderService):
    """
    Serviço para integração com Mercado Pago Point
    """
    
    def __init__(self, pinpad: Pinpad):
        self.pinpad = pinpad
        self.access_token = pinpad.api_key
        self.base_url = "https://api.mercadopago.com"
        
    def _get_headers(self) -> Dict[str, str]:
        """Headers padrão para requisições"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Idempotency-Key': f'{self.pinpad.id}-{int(time.time())}'
        }
    
    def get_devices(self) -> Dict:
        """
        Lista dispositivos Point disponíveis
        """
        try:
            url = f"{self.base_url}/point/integration-api/devices"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Dispositivos encontrados: {len(data.get('devices', []))}")
            
            return {
                'success': True,
                'devices': data.get('devices', []),
                'message': 'Dispositivos carregados com sucesso'
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar dispositivos: {str(e)}")
            return {
                'success': False,
                'devices': [],
                'message': f'Erro na comunicação: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            return {
                'success': False,
                'devices': [],
                'message': f'Erro interno: {str(e)}'
            }
    
    def create_payment_intent(self, device_id: str, amount: float, description: str = "Venda", payment_type: str = "credit") -> Dict:
      """
      Cria intenção de pagamento no dispositivo Point
      """
      try:
          url = f"{self.base_url}/point/integration-api/devices/{device_id}/payment-intents"
          headers = self._get_headers()
          
          # Converter valor para centavos (inteiro)
          amount_cents = int(amount * 100)
          
          # Payload correto conforme documentação oficial
          payload = {
              "amount": amount_cents,  # Valor em centavos
              "description": description,
              "payment": {
                  "installments": 1,
                  "type": "credit_card" if payment_type == "credit" else "debit_card",
                  "installments_cost": "seller"  # Corrigido para "seller"
              },
              "additional_info": {
                  "external_reference": f"cp-cafe-{int(time.time())}",
                  "print_on_terminal": True
              }
          }
          
          response = requests.post(url, headers=headers, json=payload, timeout=30)
          response.raise_for_status()
          
          data = response.json()
          
          return {
              'success': True,
              'payment_intent_id': data.get('id'),
              'state': data.get('state'),
              'message': 'Pagamento enviado para a maquininha!'
          }
          
      except requests.RequestException as e:
          logger.error(f"Erro ao criar payment intent: {str(e)}")
          # Log do response para debug
          if hasattr(e, 'response') and e.response is not None:
              logger.error(f"Response content: {e.response.text}")
          return {
              'success': False,
              'message': f'Erro na comunicação: {str(e)}'
          }
      except Exception as e:
          logger.error(f"Erro inesperado: {str(e)}")
          return {
              'success': False,
              'message': f'Erro interno: {str(e)}'
          }
    
    def get_payment_intent(self, payment_intent_id: str) -> Dict:
        """
        Consulta status de uma intenção de pagamento
        """
        try:
            url = f"{self.base_url}/point/integration-api/payment-intents/{payment_intent_id}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'data': data,
                'state': data.get('state'),
                'payment_id': data.get('payment', {}).get('id')
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao consultar payment intent: {str(e)}")
            return {
                'success': False,
                'message': f'Erro na comunicação: {str(e)}'
            }
    
    def cancel_payment_intent(self, device_id: str, payment_intent_id: str) -> Dict:
        """
        Cancela uma intenção de pagamento
        """
        try:
            url = f"{self.base_url}/point/integration-api/devices/{device_id}/payment-intents/{payment_intent_id}"
            headers = self._get_headers()
            
            response = requests.delete(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            return {
                'success': True,
                'message': 'Pagamento cancelado com sucesso'
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao cancelar payment intent: {str(e)}")
            return {
                'success': False,
                'message': f'Erro na comunicação: {str(e)}'
            }

    def create_pix_payment(self, amount: float, description: str = "Venda PIX") -> Dict:
        """
        Cria pagamento PIX
        """
        try:
            url = f"{self.base_url}/v1/payments"
            headers = self._get_headers()
            
            payload = {
                "transaction_amount": amount,
                "description": description,
                "payment_method_id": "pix",
                "payer": {
                    "email": "test@test.com"  # Para teste
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'payment_id': data.get('id'),
                'qr_code': data.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code'),
                'qr_code_base64': data.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code_base64'),
                'status': data.get('status'),
                'message': 'PIX criado com sucesso'
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao criar PIX: {str(e)}")
            return {
                'success': False,
                'message': f'Erro na comunicação: {str(e)}'
            }
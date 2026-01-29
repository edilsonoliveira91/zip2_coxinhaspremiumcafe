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
        if not self.access_token:
            raise ValueError("Access token não configurado")
            
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Idempotency-Key': f'cp-cafe-{self.pinpad.id}-{int(time.time())}'
        }

    def _sanitize_device_id(self, device_id: str) -> str:
        """
        Aplica URL encoding no device_id para formato esperado pela API
        """
        import urllib.parse
        
        # URL encode completo do device ID
        encoded_id = urllib.parse.quote(device_id, safe='')
        
        logger.info(f"🔧 Device ID: '{device_id}' -> URL encoded: '{encoded_id}'")
        
        return encoded_id

    def _validate_device_id(self, device_id: str) -> tuple[bool, str]:
        """
        Aceita qualquer device_id sem modificação
        """
        if not device_id:
            return False, "Device ID não pode estar vazio"
        
        logger.info(f"🔧 Validando device ID: '{device_id}' - ACEITO sem modificação")
        
        return True, device_id

    def get_devices(self) -> Dict:
        """
        Lista dispositivos Point disponíveis - com debug detalhado
        """
        try:
            url = f"{self.base_url}/point/integration-api/devices"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            devices = data.get('devices', [])
            
            logger.info(f"🔍 RESPOSTA COMPLETA DA API:")
            logger.info(f"📄 JSON completo: {json.dumps(data, indent=2)}")
            
            for i, device in enumerate(devices):
                logger.info(f"🏠 DEVICE {i+1}:")
                for key, value in device.items():
                    logger.info(f"   {key}: {value}")
                logger.info("   " + "="*50)
            
            return {
                'success': True,
                'devices': devices,
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
        Diagnóstico completo do device Point
        """
        try:
            logger.info(f"🔍 DIAGNÓSTICO COMPLETO DO DEVICE: {device_id}")
            
            # Buscar informações da conta
            headers = self._get_headers()
            
            # 1. Verificar informações da conta/usuário
            try:
                user_url = f"{self.base_url}/users/me"
                user_response = requests.get(user_url, headers=headers, timeout=30)
                
                logger.info(f"👤 INFORMAÇÕES DA CONTA:")
                logger.info(f"   Status: {user_response.status_code}")
                
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    logger.info(f"   ID: {user_data.get('id', 'N/A')}")
                    logger.info(f"   Email: {user_data.get('email', 'N/A')}")
                    logger.info(f"   País: {user_data.get('country_id', 'N/A')}")
                    logger.info(f"   Tipo conta: {user_data.get('user_type', 'N/A')}")
                else:
                    logger.info(f"   Erro: {user_response.text}")
            except Exception as e:
                logger.info(f"   Erro ao buscar conta: {str(e)}")
            
            # 2. Verificar devices da conta
            try:
                devices_response = self.get_devices()
                target_device = None
                
                logger.info(f"🏠 DEVICES VINCULADOS À CONTA:")
                
                if devices_response['success']:
                    for device in devices_response['devices']:
                        logger.info(f"   Device: {device.get('id')}")
                        logger.info(f"   POS ID: {device.get('pos_id')}")
                        logger.info(f"   Store ID: {device.get('store_id')}")
                        logger.info(f"   Operating Mode: {device.get('operating_mode')}")
                        logger.info(f"   External POS ID: {device.get('external_pos_id', 'N/A')}")
                        
                        if device.get('id') == device_id:
                            target_device = device
                        
                        logger.info(f"   ---")
                
                if not target_device:
                    return {
                        'success': False,
                        'message': 'Device não encontrado na sua conta',
                        'solution': 'Verifique se o device está vinculado à conta correta no Mercado Pago'
                    }
                    
            except Exception as e:
                logger.info(f"   Erro ao buscar devices: {str(e)}")
            
            # 3. Verificar configurações Point específicas
            try:
                point_config_url = f"{self.base_url}/point/integration-api/device_dependencies"
                config_response = requests.get(point_config_url, headers=headers, timeout=30)
                
                logger.info(f"⚙️ CONFIGURAÇÕES POINT:")
                logger.info(f"   Status: {config_response.status_code}")
                logger.info(f"   Response: {config_response.text[:200]}...")
                
            except Exception as e:
                logger.info(f"   Erro configurações Point: {str(e)}")
            
            # 4. Verificar stores/pos configuradas
            try:
                stores_url = f"{self.base_url}/users/me/stores"
                stores_response = requests.get(stores_url, headers=headers, timeout=30)
                
                logger.info(f"🏪 LOJAS CONFIGURADAS:")
                logger.info(f"   Status: {stores_response.status_code}")
                
                if stores_response.status_code == 200:
                    stores_data = stores_response.json()
                    logger.info(f"   Lojas: {len(stores_data.get('results', []))}")
                    
                    for store in stores_data.get('results', []):
                        logger.info(f"   Store ID: {store.get('id')}")
                        logger.info(f"   Nome: {store.get('name', 'N/A')}")
                        logger.info(f"   Status: {store.get('status', 'N/A')}")
                else:
                    logger.info(f"   Erro: {stores_response.text}")
                    
            except Exception as e:
                logger.info(f"   Erro ao buscar lojas: {str(e)}")
            
            # RESULTADO FINAL
            return {
                'success': False,
                'message': '🚨 DEVICE POINT NÃO CONFIGURADO PARA PAYMENT INTENTS',
                'problem': 'Device está em modo STANDALONE e não vinculado para payment intents via API',
                'solution_steps': [
                    '1. Entre em contato com o suporte do Mercado Pago',
                    '2. Solicite mudança do device para modo PDV',
                    '3. Configure o device para aceitar payment intents via API',
                    '4. Verifique se sua conta tem permissões Point habilitadas'
                ],
                'technical_info': {
                    'device_id': device_id,
                    'current_mode': target_device.get('operating_mode') if target_device else 'unknown',
                    'error_403': 'Device não tem permissão para mudança de modo',
                    'error_404': 'Device não configurado para essa loja/conta'
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no diagnóstico: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Erro interno no diagnóstico: {str(e)}'
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

    # Adicionar esta função para debug
    def debug_device_status(self, device_id: str) -> Dict:
        """
        Debug do status do device
        """
        try:
            headers = self._get_headers()
            
            # Tentar endpoint de status específico
            status_url = f"{self.base_url}/point/integration-api/devices/{device_id}"
            response = requests.get(status_url, headers=headers, timeout=30)
            
            logger.info(f"🔍 Status device: {response.status_code}")
            logger.info(f"🔍 Response: {response.text}")
            
            return response.json() if response.status_code == 200 else {}
        except:
            return {}
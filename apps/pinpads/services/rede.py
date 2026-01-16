# apps/pinpads/services/rede.py

import requests
import json
import time
import logging
import base64
from django.conf import settings
from typing import Dict, List, Optional
from ..models import Pinpad
from .base import PaymentProviderService

logger = logging.getLogger(__name__)

class RedeItauService(PaymentProviderService):
    """
    Serviço para integração com REDE Itaú
    """
    
    def __init__(self, pinpad: Pinpad):
        self.pinpad = pinpad
        self.client_id = pinpad.api_key  # PV (Número de filiação)
        self.client_secret = pinpad.api_secret  # Chave de integração
        self.sandbox = getattr(settings, 'REDE_SANDBOX', True)
        
        # URLs baseadas no ambiente
        if self.sandbox:
            self.auth_url = "https://rl7-sandbox-api.useredecloud.com.br/oauth2/token"
            self.base_url = "https://sandbox-erede.useredecloud.com.br/v2"
        else:
            self.auth_url = "https://api.userede.com.br/redelabs/oauth2/token"
            self.base_url = "https://api.userede.com.br/erede/v2"
            
        self._access_token = None
        self._token_expires_at = None
    
    def _get_access_token(self) -> str:
        """
        Obtém ou renova o token de acesso OAuth 2.0
        """
        current_time = time.time()
        
        # Verifica se o token ainda é válido (com margem de 2 minutos)
        if self._access_token and self._token_expires_at and current_time < (self._token_expires_at - 120):
            return self._access_token
        
        try:
            # Credenciais em base64
            credentials = f"{self.client_id}:{self.client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {credentials_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(self.auth_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 1440)  # Default 24 minutos
            self._token_expires_at = current_time + expires_in
            
            logger.info(f"Token REDE obtido com sucesso. Expira em {expires_in} segundos")
            return self._access_token
            
        except requests.RequestException as e:
            logger.error(f"Erro ao obter token REDE: {str(e)}")
            raise Exception(f"Erro na autenticação REDE: {str(e)}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Headers padrão para requisições autenticadas"""
        token = self._get_access_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def get_devices(self) -> Dict:
        """
        Lista dispositivos disponíveis
        Nota: REDE API e.Rede não possui endpoint específico para dispositivos físicos
        Retorna configuração do terminal configurado
        """
        try:
            # Para REDE, retornamos as informações do pinpad configurado
            device = {
                'id': self.pinpad.terminal_id or f'rede-{self.pinpad.id}',
                'name': self.pinpad.name,
                'provider': 'REDE Itaú',
                'status': 'AVAILABLE' if self.pinpad.status == 'ativo' else 'UNAVAILABLE',
                'supports_credit': self.pinpad.supports_credit,
                'supports_debit': self.pinpad.supports_debit,
                'supports_pix': self.pinpad.supports_pix,
                'merchant_id': self.pinpad.merchant_id
            }
            
            logger.info(f"Dispositivo REDE configurado: {device['id']}")
            
            return {
                'success': True,
                'devices': [device],
                'message': 'Dispositivo REDE carregado com sucesso'
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar dispositivos REDE: {str(e)}")
            return {
                'success': False,
                'devices': [],
                'message': f'Erro interno: {str(e)}'
            }
    
    def create_payment_intent(self, device_id: str, amount: float, description: str = "Venda", payment_type: str = "credit") -> Dict:
        """
        Cria intenção de pagamento na REDE
        """
        try:
            url = f"{self.base_url}/transactions"
            headers = self._get_headers()
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            
            # Payload para transação REDE
            payload = {
                "capture": True,  # Captura automática
                "kind": "credit" if payment_type == "credit" else "debit",
                "reference": f"cp-cafe-{int(time.time())}",
                "amount": amount_cents,
                "cardNumber": "4242424242424242",  # Será substituído pelos dados reais do cartão
                "expirationMonth": 12,
                "expirationYear": 2025,
                "securityCode": "123"
            }
            
            # Para ambiente de teste, usar dados de cartão de teste
            if self.sandbox:
                payload.update({
                    "cardNumber": "4242424242424242",  # Visa teste
                    "expirationMonth": 12,
                    "expirationYear": 2025,
                    "securityCode": "123"
                })
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 201:
                data = response.json()
                return {
                    'success': True,
                    'payment_intent_id': data.get('tid'),
                    'reference': data.get('reference'),
                    'state': 'approved' if data.get('returnCode') == '00' else 'pending',
                    'amount': amount,
                    'message': 'Transação processada pela REDE!'
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return {
                    'success': False,
                    'message': f'Erro REDE: {error_data.get("returnMessage", "Erro desconhecido")}'
                }
                
        except requests.RequestException as e:
            logger.error(f"Erro na requisição REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de comunicação REDE: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Erro inesperado REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro interno REDE: {str(e)}'
            }
    
    def get_payment_intent(self, payment_intent_id: str) -> Dict:
        """
        Consulta status de transação na REDE
        """
        try:
            url = f"{self.base_url}/transactions/{payment_intent_id}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Mapear status REDE para nosso padrão
            rede_status = data.get('returnCode', '')
            if rede_status == '00':
                state = 'approved'
            elif rede_status in ['51', '11']:  # Negada ou erro
                state = 'cancelled'
            else:
                state = 'pending'
            
            return {
                'success': True,
                'payment_intent_id': payment_intent_id,
                'state': state,
                'amount': data.get('amount', 0) / 100,  # Converter de centavos
                'return_code': rede_status,
                'return_message': data.get('returnMessage', ''),
                'authorization_code': data.get('authorizationCode', ''),
                'nsu': data.get('nsu', '')
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao consultar transação REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de consulta REDE: {str(e)}'
            }
    
    def create_pix_payment(self, amount: float, description: str) -> Dict:
        """
        Cria pagamento PIX na REDE
        """
        try:
            url = f"{self.base_url}/transactions"
            headers = self._get_headers()
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            
            # Payload para PIX REDE
            payload = {
                "kind": "pix",
                "reference": f"cp-cafe-pix-{int(time.time())}",
                "amount": amount_cents,
                "qrCode": {
                    "dateTimeExpiration": self._get_pix_expiration()
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 201:
                data = response.json()
                qr_data = data.get('qrCodeResponse', {})
                
                return {
                    'success': True,
                    'payment_id': data.get('tid'),
                    'qr_code': qr_data.get('qrCodeData', ''),
                    'qr_code_image': qr_data.get('qrCodeImage', ''),
                    'expires_at': qr_data.get('dateTimeExpiration', ''),
                    'amount': amount,
                    'message': 'PIX REDE gerado com sucesso!'
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return {
                    'success': False,
                    'message': f'Erro PIX REDE: {error_data.get("returnMessage", "Erro desconhecido")}'
                }
                
        except requests.RequestException as e:
            logger.error(f"Erro PIX REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de comunicação PIX REDE: {str(e)}'
            }
    
    def _get_pix_expiration(self) -> str:
        """
        Retorna data de expiração PIX (15 minutos a partir de agora)
        """
        import datetime
        expiration = datetime.datetime.now() + datetime.timedelta(minutes=15)
        return expiration.strftime('%Y-%m-%dT%H:%M:%S')
    
    def cancel_payment(self, payment_intent_id: str, amount: float = None) -> Dict:
        """
        Cancela/estorna transação na REDE
        """
        try:
            url = f"{self.base_url}/transactions/{payment_intent_id}/refunds"
            headers = self._get_headers()
            
            payload = {}
            if amount:
                payload['amount'] = int(amount * 100)  # Centavos para estorno parcial
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'refund_id': data.get('refundId'),
                'message': 'Estorno REDE processado com sucesso!'
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao cancelar transação REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de cancelamento REDE: {str(e)}'
            }
# apps/pinpads/services/rede.py

import requests
import json
import time
import logging
import base64
from django.conf import settings
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..models import Pinpad
from .base import PaymentProviderService

logger = logging.getLogger(__name__)

class RedeItauService(PaymentProviderService):
    """
    Serviço para integração com REDE Itaú
    Implementação baseada na documentação oficial e.Rede
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
        
        # Códigos de retorno REDE conforme documentação oficial
        self.return_codes = {
            '00': {'status': 'approved', 'message': 'Transação aprovada'},
            '05': {'status': 'declined', 'message': 'Contate a central do cartão'},
            '51': {'status': 'declined', 'message': 'Saldo insuficiente'},
            '54': {'status': 'declined', 'message': 'Cartão expirado'},
            '55': {'status': 'declined', 'message': 'Senha inválida'},
            '57': {'status': 'declined', 'message': 'Transação não permitida para o cartão'},
            '58': {'status': 'declined', 'message': 'Não autorizado. Contate a central do cartão'},
            '61': {'status': 'declined', 'message': 'Valor excede limite'},
            '62': {'status': 'declined', 'message': 'Cartão restrito temporariamente'},
            '63': {'status': 'declined', 'message': 'Violação de segurança'},
            '65': {'status': 'declined', 'message': 'Quantidade de saques excedida'},
            '78': {'status': 'declined', 'message': 'Transação não existe'},
            '82': {'status': 'declined', 'message': 'Cartão inválido'},
            '99': {'status': 'pending', 'message': 'Time-out'},
            '999': {'status': 'pending', 'message': 'Processando'}
        }
    
    def _get_access_token(self) -> str:
        """
        Obtém ou renova o token de acesso OAuth 2.0
        Conforme documentação oficial REDE
        """
        current_time = time.time()
        
        # Verifica se o token ainda é válido (com margem de 2 minutos)
        if self._access_token and self._token_expires_at and current_time < (self._token_expires_at - 120):
            return self._access_token
        
        try:
            # Credenciais em base64: Basic Base64(clientId:clientSecret)
            credentials = f"{self.client_id}:{self.client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {credentials_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            logger.info(f"Obtendo token OAuth2 REDE - Endpoint: {self.auth_url}")
            
            response = requests.post(self.auth_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 1440)  # Default 24 minutos (1440 segundos)
            self._token_expires_at = current_time + expires_in
            
            logger.info(f"Token REDE obtido com sucesso. Expira em {expires_in} segundos")
            return self._access_token
            
        except requests.RequestException as e:
            logger.error(f"Erro ao obter token REDE: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Resposta do servidor: {e.response.text}")
            raise Exception(f"Erro na autenticação REDE: {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado na autenticação REDE: {str(e)}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """Headers padrão para requisições autenticadas"""
        token = self._get_access_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def _generate_reference(self, prefix: str = "cp") -> str:
        """Gera referência única para transação"""
        timestamp = int(time.time())
        return f"{prefix}-{timestamp}-{self.pinpad.id}"
    
    def _parse_return_code(self, return_code: str) -> Dict[str, str]:
        """Mapeia código de retorno REDE para status padrão"""
        return self.return_codes.get(return_code, {
            'status': 'unknown',
            'message': f'Código desconhecido: {return_code}'
        })
    
    def get_devices(self) -> Dict:
        """
        Lista dispositivos disponíveis
        Para REDE, retornamos as informações do pinpad configurado
        """
        try:
            # Testa conectividade obtendo token
            self._get_access_token()
            
            device = {
                'id': self.pinpad.terminal_id or f'rede-{self.pinpad.id}',
                'name': self.pinpad.name,
                'provider': 'REDE Itaú',
                'status': 'AVAILABLE' if self.pinpad.status == 'ativo' else 'UNAVAILABLE',
                'supports_credit': self.pinpad.supports_credit,
                'supports_debit': self.pinpad.supports_debit,
                'supports_pix': self.pinpad.supports_pix,
                'merchant_id': self.pinpad.merchant_id,
                'client_id': self.client_id
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
                'message': f'Erro de conectividade REDE: {str(e)}'
            }
    
    def create_payment_intent(self, device_id: str, amount: float, description: str = "Venda", 
                             payment_type: str = "credit", card_data: Dict = None) -> Dict:
        """
        Cria intenção de pagamento na REDE
        Implementação conforme documentação oficial e.Rede
        """
        try:
            url = f"{self.base_url}/transactions"
            headers = self._get_headers()
            
            # Converter valor para centavos (formato REDE)
            amount_cents = int(amount * 100)
            
            # Reference único obrigatório (até 50 caracteres)
            reference = self._generate_reference("cafe")
            
            # Payload base conforme documentação oficial
            payload = {
                "capture": True,  # Captura automática (obrigatório para débito)
                "kind": "credit" if payment_type == "credit" else "debit",
                "reference": reference,  # Obrigatório - código da transação
                "orderId": reference,   # Código do pedido (opcional mas recomendado)
                "amount": amount_cents,  # Valor em centavos
                "origin": 1  # e.Rede = 1 (conforme documentação)
            }
            
            # Dados do cartão
            if card_data:
                payload.update({
                    "cardNumber": card_data.get("number"),
                    "expirationMonth": int(card_data.get("exp_month")),
                    "expirationYear": int(card_data.get("exp_year")),
                    "securityCode": card_data.get("cvc"),
                    "cardholderName": card_data.get("holder_name", "").upper()
                })
            elif self.sandbox:
                # Dados de teste para sandbox
                payload.update({
                    "cardNumber": "4242424242424242",  # Visa teste
                    "expirationMonth": 12,
                    "expirationYear": 2026,
                    "securityCode": "123",
                    "cardholderName": "TESTE SANDBOX REDE"
                })
            else:
                return {
                    'success': False,
                    'message': 'Dados do cartão são obrigatórios para transação em produção'
                }
            
            # Adicionar installments se for crédito e não for à vista
            if payment_type == "credit":
                payload["installments"] = 1  # À vista por padrão
            
            logger.info(f"Enviando transação REDE: {reference} - Valor: R$ {amount:.2f} - Tipo: {payment_type}")
            logger.debug(f"Payload REDE: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            logger.info(f"Resposta REDE - Status: {response.status_code}")
            
            if response.status_code == 201:  # Created - sucesso
                data = response.json()
                return_code = data.get('returnCode', '')
                code_info = self._parse_return_code(return_code)
                
                result = {
                    'success': return_code == '00',
                    'payment_intent_id': data.get('tid'),
                    'reference': data.get('reference'),
                    'state': code_info['status'],
                    'amount': amount,
                    'return_code': return_code,
                    'authorization_code': data.get('authorizationCode', ''),
                    'nsu': data.get('nsu', ''),
                    'date_time': data.get('dateTime', ''),
                    'card_bin': data.get('cardBin', ''),
                    'last4': data.get('last4', ''),
                    'message': code_info['message']
                }
                
                # Informações da bandeira se disponíveis
                if 'brand' in data:
                    brand = data['brand']
                    result.update({
                        'brand_name': brand.get('name', ''),
                        'brand_return_code': brand.get('returnCode', ''),
                        'brand_message': brand.get('returnMessage', ''),
                        'brand_authorization_code': brand.get('authorizationCode', ''),
                        'brand_tid': brand.get('brandTid', '')
                    })
                
                logger.info(f"Transação REDE processada: {return_code} - {code_info['message']}")
                return result
                
            else:
                # Tratamento de erros HTTP
                try:
                    error_data = response.json()
                    error_message = error_data.get('returnMessage', 'Erro desconhecido')
                    error_code = error_data.get('returnCode', '')
                except:
                    error_message = f'Erro HTTP {response.status_code}'
                    error_code = str(response.status_code)
                
                logger.error(f"Erro REDE: {error_code} - {error_message}")
                return {
                    'success': False,
                    'message': f'Erro REDE: {error_message}',
                    'return_code': error_code
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
        Consulta status de transação na REDE por TID
        """
        try:
            url = f"{self.base_url}/transactions/{payment_intent_id}"
            headers = self._get_headers()
            
            logger.info(f"Consultando transação REDE: {payment_intent_id}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Consulta retorna estrutura diferente da criação
            authorization = data.get('authorization', {})
            return_code = authorization.get('returnCode', '')
            code_info = self._parse_return_code(return_code)
            
            result = {
                'success': True,
                'payment_intent_id': payment_intent_id,
                'state': code_info['status'],
                'amount': authorization.get('amount', 0) / 100,  # Converter de centavos
                'return_code': return_code,
                'authorization_code': authorization.get('authorizationCode', ''),
                'nsu': authorization.get('nsu', ''),
                'reference': authorization.get('reference', ''),
                'date_time': authorization.get('dateTime', ''),
                'status': authorization.get('status', ''),
                'message': code_info['message']
            }
            
            # Informações de captura se disponível
            capture = data.get('capture')
            if capture:
                result['capture'] = {
                    'date_time': capture.get('dateTime', ''),
                    'amount': capture.get('amount', 0) / 100,
                    'nsu': capture.get('nsu', '')
                }
            
            # Informações de 3DS se disponível
            three_ds = data.get('threeDSecure')
            if three_ds:
                result['three_ds'] = {
                    'eci': three_ds.get('eci', ''),
                    'cavv': three_ds.get('cavv', ''),
                    'return_code': three_ds.get('returnCode', ''),
                    'return_message': three_ds.get('returnMessage', '')
                }
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Erro ao consultar transação REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de consulta REDE: {str(e)}'
            }
    
    def create_pix_payment(self, amount: float, description: str = "Pagamento PIX") -> Dict:
        """
        Cria pagamento PIX na REDE
        Implementação conforme documentação oficial e.Rede PIX
        """
        try:
            url = f"{self.base_url}/transactions"
            headers = self._get_headers()
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            
            # Reference único
            reference = self._generate_reference("pix")
            
            # Payload PIX conforme documentação oficial
            payload = {
                "kind": "pix",  # Obrigatório para PIX
                "reference": reference,  # Obrigatório - até 50 chars
                "orderId": reference,  # Código do pedido
                "amount": amount_cents,  # Valor em centavos
                "qrCode": {
                    "dateTimeExpiration": self._get_pix_expiration_iso_format()
                }
            }
            
            logger.info(f"Criando PIX REDE: {reference} - Valor: R$ {amount:.2f}")
            logger.debug(f"Payload PIX REDE: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 201:
                data = response.json()
                qr_response = data.get('qrCodeResponse', {})
                
                result = {
                    'success': True,
                    'payment_id': data.get('tid'),
                    'reference': data.get('reference'),
                    'qr_code': qr_response.get('qrCodeData', ''),  # String EMV (copia e cola)
                    'qr_code_image': qr_response.get('qrCodeImage', ''),  # Base64
                    'expires_at': qr_response.get('dateTimeExpiration', ''),
                    'amount': amount,
                    'date_time': data.get('dateTime', ''),
                    'return_code': data.get('returnCode', ''),
                    'return_message': data.get('returnMessage', ''),
                    'message': 'QR Code PIX REDE gerado com sucesso!'
                }
                
                logger.info(f"PIX REDE criado com sucesso: {data.get('tid')}")
                return result
                
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('returnMessage', 'Erro desconhecido')
                    error_code = error_data.get('returnCode', '')
                except:
                    error_message = f'Erro HTTP {response.status_code}'
                    error_code = str(response.status_code)
                
                logger.error(f"Erro PIX REDE: {error_code} - {error_message}")
                return {
                    'success': False,
                    'message': f'Erro PIX REDE: {error_message}',
                    'return_code': error_code
                }
            
        except Exception as e:
            logger.error(f"Erro PIX REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de comunicação PIX REDE: {str(e)}'
            }
    
    def _get_pix_expiration_iso_format(self) -> str:
        """
        Retorna data de expiração PIX no formato ISO conforme documentação REDE
        Formato: YYYY-MM-DDThh:mm:ss
        Prazo máximo: 15 dias (usando 30 minutos para operação)
        """
        expiration = datetime.now() + timedelta(minutes=30)
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
                cancel_type = "parcial"
            else:
                cancel_type = "total"
            
            # Reference para o cancelamento
            payload['referenceRefund'] = self._generate_reference("cancel")
            
            logger.info(f"Cancelando transação REDE: {payment_intent_id} - Tipo: {cancel_type}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            result = {
                'success': True,
                'refund_id': data.get('refundId'),
                'reference_refund': data.get('referenceRefund'),
                'return_code': data.get('returnCode', ''),
                'return_message': data.get('returnMessage', ''),
                'date_time': data.get('refundDateTime', ''),
                'amount': amount or 0,
                'message': f'Estorno {cancel_type} REDE processado com sucesso!'
            }
            
            logger.info(f"Estorno REDE realizado: {data.get('refundId')}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Erro ao cancelar transação REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de cancelamento REDE: {str(e)}'
            }
    
    def get_transaction_by_reference(self, reference: str) -> Dict:
        """
        Consulta transação por reference (código do pedido)
        """
        try:
            url = f"{self.base_url}/transactions"
            headers = self._get_headers()
            
            params = {'reference': reference}
            
            logger.info(f"Consultando transação REDE por reference: {reference}")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Mesmo formato da consulta por TID
            authorization = data.get('authorization', {})
            return_code = authorization.get('returnCode', '')
            code_info = self._parse_return_code(return_code)
            
            return {
                'success': True,
                'payment_intent_id': authorization.get('tid', ''),
                'reference': reference,
                'state': code_info['status'],
                'amount': authorization.get('amount', 0) / 100,
                'return_code': return_code,
                'message': code_info['message']
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao consultar por reference REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de consulta REDE: {str(e)}'
            }
    
    def capture_transaction(self, payment_intent_id: str, amount: float = None) -> Dict:
        """
        Captura transação pré-autorizada na REDE
        """
        try:
            url = f"{self.base_url}/transactions/{payment_intent_id}"
            headers = self._get_headers()
            
            payload = {}
            if amount:
                payload['amount'] = int(amount * 100)  # Valor em centavos
            
            logger.info(f"Capturando transação REDE: {payment_intent_id}")
            
            response = requests.put(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return_code = data.get('returnCode', '')
            code_info = self._parse_return_code(return_code)
            
            return {
                'success': return_code == '00',
                'tid': payment_intent_id,
                'return_code': return_code,
                'return_message': data.get('returnMessage', ''),
                'nsu': data.get('nsu', ''),
                'authorization_code': data.get('authorizationCode', ''),
                'amount': amount or 0,
                'message': f'Captura REDE: {code_info["message"]}'
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao capturar transação REDE: {str(e)}")
            return {
                'success': False,
                'message': f'Erro de captura REDE: {str(e)}'
            }
    
    def test_connection(self) -> Dict:
        """
        Testa conectividade com API REDE
        """
        try:
            token = self._get_access_token()
            
            return {
                'success': True,
                'message': 'Conexão REDE estabelecida com sucesso',
                'client_id': self.client_id,
                'environment': 'sandbox' if self.sandbox else 'production',
                'token_obtained': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Falha na conexão REDE: {str(e)}',
                'client_id': self.client_id,
                'environment': 'sandbox' if self.sandbox else 'production',
                'token_obtained': False
            }
import os
import tempfile
import hashlib
import base64
import re
import uuid
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree
from signxml import XMLSigner, methods
import requests
import urllib3
from requests import Session
from requests.adapters import HTTPAdapter

# Desabilita warnings SSL para homologação
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NFCeService:
    """
    Serviço para emissão de NFCe com ferramentas de debugging avançadas
    """
    
    def __init__(self, empresa):
        self.empresa = empresa
        self.certificado = None
        
        # Verifica se tem certificado configurado
        if hasattr(empresa, 'certificado') and empresa.certificado:
            self.certificado = empresa.certificado
            print(f"[INFO] Certificado encontrado: {self.certificado.arquivo_pfx.name}")
            print("[INFO] Certificado configurado - Modo real disponível")
        else:
            print("[INFO] Nenhum certificado encontrado - Apenas modo simulação")
    
    def emitir_nfce(self, order, cpf_cliente=None):
        """
        Método principal para emissão de NFCe com cupom fiscal
        """
        try:
            # Pega próximo número da NFCe
            numero = self._obter_proximo_numero_nfce()
            
            # Monta dados da NFCe
            dados_nfce = self._montar_dados_nfce(order, numero, cpf_cliente)
            
            # Se tem certificado, tenta emissão real
            if self.certificado:
                ambiente = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog
                print(f"[INFO] Tentando emissão real em {'PRODUÇÃO' if ambiente == '1' else 'HOMOLOGAÇÃO'}...")
                try:
                    resultado = self._emitir_nfce_real(dados_nfce)
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    print(f"[ERROR] Falha na emissão real: {e}\n{tb}")
                    # Não faz fallback para simulação — retorna erro real
                    return {
                        'sucesso': False,
                        'erro': f'Falha na conexão com a SEFAZ: {str(e)}',
                        'detalhe': tb,
                        'modo': 'erro_conexao',
                    }

                # Gerar cupom fiscal após emissão bem-sucedida
                if resultado['sucesso']:
                    cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                    resultado['cupom_fiscal'] = cupom_info
                    print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")

                return resultado
            else:
                print("[INFO] Nenhum certificado — modo simulação")
                resultado = self._emitir_nfce_simulado(dados_nfce)

            # Cupom fiscal em simulação
            if resultado['sucesso']:
                cupom_info = self.salvar_cupom_fiscal(dados_nfce, resultado)
                resultado['cupom_fiscal'] = cupom_info
                print(f"[INFO] Cupom fiscal gerado: {cupom_info.get('url_impressao', 'N/A')}")

            return resultado
            
        except Exception as e:
            print(f"[ERROR] Erro geral na emissão de NFCe: {e}")
            return {
                'sucesso': False,
                'erro': f'Erro na emissão: {str(e)}',
                'modo': 'erro'
            }

    def _debug_xml_profundo(self, xml_content):
        """
        Análise profunda do XML para identificar problemas específicos
        """
        print("\n" + "="*80)
        print("DEBUGGING PROFUNDO DO XML")
        print("="*80)
        
        try:
            # 1. Verificações básicas
            print(f"[DEBUG] Tamanho do XML: {len(xml_content)} bytes")
            print(f"[DEBUG] Codificação detectada: {xml_content[:50]}")
            
            # 2. Análise da estrutura XML
            try:
                root = etree.fromstring(xml_content.encode('utf-8'))
                print(f"[DEBUG] ✓ XML bem formado")
                print(f"[DEBUG] Root element: {root.tag}")
                print(f"[DEBUG] Namespace: {root.nsmap}")
            except Exception as e:
                print(f"[DEBUG] ✗ XML malformado: {e}")
                return
            
            # 3. Verificações específicas NFCe
            problemas = []
            
            # Verifica namespace principal
            if 'http://www.portalfiscal.inf.br/nfe' not in str(etree.tostring(root)):
                problemas.append("Namespace NFe ausente ou incorreto")
            
            # Verifica estrutura obrigatória
            nfe_elem = root.find('.//{http://www.portalfiscal.inf.br/nfe}NFe')
            if nfe_elem is None:
                problemas.append("Elemento NFe não encontrado")
            else:
                infnfe = nfe_elem.find('.//{http://www.portalfiscal.inf.br/nfe}infNFe')
                if infnfe is None:
                    problemas.append("Elemento infNFe não encontrado")
                else:
                    id_attr = infnfe.get('Id')
                    if not id_attr or not id_attr.startswith('NFe'):
                        problemas.append(f"Atributo Id inválido: {id_attr}")
            
            # Verifica elementos obrigatórios
            elementos_obrigatorios = [
                ('idLote', './/{http://www.portalfiscal.inf.br/nfe}idLote'),
                ('indSinc', './/{http://www.portalfiscal.inf.br/nfe}indSinc'),
                ('ide', './/{http://www.portalfiscal.inf.br/nfe}ide'),
                ('emit', './/{http://www.portalfiscal.inf.br/nfe}emit'),
                ('det', './/{http://www.portalfiscal.inf.br/nfe}det'),
                ('total', './/{http://www.portalfiscal.inf.br/nfe}total'),
                ('pag', './/{http://www.portalfiscal.inf.br/nfe}pag')
            ]
            
            for nome, xpath in elementos_obrigatorios:
                elem = root.find(xpath)
                if elem is None:
                    problemas.append(f"Elemento obrigatório ausente: {nome}")
                else:
                    print(f"[DEBUG] ✓ {nome}: encontrado")
            
            # Verifica campos específicos do IDE
            ide = root.find('.//{http://www.portalfiscal.inf.br/nfe}ide')
            if ide is not None:
                campos_ide = {
                    'cUF': 'Código UF',
                    'cNF': 'Código NF',
                    'mod': 'Modelo (deve ser 65)',
                    'serie': 'Série',
                    'nNF': 'Número NF',
                    'dhEmi': 'Data/Hora Emissão',
                    'tpNF': 'Tipo NF',
                    'cMunFG': 'Código Município',
                    'tpAmb': 'Tipo Ambiente'
                }
                
                # CORRIGIDO: namespace na string
                namespace = "http://www.portalfiscal.inf.br/nfe"
                
                for campo, desc in campos_ide.items():
                    elem = ide.find(f'.//{{{namespace}}}{campo}')
                    if elem is not None:
                        valor = elem.text
                        print(f"[DEBUG] {campo}: {valor} ({desc})")
                        
                        # Validações específicas
                        if campo == 'mod' and valor != '65':
                            problemas.append(f"Modelo deve ser 65, encontrado: {valor}")
                        elif campo == 'cUF' and not valor.isdigit():
                            problemas.append(f"Código UF inválido: {valor}")
                        elif campo == 'dhEmi' and 'T' not in valor:
                            problemas.append(f"Formato data/hora inválido: {valor}")
                    else:
                        problemas.append(f"Campo IDE obrigatório ausente: {campo}")
            
            # Verifica CNPJ emitente
            cnpj = root.find('.//{http://www.portalfiscal.inf.br/nfe}emit/{http://www.portalfiscal.inf.br/nfe}CNPJ')
            if cnpj is not None:
                cnpj_text = cnpj.text
                if not re.match(r'^\d{14}$', cnpj_text):
                    problemas.append(f"CNPJ inválido: {cnpj_text}")
                else:
                    print(f"[DEBUG] ✓ CNPJ válido: {cnpj_text}")
            else:
                problemas.append("CNPJ do emitente não encontrado")
            
            # Verifica produto
            prod = root.find('.//{http://www.portalfiscal.inf.br/nfe}det/{http://www.portalfiscal.inf.br/nfe}prod')
            if prod is not None:
                campos_prod = ['cProd', 'xProd', 'NCM', 'CFOP', 'uCom', 'qCom', 'vUnCom', 'vProd']
                for campo in campos_prod:
                    elem = prod.find(f'.//{{{namespace}}}{campo}')
                    if elem is None:
                        problemas.append(f"Campo produto obrigatório ausente: {campo}")
                    else:
                        print(f"[DEBUG] ✓ {campo}: {elem.text}")
            
            # 4. Verifica formatação de números
            numeros_formatacao = [
                ('.//{http://www.portalfiscal.inf.br/nfe}qCom', r'^\d+\.\d{4}$', 'Quantidade Com'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vUnCom', r'^\d+\.\d{2,10}$', 'Valor Unitário Com'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vProd', r'^\d+\.\d{2}$', 'Valor Produto'),
                ('.//{http://www.portalfiscal.inf.br/nfe}vNF', r'^\d+\.\d{2}$', 'Valor Total NF')
            ]
            
            for xpath, padrao, desc in numeros_formatacao:
                elem = root.find(xpath)
                if elem is not None:
                    if not re.match(padrao, elem.text):
                        problemas.append(f"Formatação incorreta em {desc}: {elem.text} (esperado: {padrao})")
                    else:
                        print(f"[DEBUG] ✓ Formatação correta {desc}: {elem.text}")
            
            # 5. Relatório final
            print(f"\n[DEBUG] TOTAL DE PROBLEMAS ENCONTRADOS: {len(problemas)}")
            if problemas:
                print("[DEBUG] LISTA DE PROBLEMAS:")
                for i, problema in enumerate(problemas, 1):
                    print(f"[DEBUG] {i}. {problema}")
            else:
                print("[DEBUG] ✓ Nenhum problema óbvio encontrado no XML")
            
            print("="*80)
            
        except Exception as e:
            print(f"[DEBUG] Erro no debugging: {e}")
            import traceback
            traceback.print_exc()

    def _testar_xml_contra_sefaz(self, xml_content):
        """
        Testa um XML específico contra SEFAZ sem assinatura - CORRIGIDO
        """
        try:
            # Conecta com SEFAZ com configuração melhorada
            session = Session()
            
            # Headers mais completos para evitar bloqueios
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            retry_strategy = Retry(
                total=3, 
                backoff_factor=2,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            session.verify = False  # Apenas para homologação
            
            transport = Transport(session=session)
            
            # URLs alternativas do SEFAZ SP
            urls_wsdl = [
                "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx?WSDL",
                "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao.asmx?WSDL",
                "https://homologacao.nfce.fazenda.sp.gov.br/nfeweb/services/nfeautorizacao4.asmx?WSDL"
            ]
            
            for wsdl_url in urls_wsdl:
                try:
                    print(f"[DEBUG] Tentando WSDL: {wsdl_url}")
                    client = Client(wsdl_url, transport=transport)
                    
                    # Converte para elemento lxml
                    xml_element = etree.fromstring(xml_content.encode('utf-8'))
                    
                    # Tenta enviar
                    response = client.service.nfeAutorizacaoLote(xml_element)
                    
                    if hasattr(response, 'cStat'):
                        return f"cStat: {response.cStat}, Motivo: {response.xMotivo}"
                    else:
                        return f"Resposta: {response}"
                        
                except Exception as url_error:
                    print(f"[DEBUG] Falha com {wsdl_url}: {url_error}")
                    continue
            
            return "Erro: Todos os WSDLs falharam"
                
        except Exception as e:
            return f"Erro no teste: {str(e)}"

    def _gerar_xml_ultra_minimo(self, dados):
        """
        Gera XML com absolutamente o mínimo possível
        """
        print("[DEBUG] Gerando XML ULTRA MÍNIMO para teste...")
        
        chave_acesso = dados['chave_acesso']
        agora = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M:%S-03:00')
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
    <idLote>1</idLote>
    <indSinc>1</indSinc>
    <NFe>
        <infNFe versao="4.00" Id="NFe{chave_acesso}">
            <ide>
                <cUF>35</cUF>
                <cNF>12345678</cNF>
                <natOp>Venda</natOp>
                <mod>65</mod>
                <serie>1</serie>
                <nNF>{dados['numero']}</nNF>
                <dhEmi>{agora}</dhEmi>
                <tpNF>1</tpNF>
                <idDest>1</idDest>
                <cMunFG>3523800</cMunFG>
                <tpImp>4</tpImp>
                <tpEmis>1</tpEmis>
                <cDV>{chave_acesso[-1]}</cDV>
                <tpAmb>2</tpAmb>
                <finNFe>1</finNFe>
                <indFinal>1</indFinal>
                <indPres>1</indPres>
            </ide>
            <emit>
                <CNPJ>10361831000223</CNPJ>
                <xNome>TESTE LTDA</xNome>
                <enderEmit>
                    <xLgr>RUA TESTE</xLgr>
                    <nro>1</nro>
                    <xBairro>CENTRO</xBairro>
                    <cMun>3523800</cMun>
                    <xMun>Itapetininga</xMun>
                    <UF>SP</UF>
                    <CEP>18200000</CEP>
                </enderEmit>
                <IE>371468833110</IE>
                <CRT>1</CRT>
            </emit>
            <det nItem="1">
                <prod>
                    <cProd>1</cProd>
                    <xProd>TESTE</xProd>
                    <NCM>21069090</NCM>
                    <CFOP>5102</CFOP>
                    <uCom>UN</uCom>
                    <qCom>1.0000</qCom>
                    <vUnCom>1.00</vUnCom>
                    <uTrib>UN</uTrib>
                    <qTrib>1.0000</qTrib>
                    <vUnTrib>1.00</vUnTrib>
                    <vProd>1.00</vProd>
                    <indTot>1</indTot>
                </prod>
                <imposto>
                    <ICMS>
                        <ICMSSN102>
                            <orig>0</orig>
                            <CSOSN>102</CSOSN>
                        </ICMSSN102>
                    </ICMS>
                </imposto>
            </det>
            <total>
                <ICMSTot>
                    <vBC>0.00</vBC>
                    <vICMS>0.00</vICMS>
                    <vICMSDeson>0.00</vICMSDeson>
                    <vFCP>0.00</vFCP>
                    <vBCST>0.00</vBCST>
                    <vST>0.00</vST>
                    <vFCPST>0.00</vFCPST>
                    <vFCPSTRet>0.00</vFCPSTRet>
                    <vProd>1.00</vProd>
                    <vFrete>0.00</vFrete>
                    <vSeg>0.00</vSeg>
                    <vDesc>0.00</vDesc>
                    <vII>0.00</vII>
                    <vIPI>0.00</vIPI>
                    <vIPIDevol>0.00</vIPIDevol>
                    <vPIS>0.00</vPIS>
                    <vCOFINS>0.00</vCOFINS>
                    <vOutro>0.00</vOutro>
                    <vNF>1.00</vNF>
                </ICMSTot>
            </total>
            <transp>
                <modFrete>9</modFrete>
            </transp>
            <pag>
                <detPag>
                    <tPag>01</tPag>
                    <vPag>1.00</vPag>
                </detPag>
            </pag>
        </infNFe>
    </NFe>
</enviNFe>'''
        
        return xml_content

    def _emitir_nfce_real(self, dados):
        """
        Emite NFCe real no SEFAZ:
        1. Carrega certificado A1
        2. Gera XML com dados reais
        3. Assina com XMLDSig RSA-SHA1
        4. Envia para webservice SEFAZ
        5. Parseia resposta e retorna protocolo
        """
        cert_path = None
        key_path = None

        try:
            # 1. Carregar certificado
            print("[INFO] Carregando certificado digital...")
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()

            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data,
                self.certificado.senha_pfx.encode('utf-8'),
            )
            print(f"[INFO] Certificado carregado: {certificate.subject.rfc4514_string()}")

            # 2. Exportar cert e key para arquivos temporários (necessário para requests cert=)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pem', mode='wb') as cf:
                cf.write(certificate.public_bytes(serialization.Encoding.PEM))
                cert_path = cf.name

            with tempfile.NamedTemporaryFile(delete=False, suffix='.key', mode='wb') as kf:
                kf.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
                key_path = kf.name

            # 3. Gerar XML completo
            print("[INFO] Gerando XML da NFCe...")
            xml_content = self._gerar_xml_nfce_completo(dados)

            # 4. Assinar XML
            print("[INFO] Assinando XML com certificado digital...")
            xml_assinado = self._assinar_xml(xml_content, dados)
            print(f"[INFO] XML assinado ({len(xml_assinado)} chars)")

            # 5. Enviar para SEFAZ
            print("[INFO] Enviando para SEFAZ...")
            resposta_xml = self._chamar_sefaz(xml_assinado, cert_path, key_path)

            # 6. Parsear resposta
            resultado_sefaz = self._parsear_resposta_sefaz(resposta_xml)

            if resultado_sefaz['sucesso']:
                print(f"[SEFAZ] NFCe autorizada! Protocolo: {resultado_sefaz['protocolo']}")
                return {
                    'sucesso': True,
                    'numero_nfce': dados['numero'],
                    'chave_acesso': dados['chave_acesso'],
                    'protocolo': resultado_sefaz['protocolo'],
                    'modo': 'producao' if self.empresa.ambiente_nfce == '1' else 'homologacao',
                }
            else:
                _extra = ''
                if resultado_sefaz.get('cStat') == '464':
                    _extra = (
                        f"\n\nhash_input usado:\n{getattr(self, '_last_qr_hash_input', 'N/A')}"
                        f"\n\nc_hash gerado:\n{getattr(self, '_last_qr_hash', 'N/A')}"
                        f"\n\ncsc_id={self.empresa.csc_id!r}  csc_codigo={self.empresa.csc_codigo!r}"
                    )
                return {
                    'sucesso': False,
                    'erro': resultado_sefaz['erro'] + _extra,
                    'cStat': resultado_sefaz.get('cStat', ''),
                    'xMotivo': resultado_sefaz.get('xMotivo', ''),
                }

        except Exception as e:
            print(f"[ERROR] Falha na emissão real: {e}")
            import traceback
            traceback.print_exc()
            raise e

        finally:
            self._limpar_certificados_temporarios(cert_path, key_path)

    def _obter_proximo_numero_nfce(self):
        """Obtém próximo número sequencial da NFCe a partir da empresa"""
        return self.empresa.get_proximo_numero_nfce()
    
    def _montar_dados_nfce(self, order, numero, cpf_cliente=None):
        """Monta estrutura de dados da NFCe"""
        chave_acesso = self._gerar_chave_acesso(numero)
        
        return {
            'numero': numero,
            'chave_acesso': chave_acesso,
            'order': order,
            'cpf_cliente': cpf_cliente,
            'qr_code': self._gerar_qr_code(chave_acesso, order.total_amount)  # CORRIGIDO: total_amount
        }
    
    def _gerar_chave_acesso(self, numero):
        """Gera chave de acesso da NFCe usando dados da empresa"""
        agora = timezone.localtime(timezone.now())
        uf_codigo = self._get_codigo_uf()
        cnpj = re.sub(r'\D', '', self.empresa.cnpj)  # apenas dígitos
        modelo = "65"
        serie = f"{self.empresa.serie_nfce:03d}"
        numero_formatado = f"{numero:09d}"
        # Código numérico: 8 dígitos derivados do CNPJ+número
        codigo_numerico = f"{abs(hash(cnpj + str(numero))) % 100000000:08d}"

        chave_sem_dv = (
            f"{uf_codigo}"             # 2 digits
            f"{agora.strftime('%y%m')}"  # 4 digits
            f"{cnpj}"                  # 14 digits
            f"{modelo}"                # 2 digits
            f"{serie}"                 # 3 digits
            f"{numero_formatado}"      # 9 digits
            "1"                        # tpEmis = 1 (normal)
            f"{codigo_numerico}"       # 8 digits
        )  # total 43 + cDV = 44

        dv = self._calcular_dv_chave_acesso(chave_sem_dv)
        chave_completa = chave_sem_dv + str(dv)
        print(f"[DEBUG] Chave de acesso gerada: {chave_completa} ({len(chave_completa)} chars)")
        return chave_completa
    
    def _calcular_dv_chave_acesso(self, chave_sem_dv):
        """Calcula dígito verificador da chave de acesso"""
        sequencia = "4329876543298765432987654329876543298765432"
        soma = 0
        
        for i, digito in enumerate(chave_sem_dv):
            soma += int(digito) * int(sequencia[i])
        
        resto = soma % 11
        
        if resto in [0, 1]:
            return 0
        else:
            return 11 - resto

    def _gerar_qr_code(self, chave_acesso, valor_total):
        """
        Gera URL do QR Code da NFCe conforme schema NF-e 4.00 (QRCODE V2 ONLINE).
        Formato V2: <url>?p=<chave>|2|<tpAmb>|<cIdToken>|<cHashQRCode>
        cIdToken: csc_id SEM zeros à esquerda (ex: 1, não 000001)
        cHashQRCode = SHA1(chave + "|2|" + tpAmb + "|" + cIdToken + csc_codigo).upper()
        Schema pattern: CHAVE|2|tpAmb|cIdToken(0-999999 sem leading zeros)|SHA1(40 hex)
        """
        tp_amb = self.empresa.ambiente_nfce  # '1' prod, '2' homolog
        # Na URL: cIdToken SEM zeros à esquerda
        cid_token_url = str(int(str(self.empresa.csc_id)))
        csc_codigo = self.empresa.csc_codigo.strip()

        # sped-nfe ref: SHA1(chNFe|2|tpAmb|cIdToken_sem_zeroscCSC) -- cIdToken é inteiro sem zeros, sem pipe antes do cCSC
        hash_input = f"{chave_acesso}|2|{tp_amb}|{cid_token_url}{csc_codigo}"
        c_hash = hashlib.sha1(hash_input.encode('utf-8')).hexdigest().upper()
        self._last_qr_hash_input = hash_input
        self._last_qr_hash = c_hash

        print(f"[QRCODE DEBUG] cid_token_url={cid_token_url!r}")
        print(f"[QRCODE DEBUG] csc_codigo={csc_codigo!r} len={len(csc_codigo)}")
        print(f"[QRCODE DEBUG] hash_input={hash_input!r}")
        print(f"[QRCODE DEBUG] c_hash={c_hash!r}")

        url_base = self._get_url_consulta_qrcode()
        qr_url = f"{url_base}?p={chave_acesso}|2|{tp_amb}|{cid_token_url}|{c_hash}"
        return qr_url

    def _get_url_consulta_qrcode(self):
        """Retorna URL de consulta pública do QR Code por UF e ambiente"""
        uf = self.empresa.uf
        amb = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog

        urls = {
            'SP': {
                '1': 'https://www.nfce.fazenda.sp.gov.br/qrcode',
                '2': 'https://www.homologacao.nfce.fazenda.sp.gov.br/qrcode',
            },
            'MG': {
                '1': 'https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
                '2': 'https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
            },
            'RS': {
                '1': 'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx',
                '2': 'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx',
            },
            'PR': {
                '1': 'http://www.fazenda.pr.gov.br/nfce/qrcode',
                '2': 'http://www.fazenda.pr.gov.br/nfce/qrcode',
            },
        }
        # SVRS states (default for unregistered states)
        svrs_states = ['AC', 'AL', 'AP', 'DF', 'ES', 'PB', 'PI', 'RN', 'RO', 'RR', 'SC', 'SE', 'TO']
        svrs_urls = {
            '1': 'https://nfce.svrs.rs.gov.br/off/gqrcodeoff.aspx',
            '2': 'https://nfce-homologacao.svrs.rs.gov.br/off/gqrcodeoff.aspx',
        }

        if uf in urls:
            return urls[uf].get(amb, urls[uf]['2'])
        elif uf in svrs_states:
            return svrs_urls.get(amb, svrs_urls['2'])
        else:
            # AN/SVAN states
            return svrs_urls.get(amb, svrs_urls['2'])

    def _get_url_chave(self):
        """Retorna URL de consulta pública (urlChave) — máx 85 chars no schema NF-e 4.00.
        Diferente da URL do QR Code que inclui /Paginas/ConsultaQRCode.aspx"""
        uf = self.empresa.uf
        amb = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog
        urls = {
            'SP': {
                '1': 'https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica',
                '2': 'https://www.homologacao.nfce.fazenda.sp.gov.br/NFCeConsultaPublica',
            },
            'MG': {
                '1': 'https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
                '2': 'https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml',
            },
            'RS': {
                '1': 'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx',
                '2': 'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx',
            },
            'PR': {
                '1': 'http://www.fazenda.pr.gov.br/nfce/qrcode',
                '2': 'http://www.fazenda.pr.gov.br/nfce/qrcode',
            },
        }
        svrs_states = ['AC', 'AL', 'AP', 'DF', 'ES', 'PB', 'PI', 'RN', 'RO', 'RR', 'SC', 'SE', 'TO']
        svrs_urls = {
            '1': 'https://nfce.svrs.rs.gov.br/off/gqrcodeoff.aspx',
            '2': 'https://nfce-homologacao.svrs.rs.gov.br/off/gqrcodeoff.aspx',
        }
        if uf in urls:
            return urls[uf].get(amb, urls[uf]['2'])
        elif uf in svrs_states:
            return svrs_urls.get(amb, svrs_urls['2'])
        else:
            return svrs_urls.get(amb, svrs_urls['2'])

    def _gerar_xml_nfce_completo(self, dados):
        """Gera XML da NFCe usando lxml SubElement (sem enviNFe - adicionado no envio)"""
        NS = 'http://www.portalfiscal.inf.br/nfe'
        chave_acesso = dados['chave_acesso']
        order = dados['order']
        empresa = self.empresa
        ambiente = empresa.ambiente_nfce  # '1'=prod, '2'=homolog

        agora = timezone.localtime(timezone.now()).isoformat(timespec='seconds')
        uf_codigo = self._get_codigo_uf()
        cod_municipio = empresa.codigo_municipio_ibge or '3523800'
        cnpj_digits = re.sub(r'\D', '', empresa.cnpj)
        ie_digits = re.sub(r'\D', '', empresa.inscricao_estadual) or 'ISENTO'
        cep_digits = re.sub(r'\D', '', empresa.cep)
        cfop = empresa.cfop_padrao or '5102'
        crt = empresa.regime_tributario
        c_nf = chave_acesso[35:43] if len(chave_acesso) == 44 else '00000001'

        # ── NFe root ─────────────────────────────────────────────────────────
        nsmap = {None: NS}
        NFe = etree.Element('NFe', nsmap=nsmap)
        infNFe = etree.SubElement(NFe, 'infNFe', Id=f'NFe{chave_acesso}', versao='4.00')

        # ── ide ──────────────────────────────────────────────────────────────
        ide = etree.SubElement(infNFe, 'ide')
        etree.SubElement(ide, 'cUF').text = uf_codigo
        etree.SubElement(ide, 'cNF').text = c_nf
        etree.SubElement(ide, 'natOp').text = 'VENDA'
        etree.SubElement(ide, 'mod').text = '65'
        etree.SubElement(ide, 'serie').text = str(empresa.serie_nfce)
        etree.SubElement(ide, 'nNF').text = str(dados['numero'])
        etree.SubElement(ide, 'dhEmi').text = agora
        etree.SubElement(ide, 'tpNF').text = '1'
        etree.SubElement(ide, 'idDest').text = '1'
        etree.SubElement(ide, 'cMunFG').text = cod_municipio
        etree.SubElement(ide, 'tpImp').text = '4'
        etree.SubElement(ide, 'tpEmis').text = '1'
        etree.SubElement(ide, 'cDV').text = chave_acesso[-1]
        etree.SubElement(ide, 'tpAmb').text = ambiente
        etree.SubElement(ide, 'finNFe').text = '1'
        etree.SubElement(ide, 'indFinal').text = '1'
        etree.SubElement(ide, 'indPres').text = '1'
        etree.SubElement(ide, 'indIntermed').text = '0'
        etree.SubElement(ide, 'procEmi').text = '0'
        etree.SubElement(ide, 'verProc').text = '1.0.0'

        # ── emit ─────────────────────────────────────────────────────────────
        emit = etree.SubElement(infNFe, 'emit')
        etree.SubElement(emit, 'CNPJ').text = cnpj_digits
        etree.SubElement(emit, 'xNome').text = empresa.razao_social[:60]
        if empresa.nome_fantasia:
            etree.SubElement(emit, 'xFant').text = empresa.nome_fantasia[:60]
        enderEmit = etree.SubElement(emit, 'enderEmit')
        etree.SubElement(enderEmit, 'xLgr').text = empresa.logradouro[:60]
        etree.SubElement(enderEmit, 'nro').text = empresa.numero[:60]
        etree.SubElement(enderEmit, 'xBairro').text = empresa.bairro[:60]
        etree.SubElement(enderEmit, 'cMun').text = cod_municipio
        etree.SubElement(enderEmit, 'xMun').text = empresa.cidade[:60]
        etree.SubElement(enderEmit, 'UF').text = empresa.uf
        etree.SubElement(enderEmit, 'CEP').text = cep_digits
        etree.SubElement(emit, 'IE').text = ie_digits
        etree.SubElement(emit, 'CRT').text = crt

        # ── dest (destinatário) ───────────────────────────────────────────────
        cpf_cliente = dados.get('cpf_cliente')
        cpf_digits = re.sub(r'\D', '', str(cpf_cliente)) if cpf_cliente else ''
        if cpf_digits and len(cpf_digits) == 11:
            dest = etree.SubElement(infNFe, 'dest')
            etree.SubElement(dest, 'CPF').text = cpf_digits
            etree.SubElement(dest, 'xNome').text = 'CONSUMIDOR'
            etree.SubElement(dest, 'indIEDest').text = '9'

        # ── det (itens) ───────────────────────────────────────────────────────
        all_items = []
        for pedido in order.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']):
            for item in pedido.items.select_related('product').all():
                all_items.append(item)

        if not all_items:
            all_items = [{'_fallback': True}]

        valor_total = float(order.total_amount)
        total_item_sum = 0.0

        total_pis_nf = Decimal('0.00')
        total_cofins_nf = Decimal('0.00')

        for i, item in enumerate(all_items, 1):
            if isinstance(item, dict) and item.get('_fallback'):
                nome_orig = 'VENDA DE ALIMENTOS'
                qty = 1.0
                v_unit = valor_total
                v_prod = valor_total
                ncm_val = '21069090'
                cprod = '1'
                # CRT=1 usa CSOSN 102; CRT=3 usa CST 40 (isenta) com CFOP 5102
                cst_icms_item = '102' if crt == '1' else '40'
                cfop_item = cfop[:4] if crt == '1' else '5102'
                cbenef_item = ''
                cst_pis_item = '99'
                aliq_pis_item = Decimal('0.00')
                aliq_cofins_item = Decimal('0.00')
            else:
                nome_orig = item.product.name[:120]
                qty = float(item.quantity)
                v_unit = float(item.unit_price)
                v_prod = round(qty * v_unit, 2)
                ncm_val = getattr(item.product, 'ncm', '') or '21069090'
                ncm_val = re.sub(r'\D', '', str(ncm_val))
                if len(ncm_val) not in (2, 8): ncm_val = '21069090'
                cprod = str(getattr(item.product, 'id', i))
                # CFOP do produto (fallback para empresa)
                _cfop_prod = (getattr(item.product, 'cfop', '') or '').strip()[:4]
                cfop_item = _cfop_prod if _cfop_prod else cfop[:4]
                # CST ICMS: para CRT=1 mapeia para CSOSN; para CRT=3 usa CST direto do produto
                _cst_raw = (getattr(item.product, 'cst_icms', '') or '').strip()
                if crt == '1':
                    _csosn_map = {'060': '500', '090': '900', '500': '500', '900': '900'}
                    cst_icms_item = _csosn_map.get(_cst_raw, '102')
                else:
                    # Normaliza: aceita '0', '00', '060', '60' → sempre 2 dígitos
                    _cst_norm = _cst_raw.lstrip('0') or '0'
                    _cst_norm = _cst_norm.zfill(2)
                    if _cst_norm not in ('00','10','20','30','40','41','50','51','60','70','90'):
                        _cst_norm = '60' if cfop_item in ('5405','6405') else '40'
                    cst_icms_item = _cst_norm
                    # Garantir consistência CST ↔ CFOP para CRT=3:
                    # CST 60 (ST) exige CFOP 5405; CST 00 (tributada) exige CFOP 5101
                    # CST 40/41 (isenta/não trib.) usa CFOP 5102
                    if cst_icms_item == '60' and cfop_item not in ('5405', '6405'):
                        cfop_item = '5405'
                    elif cst_icms_item in ('40', '41') and cfop_item not in ('5102', '6102', '5405', '6405'):
                        cfop_item = '5102'
                    elif cst_icms_item == '00' and cfop_item not in ('5101', '6101', '5102', '6102'):
                        cfop_item = '5101'
                # CBENEF
                _cbenef_raw = (getattr(item.product, 'codigo_cbenef', '') or '').strip()
                cbenef_item = _cbenef_raw if _cbenef_raw and _cbenef_raw.upper() != 'SEM CBENEF' else ''
                # PIS/COFINS
                cst_pis_item = str(getattr(item.product, 'cst_pis_cofins', '') or '99').strip().zfill(2)
                aliq_pis_item = Decimal(str(getattr(item.product, 'aliq_pis', 0) or 0))
                aliq_cofins_item = Decimal(str(getattr(item.product, 'aliq_cofins', 0) or 0))

            total_item_sum += v_prod

            # Em homologação o nome deve ser este texto fixo
            xprod_text = ('NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL'
                          if ambiente == '2' else nome_orig)

            det = etree.SubElement(infNFe, 'det', nItem=str(i))
            prod = etree.SubElement(det, 'prod')
            etree.SubElement(prod, 'cProd').text = cprod
            etree.SubElement(prod, 'cEAN').text = 'SEM GTIN'
            etree.SubElement(prod, 'xProd').text = xprod_text
            etree.SubElement(prod, 'NCM').text = ncm_val
            # cBenef: CSOSN 900 (CRT=1) ou CST 90 (CRT=3) — regime especial
            if cbenef_item and cst_icms_item in ('900', '90'):
                etree.SubElement(prod, 'cBenef').text = cbenef_item
            etree.SubElement(prod, 'CFOP').text = cfop_item
            etree.SubElement(prod, 'uCom').text = 'UN'
            etree.SubElement(prod, 'qCom').text = f'{qty:.4f}'
            etree.SubElement(prod, 'vUnCom').text = f'{v_unit:.4f}'
            etree.SubElement(prod, 'vProd').text = f'{v_prod:.2f}'
            etree.SubElement(prod, 'cEANTrib').text = 'SEM GTIN'
            etree.SubElement(prod, 'uTrib').text = 'UN'
            etree.SubElement(prod, 'qTrib').text = f'{qty:.4f}'
            etree.SubElement(prod, 'vUnTrib').text = f'{v_unit:.4f}'
            etree.SubElement(prod, 'indTot').text = '1'

            # Impostos
            imposto = etree.SubElement(det, 'imposto')
            icms = etree.SubElement(imposto, 'ICMS')
            if crt == '1':
                if cst_icms_item == '500':
                    icms_sn = etree.SubElement(icms, 'ICMSSN500')
                    etree.SubElement(icms_sn, 'orig').text = '0'
                    etree.SubElement(icms_sn, 'CSOSN').text = '500'
                elif cst_icms_item == '900':
                    icms_sn = etree.SubElement(icms, 'ICMSSN900')
                    etree.SubElement(icms_sn, 'orig').text = '0'
                    etree.SubElement(icms_sn, 'CSOSN').text = '900'
                    etree.SubElement(icms_sn, 'modBC').text = '3'
                    etree.SubElement(icms_sn, 'vBC').text = '0.00'
                    etree.SubElement(icms_sn, 'pICMS').text = '0.00'
                    etree.SubElement(icms_sn, 'vICMS').text = '0.00'
                else:
                    icms_sn = etree.SubElement(icms, 'ICMSSN102')
                    etree.SubElement(icms_sn, 'orig').text = '0'
                    etree.SubElement(icms_sn, 'CSOSN').text = '102'
            else:
                # Regime Normal (CRT=2 ou 3) — seleciona grupo ICMS pelo CST do produto
                if cst_icms_item == '00':
                    icms_rn = etree.SubElement(icms, 'ICMS00')
                    etree.SubElement(icms_rn, 'orig').text = '0'
                    etree.SubElement(icms_rn, 'CST').text = '00'
                    etree.SubElement(icms_rn, 'modBC').text = '3'
                    etree.SubElement(icms_rn, 'vBC').text = f'{v_prod:.2f}'
                    etree.SubElement(icms_rn, 'pICMS').text = '12.00'
                    etree.SubElement(icms_rn, 'vICMS').text = f'{v_prod * 0.12:.2f}'
                elif cst_icms_item in ('40', '41'):
                    icms_rn = etree.SubElement(icms, 'ICMS40')
                    etree.SubElement(icms_rn, 'orig').text = '0'
                    etree.SubElement(icms_rn, 'CST').text = cst_icms_item
                elif cst_icms_item == '90':
                    # CST 90: Outras (regime especial SP Decreto 51.597/2007) — CFOP 5101
                    icms_rn = etree.SubElement(icms, 'ICMS90')
                    etree.SubElement(icms_rn, 'orig').text = '0'
                    etree.SubElement(icms_rn, 'CST').text = '90'
                    etree.SubElement(icms_rn, 'modBC').text = '3'
                    _prod_obj = getattr(item, 'product', None)
                    _bc_perc = Decimal(str(getattr(_prod_obj, 'base_calculo_icms', 0) or 0)) / Decimal('100')
                    _aliq_icms = Decimal(str(getattr(_prod_obj, 'aliq_icms', 0) or 0))
                    _vbc = (Decimal(str(v_prod)) * _bc_perc).quantize(Decimal('0.01'))
                    _vicms = (_vbc * _aliq_icms / Decimal('100')).quantize(Decimal('0.01'))
                    etree.SubElement(icms_rn, 'vBC').text = f'{_vbc:.2f}'
                    etree.SubElement(icms_rn, 'pICMS').text = f'{_aliq_icms:.2f}'
                    etree.SubElement(icms_rn, 'vICMS').text = f'{_vicms:.2f}'
                else:
                    # CST 60: ST já recolhida — CFOP deve ser 5405
                    icms_rn = etree.SubElement(icms, 'ICMS60')
                    etree.SubElement(icms_rn, 'orig').text = '0'
                    etree.SubElement(icms_rn, 'CST').text = '60'

            # PIS
            pis = etree.SubElement(imposto, 'PIS')
            _pis_nt = {'04', '05', '06', '07', '08', '09'}
            if cst_pis_item in _pis_nt:
                pis_nt = etree.SubElement(pis, 'PISNT')
                etree.SubElement(pis_nt, 'CST').text = cst_pis_item
            elif cst_pis_item in ('01', '02') and aliq_pis_item > 0:
                _v_pis = (Decimal(str(v_prod)) * aliq_pis_item / Decimal('100')).quantize(Decimal('0.01'))
                total_pis_nf += _v_pis
                pis_aliq = etree.SubElement(pis, 'PISAliq')
                etree.SubElement(pis_aliq, 'CST').text = cst_pis_item
                etree.SubElement(pis_aliq, 'vBC').text = f'{v_prod:.2f}'
                etree.SubElement(pis_aliq, 'pPIS').text = f'{aliq_pis_item:.4f}'
                etree.SubElement(pis_aliq, 'vPIS').text = f'{_v_pis:.2f}'
            else:
                pis_outr = etree.SubElement(pis, 'PISOutr')
                etree.SubElement(pis_outr, 'CST').text = cst_pis_item if cst_pis_item else '99'
                etree.SubElement(pis_outr, 'vBC').text = '0.00'
                etree.SubElement(pis_outr, 'pPIS').text = '0.00'
                etree.SubElement(pis_outr, 'vPIS').text = '0.00'

            # COFINS
            cofins = etree.SubElement(imposto, 'COFINS')
            _cofins_nt = {'04', '05', '06', '07', '08', '09'}
            if cst_pis_item in _cofins_nt:
                cofins_nt = etree.SubElement(cofins, 'COFINSNT')
                etree.SubElement(cofins_nt, 'CST').text = cst_pis_item
            elif cst_pis_item in ('01', '02') and aliq_cofins_item > 0:
                _v_cofins = (Decimal(str(v_prod)) * aliq_cofins_item / Decimal('100')).quantize(Decimal('0.01'))
                total_cofins_nf += _v_cofins
                cofins_aliq = etree.SubElement(cofins, 'COFINSAliq')
                etree.SubElement(cofins_aliq, 'CST').text = cst_pis_item
                etree.SubElement(cofins_aliq, 'vBC').text = f'{v_prod:.2f}'
                etree.SubElement(cofins_aliq, 'pCOFINS').text = f'{aliq_cofins_item:.4f}'
                etree.SubElement(cofins_aliq, 'vCOFINS').text = f'{_v_cofins:.2f}'
            else:
                cofins_outr = etree.SubElement(cofins, 'COFINSOutr')
                etree.SubElement(cofins_outr, 'CST').text = cst_pis_item if cst_pis_item else '99'
                etree.SubElement(cofins_outr, 'vBC').text = '0.00'
                etree.SubElement(cofins_outr, 'pCOFINS').text = '0.00'
                etree.SubElement(cofins_outr, 'vCOFINS').text = '0.00'

        # ── total ─────────────────────────────────────────────────────────────
        total = etree.SubElement(infNFe, 'total')
        icms_tot = etree.SubElement(total, 'ICMSTot')
        etree.SubElement(icms_tot, 'vBC').text = '0.00'
        etree.SubElement(icms_tot, 'vICMS').text = '0.00'
        etree.SubElement(icms_tot, 'vICMSDeson').text = '0.00'
        etree.SubElement(icms_tot, 'vFCP').text = '0.00'
        etree.SubElement(icms_tot, 'vBCST').text = '0.00'
        etree.SubElement(icms_tot, 'vST').text = '0.00'
        etree.SubElement(icms_tot, 'vFCPST').text = '0.00'
        etree.SubElement(icms_tot, 'vFCPSTRet').text = '0.00'
        etree.SubElement(icms_tot, 'vProd').text = f'{valor_total:.2f}'
        etree.SubElement(icms_tot, 'vFrete').text = '0.00'
        etree.SubElement(icms_tot, 'vSeg').text = '0.00'
        etree.SubElement(icms_tot, 'vDesc').text = '0.00'
        etree.SubElement(icms_tot, 'vII').text = '0.00'
        etree.SubElement(icms_tot, 'vIPI').text = '0.00'
        etree.SubElement(icms_tot, 'vIPIDevol').text = '0.00'
        etree.SubElement(icms_tot, 'vPIS').text = f'{total_pis_nf:.2f}'
        etree.SubElement(icms_tot, 'vCOFINS').text = f'{total_cofins_nf:.2f}'
        etree.SubElement(icms_tot, 'vOutro').text = '0.00'
        etree.SubElement(icms_tot, 'vNF').text = f'{valor_total:.2f}'

        # ── transp ────────────────────────────────────────────────────────────
        transp = etree.SubElement(infNFe, 'transp')
        etree.SubElement(transp, 'modFrete').text = '9'

        # ── pag ───────────────────────────────────────────────────────────────
        _tp_map = {'dinheiro': '01', 'cartao_credito': '03', 'cartao_debito': '04',
                   'pix': '17', 'voucher': '15'}
        # Monta lista de pagamentos: [(tPag, valor), ...]
        _pagamentos = []
        _total_pago = Decimal('0.00')
        if hasattr(order, 'checkout') and order.checkout:
            _checkout = order.checkout
            if _checkout.is_parcial:
                for _cp in _checkout.payments.all():
                    _tp = _tp_map.get(_cp.payment_method, '01')
                    _pagamentos.append((_tp, Decimal(str(_cp.amount))))
                    _total_pago += Decimal(str(_cp.amount))
            else:
                _tp = _tp_map.get(_checkout.payment_method, '01')
                _pagamentos.append((_tp, Decimal(str(valor_total))))
                _total_pago = Decimal(str(valor_total))
        else:
            _pagamentos.append(('01', Decimal(str(valor_total))))
            _total_pago = Decimal(str(valor_total))
        # Garante ao menos um pagamento
        if not _pagamentos:
            _pagamentos.append(('01', Decimal(str(valor_total))))
            _total_pago = Decimal(str(valor_total))
        pag = etree.SubElement(infNFe, 'pag')
        for _tp, _vp in _pagamentos:
            det_pag = etree.SubElement(pag, 'detPag')
            etree.SubElement(det_pag, 'tPag').text = _tp
            etree.SubElement(det_pag, 'vPag').text = f'{_vp:.2f}'
            # cartão de crédito (03) ou débito (04) exige <card> com tpIntegra
            if _tp in ('03', '04'):
                card = etree.SubElement(det_pag, 'card')
                etree.SubElement(card, 'tpIntegra').text = '2'  # não integrado
        _troco = _total_pago - Decimal(str(valor_total))
        if _troco > Decimal('0.00'):
            etree.SubElement(pag, 'vTroco').text = f'{_troco:.2f}'

        # ── infAdic (informações adicionais) ──────────────────────────────────
        textos_adicionais = []
        if crt == '1':
            textos_adicionais.append('DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL')
        for _item in all_items:
            if not (isinstance(_item, dict) and _item.get('_fallback')):
                _txt = (getattr(_item.product, 'dados_adicionais_nfe', '') or '').strip()
                if _txt and _txt not in textos_adicionais:
                    textos_adicionais.append(_txt)
        if textos_adicionais:
            inf_adic = etree.SubElement(infNFe, 'infAdic')
            etree.SubElement(inf_adic, 'infCpl').text = ' | '.join(textos_adicionais)[:5000]

        # ── infNFeSupl (NFC-e) — ANTES da Signature, conforme schema NF-e 4.00 ──
        # schema: NFe > infNFe > infNFeSupl > Signature
        qr_code_url = dados.get('qr_code', '')
        url_consulta = self._get_url_chave()
        if qr_code_url:
            NS = 'http://www.portalfiscal.inf.br/nfe'
            supl = etree.SubElement(NFe, f'{{{NS}}}infNFeSupl')
            qr = etree.SubElement(supl, f'{{{NS}}}qrCode')
            qr.text = etree.CDATA(qr_code_url)
            url_elem = etree.SubElement(supl, f'{{{NS}}}urlChave')
            url_elem.text = url_consulta

        xml_str = etree.tostring(NFe, encoding='unicode', xml_declaration=False)
        print(f"[INFO] XML gerado para NFCe #{dados['numero']} ({len(xml_str)} chars)")
        return xml_str


    def _preparar_certificado(self):
        """Prepara certificado para uso"""
        with open(self.certificado.arquivo_pfx.path, 'rb') as f:
            pfx_data = f.read()
        
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data, 
            self.certificado.senha_pfx.encode('utf-8')
        )
        
        # Salva certificado temporário
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as cert_file:
            cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            cert_file.write(cert_pem)
            cert_path = cert_file.name
        
        # Salva chave privada temporária
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as key_file:
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            key_file.write(key_pem)
            key_path = key_file.name
        
        return cert_path, key_path

    def _assinar_xml(self, xml_str, dados=None):
        """Assina o XML NFe com signxml (RSA-SHA1 envelopado) conforme SEFAZ."""
        xml_bytes = etree.fromstring(xml_str.encode('utf-8'))

        with open(self.certificado.arquivo_pfx.path, 'rb') as f:
            pfx_data = f.read()

        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            pfx_data, self.certificado.senha_pfx.encode('utf-8')
        )
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

        # Desativa aviso de deprecação do signxml para métodos RSA-SHA1
        XMLSigner.check_deprecated_methods = lambda self: None

        NS = 'http://www.portalfiscal.inf.br/nfe'
        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm='rsa-sha1',
            digest_algorithm='sha1',
            c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
        )
        signer.namespaces = {None: 'http://www.w3.org/2000/09/xmldsig#'}

        ref_id = xml_bytes.find(f'.//{{{NS}}}infNFe').get('Id')
        signed_root = signer.sign(xml_bytes, key=key_pem, cert=cert_pem, reference_uri=ref_id)

        xml_signed = etree.tostring(signed_root, encoding='unicode', xml_declaration=False)
        # Remove prefixo 'ds:' que a SEFAZ rejeita
        xml_signed = xml_signed.replace('ds:', '').replace(':ds', '')
        # Corrige CDATA escapado
        xml_signed = xml_signed.replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')
        return xml_signed


    def _get_sefaz_url(self):
        """Retorna URL do webservice SEFAZ de autorização NFCe por UF e ambiente"""
        uf = self.empresa.uf
        amb = self.empresa.ambiente_nfce  # '1'=prod, '2'=homolog

        urls = {
            'SP': {
                '1': 'https://nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx',
                '2': 'https://homologacao.nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx',
            },
            'MG': {
                '1': 'https://nfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4',
                '2': 'https://hnfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4',
            },
            'RS': {
                '1': 'https://nfce.sefazrs.rs.gov.br/ws/nfceautorizacao/NFeAutorizacao4.asmx',
                '2': 'https://nfce-homologacao.sefazrs.rs.gov.br/ws/nfceautorizacao/NFeAutorizacao4.asmx',
            },
            'PR': {
                '1': 'https://nfe.sefa.pr.gov.br/nfe-portal-web/NFeAutorizacao4',
                '2': 'https://homologacao.nfe.sefa.pr.gov.br/nfe-portal-homologacao-web/NFeAutorizacao4',
            },
        }
        svrs = {
            '1': 'https://nfce.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx',
            '2': 'https://nfce-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx',
        }

        if uf in urls:
            return urls[uf].get(amb, urls[uf]['2'])
        return svrs.get(amb, svrs['2'])

    def _chamar_sefaz(self, xml_assinado, cert_path, key_path):
        """Envolve NFe assinada em enviNFe, envia SOAP para SEFAZ."""
        NS = 'http://www.portalfiscal.inf.br/nfe'
        url = self._get_sefaz_url()

        # Wrapper enviNFe adicionado APÓS a assinatura
        envi = (
            f'<enviNFe versao="4.00" xmlns="{NS}">'
            f'<idLote>{str(uuid.uuid4().int)[:15]}</idLote>'
            f'<indSinc>1</indSinc>'
            f'{xml_assinado}'
            f'</enviNFe>'
        )

        soap_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap12:Envelope '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            '<soap12:Body>'
            f'<nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">'
            f'{envi}'
            '</nfeDadosMsg>'
            '</soap12:Body>'
            '</soap12:Envelope>'
        )

        import ssl as _ssl
        import http.client as _http
        from urllib.parse import urlparse as _urlparse

        def _build_ssl_ctx(cert_file, key_file):
            ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            # Desabilitar TLS 1.3 via options (mais confiável que maximum_version no Nix)
            for _flag in ('OP_NO_TLSv1_3',):
                _v = getattr(_ssl, _flag, None)
                if _v:
                    ctx.options |= _v
            # Garantir TLS 1.2 como mínimo
            try:
                ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
            except AttributeError:
                pass
            # OP_LEGACY_SERVER_CONNECT para IIS antigos
            _legacy = getattr(_ssl, 'OP_LEGACY_SERVER_CONNECT', None)
            if _legacy:
                ctx.options |= _legacy
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            return ctx

        parsed = _urlparse(url)
        host = parsed.hostname
        port = parsed.port or 443
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query

        ssl_ctx = _build_ssl_ctx(cert_path, key_path)
        body_bytes = soap_body.encode('utf-8')

        print(f"[SEFAZ] Enviando NFCe para {url} via http.client (TLS1.2)")
        conn = _http.HTTPSConnection(host, port=port, context=ssl_ctx, timeout=60)
        conn.request(
            'POST', path, body=body_bytes,
            headers={
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'Content-Length': str(len(body_bytes)),
            }
        )
        response = conn.getresponse()
        resp_text = response.read().decode('utf-8')
        print(f"[SEFAZ] HTTP {response.status}")
        conn.close()
        return resp_text


    def _parsear_resposta_sefaz(self, xml_resposta):
        """Parseia resposta SOAP da SEFAZ usando namespace dict (evita FutureWarning)."""
        try:
            root = etree.fromstring(xml_resposta.encode('utf-8'))
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            # Busca infProt primeiro (mais preciso), senão cai no retEnviNFe
            inf_prot = root.find('.//nfe:infProt', ns)
            if inf_prot is not None:
                cstat_elem  = inf_prot.find('nfe:cStat', ns)
                xmot_elem   = inf_prot.find('nfe:xMotivo', ns)
                nprot_elem  = inf_prot.find('nfe:nProt', ns)
            else:
                cstat_elem  = root.find('.//nfe:cStat', ns)
                xmot_elem   = root.find('.//nfe:xMotivo', ns)
                nprot_elem  = root.find('.//nfe:nProt', ns)

            c_stat  = cstat_elem.text  if cstat_elem  is not None else '000'
            x_motivo = xmot_elem.text if xmot_elem   is not None else 'Sem motivo'
            n_prot  = nprot_elem.text  if nprot_elem  is not None else ''

            print(f"[SEFAZ] cStat={c_stat} — {x_motivo}")

            sucesso = c_stat in ('100', '150')
            if sucesso:
                return {
                    'sucesso': True,
                    'protocolo': n_prot,
                    'cStat': c_stat,
                    'xMotivo': x_motivo,
                }
            else:
                return {
                    'sucesso': False,
                    'erro': f'SEFAZ {c_stat}: {x_motivo}',
                    'cStat': c_stat,
                    'xMotivo': x_motivo,
                }
        except Exception as e:
            return {'sucesso': False, 'erro': f'Erro ao parsear resposta SEFAZ: {e}'}


    def _emitir_nfce_simulado(self, dados):
        """Emite NFCe em modo simulação - CORRIGIDO"""
        print(f"[SIMULAÇÃO] Emitindo NFCe #{dados['numero']}")
        print(f"[SIMULAÇÃO] Empresa: {self.empresa.nome_fantasia}")
        print(f"[SIMULAÇÃO] Cliente: CONSUMIDOR NAO IDENTIFICADO")
        print(f"[SIMULAÇÃO] Valor: R$ {dados['order'].total_amount:.2f}")  # CORRIGIDO: total_amount
        print(f"[SIMULAÇÃO] ✓ NFCe autorizada com sucesso!")
        
        return {
            'sucesso': True,
            'numero_nfce': dados['numero'],  # CORRIGIDO: campo consistente
            'chave_acesso': dados['chave_acesso'],
            'protocolo': 'SIM123456789',
            'modo': 'simulacao'
        }

    def _limpar_certificados_temporarios(self, cert_path, key_path):
        """Remove arquivos temporários de certificado"""
        try:
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)
                print("[INFO] Arquivo certificado temporário removido")
            if key_path and os.path.exists(key_path):
                os.unlink(key_path)
                print("[INFO] Arquivo chave temporária removida")
        except Exception as e:
            print(f"[WARNING] Erro ao limpar certificados temporários: {e}")

    def _get_codigo_uf(self):
        """Retorna código IBGE da UF"""
        codigos_uf = {
            'SP': '35', 'RJ': '33', 'MG': '31', 'RS': '43', 'PR': '41',
            'SC': '42', 'GO': '52', 'MT': '51', 'MS': '50', 'BA': '29',
            'PE': '26', 'CE': '23', 'MA': '21', 'PA': '15', 'PB': '25',
            'RN': '24', 'AL': '27', 'SE': '28', 'PI': '22', 'TO': '17',
            'AC': '12', 'AM': '13', 'AP': '16', 'RO': '11', 'RR': '14',
            'DF': '53', 'ES': '32'
        }
        return codigos_uf.get(self.empresa.uf, '35')

    def _get_codigo_municipio(self):
        """Retorna código IBGE do município"""
        return '3523800'

    def validar_certificado(self):
        """Valida se o certificado está válido e não expirou"""
        try:
            with open(self.certificado.arquivo_pfx.path, 'rb') as f:
                pfx_data = f.read()
            
            _, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data, 
                self.certificado.senha_pfx.encode('utf-8')
            )
            
            if certificate.not_valid_after < timezone.now():
                return {
                    'valido': False,
                    'erro': f'Certificado expirou em {certificate.not_valid_after.strftime("%d/%m/%Y")}'
                }
            
            return {
                'valido': True,
                'valido_ate': certificate.not_valid_after
            }
            
        except Exception as e:
            return {
                'valido': False,
                'erro': f'Erro ao validar certificado: {str(e)}'
            }

    def consultar_status_nfce(self, chave_acesso):
        """Consulta status de uma NFCe na SEFAZ"""
        print(f"[INFO] Consultaria status da NFCe: {chave_acesso}")
        
    def cancelar_nfce(self, chave_acesso, justificativa):
        """Cancela uma NFCe"""
        print(f"[INFO] Cancelaria NFCe: {chave_acesso} - Motivo: {justificativa}")


    # =============== VISTA DE GERAÇÃO DE CUPOM FISCAL (HTML) ===============
    def gerar_cupom_fiscal_html(self, dados_nfce, resultado_emissao):
        """
        Gera HTML do cupom fiscal NFCe seguindo conformidades brasileiras
        """
        order = dados_nfce['order']
        chave_acesso = dados_nfce['chave_acesso']
        qr_code = dados_nfce['qr_code']
        numero_nfce = dados_nfce['numero']
        cpf_cliente = dados_nfce.get('cpf_cliente') or ''
        cpf_digits_cupom = re.sub(r'\D', '', str(cpf_cliente)) if cpf_cliente else ''

        # Gerar imagem QR Code
        qr_img_b64 = ''
        try:
            import qrcode as _qr
            import io as _io
            _qr_obj = _qr.QRCode(version=None, error_correction=_qr.constants.ERROR_CORRECT_M, box_size=4, border=2)
            _qr_obj.add_data(qr_code)
            _qr_obj.make(fit=True)
            _qr_img = _qr_obj.make_image(fill_color="black", back_color="white")
            _buf = _io.BytesIO()
            _qr_img.save(_buf, format='PNG')
            qr_img_b64 = base64.b64encode(_buf.getvalue()).decode('utf-8')
        except Exception as _e:
            print(f"[WARN] Não foi possível gerar imagem QR Code: {_e}")

        # Dados dinâmicos da empresa
        nome_empresa = self.empresa.nome_fantasia or self.empresa.razao_social
        cnpj_fmt = self.empresa.cnpj
        ie_fmt = self.empresa.inscricao_estadual
        end_linha1 = f"{self.empresa.logradouro}, {self.empresa.numero}"
        end_linha2 = f"{self.empresa.bairro} - {self.empresa.cidade}/{self.empresa.uf}"
        cep_fmt = self.empresa.cep
        ambiente_label = "Homologação" if self.empresa.ambiente_nfce == "2" else "Produção"

        # Forma de pagamento do checkout
        _pm_label = {
            'dinheiro': 'Dinheiro',
            'cartao_debito': 'Cartão de Débito',
            'cartao_credito': 'Cartão de Crédito',
            'pix': 'PIX',
            'voucher': 'Voucher',
        }
        _pagamentos_cupom = []  # lista de (label, valor)
        _total_pago_cupom = Decimal('0.00')
        if hasattr(order, 'checkout') and order.checkout:
            _co = order.checkout
            if _co.is_parcial:
                for _cp in _co.payments.all():
                    _pagamentos_cupom.append((_pm_label.get(_cp.payment_method, _cp.payment_method), Decimal(str(_cp.amount))))
                    _total_pago_cupom += Decimal(str(_cp.amount))
            else:
                _pagamentos_cupom.append((_pm_label.get(_co.payment_method, _co.get_payment_method_display()), Decimal(str(order.total_amount))))
                _total_pago_cupom = Decimal(str(order.total_amount))
        else:
            _pagamentos_cupom.append(('Dinheiro', Decimal(str(order.total_amount))))
            _total_pago_cupom = Decimal(str(order.total_amount))
        _troco_cupom = _total_pago_cupom - Decimal(str(order.total_amount))
        payment_display = " + ".join(f"{l} R$ {v:.2f}" for l, v in _pagamentos_cupom)

        # Data de emissão formatada
        agora = timezone.localtime(timezone.now())
        data_emissao = agora.strftime('%d/%m/%Y %H:%M:%S')

        # Coletar todos os itens de todos os pedidos da comanda
        all_items = []
        for pedido in order.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']):
            for item in pedido.items.all():
                all_items.append(item)

        # Valor aproximado dos tributos (estimativa de 20% sobre o total)
        valor_total = float(order.total_amount)
        tributos_aproximados = valor_total * 0.20

        # Dados adicionais dos produtos para infCpl
        textos_adicionais_cupom = []
        if self.empresa.regime_tributario == '1':
            textos_adicionais_cupom.append('DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL')
        for _ci in all_items:
            _txt = (getattr(_ci.product, 'dados_adicionais_nfe', '') or '').strip()
            if _txt and _txt not in textos_adicionais_cupom:
                textos_adicionais_cupom.append(_txt)
        inf_cpl_text = ' | '.join(textos_adicionais_cupom) if textos_adicionais_cupom else ''

        html_cupom = f'''
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cupom Fiscal NFCe #{numero_nfce}</title>
        <style>
            /* === CONFIGURAÇÃO PARA IMPRESSORA TÉRMICA 80MM === */
            @page {{
                size: 80mm auto;
                margin: 0;
            }}

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.2;
                color: #000;
                background: #fff;
                width: 80mm;
                margin: 0 auto;
                padding: 4mm;
            }}

            @media print {{
                body {{
                    background: white;
                    font-size: 10px;
                }}
                .no-print {{
                    display: none;
                }}
            }}

            /* === ESTILOS DO CUPOM FISCAL === */
            .center {{
                text-align: center;
            }}

            .bold {{
                font-weight: bold;
            }}

            .line {{
                border-bottom: 1px dashed #000;
                margin: 3px 0;
                height: 1px;
            }}

            .double-line {{
                border-bottom: 2px solid #000;
                margin: 4px 0;
                height: 2px;
            }}

            .empresa-header {{
                text-align: center;
                margin-bottom: 8px;
            }}

            .empresa-nome {{
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 2px;
            }}

            .empresa-dados {{
                font-size: 9px;
                line-height: 1.3;
            }}

            .nfce-header {{
                text-align: center;
                border: 2px solid #000;
                padding: 4px;
                margin: 6px 0;
                font-size: 12px;
                font-weight: bold;
            }}

            .dados-nfce {{
                font-size: 9px;
                margin: 6px 0;
            }}

            .consumidor {{
                font-size: 10px;
                margin: 4px 0;
                padding: 2px 0;
                border-top: 1px dashed #000;
                border-bottom: 1px dashed #000;
            }}

            .item {{
                margin: 2px 0;
                font-size: 9px;
            }}

            .item-desc {{
                font-weight: bold;
            }}

            .item-valores {{
                display: flex;
                justify-content: space-between;
                font-size: 8px;
            }}

            .totais {{
                margin: 6px 0;
                font-size: 10px;
            }}

            .total-final {{
                font-size: 12px;
                font-weight: bold;
                text-align: center;
                border: 1px solid #000;
                padding: 3px;
                margin: 4px 0;
            }}

            .pagamento {{
                margin: 4px 0;
                font-size: 9px;
                text-align: center;
            }}

            .tributos {{
                font-size: 8px;
                margin: 4px 0;
                padding: 2px 0;
                border: 1px dashed #000;
                text-align: center;
            }}

            .qrcode-section {{
                text-align: center;
                margin: 8px 0;
            }}

            .qrcode-box {{
                border: 2px solid #000;
                padding: 8px;
                margin: 4px 0;
                display: inline-block;
            }}

            .consulta-info {{
                font-size: 8px;
                text-align: center;
                margin: 4px 0;
            }}

            .protocolo {{
                font-size: 9px;
                margin: 4px 0;
                text-align: center;
            }}

            .mensagens-legais {{
                font-size: 7px;
                text-align: center;
                margin: 6px 0;
                padding: 3px 0;
                border-top: 1px dashed #000;
            }}

            .footer {{
                text-align: center;
                font-size: 8px;
                margin-top: 8px;
            }}

            /* Controles de impressão */
            .print-controls {{
                text-align: center;
                margin: 10px 0;
                background: #f0f0f0;
                padding: 10px;
                border-radius: 4px;
            }}

            .btn {{
                display: inline-block;
                padding: 8px 16px;
                margin: 0 4px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
                border: none;
                cursor: pointer;
            }}

            .btn:hover {{
                background: #0056b3;
            }}

            .btn-success {{
                background: #28a745;
            }}
        </style>
    </head>
    <body>
        <!-- Controles de Impressão -->
        <div class="print-controls no-print">
            <button class="btn" onclick="window.print()">🖨️ Imprimir</button>
            <button class="btn btn-success" onclick="window.close()">✕ Fechar</button>
        </div>

        <!-- === CABEÇALHO DA EMPRESA === -->
        <div class="empresa-header">
            <div class="empresa-nome">{nome_empresa}</div>
            <div class="empresa-dados">
                {end_linha1}<br>
                {end_linha2}<br>
                CEP: {cep_fmt}<br>
                CNPJ: {cnpj_fmt}<br>
                IE: {ie_fmt}
            </div>
        </div>

        <!-- === IDENTIFICAÇÃO NFCe === -->
        <div class="nfce-header">
            DOCUMENTO AUXILIAR DA<br>
            NOTA FISCAL DE CONSUMIDOR<br>
            ELETRÔNICA
        </div>

        <div class="dados-nfce center">
            <div class="bold">NFCe Nº {numero_nfce:09d} - Série 001</div>
            <div>Emissão: {data_emissao}</div>
            <div style="font-size: 8px; margin-top: 2px;">
                Ambiente: {ambiente_label}
            </div>
        </div>

        <div class="line"></div>

        <!-- === CONSUMIDOR === -->
        <div class="consumidor center">
            {f'<div class="bold">CPF: {cpf_digits_cupom[:3]}.{cpf_digits_cupom[3:6]}.{cpf_digits_cupom[6:9]}-{cpf_digits_cupom[9:]}</div>' if len(cpf_digits_cupom) == 11 else '<div class="bold">CONSUMIDOR NÃO IDENTIFICADO</div>'}
        </div>

        <!-- === DISCRIMINAÇÃO DOS ITENS === -->
        <div class="bold center" style="margin: 6px 0;">ITENS</div>
        <div class="line"></div>
    '''

        # Adicionar itens
        for i, item in enumerate(all_items, 1):
            subtotal = float(item.quantity) * float(item.unit_price)
            html_cupom += f'''
        <div class="item">
            <div class="item-desc">{i:03d} {item.product.name}</div>
            <div class="item-valores">
                <span>Qtd: {item.quantity} UN</span>
                <span>Unit: R$ {item.unit_price:.2f}</span>
            </div>
            <div class="item-valores">
                <span>Cód: {getattr(item.product, 'id', '000001')}</span>
                <span>Total: R$ {subtotal:.2f}</span>
            </div>
        </div>
        <div class="line"></div>
    '''

        # Continuar HTML com totais, pagamento, etc.
        html_cupom += f'''
        <!-- === TOTALIZADORES === -->
        <div class="totais">
            <div style="display: flex; justify-content: space-between;">
                <span>Qtd. total de itens:</span>
                <span>{len(all_items)}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>Valor total R$:</span>
                <span>{valor_total:.2f}</span>
            </div>
        </div>

        <div class="total-final">
            TOTAL R$ {valor_total:.2f}
        </div>

        <!-- === FORMA DE PAGAMENTO === -->
        <div class="pagamento">
            <div class="bold">FORMA PAGAMENTO</div>
            {''.join(f'<div>{label} - R$ {valor:.2f}</div>' for label, valor in _pagamentos_cupom)}
            {f'<div><b>Troco: R$ {_troco_cupom:.2f}</b></div>' if _troco_cupom > Decimal("0.00") else ''}
        </div>

        <div class="line"></div>

        <!-- === TRIBUTOS APROXIMADOS === -->
        <div class="tributos">
            Valor aprox. tributos R$ {tributos_aproximados:.2f} ({(tributos_aproximados/valor_total)*100:.1f}%)<br>
            Fonte: IBPT/empresometro.com.br
        </div>

        <!-- === QR CODE === -->
        <div class="qrcode-section">
            <div style="font-size: 9px; font-weight: bold; margin-bottom: 4px;">
                CONSULTE PELA CHAVE DE ACESSO
            </div>
            {f'<img src="data:image/png;base64,{qr_img_b64}" style="display:block;margin:4px auto;width:140px;height:140px;" alt="QR Code NFCe"/>' if qr_img_b64 else f'<div class="qrcode-box" style="font-size:7px;word-break:break-all;max-width:200px;">{qr_code}</div>'}
            <div class="consulta-info" style="font-size:7px;word-break:break-all;margin-top:4px;">
                {qr_code[:44]}...
            </div>
        </div>

        <!-- === CHAVE DE ACESSO === -->
        <div class="center" style="font-size: 8px; word-break: break-all; margin: 4px 0;">
            <div class="bold">CHAVE DE ACESSO:</div>
            {chave_acesso}
        </div>

        <!-- === PROTOCOLO (SE AUTORIZADA) === -->
        {f'<div class="protocolo"><div class="bold">PROTOCOLO DE AUTORIZAÇÃO:</div>{resultado_emissao.get("protocolo", "PENDENTE")}<br>{data_emissao}</div>' if resultado_emissao.get('sucesso') else ''}

        <div class="line"></div>

        <!-- === INFORMAÇÕES ADICIONAIS === -->
        {f'<div class="mensagens-legais" style="text-align:left;"><div class="bold" style="text-align:center;">INFORMAÇÕES ADICIONAIS</div>{inf_cpl_text}</div><div class="line"></div>' if inf_cpl_text else ''}

        <!-- === INFORMAÇÕES LEGAIS === -->
        <div class="mensagens-legais">
            Esta NFCe foi emitida nos termos da<br>
            Resolução CGSN nº 140/2018 e<br>
            condições descritas em<br>
            fazenda.sp.gov.br/nfe
        </div>

        <div class="mensagens-legais">
            Não permite aproveitamento de crédito de ICMS
        </div>

        <!-- === FOOTER === -->
        <div class="footer">
            <div style="margin: 8px 0;">
                ★★★ OBRIGADO PELA PREFERÊNCIA! ★★★
            </div>
            <div style="margin: 4px 0;">
                Volte sempre!
            </div>
            <div style="font-size: 6px; margin-top: 8px;">
                Cupom gerado em {data_emissao}
            </div>
        </div>

        <!-- Espaço para corte -->
        <div style="height: 20mm;"></div>

        <script>
            // Auto-impressão quando solicitado
            if (window.location.search.includes('print=auto')) {{
                setTimeout(() => {{
                    window.print();
                    setTimeout(() => window.close(), 1000);
                }}, 500);
            }}
            // Salvar como PDF (abre diálogo sem fechar janela)
            if (window.location.search.includes('pdf=1')) {{
                setTimeout(() => {{
                    window.print();
                }}, 500);
            }}
        </script>

    </body>
    </html>
    '''
        
        return html_cupom

    def salvar_cupom_fiscal(self, dados_nfce, resultado_emissao):
        """
        Salva o cupom fiscal em arquivo HTML para impressão
        """
        try:
            cupom_html = self.gerar_cupom_fiscal_html(dados_nfce, resultado_emissao)
            
            # Criar diretório se não existir
            cupons_dir = os.path.join(settings.MEDIA_ROOT, 'cupons_fiscais')
            os.makedirs(cupons_dir, exist_ok=True)
            
            # Nome do arquivo
            numero_nfce = dados_nfce['numero']
            chave_acesso = dados_nfce['chave_acesso']
            filename = f"cupom_nfce_{numero_nfce}_{chave_acesso}.html"
            filepath = os.path.join(cupons_dir, filename)
            
            # Salvar arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cupom_html)
            
            print(f"[INFO] Cupom fiscal salvo: {filepath}")
            
            return {
                'arquivo_salvo': True,
                'caminho': filepath,
                'url_impressao': f'/media/cupons_fiscais/{filename}',
                'html_content': cupom_html
            }
            
        except Exception as e:
            print(f"[ERROR] Erro ao salvar cupom fiscal: {e}")
            return {
                'arquivo_salvo': False,
                'erro': str(e),
                'html_content': cupom_html  # Retorna HTML mesmo se não conseguir salvar
            }

import json
import hashlib
from django.db.models import Max
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from products.models import Product, OpcionalObrigatorio, StockEntry, StockExit
from orders.models import Comanda, Pedido, PedidoItem
from django.core.exceptions import ValidationError
from utils.image_optimizer import validate_image_file_size
from .models import KioskSlide
from django.db import transaction


def _slides_fingerprint():
    rows = KioskSlide.objects.values_list(
        'id', 'title', 'order', 'is_active', 'image', 'created_at'
    ).order_by('id')
    h = hashlib.sha1()
    for r in rows:
        h.update('|'.join(str(x or '') for x in r).encode('utf-8'))
    return h.hexdigest()


def _catalog_version_value():
    from django.utils import timezone

    ts_product = Product.objects.aggregate(v=Max('updated_at'))['v']
    ts_opcional = OpcionalObrigatorio.objects.aggregate(v=Max('updated_at'))['v']
    ts_stock_entry = StockEntry.objects.aggregate(v=Max('created_at'))['v']
    ts_stock_exit = StockExit.objects.aggregate(v=Max('created_at'))['v']

    candidates = [
        t for t in (ts_product, ts_opcional, ts_stock_entry, ts_stock_exit)
        if t is not None
    ]
    base = max(candidates).isoformat() if candidates else timezone.now().isoformat()
    return f"{base}:{_slides_fingerprint()}"


def entrada(request):
    """Tela inicial do kiosk — teclado numérico para digitar o número da mesa."""
    # AJAX: verifica se mesa já está aberta
    if request.method == 'GET' and request.GET.get('check'):
        numero = request.GET.get('check', '').strip()
        aberta = Comanda.objects.filter(numero=numero, status='em_uso').exists()
        return JsonResponse({'aberta': aberta})

    if request.method == 'POST':
        numero = request.POST.get('numero', '').strip()
        if numero:
            return redirect('kiosk:cardapio', numero=numero)
    slides = list(KioskSlide.objects.filter(is_active=True).order_by('order', 'id'))
    return render(request, 'kiosk/entrada.html', {'slides': slides})


def cardapio(request, numero):
    """Tela principal de pedido — categorias, produtos e carrinho."""
    # Abre (ou recupera) a comanda da mesa assim que o cardápio é acessado
    numero_limpo = str(numero).strip()
    mesa_numero = numero_limpo.zfill(2) if numero_limpo.isdigit() else numero_limpo
    mesa_label = f"MESA {mesa_numero}"
    # Busca comanda ativa (em_uso OU aguardando_caixa) para evitar criar uma
    # comanda vazia duplicada caso o tablet recarregue enquanto a mesa já está
    # em processo de fechamento (bug: tela apagada + reload do catálogo).
    _STATUSES_ATIVAS = ('em_uso', 'aguardando_caixa')
    comanda_mesa = Comanda.objects.filter(
        numero=numero, status__in=_STATUSES_ATIVAS
    ).order_by('-created_at').first()
    if comanda_mesa is None:
        comanda_mesa = Comanda.objects.create(
            numero=numero, status='em_uso', cliente_nome=mesa_label
        )
    elif not comanda_mesa.cliente_nome:
        comanda_mesa.cliente_nome = mesa_label
        comanda_mesa.save(update_fields=['cliente_nome'])

    produtos = Product.objects.filter(show_in_menu=True, is_active=True, visivel_kiosk=True).order_by('name')

    # Agrupar por categoria
    categorias = {}
    for p in produtos:
        cat = p.get_category_display()
        if cat not in categorias:
            categorias[cat] = {'slug': p.category, 'produtos': []}
        categorias[cat]['produtos'].append(p)

    # Reordenar categorias conforme CATEGORY_CHOICES (ordem definida no model)
    _cat_order = {slug: idx for idx, (slug, _) in enumerate(Product.CATEGORY_CHOICES)}
    categorias = dict(sorted(categorias.items(), key=lambda x: _cat_order.get(x[1]['slug'], 999)))

    # Serializa para JS: json.dumps usa ponto decimal, evitando bug de locale pt-BR
    produtos_json_data = {}
    for nome_cat, dados in categorias.items():
        produtos_json_data[dados['slug']] = {
            'nome': nome_cat,
            'itens': [
                {
                    'id': p.pk,
                    'nome': p.name,
                    'desc': (p.description or '')[:60],
                    'preco': float(p.price),
                    'img': p.image.url if p.image else '',
                    'opcionais_obrigatorios': [
                        {
                            'id': o.pk,
                            'nome': o.name,
                            'desc': o.description or '',
                            'preco': float(o.price),
                        }
                        for o in p.opcionais_obrigatorios.filter(is_active=True)
                    ],
                    'adicionais': [
                        {
                            'id': a.pk,
                            'nome': a.name,
                            'desc': a.description or '',
                            'preco': float(a.price),
                        }
                        for a in p.adicionais.filter(is_active=True)
                    ],
                }
                for p in dados['produtos']
            ],
        }

    slides = list(KioskSlide.objects.filter(is_active=True).order_by('order', 'id'))

    # Versão atual do catálogo para polling de atualizações
    catalog_version_initial = _catalog_version_value()

    context = {
        'numero': numero,
        'categorias': categorias,
        'produtos_json': json.dumps(produtos_json_data, ensure_ascii=False),
        'slides': slides,
        'catalog_version_initial': catalog_version_initial,
    }
    return render(request, 'kiosk/cardapio.html', context)


@require_http_methods(['POST'])
def enviar_pedido(request, numero):
    try:
        body = json.loads(request.body)
        itens = body.get('itens', [])
        observacoes = body.get('observacoes', '')

        if not itens:
            return JsonResponse({'erro': 'Carrinho vazio'}, status=400)

        numero_limpo = str(numero).strip()
        mesa_numero = numero_limpo.zfill(2) if numero_limpo.isdigit() else numero_limpo
        mesa_label = f"MESA {mesa_numero}"
        _STATUSES_ATIVAS = ('em_uso', 'aguardando_caixa')

        # Valida e prepara todos os itens ANTES da transação
        itens_processados = []
        for item in itens:
            produto = get_object_or_404(Product, pk=item['id'])
            qty = int(item.get('qty', 1))
            opcional_id = item.get('opcional_obrigatorio')
            adicionais_ids = item.get('adicionais', [])

            opcionais_produto = produto.opcionais_obrigatorios.filter(is_active=True)
            opcional_escolhido = None
            if opcionais_produto.exists():
                if not opcional_id:
                    return JsonResponse({'erro': f'Escolha obrigatória não informada para {produto.name}'}, status=400)
                opcional_escolhido = opcionais_produto.filter(pk=opcional_id).first()
                if not opcional_escolhido:
                    return JsonResponse({'erro': f'Opção obrigatória inválida para {produto.name}'}, status=400)

            preco_base = opcional_escolhido.price if (opcional_escolhido and opcional_escolhido.price > 0) else produto.price
            preco_extras = Decimal('0.00')
            obs_partes = []

            if opcional_escolhido:
                obs_partes.append(f"Opcional: {opcional_escolhido.name}")

            for aid in adicionais_ids:
                try:
                    ad = produto.adicionais.get(pk=aid)
                    preco_extras += ad.price
                    obs_partes.append(f"Adicional: {ad.name}")
                except Exception:
                    pass

            itens_processados.append({
                'produto': produto,
                'qty': qty,
                'opcional_escolhido': opcional_escolhido,
                'unit_price': preco_base + preco_extras,
                'obs_item': ' | '.join(obs_partes),
            })

        # Só grava no banco quando tudo já está validado
        with transaction.atomic():
            comanda = Comanda.objects.filter(
                numero=numero, status__in=_STATUSES_ATIVAS
            ).order_by('-created_at').first()

            if comanda is None:
                comanda = Comanda.objects.create(
                    numero=numero, status='em_uso', cliente_nome=mesa_label
                )
            elif not comanda.cliente_nome:
                comanda.cliente_nome = mesa_label
                comanda.save(update_fields=['cliente_nome'])

            pedido = Pedido.objects.create(
                comanda=comanda,
                observations=observacoes,
                status='aguardando',
            )

            for item in itens_processados:
                PedidoItem.objects.create(
                    pedido=pedido,
                    product=item['produto'],
                    opcional_obrigatorio=item['opcional_escolhido'],
                    quantity=item['qty'],
                    unit_price=item['unit_price'],
                    observations=item['obs_item'],
                )

            pedido.update_total()

        return JsonResponse({'ok': True, 'pedido_id': pedido.id})

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return JsonResponse({'erro': str(e)}, status=400)


def status_mesa(request, numero):
    """Retorna o status atual da mesa para polling do kiosk.

    Prioriza comandas em uso para evitar encerramento indevido por registros antigos
    ou leituras transitórias durante deploy/restart.
    """
    comanda_em_uso = Comanda.objects.filter(numero=numero, status='em_uso').order_by('-created_at').first()
    if comanda_em_uso:
        return JsonResponse({'status': 'em_uso'})

    # Sem comanda em uso: devolve o último status conhecido (se houver)
    comanda = Comanda.objects.filter(numero=numero).order_by('-created_at').first()
    return JsonResponse({'status': comanda.status if comanda else 'livre'})


def fechar_mesa(request, numero):
    """Marca a comanda da mesa como aguardando_caixa (cliente indo pagar)."""
    comanda = Comanda.objects.filter(numero=numero, status='em_uso').first()
    if not comanda:
        return JsonResponse({'ok': False, 'erro': 'Comanda não encontrada'})
    comanda.status = 'aguardando_caixa'
    comanda.save(update_fields=['status'])
    return JsonResponse({'ok': True})


def ver_conta(request, numero):
    """Retorna JSON com todos os itens pedidos da mesa e o total."""
    comanda = Comanda.objects.filter(
        numero=numero, status__in=('em_uso', 'aguardando_caixa')
    ).order_by('-created_at').first()
    if not comanda:
        return JsonResponse({'itens': [], 'total': '0,00'})

    itens = []
    for pedido in comanda.pedidos.exclude(status='cancelado').order_by('created_at'):
        for item in pedido.items.all():
            itens.append({
                'nome': item.product.name,
                'qty': item.quantity,
                'unit_price': float(item.unit_price),
                'subtotal': float(item.unit_price * item.quantity),
                'obs': item.observations or '',
            })

    total = float(comanda.total_amount)
    return JsonResponse({'itens': itens, 'total': f"{total:.2f}".replace('.', ',')})


def confirmacao(request, pedido_id):
    """Tela de confirmação após envio do pedido."""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    return render(request, 'kiosk/confirmacao.html', {'pedido': pedido})


def manifest(request):
    """Manifest PWA do kiosk."""
    data = {
        "name": "Coxinhas Premium Café — Cardápio",
        "short_name": "Cardápio",
        "description": "Faça seu pedido direto da mesa",
        "start_url": "/kiosk/",
        "scope": "/kiosk/",
        "display": "standalone",
        "orientation": "landscape",
        "background_color": "#1a0a00",
        "theme_color": "#ea8828",
        "icons": [
            {
                "src": "/static/img/logo/logo-coxinhaspremiumcafe.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/img/logo/logo-coxinhaspremiumcafe.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return JsonResponse(data, content_type='application/manifest+json')


# ─── Display Mesa — gerenciamento de slides ────────────────────────────────────────────

@login_required
def slide_list(request):
    """Lista todos os slides do carrossel do kiosk."""
    slides = KioskSlide.objects.all()
    return render(request, 'kiosk/slide_list.html', {'slides': slides})


@login_required
def slide_create(request):
    """Cadastra um novo slide."""
    if request.method == 'POST':
        image = request.FILES.get('image')
        title = request.POST.get('title', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'

        if not image:
            messages.error(request, 'Selecione uma imagem.')
            return render(request, 'kiosk/slide_form.html', {'action': 'Adicionar'})

        try:
            order = int(order)
        except (ValueError, TypeError):
            order = 0

        try:
            validate_image_file_size(image)
        except ValidationError as exc:
            messages.error(request, str(exc))
            return render(request, 'kiosk/slide_form.html', {'action': 'Adicionar'})

        KioskSlide.objects.create(
            image=image,
            title=title,
            order=order,
            is_active=is_active,
        )
        messages.success(request, 'Slide adicionado com sucesso!')
        return redirect('kiosk:slide_list')

    return render(request, 'kiosk/slide_form.html', {'action': 'Adicionar'})


@login_required
def slide_update(request, pk):
    """Edita um slide existente."""
    slide = get_object_or_404(KioskSlide, pk=pk)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')

        try:
            order = int(order)
        except (ValueError, TypeError):
            order = 0

        slide.title = title
        slide.order = order
        slide.is_active = is_active
        if image:
            try:
                validate_image_file_size(image)
            except ValidationError as exc:
                messages.error(request, str(exc))
                return render(request, 'kiosk/slide_form.html', {'action': 'Editar', 'slide': slide})
            slide.image = image
        slide.save()
        messages.success(request, 'Slide atualizado com sucesso!')
        return redirect('kiosk:slide_list')

    return render(request, 'kiosk/slide_form.html', {'action': 'Editar', 'slide': slide})


@login_required
def slide_delete(request, pk):
    """Remove um slide."""
    slide = get_object_or_404(KioskSlide, pk=pk)
    if request.method == 'POST':
        slide.delete()
        messages.success(request, 'Slide removido.')
        return redirect('kiosk:slide_list')
    return render(request, 'kiosk/slide_confirm_delete.html', {'slide': slide})


def catalog_version(request):
    """Retorna a versão atual do catálogo para polling do kiosk.
    Considera produtos, opcionais, movimentações de estoque e alterações em slides.
    """
    return JsonResponse({'version': _catalog_version_value()})

import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from products.models import Product
from orders.models import Comanda, Pedido, PedidoItem
from .models import KioskSlide


def entrada(request):
    """Tela inicial do kiosk — teclado numérico para digitar o número da mesa."""
    if request.method == 'POST':
        numero = request.POST.get('numero', '').strip()
        if numero:
            return redirect('kiosk:cardapio', numero=numero)
    slides = list(KioskSlide.objects.filter(is_active=True).order_by('order', 'id'))
    return render(request, 'kiosk/entrada.html', {'slides': slides})


def cardapio(request, numero):
    """Tela principal de pedido — categorias, produtos e carrinho."""
    produtos = Product.objects.filter(show_in_menu=True).order_by('category', 'name')

    # Agrupar por categoria
    categorias = {}
    for p in produtos:
        cat = p.get_category_display()
        if cat not in categorias:
            categorias[cat] = {'slug': p.category, 'produtos': []}
        categorias[cat]['produtos'].append(p)

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
                    'adicionais': [
                        {
                            'id': a.pk,
                            'nome': a.name,
                            'desc': a.description or '',
                            'preco': float(a.price),
                        }
                        for a in p.adicionais.all()
                    ],
                }
                for p in dados['produtos']
            ],
        }

    slides = list(KioskSlide.objects.filter(is_active=True).order_by('order', 'id'))

    context = {
        'numero': numero,
        'categorias': categorias,
        'produtos_json': json.dumps(produtos_json_data, ensure_ascii=False),
        'slides': slides,
    }
    return render(request, 'kiosk/cardapio.html', context)


@require_http_methods(['POST'])
def enviar_pedido(request, numero):
    """Recebe o carrinho em JSON, cria Comanda + Pedido + PedidoItems."""
    try:
        body = json.loads(request.body)
        itens = body.get('itens', [])
        observacoes = body.get('observacoes', '')

        if not itens:
            return JsonResponse({'erro': 'Carrinho vazio'}, status=400)

        # Busca ou cria comanda em_uso para esta mesa
        comanda, _ = Comanda.objects.get_or_create(
            numero=numero,
            status='em_uso',
            defaults={'status': 'em_uso'},
        )

        # Cria o pedido
        pedido = Pedido.objects.create(
            comanda=comanda,
            observations=observacoes,
            status='aguardando',
        )

        # Cria os itens
        for item in itens:
            produto = get_object_or_404(Product, pk=item['id'])
            qty = int(item.get('qty', 1))
            adicionais_ids = item.get('adicionais', [])
            preco_adicional = Decimal('0.00')
            obs_partes = []
            for aid in adicionais_ids:
                try:
                    ad = produto.adicionais.get(pk=aid)
                    preco_adicional += ad.price
                    obs_partes.append(ad.name)
                except Exception:
                    pass
            unit_price = produto.price + preco_adicional
            obs_item = ' + '.join(obs_partes)
            PedidoItem.objects.create(
                pedido=pedido,
                product=produto,
                quantity=qty,
                unit_price=unit_price,
                observations=obs_item,
            )

        # Atualiza totais
        pedido.update_total()

        return JsonResponse({'ok': True, 'pedido_id': pedido.id})

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return JsonResponse({'erro': str(e)}, status=400)


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

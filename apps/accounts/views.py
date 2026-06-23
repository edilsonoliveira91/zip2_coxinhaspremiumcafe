from django.urls import reverse_lazy
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from .forms import CustomUserCreationForm
from .models import User
from products.models import Product
from orders.models import Comanda, Pedido
from django.db.models import Prefetch
from django.utils import timezone
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.shortcuts import render, get_object_or_404
from .forms import UserPermissionForm
from apps.impressao.services import epson_service
from django.http import JsonResponse
from config.models import SystemConfig
from django.contrib.auth.models import Permission
from django.apps import apps
from checkouts.models import Checkout, CheckoutPayment
from orders.models import PedidoItem
from decimal import Decimal
import json as _json


class CustomLoginView(LoginView):
    """
    View de login customizada usando CBV
    """
    template_name = 'login/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        user = self.request.user
        dashboard = getattr(user, 'dashboard_home', 'home')
        if dashboard == 'ceo':
            return reverse_lazy('accounts:ceo_dashboard')
        elif dashboard == 'manage':
            return reverse_lazy('accounts:manage_dashboard')
        elif dashboard == 'banks':
            return reverse_lazy('accounts:manage_banks')
        return reverse_lazy('accounts:dashboard')

    def get_redirect_url(self):
        # Ignora o parâmetro ?next= para sempre usar a tela configurada no usuário
        return None

    def form_valid(self, form):
        user = form.get_user()
        messages.success(self.request, f'Bem-vindo, {user.get_full_name() or user.username}!')
        from django.contrib.auth import login as auth_login
        auth_login(self.request, user)
        dashboard = getattr(user, 'dashboard_home', 'home')
        if dashboard == 'ceo':
            return redirect(reverse_lazy('accounts:ceo_dashboard'))
        elif dashboard == 'manage':
            return redirect(reverse_lazy('accounts:manage_dashboard'))
        elif dashboard == 'banks':
            return redirect(reverse_lazy('accounts:manage_banks'))
        return redirect(reverse_lazy('accounts:dashboard'))


class CeoDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/ceo_dashboard.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Sum, Count
        hoje = timezone.localtime().date()

        # Checkouts aprovados de hoje
        checkouts_hoje = Checkout.objects.filter(
            status='aprovado',
            processed_at__date=hoje,
        ).exclude(comanda__status__in=['cancelada', 'cortesia'])

        parcial_ids = list(checkouts_hoje.filter(payment_method='parcial').values_list('id', flat=True))

        def _sum_method(method):
            simples = checkouts_hoje.exclude(payment_method='parcial').filter(
                payment_method=method
            ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
            parcial = CheckoutPayment.objects.filter(
                checkout_id__in=parcial_ids, payment_method=method
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            return simples + parcial

        dinheiro   = _sum_method('dinheiro')
        credito    = _sum_method('cartao_credito')
        debito     = _sum_method('cartao_debito')
        pix        = _sum_method('pix')
        voucher    = _sum_method('voucher')
        total_dia  = checkouts_hoje.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        qtd_comandas = checkouts_hoje.count()

        # Gráfico de linha: faturamento dos últimos 30 dias
        labels = []
        valores = []
        for i in range(29, -1, -1):
            dia = hoje - timezone.timedelta(days=i)
            total = Checkout.objects.filter(
                status='aprovado',
                processed_at__date=dia,
            ).exclude(comanda__status__in=['cancelada', 'cortesia']).aggregate(
                total=Sum('total')
            )['total'] or Decimal('0.00')
            labels.append(dia.strftime('%d/%m'))
            valores.append(float(total))

        # Top 5 produtos do dia
        top_produtos = (
            PedidoItem.objects
            .filter(pedido__comanda__checkout__processed_at__date=hoje,
                    pedido__comanda__checkout__status='aprovado')
            .exclude(pedido__comanda__status__in=['cancelada', 'cortesia'])
            .values('product_name')
            .annotate(total_qty=Sum('quantity'))
            .order_by('-total_qty')[:5]
        )

        context.update({
            'hoje': hoje,
            'total_dia': total_dia,
            'qtd_comandas': qtd_comandas,
            'dinheiro': dinheiro,
            'credito': credito,
            'debito': debito,
            'pix': pix,
            'voucher': voucher,
            'chart_labels': _json.dumps(labels),
            'chart_valores': _json.dumps(valores),
            'top_produtos': list(top_produtos),
        })
        return context


class ManageDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/manage_dashboard.html'
    login_url = reverse_lazy('accounts:login')


class ManageBanksDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/manage_banks.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from banks.models import Bank
        from financials.models import CaixaAdmTransferencia
        from pinpads.models import Pinpad
        from django.db.models import Sum
        from datetime import timedelta

        hoje = timezone.localtime().date()

        # Saldo de cada banco (entradas - saídas das BankTransactions)
        banks = Bank.objects.all().order_by('nome')
        banks_data = []
        total_geral_bancos = Decimal('0')
        for bank in banks:
            entradas = bank.transactions.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas   = bank.transactions.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saldo    = entradas - saidas
            total_geral_bancos += saldo
            banks_data.append({'banco': bank, 'saldo': saldo})

        # Conciliações vencidas (data_liquidacao_dinamica <= hoje, não conciliadas, não canceladas)
        pinpad = Pinpad.objects.filter(is_active=True).first()
        dias_map = {
            'credito':  pinpad.dias_credito if pinpad else 30,
            'debito':   pinpad.dias_debito  if pinpad else 1,
            'pix':      pinpad.dias_pix     if pinpad else 1,
            'dinheiro': 0,
        }
        pendentes_qs = CaixaAdmTransferencia.objects.filter(
            conciliado=False, cancelada=False
        ).select_related('banco_destino', 'criado_por').order_by('data_caixa')

        vencidas = []
        a_vencer = []
        total_vencido = Decimal('0')
        total_a_vencer = Decimal('0')
        for t in pendentes_qs:
            base = t.data_caixa or hoje
            t.data_liquidacao_dinamica = base + timedelta(days=dias_map.get(t.metodo_pagamento, 0))
            if t.data_liquidacao_dinamica <= hoje:
                vencidas.append(t)
                total_vencido += t.valor
            else:
                a_vencer.append(t)
                total_a_vencer += t.valor

        context.update({
            'hoje': hoje,
            'banks_data': banks_data,
            'total_geral_bancos': total_geral_bancos,
            'vencidas': vencidas,
            'a_vencer': a_vencer,
            'total_vencido': total_vencido,
            'total_a_vencer': total_a_vencer,
            'qtd_vencidas': len(vencidas),
            'qtd_a_vencer': len(a_vencer),
        })
        return context


class HomeView(LoginRequiredMixin, TemplateView):
    """
    Dashboard principal da cafeteria
    """
    template_name = 'home/home.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Buscar produtos ativos que estão no cardápio
        products = Product.objects.filter(
            is_active=True, 
            show_in_menu=True
        ).order_by('category', 'name')
        
        # Buscar comandas abertas (não finalizadas) ordenadas por prioridade
        hoje = timezone.now().date()
        
        # TESTE: Remover filtro de data
        _prefetch_pedidos = Prefetch(
            'pedidos',
            queryset=Pedido.objects.filter(status__in=['aguardando', 'preparando', 'pronta']),
            to_attr='pedidos_ativos',
        )
        comandas_abertas = sorted(
            Comanda.objects.filter(
                status__in=['em_uso', 'aguardando_caixa']
            ).prefetch_related(_prefetch_pedidos),
            key=lambda c: int(c.numero) if c.numero and str(c.numero).strip().isdigit() else 0
        )

                # ---> LÓGICA DE TEMPO DA CONFIGURAÇÃO <---
        config = SystemConfig.get_settings()
        limit_minutes = config.max_order_time_minutes
        agora = timezone.now()
        
                # Analisaremos todas as comandas abertas para saber se estão atrasadas
        for comanda in comandas_abertas:
            comanda.is_delayed = False # Padrão: não está atrasada
            comanda.has_pending = False # Padrão: tudo entregue ou vazia
            
            # Pega TODOS os pedidos que não estão finalizados/entregues (avaliado como lista p/ eficiência)
            pedidos_pendentes = comanda.pedidos_ativos
            
            # Se encontrou algum pedido não entregue, fica amarela!
            if pedidos_pendentes:
                comanda.has_pending = True
                # Azul (em_atendimento) somente se TODOS os pedidos pendentes já têm atendente registrado
                # Caso contrário (pedido novo sem atendente), volta ao amarelo automaticamente
                comanda.em_atendimento = all(
                    p.atendente_numero is not None for p in pedidos_pendentes
                )
            else:
                # Sem pendentes: limpa o estado de atendimento no DB
                if comanda.em_atendimento:
                    comanda.em_atendimento = False
                    comanda.atendente_numero = None
                    comanda.atendimento_em = None
                    Comanda.objects.filter(pk=comanda.pk).update(
                        em_atendimento=False, atendente_numero=None, atendimento_em=None
                    )
            
            # Pedidos não impressos ainda
            comanda.tem_nao_impressos = any(not p.impresso for p in pedidos_pendentes)
            
            # Das pendentes, a gente checa se tem atraso (apenas as que tão aguardando/preparando entram no tempo crítico)
            for pedido in pedidos_pendentes:
                if pedido.status in ['aguardando', 'preparando']:
                    espera_minutos = (agora - pedido.created_at).total_seconds() / 60
                    if espera_minutos > limit_minutes:
                        comanda.is_delayed = True
                        break # Já achou um atrasado na comanda, vira vermelho e escapa do loop

            # Label de exibição: mesa (kiosk) ou comanda normal
            # display_badge sempre vem do numero (campo autoritativo), não do cliente_nome,
            # para evitar inconsistência após transferência de mesa.
            if comanda.cliente_nome and comanda.cliente_nome.upper().startswith('MESA'):
                comanda.display_label = comanda.cliente_nome
                comanda.display_badge = str(int(comanda.numero)) if comanda.numero and comanda.numero.isdigit() else comanda.numero
            else:
                comanda.display_label = f"Comanda {comanda.numero}"
                comanda.display_badge = comanda.numero

        # Estatísticas das comandas
        stats_comandas = {
            'em_uso': Comanda.objects.filter(status='em_uso').count(),
            'livres': Comanda.objects.filter(status='livre').count(),
        }
        
        context.update({
            'products': products,
            'comandas_abertas': comandas_abertas,
            'stats_comandas': stats_comandas,
        })
        
        return context


def custom_logout_view(request):
    """
    View de logout funcional - bloqueia logout se o usuário de caixa tiver sessão aberta.
    """
    if request.user.is_authenticated:
        # Bloqueia logout se usuário de caixa tem sessão aberta com recebimentos
        if getattr(request.user, 'is_caixa', False):
            try:
                from checkouts.models import SessaoCaixa
                sessao_aberta = SessaoCaixa.objects.filter(
                    usuario=request.user,
                    status='aberta',
                ).first()
                if sessao_aberta and sessao_aberta.get_checkouts().exists():
                    messages.warning(
                        request,
                        'Você possui um caixa aberto com recebimentos. Feche o caixa antes de sair.'
                    )
                    return redirect('checkouts:fechamento_caixa')
            except Exception:
                pass

        username = request.user.get_full_name() or request.user.username
        logout(request)
        messages.success(request, f'Até logo, {username}!')
    return redirect('accounts:login')


class RegisterView(CreateView):
    """
    View de registro de usuário usando CBV
    """
    model = User
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:dashboard')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Fazer login automaticamente após o registro
        login(self.request, self.object)
        messages.success(
            self.request, 
            f'Usuário {self.object.username} criado com sucesso!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(
            self.request,
            'Erro ao criar usuário. Verifique os dados informados.'
        )
        return super().form_invalid(form)




def is_superuser(user):
    """Verifica se o usuário é superuser"""
    return user.is_superuser


@login_required
@permission_required("accounts.view_user", raise_exception=True)
def user_list(request):
    """Lista todos os usuários do sistema"""
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})


def get_permissions_by_app():
    # ── Tradução: app label → nome em português ──────────────────────────
    APP_LABELS_PT = {
        'accounts':  'Usuários e Acessos',
        'banks':     'Bancos',
        'orders':    'Pedidos e Comandas',
        'products':  'Produtos e Estoque',
        'checkouts': 'Caixa',
        'financials':'Financeiro',
        'pinpads':   'Maquininhas (Pinpads)',
        'companys':  'Empresa',
        'reports':   'Relatórios',
        'config':    'Configurações do Sistema',
        'kiosk':     'Kiosk (Autoatendimento)',
        'utils':     'Utilitários',
    }

    # ── Tradução: model name (lower) → nome em português ─────────────────
    MODEL_NAMES_PT = {
        # accounts
        'user':                        'Usuário',
        # banks
        'bank':                        'Banco',
        'banktransaction':             'Transação Bancária',
        # orders
        'comanda':                     'Comanda',
        'pedido':                      'Pedido',
        'pedidoitem':                  'Item do Pedido',
        'comandapartialpayment':       'Pagamento Parcial',
        'itemremovidolog':             'Log de Item Removido',
        # products
        'product':                     'Produto',
        'combo':                       'Combo',
        'comboitem':                   'Item do Combo',
        'adicional':                   'Adicional',
        'opcionalobrigatorio':         'Opcional Obrigatório',
        'stockentry':                  'Entrada de Estoque',
        'stockexit':                   'Saída de Estoque',
        'rawmaterial':                 'Matéria-Prima',
        # checkouts
        'checkout':                    'Fechamento de Caixa',
        'sessaocaixa':                 'Sessão de Caixa',
        'checkoutpayment':             'Pagamento do Caixa',
        # financials
        'sangria':                     'Sangria',
        'fechamentocaixadiario':       'Fechamento Diário de Caixa',
        'ajustefechamentocaixadiario': 'Ajuste de Fechamento Diário',
        'caixaadm':                    'Caixa ADM (Malotes)',
        'caixaadmtransferencia':       'Transferência Caixa ADM',
        'despesamalote':               'Despesa do Malote',
        # pinpads
        'pinpad':                      'Maquininha (Pinpad)',
        'bandeirapinpad':              'Bandeira de Maquininha',
        # companys
        'company':                     'Empresa',
        'certificadodigital':          'Certificado Digital',
        # reports
        'report':                      'Relatório',
        # config
        'systemconfig':                'Configuração do Sistema (legado)',
        'configtempoespera':           'Tempo de Espera',
        'configtrocoinicial':          'Troco Inicial',
        'configquebracaixa':           'Quebra de Caixa',
        'configcomissao':              'Comissão',
        'configkioskpin':              'PIN do Kiosk',
        'garcom':                      'Garçom',
        # kiosk
        'kioskslide':                  'Slide do Kiosk',
    }

    # Modelos legados que não devem aparecer na tela de permissões
    EXCLUDED_MODELS = {'order', 'orderitem'}

    excluded_apps = {
        'admin', 'auth', 'contenttypes', 'sessions', 'messages',
        'staticfiles', 'tailwind', 'django_browser_reload', 'theme', 'impressao',
        'utils',  # modelos internos do sistema (SyncLog, etc.)
    }

    STANDARD_ACTIONS = {'add', 'view', 'change', 'delete'}

    app_configs = [
        app_config for app_config in apps.get_app_configs()
        if app_config.label not in excluded_apps
    ]
    app_configs = sorted(
        app_configs,
        key=lambda x: APP_LABELS_PT.get(x.label, x.verbose_name).lower()
    )

    permissions_by_app = {}
    for app_config in app_configs:
        all_perms = list(Permission.objects.filter(
            content_type__app_label=app_config.label
        ).order_by('content_type__model', 'codename').select_related('content_type'))

        if not all_perms:
            continue

        permissions_by_model = {}
        for perm in all_perms:
            model_name = perm.content_type.model
            if model_name in EXCLUDED_MODELS:
                continue
            if model_name not in permissions_by_model:
                display_name = MODEL_NAMES_PT.get(model_name, perm.content_type.name.title())
                permissions_by_model[model_name] = {
                    'name': display_name,
                    'permissions': [],
                    'custom_permissions': [],
                }
            standard_codenames = {f'{action}_{model_name}' for action in STANDARD_ACTIONS}
            if perm.codename in standard_codenames:
                permissions_by_model[model_name]['permissions'].append(perm)
            else:
                permissions_by_model[model_name]['custom_permissions'].append(perm)

        # Remove modelos sem nenhuma permissão relevante
        permissions_by_model = {
            k: v for k, v in permissions_by_model.items()
            if v['permissions'] or v['custom_permissions']
        }

        if permissions_by_model:
            app_display = APP_LABELS_PT.get(app_config.label, app_config.verbose_name)
            permissions_by_app[app_display] = permissions_by_model

    return permissions_by_app

def _save_bank_accesses(user, post_data):
    """Sincroniza registros de UserBankAccess a partir dos dados do POST."""
    from banks.models import Bank, UserBankAccess
    for bank in Bank.objects.all():
        can_view     = f'bank_view_{bank.id}'        in post_data
        can_change   = f'bank_change_{bank.id}'      in post_data
        can_add      = f'bank_add_tx_{bank.id}'      in post_data
        can_pay      = f'bank_pay_tx_{bank.id}'      in post_data
        can_transfer = f'bank_transfer_tx_{bank.id}' in post_data
        can_del      = f'bank_del_tx_{bank.id}'      in post_data
        if any([can_view, can_change, can_add, can_pay, can_transfer, can_del]):
            UserBankAccess.objects.update_or_create(
                user=user, bank=bank,
                defaults={
                    'can_view':               can_view,
                    'can_change':             can_change,
                    'can_add_transaction':    can_add,
                    'can_pay_transaction':    can_pay,
                    'can_transfer_transaction': can_transfer,
                    'can_delete_transaction': can_del,
                }
            )
        else:
            UserBankAccess.objects.filter(user=user, bank=bank).delete()


def _get_bank_context(user_to_edit=None):
    """Retorna lista de dicts {bank, can_view, can_change, ...} para o template."""
    from banks.models import Bank, UserBankAccess
    accesses = {}
    if user_to_edit:
        for a in UserBankAccess.objects.filter(user=user_to_edit):
            accesses[a.bank_id] = a
    rows = []
    for bank in Bank.objects.order_by('nome'):
        acc = accesses.get(bank.id)
        rows.append({
            'bank':                    bank,
            'can_view':                acc.can_view                if acc else False,
            'can_change':              acc.can_change              if acc else False,
            'can_add_transaction':     acc.can_add_transaction     if acc else False,
            'can_pay_transaction':     acc.can_pay_transaction     if acc else False,
            'can_transfer_transaction':acc.can_transfer_transaction if acc else False,
            'can_delete_transaction':  acc.can_delete_transaction  if acc else False,
        })
    return rows


@login_required
@permission_required("accounts.add_user", raise_exception=True)
def user_create(request):
    """Cria um novo usuário com permissões dinâmicas"""
    if request.method == 'POST':
        form = UserPermissionForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_staff = True
            user.save()
            user.user_permissions.set(request.POST.getlist('permissions'))
            _save_bank_accesses(user, request.POST)
            messages.success(request, f'✅ Usuário {user.username} criado com sucesso!')
            return redirect('accounts:user_list')
    else:
        form = UserPermissionForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Criar Novo Usuário',
        'is_editing': False,
        'permissions_by_app': get_permissions_by_app(),
        'user_permissions': [],
        'bank_rows': _get_bank_context(),
    })

@login_required
@permission_required("accounts.change_user", raise_exception=True)
def user_edit(request, user_id):
    """Edita as permissões de um usuário existente (dinamicamente)"""
    user_to_edit = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserPermissionForm(request.POST, instance=user_to_edit)
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False

        if form.is_valid():
            user = form.save(commit=False)
            if form.cleaned_data.get('password'):
                user.set_password(form.cleaned_data['password'])
            user.save()
            user.user_permissions.set(request.POST.getlist('permissions'))
            _save_bank_accesses(user, request.POST)
            messages.success(request, f'✅ Permissões de {user.username} atualizadas!')
            return redirect('accounts:user_list')
    else:
        form = UserPermissionForm(instance=user_to_edit)
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        form.fields['password'].help_text = 'Deixe em branco para manter a senha atual'
        
    user_permissions = [perm.id for perm in user_to_edit.user_permissions.all()]

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Editar: {user_to_edit.username}',
        'is_editing': True,
        'user_to_edit': user_to_edit,
        'permissions_by_app': get_permissions_by_app(),
        'user_permissions': user_permissions,
        'bank_rows': _get_bank_context(user_to_edit),
    })


@login_required
@permission_required("accounts.delete_user", raise_exception=True)
def user_delete(request, user_id):
    """Deleta um usuário"""
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if request.user.id == user_to_delete.id:
        messages.error(request, '❌ Você não pode deletar seu próprio usuário!')
        return redirect('accounts:user_list')
    
    if request.method == 'POST':
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f'✅ Usuário {username} deletado com sucesso!')
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_confirm_delete.html', {
        'user_to_delete': user_to_delete
    })


# API para verificar mudanças nas comandas (polling inteligente)


class HomeCardsView(LoginRequiredMixin, View):
    """
    Retorna apenas o HTML dos cards de comandas (sem base template).
    Usado pelo polling AJAX para atualizar os cards sem recarregar a página.
    """
    login_url = reverse_lazy('accounts:login')

    def get(self, request):
        from django.shortcuts import render as _render
        config = SystemConfig.get_settings()
        limit_minutes = config.max_order_time_minutes
        agora = timezone.now()

        _prefetch_pedidos = Prefetch(
            'pedidos',
            queryset=Pedido.objects.filter(status__in=['aguardando', 'preparando', 'pronta']),
            to_attr='pedidos_ativos',
        )
        comandas_abertas = sorted(
            Comanda.objects.filter(
                status__in=['em_uso', 'aguardando_caixa']
            ).prefetch_related(_prefetch_pedidos),
            key=lambda c: int(c.numero) if c.numero and str(c.numero).strip().isdigit() else 0
        )

        for comanda in comandas_abertas:
            comanda.is_delayed = False
            comanda.has_pending = False
            pedidos_pendentes = comanda.pedidos_ativos
            if pedidos_pendentes:
                comanda.has_pending = True
                # Azul (em_atendimento) somente se TODOS os pedidos pendentes já têm atendente registrado
                comanda.em_atendimento = all(
                    p.atendente_numero is not None for p in pedidos_pendentes
                )
            else:
                if comanda.em_atendimento:
                    comanda.em_atendimento = False
                    comanda.atendente_numero = None
                    comanda.atendimento_em = None
                    Comanda.objects.filter(pk=comanda.pk).update(
                        em_atendimento=False, atendente_numero=None, atendimento_em=None
                    )
            comanda.tem_nao_impressos = any(not p.impresso for p in pedidos_pendentes)
            for pedido in pedidos_pendentes:
                if pedido.status in ['aguardando', 'preparando']:
                    espera_minutos = (agora - pedido.created_at).total_seconds() / 60
                    if espera_minutos > limit_minutes:
                        comanda.is_delayed = True
                        break
            if comanda.cliente_nome and comanda.cliente_nome.upper().startswith('MESA'):
                comanda.display_label = comanda.cliente_nome
                comanda.display_badge = str(int(comanda.numero)) if comanda.numero and comanda.numero.isdigit() else comanda.numero
            else:
                comanda.display_label = f"Comanda {comanda.numero}"
                comanda.display_badge = comanda.numero

        return _render(request, 'home/_cards_fragment.html', {
            'comandas_abertas': comandas_abertas,
        })

class CheckOrderChangesView(LoginRequiredMixin, View):
    """
    API que verifica se houve mudanças nas comandas abertas
    Retorna JSON com informações sobre mudanças
    """
    
    def get(self, request):
        try:
            hoje = timezone.localtime().date()
            
            # Contar comandas abertas de hoje
            comandas_abertas = Comanda.objects.filter(
                status='em_uso'
            ).count()
            
            # Pegar total de comandas de hoje (para detectar finalizações)
            total_comandas_hoje = Comanda.objects.filter(
                created_at__date=hoje,
                status__in=['em_uso', 'fechada']
            ).count()
            
            # Pegar timestamp da última modificação
            ultima_comanda = Comanda.objects.filter(
                status='em_uso'
            ).order_by('-updated_at').first()
            
            ultima_atualizacao = None
            if ultima_comanda:
                ultima_atualizacao = ultima_comanda.updated_at.timestamp()
            
            return JsonResponse({
                'success': True,
                'comandas_abertas': comandas_abertas,
                'total_comandas_hoje': total_comandas_hoje,
                'ultima_atualizacao': ultima_atualizacao,
                'timestamp': timezone.now().timestamp()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


def imprimir_comanda_view(request, comanda_code):
    """View para imprimir comanda"""
    if request.method == 'POST':
        try:
            # Buscar a comanda pelo código
            comanda = Comanda.objects.get(code=comanda_code)
            
            # Preparar dados para impressão
            dados_impressao = {
                'id': comanda.id,
                'mesa': comanda.name,
                'data': comanda.created_at.strftime('%d/%m/%Y %H:%M'),
                'itens': []
            }
            
            # Adicionar itens da comanda
            for item in comanda.items.all():
                dados_impressao['itens'].append({
                    'nome': item.product.name,
                    'qtd': item.quantity,
                    'preco': float(item.unit_price),
                    'subtotal': float(item.total_price)
                })
            
            # Imprimir
            sucesso = epson_service.imprimir_comanda(dados_impressao)
            
            if sucesso:
                return JsonResponse({
                    'success': True,
                    'message': 'Comanda impressa com sucesso!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Erro na impressão. Verifique a impressora.'
                })
                
        except Comanda.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Comanda não encontrada.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método não permitido'})

def imprimir_cupom_view(request, comanda_code):
    """View para imprimir cupom fiscal/recibo"""
    if request.method == 'POST':
        try:
            import json
            
            # Buscar a comanda pelo código
            comanda = Comanda.objects.get(code=comanda_code)
            
            # Obter dados do corpo da requisição
            body_data = json.loads(request.body)
            
            # Preparar dados para impressão de cupom
            dados_cupom = {
                'tipo': 'cupom',
                'codigo': comanda.code,
                'cliente': comanda.name,
                'data': comanda.created_at.strftime('%d/%m/%Y %H:%M'),
                'metodo_pagamento': body_data.get('metodo_pagamento', 'Não informado'),
                'total': body_data.get('total', f'R$ {float(comanda.total_amount):.2f}'),
                'itens': []
            }
            
            # Adicionar itens da comanda
            for item in comanda.items.all():
                dados_cupom['itens'].append({
                    'nome': item.product.name,
                    'qtd': item.quantity,
                    'preco': float(item.unit_price),
                    'subtotal': float(item.unit_price * item.quantity)
                })
            
            # Imprimir usando o serviço
            sucesso = epson_service.imprimir_cupom(dados_cupom)
            
            if sucesso:
                return JsonResponse({
                    'success': True,
                    'message': 'Cupom impresso com sucesso!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Erro na impressão. Verifique a impressora.'
                })
                
        except Comanda.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Comanda não encontrada.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método não permitido'})
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
from orders.models import Comanda
from django.utils import timezone
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404
from .forms import UserPermissionForm
from apps.impressao.services import epson_service
from django.http import JsonResponse
from config.models import SystemConfig
from django.contrib.auth.models import Permission
from django.apps import apps


class CustomLoginView(LoginView):
    """
    View de login customizada usando CBV
    """
    template_name = 'login/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('accounts:dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, f'Bem-vindo, {form.get_user().get_full_name() or form.get_user().username}!')
        return super().form_valid(form)


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
        comandas_abertas = Comanda.objects.filter(
            status='em_uso'
        ).order_by('-created_at')

                # ---> LÓGICA DE TEMPO DA CONFIGURAÇÃO <---
        config = SystemConfig.get_settings()
        limit_minutes = config.max_order_time_minutes
        agora = timezone.now()
        
                # Analisaremos todas as comandas abertas para saber se estão atrasadas
        for comanda in comandas_abertas:
            comanda.is_delayed = False # Padrão: não está atrasada
            comanda.has_pending = False # Padrão: tudo entregue ou vazia
            
            # Pega TODOS os pedidos que não estão finalizados/entregues
            pedidos_pendentes = comanda.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta'])
            
            # Se encontrou algum pedido não entregue, fica amarela!
            if pedidos_pendentes.exists():
                comanda.has_pending = True
            
            # Das pendentes, a gente checa se tem atraso (apenas as que tão aguardando/preparando entram no tempo crítico)
            for pedido in pedidos_pendentes:
                if pedido.status in ['aguardando', 'preparando']:
                    espera_minutos = (agora - pedido.created_at).total_seconds() / 60
                    if espera_minutos > limit_minutes:
                        comanda.is_delayed = True
                        break # Já achou um atrasado na comanda, vira vermelho e escapa do loop
        
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
    View de logout funcional - mais confiável
    """
    if request.user.is_authenticated:
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
@user_passes_test(is_superuser)
def user_list(request):
    """Lista todos os usuários do sistema"""
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})


def get_permissions_by_app():
    permissions_by_app = {}
    # Nomes das pastas/apps registradas no Django que queremos controlar:
    relevant_apps = ['products', 'orders', 'financials', 'pinpads', 'companies', 'config']
    
    for app_label in relevant_apps:
        try:
            app_config = apps.get_app_config(app_label)
            # Puxa só as permissões dos modelos deste app
            app_permissions = Permission.objects.filter(
                content_type__app_label=app_label
            ).order_by('content_type__model', 'codename')
            
            permissions_by_model = {}
            for perm in app_permissions:
                model_name = perm.content_type.model
                if model_name not in permissions_by_model:
                    permissions_by_model[model_name] = {
                        'name': perm.content_type.name.title(),
                        'permissions': []
                    }
                permissions_by_model[model_name]['permissions'].append(perm)
                
            if permissions_by_model:
                app_name = app_config.verbose_name if hasattr(app_config, 'verbose_name') else app_label.title()
                permissions_by_app[app_name] = permissions_by_model
        except LookupError:
            continue
            
    return permissions_by_app

@login_required
@user_passes_test(is_superuser)
def user_create(request):
    """Cria um novo usuário com permissões dinâmicas"""
    if request.method == 'POST':
        form = UserPermissionForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_staff = True  # Padrão do sistema para conseguir fazer login
            user.save()
            
            # MAGIA: Captura todos os checkboxes marcados na tela e salva
            permissions_ids = request.POST.getlist('permissions')
            user.user_permissions.set(permissions_ids)
            
            messages.success(request, f'✅ Usuário {user.username} criado com sucesso!')
            return redirect('accounts:user_list')
    else:
        form = UserPermissionForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Criar Novo Usuário',
        'is_editing': False,
        'permissions_by_app': get_permissions_by_app(),
        'user_permissions': []
    })

@login_required
@user_passes_test(is_superuser)
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
            
            # Atualiza permissões do banco nativo do Django
            permissions_ids = request.POST.getlist('permissions')
            user.user_permissions.set(permissions_ids)
            
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
        'user_permissions': user_permissions
    })


@login_required
@user_passes_test(is_superuser)
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
                created_at__date=hoje,
                status__in=['aguardando', 'preparando', 'pronta']
            ).count()
            
            # Pegar total de comandas de hoje (para detectar finalizações)
            total_comandas_hoje = Comanda.objects.filter(
                created_at__date=hoje
            ).count()
            
            # Pegar timestamp da última modificação
            ultima_comanda = Comanda.objects.filter(
                created_at__date=hoje
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
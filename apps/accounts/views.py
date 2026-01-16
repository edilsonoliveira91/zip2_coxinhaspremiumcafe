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
from orders.models import Order
from django.utils import timezone
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404
from .forms import UserPermissionForm


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
        comandas_abertas = Order.objects.filter(
            status__in=['aguardando', 'preparando', 'pronta']
        ).select_related('created_by').prefetch_related('items__product').order_by('created_at')

        # Debug: adicionar todas as comandas para teste
        todas_comandas = Order.objects.all()
        print(f"Debug: Total comandas: {todas_comandas.count()}")
        for cmd in todas_comandas:
            print(f"Debug: #{cmd.code} - {cmd.status} - {cmd.created_at}")

        print(f"Debug: Comandas abertas encontradas: {comandas_abertas.count()}")
        
        # Estatísticas das comandas
        stats_comandas = {
            'abertas': Order.objects.filter(created_at__date=hoje, status='aguardando').count(),
            'preparo': Order.objects.filter(created_at__date=hoje, status='preparando').count(),
            'prontas': Order.objects.filter(created_at__date=hoje, status='pronta').count(),
            'entregues': Order.objects.filter(created_at__date=hoje, status='entregue').count(),
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


@login_required
@user_passes_test(is_superuser)
def user_create(request):
    """Cria um novo usuário com permissões"""
    if request.method == 'POST':
        form = UserPermissionForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'✅ Usuário {user.username} criado com sucesso!')
            return redirect('accounts:user_list')
    else:
        form = UserPermissionForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Criar Novo Usuário',
        'is_editing': False
    })


@login_required
@user_passes_test(is_superuser)
def user_edit(request, user_id):
    """Edita as permissões de um usuário existente"""
    user_to_edit = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Criar o form mas não validar o password (será opcional na edição)
        form = UserPermissionForm(request.POST, instance=user_to_edit)
        # Remove validação de senha na edição
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        
        if form.is_valid():
            user = form.save(commit=False)
            # Só atualiza senha se foi fornecida
            if form.cleaned_data.get('password'):
                user.set_password(form.cleaned_data['password'])
            user.save()
            form._save_permissions(user)
            messages.success(request, f'✅ Permissões de {user.username} atualizadas!')
            return redirect('accounts:user_list')
    else:
        # Preencher o formulário com as permissões atuais
        initial_data = {}
        user_perms = user_to_edit.user_permissions.all()
        
        for perm in user_perms:
            if 'product' in perm.codename:
                action = perm.codename.split('_')[0]
                initial_data[f'products_{action}'] = True
            elif 'order' in perm.codename:
                action = perm.codename.split('_')[0]
                initial_data[f'orders_{action}'] = True
            elif 'checkout' in perm.codename:
                action = perm.codename.split('_')[0]
                initial_data[f'checkouts_{action}'] = True
        
        form = UserPermissionForm(instance=user_to_edit, initial=initial_data)
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        form.fields['password'].help_text = 'Deixe em branco para manter a senha atual'
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Editar: {user_to_edit.username}',
        'is_editing': True,
        'user_to_edit': user_to_edit
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
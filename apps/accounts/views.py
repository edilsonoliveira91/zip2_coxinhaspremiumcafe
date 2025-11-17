from django.urls import reverse_lazy
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from .forms import CustomUserCreationForm
from .models import User


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
        context.update({
            'comandas_abertas': [],  # Dados fictícios por enquanto
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
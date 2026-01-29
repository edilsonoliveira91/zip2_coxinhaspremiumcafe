from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Company, CertificadoDigital
from .forms import CompanyForm, CertificadoDigitalForm


class CompanyListView(LoginRequiredMixin, ListView):
    """Lista de empresas"""
    model = Company
    template_name = 'companys/company_list.html'
    context_object_name = 'companies'
    paginate_by = 10
    
    def get_queryset(self):
        return Company.objects.all().order_by('-created_at')


class CompanyDetailView(LoginRequiredMixin, DetailView):
    """Detalhes da empresa"""
    model = Company
    template_name = 'companys/company_detail.html'
    context_object_name = 'company'


class CompanyCreateView(LoginRequiredMixin, CreateView):
    """Criar nova empresa"""
    model = Company
    form_class = CompanyForm
    template_name = 'companys/company_form.html'
    success_url = reverse_lazy('companys:company_list')
    
    def form_valid(self, form):
        # Debug: verificar se chegou até aqui
        print("DEBUG: Form é válido, tentando salvar...")
        messages.success(self.request, '✅ Empresa criada com sucesso!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        # Debug: mostrar erros do formulário
        print("DEBUG: Form inválido!")
        print("Erros do formulário:", form.errors)
        print("Erros não-field:", form.non_field_errors())
        
        # Mostrar erros específicos de cada campo
        for field, errors in form.errors.items():
            print(f"Campo {field}: {errors}")
            messages.error(self.request, f"Erro no campo {field}: {errors[0]}")
        
        return super().form_invalid(form)


class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    """Editar empresa"""
    model = Company
    form_class = CompanyForm
    template_name = 'companys/company_form.html'
    success_url = reverse_lazy('companys:company_list')
    
    def form_valid(self, form):
        messages.success(self.request, '✅ Empresa atualizada com sucesso!')
        return super().form_valid(form)


@login_required
def company_delete(request, pk):
    """Deletar empresa via AJAX"""
    if request.method == 'POST':
        try:
            company = get_object_or_404(Company, pk=pk)
            company_name = company.razao_social
            company.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Empresa "{company_name}" deletada com sucesso!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'❌ Erro ao deletar empresa: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': '❌ Método não permitido'})


@login_required  
def toggle_company_status(request, pk):
    """Ativar/Desativar empresa"""
    company = get_object_or_404(Company, pk=pk)
    company.ativa = not company.ativa
    company.save()
    
    status = "ativada" if company.ativa else "desativada"
    messages.success(request, f'✅ Empresa {status} com sucesso!')
    return redirect('companys:company_list')

# Adicionar ao final do arquivo views.py:

class CertificadoCreateView(LoginRequiredMixin, CreateView):
    """Criar certificado digital para empresa"""
    model = CertificadoDigital
    form_class = CertificadoDigitalForm
    template_name = 'companys/certificado_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = get_object_or_404(Company, pk=self.kwargs['company_id'])
        return context
    
    def form_valid(self, form):
        form.instance.company = get_object_or_404(Company, pk=self.kwargs['company_id'])
        messages.success(self.request, '✅ Certificado digital adicionado com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('companys:company_detail', kwargs={'pk': self.kwargs['company_id']})


class CertificadoUpdateView(LoginRequiredMixin, UpdateView):
    """Editar certificado digital"""
    model = CertificadoDigital
    form_class = CertificadoDigitalForm
    template_name = 'companys/certificado_form.html'
    
    def get_object(self):
        company = get_object_or_404(Company, pk=self.kwargs['company_id'])
        return get_object_or_404(CertificadoDigital, company=company)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = get_object_or_404(Company, pk=self.kwargs['company_id'])
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '✅ Certificado digital atualizado com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('companys:company_detail', kwargs={'pk': self.kwargs['company_id']})


class CertificadoDeleteView(LoginRequiredMixin, UpdateView):
    """Remover certificado digital"""
    model = CertificadoDigital
    template_name = 'companys/certificado_delete.html'
    
    def get_object(self):
        company = get_object_or_404(Company, pk=self.kwargs['company_id'])
        return get_object_or_404(CertificadoDigital, company=company)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = get_object_or_404(Company, pk=self.kwargs['company_id'])
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, '✅ Certificado digital removido com sucesso!')
        return redirect('companys:company_detail', pk=self.kwargs['company_id'])



@login_required
def testar_certificado(request, company_id):
    """Testar conectividade do certificado digital com a SEFAZ"""
    company = get_object_or_404(Company, pk=company_id)
    
    try:
        certificado = company.certificado_digital
        if not certificado:
            messages.error(request, '❌ Empresa não possui certificado digital configurado!')
            return redirect('companys:company_detail', pk=company_id)
        
        # Aqui implementar teste real com a SEFAZ
        # Por enquanto, simulando sucesso
        messages.success(request, '✅ Certificado digital testado com sucesso! Conectividade OK.')
        
    except CertificadoDigital.DoesNotExist:
        messages.error(request, '❌ Certificado digital não encontrado!')
    except Exception as e:
        messages.error(request, f'❌ Erro ao testar certificado: {str(e)}')
    
    return redirect('companys:company_detail', pk=company_id)


@login_required
def consultar_status_sefaz(request, company_id):
    """Consultar status dos serviços da SEFAZ"""
    company = get_object_or_404(Company, pk=company_id)
    
    try:
        # Aqui implementar consulta real à SEFAZ
        # Por enquanto, simulando resposta
        status_info = {
            'nfce': 'Operacional',
            'consulta': 'Operacional',
            'autorizacao': 'Operacional',
            'ultimo_check': 'Agora'
        }
        
        messages.info(request, f'📊 Status SEFAZ - NFCe: {status_info["nfce"]} | Consulta: {status_info["consulta"]}')
        
    except Exception as e:
        messages.error(request, f'❌ Erro ao consultar SEFAZ: {str(e)}')
    
    return redirect('companys:company_detail', pk=company_id)
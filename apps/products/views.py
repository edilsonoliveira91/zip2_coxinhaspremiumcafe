from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import transaction
from .models import Product, Combo, ComboItem
from .forms import ProductForm, ComboForm, ComboItemFormSet, ProductSearchForm, ComboSearchForm


# ==================== VIEWS DE PRODUTOS ====================

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related('created_by')
        
        # Filtros de pesquisa
        search = self.request.GET.get('search')
        category = self.request.GET.get('category')
        show_in_menu = self.request.GET.get('show_in_menu')
        
        if search:
            queryset = queryset.filter(name__icontains=search)
            
        if category:
            queryset = queryset.filter(category=category)
            
        if show_in_menu == 'true':
            queryset = queryset.filter(show_in_menu=True)
        elif show_in_menu == 'false':
            queryset = queryset.filter(show_in_menu=False)
            
        return queryset.order_by('category', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Product.objects.filter(is_active=True)
        
        context.update({
            'search_form': ProductSearchForm(self.request.GET),
            'categories': Product.CATEGORY_CHOICES,
            'total_products': queryset.count(),
            'menu_products': queryset.filter(show_in_menu=True).count(),
            'search_query': self.request.GET.get('search', ''),
        })
        return context


class ProductDetailView(LoginRequiredMixin, DetailView):
    """
    Detalhes de um produto específico
    """
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Combos que usam este produto
        context['combos_using_product'] = Combo.objects.filter(
            items__product=product,
            is_active=True
        ).distinct()
        
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de novo produto
    """
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        
        messages.success(
            self.request, 
            f'Produto "{form.instance.name}" criado com sucesso!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(
            self.request,
            'Erro ao criar produto. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de produto existente
    """
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        
        messages.success(
            self.request, 
            f'Produto "{form.instance.name}" atualizado com sucesso!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(
            self.request,
            'Erro ao atualizar produto. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class ProductDeleteView(LoginRequiredMixin, DeleteView):
    """
    Exclusão (soft delete) de produto
    """
    model = Product
    template_name = 'products/product_confirm_delete.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Verificar se o produto está sendo usado em combos
        context['combos_using_product'] = Combo.objects.filter(
            items__product=product,
            is_active=True
        ).distinct()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Verificar se o produto está sendo usado em algum combo ativo
        active_combos = Combo.objects.filter(
            items__product=self.object,
            is_active=True
        ).distinct()
        
        if active_combos.exists():
            combo_names = ', '.join([combo.name for combo in active_combos])
            messages.error(
                request,
                f'Não é possível excluir o produto "{self.object.name}" pois está sendo usado nos combos: {combo_names}'
            )
            return redirect(self.success_url)
        
        # Soft delete
        self.object.is_active = False
        self.object.updated_by = request.user
        self.object.save()
        
        messages.success(
            request,
            f'Produto "{self.object.name}" removido com sucesso!'
        )
        return redirect(self.success_url)


# ==================== VIEWS DE COMBOS ====================

class ComboListView(LoginRequiredMixin, ListView):
    """
    Lista todos os combos ativos
    """
    model = Combo
    template_name = 'products/combo_list.html'
    context_object_name = 'combos'
    paginate_by = 12
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        queryset = Combo.objects.filter(is_active=True).prefetch_related(
            'items__product'
        ).select_related('created_by')
        
        # Filtros de pesquisa
        search = self.request.GET.get('search')
        show_in_menu = self.request.GET.get('show_in_menu')
        
        if search:
            queryset = queryset.filter(name__icontains=search)
            
        if show_in_menu == 'true':
            queryset = queryset.filter(show_in_menu=True)
        elif show_in_menu == 'false':
            queryset = queryset.filter(show_in_menu=False)
            
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Combo.objects.filter(is_active=True)
        
        context.update({
            'search_form': ComboSearchForm(self.request.GET),
            'total_combos': queryset.count(),
            'menu_combos': queryset.filter(show_in_menu=True).count(),
            'search_query': self.request.GET.get('search', ''),
        })
        return context


class ComboDetailView(LoginRequiredMixin, DetailView):
    """
    Detalhes de um combo específico - mostra preços individuais customizados
    """
    model = Combo
    template_name = 'products/combo_detail.html'
    context_object_name = 'combo'
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Combo.objects.filter(is_active=True).prefetch_related(
            'items__product'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        combo = self.get_object()
        
        # Preparar dados detalhados dos itens do combo
        items_data = []
        total_original = 0
        total_combo = 0
        
        for item in combo.items.all():
            original_price = item.product.price * item.quantity
            combo_price = item.combo_price * item.quantity
            discount = original_price - combo_price
            
            items_data.append({
                'product': item.product,
                'quantity': item.quantity,
                'unit_original_price': item.product.price,
                'unit_combo_price': item.combo_price,
                'total_original_price': original_price,
                'total_combo_price': combo_price,
                'discount_amount': discount,
                'discount_percentage': round(
                    (discount / original_price) * 100, 2
                ) if original_price > 0 else 0
            })
            
            total_original += original_price
            total_combo += combo_price
        
        context.update({
            'items_data': items_data,
            'total_original_price': total_original,
            'total_combo_price': total_combo,
            'total_discount': total_original - total_combo,
            'total_discount_percentage': round(
                ((total_original - total_combo) / total_original) * 100, 2
            ) if total_original > 0 else 0
        })
        
        return context


class ComboCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de novo combo com produtos e preços customizados
    """
    model = Combo
    form_class = ComboForm
    template_name = 'products/combo_form.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = ComboItemFormSet(
                self.request.POST, 
                prefix='items'
            )
        else:
            context['formset'] = ComboItemFormSet(prefix='items')
        
        # Produtos disponíveis para JavaScript
        products = Product.objects.filter(is_active=True).values(
            'id', 'name', 'price', 'category'
        )
        context['products_json'] = list(products)
        context['is_editing'] = False
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        with transaction.atomic():
            form.instance.created_by = self.request.user
            form.instance.updated_by = self.request.user
            self.object = form.save()
            
            if formset.is_valid():
                formset.instance = self.object
                instances = formset.save()
                
                if not instances:
                    messages.error(
                        self.request,
                        'É necessário adicionar pelo menos um produto ao combo.'
                    )
                    return self.form_invalid(form)
                
                messages.success(
                    self.request,
                    f'Combo "{self.object.name}" criado com sucesso! '
                    f'{len(instances)} produtos adicionados com preços customizados.'
                )
                return super().form_valid(form)
            else:
                messages.error(
                    self.request,
                    'Erro nos produtos do combo. Verifique os dados informados.'
                )
                return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request,
            'Erro ao criar combo. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class ComboUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de combo existente - permite alterar preços individuais
    """
    model = Combo
    form_class = ComboForm
    template_name = 'products/combo_form.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Combo.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = ComboItemFormSet(
                self.request.POST, 
                instance=self.object,
                prefix='items'
            )
        else:
            context['formset'] = ComboItemFormSet(
                instance=self.object,
                prefix='items'
            )
        
        # Produtos disponíveis para JavaScript
        products = Product.objects.filter(is_active=True).values(
            'id', 'name', 'price', 'category'
        )
        context['products_json'] = list(products)
        context['is_editing'] = True
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        with transaction.atomic():
            form.instance.updated_by = self.request.user
            self.object = form.save()
            
            if formset.is_valid():
                instances = formset.save()
                
                # Verificar se ainda tem itens após possíveis exclusões
                remaining_items = ComboItem.objects.filter(combo=self.object).count()
                
                if remaining_items == 0:
                    messages.error(
                        self.request,
                        'É necessário manter pelo menos um produto no combo.'
                    )
                    return self.form_invalid(form)
                
                messages.success(
                    self.request,
                    f'Combo "{self.object.name}" atualizado com sucesso! '
                    f'Preços customizados salvos.'
                )
                return super().form_valid(form)
            else:
                messages.error(
                    self.request,
                    'Erro nos produtos do combo. Verifique os dados informados.'
                )
                return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request,
            'Erro ao atualizar combo. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class ComboDeleteView(LoginRequiredMixin, DeleteView):
    """
    Exclusão (soft delete) de combo
    """
    model = Combo
    template_name = 'products/combo_confirm_delete.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        return Combo.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        combo = self.get_object()
        
        # Informações do combo para confirmação
        context['combo_items'] = combo.items.all()
        context['total_price'] = combo.total_price
        
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Soft delete
        self.object.is_active = False
        self.object.updated_by = request.user
        self.object.save()
        
        messages.success(
            request,
            f'Combo "{self.object.name}" removido com sucesso!'
        )
        return redirect(self.success_url)
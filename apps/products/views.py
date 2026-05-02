from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.db import transaction
from .models import Product, Combo, ComboItem
from .forms import ProductForm, ComboForm, ComboItemFormSet, ProductSearchForm, ComboSearchForm
from .models import StockEntry
from .forms import StockEntryForm
from django.db.models import Sum, F


# ==================== VIEWS DE PRODUTOS ====================

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    permission_required = 'products.view_product'
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


class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detalhes de um produto específico
    """
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.view_product'
    
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


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Criação de novo produto
    """
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.add_product'
    
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


class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Edição de produto existente
    """
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.change_product' 
    
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


class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Exclusão (soft delete) de produto
    """
    model = Product
    template_name = 'products/product_confirm_delete.html'
    success_url = reverse_lazy('products:product_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.delete_product'
    
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

class ComboListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista todos os combos ativos
    """
    model = Combo
    template_name = 'products/combo_list.html'
    context_object_name = 'combos'
    paginate_by = 12
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.view_combo'
    
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


class ComboDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detalhes de um combo específico - mostra preços individuais customizados
    """
    model = Combo
    template_name = 'products/combo_detail.html'
    context_object_name = 'combo'
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.view_combo'
    
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


class ComboCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Criação de novo combo com produtos e preços customizados
    """
    model = Combo
    form_class = ComboForm
    template_name = 'products/combo_form.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.add_combo'
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


class ComboUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Edição de combo existente - permite alterar preços individuais
    """
    model = Combo
    form_class = ComboForm
    template_name = 'products/combo_form.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.change_combo'
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


class ComboDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Exclusão (soft delete) de combo
    """
    model = Combo
    template_name = 'products/combo_confirm_delete.html'
    success_url = reverse_lazy('products:combo_list')
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.delete_combo'
    
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


# ==================== VIEWS DE ADICIONAIS ====================

import json
from django.http import JsonResponse
from decimal import Decimal as _Decimal
from .models import Adicional


class AdicionalListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista e gerencia adicionais
    """
    model = Adicional
    template_name = 'products/adicional_list.html'
    context_object_name = 'adicionais'
    permission_required = 'products.view_product'
    login_url = reverse_lazy('accounts:login')

    def get_queryset(self):
        qs = Adicional.objects.filter(is_active=True)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['total'] = Adicional.objects.filter(is_active=True).count()
        return context


class AdicionalCreateView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Criação de adicional via AJAX (POST JSON)
    """
    model = Adicional
    permission_required = 'products.add_product'
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            price_raw = data.get('price', '')

            if not name:
                return JsonResponse({'success': False, 'message': 'Nome é obrigatório.'})
            if not price_raw:
                return JsonResponse({'success': False, 'message': 'Preço é obrigatório.'})

            price = _Decimal(str(price_raw).replace(',', '.'))
            if price <= 0:
                return JsonResponse({'success': False, 'message': 'Preço deve ser maior que zero.'})

            adicional = Adicional.objects.create(
                name=name,
                description=description,
                price=price,
                created_by=request.user,
            )
            return JsonResponse({
                'success': True,
                'message': f'Adicional "{adicional.name}" criado com sucesso!',
                'adicional': {
                    'id': adicional.id,
                    'name': adicional.name,
                    'description': adicional.description,
                    'price': str(adicional.price),
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class AdicionalUpdateView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Edição de adicional via AJAX (POST JSON)
    """
    model = Adicional
    permission_required = 'products.change_product'
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        try:
            from django.shortcuts import get_object_or_404
            adicional = get_object_or_404(Adicional, pk=pk, is_active=True)
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            price_raw = data.get('price', '')

            if not name:
                return JsonResponse({'success': False, 'message': 'Nome é obrigatório.'})
            if not price_raw:
                return JsonResponse({'success': False, 'message': 'Preço é obrigatório.'})

            price = _Decimal(str(price_raw).replace(',', '.'))
            if price <= 0:
                return JsonResponse({'success': False, 'message': 'Preço deve ser maior que zero.'})

            adicional.name = name
            adicional.description = description
            adicional.price = price
            adicional.updated_by = request.user
            adicional.save(update_fields=['name', 'description', 'price', 'updated_by', 'updated_at'])

            return JsonResponse({
                'success': True,
                'message': f'Adicional "{adicional.name}" atualizado com sucesso!',
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class AdicionalDeleteView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Remoção (soft delete) de adicional via AJAX (POST JSON)
    """
    model = Adicional
    permission_required = 'products.delete_product'
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        try:
            from django.shortcuts import get_object_or_404
            adicional = get_object_or_404(Adicional, pk=pk, is_active=True)
            adicional.is_active = False
            adicional.updated_by = request.user
            adicional.save(update_fields=['is_active', 'updated_by', 'updated_at'])
            return JsonResponse({'success': True, 'message': f'Adicional "{adicional.name}" removido com sucesso!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)



# ==================== VIEWS DE ESTOQUE ====================

class StockListView(LoginRequiredMixin, ListView):
    model = StockEntry
    template_name = 'stock/stock_list.html'
    context_object_name = 'entries'
    paginate_by = 20
    login_url = reverse_lazy('accounts:login')

    def get_queryset(self):
        qs = StockEntry.objects.select_related('product').order_by('-date', '-created_at')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(product__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['totals'] = (
            StockEntry.objects
            .values('product__id', 'product__name', 'product__category')
            .annotate(
                total_qty=Sum('quantity'),
                total_invested=Sum(F('quantity') * F('unit_cost'))
            )
            .order_by('product__category', 'product__name')
        )
        context['q'] = self.request.GET.get('q', '')
        return context


class StockEntryCreateView(LoginRequiredMixin, CreateView):
    model = StockEntry
    form_class = StockEntryForm
    template_name = 'stock/stock_form.html'
    success_url = reverse_lazy('products:stock_list')
    login_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '✅ Entrada de estoque registrada com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, '❌ Verifique os campos e tente novamente.')
        return super().form_invalid(form)


class StockEntryDeleteView(LoginRequiredMixin, DeleteView):
    model = StockEntry
    template_name = 'stock/stock_confirm_delete.html'
    success_url = reverse_lazy('products:stock_list')
    login_url = reverse_lazy('accounts:login')

    def delete(self, request, *args, **kwargs):
        messages.success(request, '✅ Entrada removida com sucesso!')
        return super().delete(request, *args, **kwargs)

# ==================== VIEW SEM ESTOQUE ====================

class NoStockListView(LoginRequiredMixin, TemplateView):
    """
    Lista produtos com saldo de estoque igual a zero.
    """
    template_name = 'stock/nostock_list.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        from django.db.models import OuterRef, Subquery, ExpressionWrapper, IntegerField
        from django.db.models.functions import Coalesce
        from .models import StockExit
        from orders.models import PedidoItem

        context = super().get_context_data(**kwargs)

        # Subquery: saídas em andamento (pedidos não entregues)
        active_items_qs = (
            PedidoItem.objects
            .filter(product=OuterRef('pk'), pedido__status__in=['aguardando', 'preparando', 'pronta'])
            .values('product')
            .annotate(t=Sum('quantity'))
            .values('t')
        )

        produtos = (
            Product.objects
            .filter(show_in_menu=True)
            .annotate(
                entradas=Coalesce(Sum('stock_entries__quantity'), 0, output_field=IntegerField()),
                saidas_perm=Coalesce(Sum('stock_exits__quantity'), 0, output_field=IntegerField()),
                saidas_ativas=Coalesce(
                    Subquery(active_items_qs, output_field=IntegerField()), 0,
                    output_field=IntegerField()
                ),
            )
            .filter(entradas__gt=0)  # apenas produtos com controle de estoque
            .annotate(
                saldo=ExpressionWrapper(
                    F('entradas') - F('saidas_perm') - F('saidas_ativas'),
                    output_field=IntegerField()
                )
            )
            .filter(saldo__lte=0)
            .order_by('category', 'name')
        )

        context['produtos'] = produtos
        context['total'] = produtos.count()
        return context

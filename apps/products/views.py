from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.views import View
from django.http import JsonResponse
from django.db import transaction
from .models import Product, Combo, ComboItem, RawMaterial, OpcionalObrigatorio
from .forms import ProductForm, ComboForm, ComboItemFormSet, ProductSearchForm, ComboSearchForm, RawMaterialForm
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
        # Filtros de pesquisa
        search = self.request.GET.get('search')
        category = self.request.GET.get('category')
        show_in_menu = self.request.GET.get('show_in_menu')
        only_active = self.request.GET.get('only_active')

        # Padrão: mostrar apenas ativos; only_active=false mostra apenas inativos
        if only_active == 'false':
            queryset = Product.objects.filter(is_active=False).select_related('created_by')
        else:
            queryset = Product.objects.filter(is_active=True).select_related('created_by')

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
        all_products = Product.objects.all()
        
        context.update({
            'search_form': ProductSearchForm(self.request.GET),
            'categories': Product.CATEGORY_CHOICES,
            'total_products': all_products.filter(is_active=True).count(),
            'menu_products': all_products.filter(is_active=True, show_in_menu=True).count(),
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
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['can_edit_nfce'] = True  # criação sempre permite NFC-e (campos obrigatórios)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_edit_nfce'] = True
        return context

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
        return Product.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['can_edit_nfce'] = self.request.user.has_perm('products.manage_nfce_fields')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_edit_nfce'] = self.request.user.has_perm('products.manage_nfce_fields')
        return context
    
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
    
    def form_valid(self, form):
        # Django 5.x: post() → form_valid() (não mais delete())
        # Verificar se o produto está sendo usado em algum combo ativo
        active_combos = Combo.objects.filter(
            items__product=self.object,
            is_active=True
        ).distinct()

        if active_combos.exists():
            combo_names = ', '.join([combo.name for combo in active_combos])
            messages.error(
                self.request,
                f'Não é possível excluir o produto "{self.object.name}" pois está sendo usado nos combos: {combo_names}'
            )
            return redirect(self.success_url)

        # Soft delete
        self.object.is_active = False
        self.object.updated_by = self.request.user
        self.object.save()

        messages.success(
            self.request,
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
    
    def form_valid(self, form):
        # Django 5.x: post() → form_valid() (não mais delete())
        # Soft delete
        self.object.is_active = False
        self.object.updated_by = self.request.user
        self.object.save()

        messages.success(
            self.request,
            f'Combo "{self.object.name}" removido com sucesso!'
        )
        return redirect(self.success_url)


# ==================== VIEWS DE ADICIONAIS ====================

import json
from decimal import Decimal as _Decimal
from .models import Adicional, OpcionalObrigatorio


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
            price = _Decimal(str(price_raw).replace(',', '.')) if price_raw else _Decimal('0.00')
            if price < 0:
                return JsonResponse({'success': False, 'message': 'Preço não pode ser negativo.'})

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
            price = _Decimal(str(price_raw).replace(',', '.')) if price_raw else _Decimal('0.00')
            if price < 0:
                return JsonResponse({'success': False, 'message': 'Preço não pode ser negativo.'})

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



class ProdutoAdicionaisView(LoginRequiredMixin, View):
    """API: lista adicionais de um produto específico (GET) ou cria novo (POST)"""
    def get(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        from .models import Product
        product = get_object_or_404(Product, pk=product_pk)
        adicionais = Adicional.objects.filter(product=product, is_active=True).values('id', 'name', 'price')
        return JsonResponse({'adicionais': list(adicionais)})

    def post(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        from .models import Product
        product = get_object_or_404(Product, pk=product_pk)
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            price_raw = data.get('price', '')
            if not name:
                return JsonResponse({'success': False, 'message': 'Nome é obrigatório.'})
            if not price_raw:
                return JsonResponse({'success': False, 'message': 'Preço é obrigatório.'})
            price = _Decimal(str(price_raw).replace(',', '.'))
            if price <= 0:
                return JsonResponse({'success': False, 'message': 'Preço deve ser maior que zero.'})
            adicional = Adicional.objects.create(
                product=product,
                name=name,
                price=price,
                created_by=request.user,
            )
            return JsonResponse({'success': True, 'adicional': {'id': adicional.id, 'name': adicional.name, 'price': str(adicional.price)}})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ProdutoAdicionalDeleteView(LoginRequiredMixin, View):
    """API: remove adicional de um produto (POST)"""
    def post(self, request, product_pk, adicional_pk):
        from django.shortcuts import get_object_or_404
        adicional = get_object_or_404(Adicional, pk=adicional_pk, product_id=product_pk, is_active=True)
        adicional.is_active = False
        adicional.updated_by = request.user
        adicional.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return JsonResponse({'success': True})


class ProdutoOpcionaisObrigatoriosView(LoginRequiredMixin, View):
    """API: lista opcionais obrigatórios de um produto (GET) ou cria novo (POST)."""
    def get(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        from .models import Product
        product = get_object_or_404(Product, pk=product_pk)
        opcionais = OpcionalObrigatorio.objects.filter(product=product, is_active=True).values('id', 'name', 'price')
        return JsonResponse({'opcionais': list(opcionais)})

    def post(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        from .models import Product
        product = get_object_or_404(Product, pk=product_pk)
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            price_raw = data.get('price', 0)

            if not name:
                return JsonResponse({'success': False, 'message': 'Nome é obrigatório.'})

            price = _Decimal(str(price_raw).replace(',', '.'))
            if price < 0:
                return JsonResponse({'success': False, 'message': 'Preço não pode ser negativo.'})

            opcional = OpcionalObrigatorio.objects.create(
                product=product,
                name=name,
                price=price,
                created_by=request.user,
            )
            return JsonResponse({'success': True, 'opcional': {'id': opcional.id, 'name': opcional.name, 'price': str(opcional.price)}})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ProdutoOpcionalObrigatorioDeleteView(LoginRequiredMixin, View):
    """API: remove opcional obrigatório de um produto (POST)."""
    def post(self, request, product_pk, opcional_pk):
        from django.shortcuts import get_object_or_404
        opcional = get_object_or_404(OpcionalObrigatorio, pk=opcional_pk, product_id=product_pk, is_active=True)
        opcional.is_active = False
        opcional.updated_by = request.user
        opcional.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return JsonResponse({'success': True})


# ==================== VIEWS DE ESTOQUE ====================

class StockListView(LoginRequiredMixin, ListView):
    model = StockEntry
    template_name = 'stock/stock_list.html'
    context_object_name = 'entries'
    paginate_by = 20
    login_url = reverse_lazy('accounts:login')

    def _get_filters(self):
        q = self.request.GET.get('q', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        return q, date_from, date_to

    def get_queryset(self):
        q, date_from, date_to = self._get_filters()
        qs = StockEntry.objects.select_related('product').order_by('-date', '-created_at')
        if q:
            qs = qs.filter(product__name__icontains=q)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import StockExit

        q, date_from, date_to = self._get_filters()

        # Entradas agrupadas por produto (respeitando filtros de data e busca)
        totals_qs = StockEntry.objects.values('product__id', 'product__name', 'product__category')
        if q:
            totals_qs = totals_qs.filter(product__name__icontains=q)
        if date_from:
            totals_qs = totals_qs.filter(date__gte=date_from)
        if date_to:
            totals_qs = totals_qs.filter(date__lte=date_to)
        totals_qs = totals_qs.annotate(
            total_qty=Sum('quantity'),
            total_invested=Sum(F('quantity') * F('unit_cost'))
        ).order_by('product__category', 'product__name')

        # Saídas agrupadas por produto (respeitando filtros de data e busca)
        exits_qs = StockExit.objects.values('product_id')
        if q:
            exits_qs = exits_qs.filter(product__name__icontains=q)
        if date_from:
            exits_qs = exits_qs.filter(created_at__date__gte=date_from)
        if date_to:
            exits_qs = exits_qs.filter(created_at__date__lte=date_to)
        saidas_por_produto = dict(
            exits_qs.annotate(t=Sum('quantity')).values_list('product_id', 't')
        )

        totals = []
        for t in totals_qs:
            saidas = saidas_por_produto.get(t['product__id'], 0) or 0
            t['saidas_qty'] = saidas
            t['saldo_qty'] = (t['total_qty'] or 0) - saidas
            totals.append(t)

        context['totals'] = totals
        context['q'] = q
        context['date_from'] = date_from
        context['date_to'] = date_to
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

        # Parâmetro de mínimo de estoque (padrão = 0 → só sem estoque)
        try:
            minimo = int(self.request.GET.get('minimo', 0))
        except (ValueError, TypeError):
            minimo = 0

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
            .annotate(
                saldo=ExpressionWrapper(
                    F('entradas') - F('saidas_perm') - F('saidas_ativas'),
                    output_field=IntegerField()
                )
            )
            .filter(saldo__lte=minimo)
            .order_by('category', 'name')
        )

        context['produtos'] = produtos
        context['total'] = produtos.count()
        context['minimo'] = minimo
        return context


# ==================== VIEWS DE MATÉRIA PRIMA ====================

class RawMaterialListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = RawMaterial
    permission_required = 'products.view_product'
    template_name = 'raw_materials/rawmaterial_list.html'
    context_object_name = 'materials'
    paginate_by = 20
    login_url = reverse_lazy('accounts:login')

    def get_queryset(self):
        qs = RawMaterial.objects.all()
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total'] = RawMaterial.objects.count()
        context['search'] = self.request.GET.get('search', '')
        return context


class RawMaterialCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = RawMaterial
    form_class = RawMaterialForm
    permission_required = 'products.add_product'
    template_name = 'raw_materials/rawmaterial_form.html'
    success_url = reverse_lazy('products:rawmaterial_list')
    login_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        messages.success(self.request, f'Matéria prima "{form.instance.name}" cadastrada com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Erro ao cadastrar. Verifique os dados informados.')
        return super().form_invalid(form)


class RawMaterialUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = RawMaterial
    form_class = RawMaterialForm
    permission_required = 'products.change_product'
    template_name = 'raw_materials/rawmaterial_form.html'
    success_url = reverse_lazy('products:rawmaterial_list')
    login_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        messages.success(self.request, f'Matéria prima "{form.instance.name}" atualizada com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Erro ao atualizar. Verifique os dados informados.')
        return super().form_invalid(form)


class RawMaterialDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = RawMaterial
    permission_required = 'products.delete_product'
    success_url = reverse_lazy('products:rawmaterial_list')
    login_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        # Django 5.x: post() → form_valid() (não mais delete())
        messages.success(self.request, f'Matéria prima "{self.object.name}" removida com sucesso!')
        return super().form_valid(form)

class ProdutoListaPDFView(LoginRequiredMixin, View):
    """Gera PDF com lista de produtos (somente nomes, sem preço)."""
    login_url = reverse_lazy('accounts:login')

    def get(self, request, *args, **kwargs):
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=18,
            textColor=colors.HexColor('#ea580c'),
            spaceAfter=8,
        )
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=20,
        )
        item_style = ParagraphStyle(
            'Item',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#111827'),
            leading=16,
        )
        cat_style = ParagraphStyle(
            'Category',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#374151'),
            spaceBefore=14,
            spaceAfter=6,
        )

        from django.utils.timezone import localdate
        today = localdate().strftime('%d/%m/%Y')

        story = []
        story.append(Paragraph('Lista de Produtos', title_style))
        story.append(Paragraph(f'Emitido em: {today}', subtitle_style))

        products = Product.objects.all().order_by('category', 'name')

        # Agrupar por categoria
        current_cat = None
        for p in products:
            cat_name = p.get_category_display() if p.category else 'Sem Categoria'
            if cat_name != current_cat:
                current_cat = cat_name
                story.append(Paragraph(cat_name, cat_style))
            story.append(Paragraph(f'• {p.name}', item_style))

        if not products.exists():
            story.append(Paragraph('Nenhum produto encontrado.', item_style))

        doc.build(story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="lista_produtos.pdf"'
        return response


class ProdutoNFCeCSVView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Exporta CSV com dados fiscais NFC-e de todos os produtos ativos."""
    login_url = reverse_lazy('accounts:login')
    permission_required = 'products.view_product'

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse
        from django.utils import timezone

        produtos = Product.objects.filter(is_active=True).order_by('category', 'name')

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        # Cabeçalho
        writer.writerow([
            'Produto',
            'Categoria',
            'Preço de Venda',
            'NCM',
            'CFOP',
            'CST ICMS',
            '% Base Cálculo ICMS',
            'Alíq ICMS (%)',
            'Código CBENEF',
            'CST PIS e COFINS',
            'Alíq PIS (%)',
            'Alíq COFINS (%)',
            'CST IBS CBS',
            'CCLASS',
            'Dados Adicionais NF-e',
        ])

        for p in produtos:
            writer.writerow([
                p.name,
                p.get_category_display(),
                str(p.price).replace('.', ','),
                p.ncm,
                p.cfop,
                p.cst_icms,
                str(p.base_calculo_icms).replace('.', ','),
                str(p.aliq_icms).replace('.', ','),
                p.codigo_cbenef,
                p.cst_pis_cofins,
                str(p.aliq_pis).replace('.', ','),
                str(p.aliq_cofins).replace('.', ','),
                p.cst_ibs_cbs,
                p.cclass,
                p.dados_adicionais_nfe,
            ])

        data = output.getvalue().encode('utf-8-sig')  # BOM para Excel abrir corretamente
        response = HttpResponse(data, content_type='text/csv; charset=utf-8-sig')
        filename = f"produtos_nfce_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

# ==================== PRODUTOS ATIVOS (Controle de Disponibilidade) ====================

class ProdutosAtivosView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Vista para listar todos os produtos com seus opcionais obrigatórios.
    Permite ativar/desativar produtos e opcionais via checkbox.
    Requer permissão: products.change_product
    """
    template_name = 'products/produtos_ativos.html'
    permission_required = 'products.change_product'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Apenas produtos ativos no sistema (inativo no sistema = não aparece aqui)
        products = Product.objects.filter(is_active=True).select_related('created_by').prefetch_related(
            'opcionais_obrigatorios'
        ).order_by('category', 'name')
        
        # Formata dados para o template
        produtos_com_opcionais = []
        for product in products:
            produtos_com_opcionais.append({
                'product': product,
                'opcionais': product.opcionais_obrigatorios.all().order_by('name'),
                'tem_opcionais_inativos': product.opcionais_obrigatorios.filter(is_active=False).exists(),
            })
        
        context['produtos_com_opcionais'] = produtos_com_opcionais
        return context

    def post(self, request, *args, **kwargs):
        """Processa ativação/desativação de produtos e opcionais via POST."""
        import json
        
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'toggle_product':
                product_id = data.get('product_id')
                product = get_object_or_404(Product, id=product_id)
                product.visivel_kiosk = not product.visivel_kiosk
                product.updated_by = request.user
                product.save()
                return JsonResponse({
                    'status': 'success',
                    'message': f'Produto {product.name} foi {"ativado" if product.visivel_kiosk else "desativado"} no Kiosk',
                    'is_active': product.visivel_kiosk,
                })
            
            elif action == 'toggle_opcional':
                opcional_id = data.get('opcional_id')
                opcional = get_object_or_404(OpcionalObrigatorio, id=opcional_id)
                opcional.is_active = not opcional.is_active
                opcional.updated_by = request.user
                opcional.save()
                return JsonResponse({
                    'status': 'success',
                    'message': f'Opcional {opcional.name} foi {"ativado" if opcional.is_active else "desativado"}',
                    'is_active': opcional.is_active,
                })
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


from django.http import JsonResponse

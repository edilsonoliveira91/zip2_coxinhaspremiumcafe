from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('products-list/', views.ProductListView.as_view(), name='product_list'),
    path('adicionais/', views.AdicionalListView.as_view(), name='adicional_list'),
    path('adicionais/create/', views.AdicionalCreateView.as_view(), name='adicional_create'),
    path('adicionais/<int:pk>/update/', views.AdicionalUpdateView.as_view(), name='adicional_update'),
    path('adicionais/<int:pk>/delete/', views.AdicionalDeleteView.as_view(), name='adicional_delete'),
    path('product/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('product/<int:pk>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('product/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),

    # Adicionais por produto (inline no cadastro)
    path('product/<int:product_pk>/adicionais/', views.ProdutoAdicionaisView.as_view(), name='produto_adicionais'),
    path('product/<int:product_pk>/adicionais/<int:adicional_pk>/delete/', views.ProdutoAdicionalDeleteView.as_view(), name='produto_adicional_delete'),
    path('product/<int:product_pk>/opcionais-obrigatorios/', views.ProdutoOpcionaisObrigatoriosView.as_view(), name='produto_opcionais_obrigatorios'),
    path('product/<int:product_pk>/opcionais-obrigatorios/<int:opcional_pk>/delete/', views.ProdutoOpcionalObrigatorioDeleteView.as_view(), name='produto_opcional_obrigatorio_delete'),
    path('product/<int:product_pk>/opcionais-obrigatorios/<int:opcional_pk>/update/', views.ProdutoOpcionalObrigatorioUpdateView.as_view(), name='produto_opcional_obrigatorio_update'),

     # Estoque
    path('estoque/', views.StockListView.as_view(), name='stock_list'),
    path('estoque/entrada/', views.StockEntryCreateView.as_view(), name='stock_create'),
    path('estoque/opcionais/<int:product_id>/', views.StockOpcionaisByProductView.as_view(), name='stock_opcionais_by_product'),
    path('estoque/<int:pk>/remover/', views.StockEntryDeleteView.as_view(), name='stock_delete'),
    path('estoque/sem-estoque/', views.NoStockListView.as_view(), name='nostock_list'),

    # Matéria Prima
    path('materia-prima/', views.RawMaterialListView.as_view(), name='rawmaterial_list'),
    path('materia-prima/nova/', views.RawMaterialCreateView.as_view(), name='rawmaterial_create'),
    path('materia-prima/<int:pk>/editar/', views.RawMaterialUpdateView.as_view(), name='rawmaterial_update'),
    path('materia-prima/<int:pk>/excluir/', views.RawMaterialDeleteView.as_view(), name='rawmaterial_delete'),

    # Receita / Ingredientes do produto
    path('product/<int:product_pk>/ingredientes/', views.ProductIngredientListView.as_view(), name='product_ingredients'),
    path('product/<int:product_pk>/ingredientes/<int:ingredient_pk>/delete/', views.ProductIngredientDeleteView.as_view(), name='product_ingredient_delete'),
    path('raw-materials/search/', views.RawMaterialSearchView.as_view(), name='rawmaterial_search'),

    # PDF
    path('lista-produtos.pdf', views.ProdutoListaPDFView.as_view(), name='produto_lista_pdf'),

    # CSV NFC-e
    path('exportar-nfce.csv', views.ProdutoNFCeCSVView.as_view(), name='produto_nfce_csv'),
    path('produtos-ativos/', views.ProdutosAtivosView.as_view(), name='produtos_ativos'),
]

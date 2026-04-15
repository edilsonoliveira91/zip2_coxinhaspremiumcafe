from django.contrib import admin
from .models import Comanda, Pedido, PedidoItem

admin.site.register(Comanda)
admin.site.register(Pedido)
admin.site.register(PedidoItem)

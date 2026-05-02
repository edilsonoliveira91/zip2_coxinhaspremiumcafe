from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender='orders.Pedido')
def criar_saida_estoque_ao_entregar(sender, instance, **kwargs):
    """
    Quando um Pedido muda de status para 'entregue', cria registros de
    StockExit para cada item do pedido que tem controle de estoque.
    Evita duplicar saídas verificando se o pedido já estava 'entregue' antes.
    """
    from products.models import StockExit, StockEntry

    if instance.pk is None:
        return  # pedido novo, sem itens ainda

    try:
        anterior = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if anterior.status == instance.status:
        return  # sem mudança de status

    if instance.status != 'entregue':
        return  # só interessa quando vira entregue

    # Cria StockExit para cada item que tem controle de estoque
    for item in instance.items.select_related('product').all():
        tem_estoque = StockEntry.objects.filter(product=item.product).exists()
        if tem_estoque:
            StockExit.objects.create(
                product=item.product,
                quantity=item.quantity,
                pedido=instance,
            )

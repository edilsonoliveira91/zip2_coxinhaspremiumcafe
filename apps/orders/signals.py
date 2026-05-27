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
    for item in instance.items.select_related('product', 'opcional_obrigatorio').all():
        estoque_qs = StockEntry.objects.filter(product=item.product)
        if item.opcional_obrigatorio_id:
            estoque_qs = estoque_qs.filter(opcional_obrigatorio_id=item.opcional_obrigatorio_id)
        tem_estoque = estoque_qs.exists()
        if tem_estoque:
            StockExit.objects.create(
                product=item.product,
                opcional_obrigatorio=item.opcional_obrigatorio,
                quantity=item.quantity,
                pedido=instance,
            )

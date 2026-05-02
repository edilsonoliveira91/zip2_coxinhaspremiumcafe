from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='checkouts.Checkout')
def abrir_sessao_caixa(sender, instance, created, **kwargs):
    """
    Quando um Checkout é aprovado, garante que o usuário operador
    (is_caixa=True) tenha uma SessaoCaixa aberta.
    A sessão é criada no primeiro recebimento após o último fechamento.
    """
    if instance.status != 'aprovado':
        return
    if not instance.processed_by:
        return
    if not getattr(instance.processed_by, 'is_caixa', False):
        return

    from checkouts.models import SessaoCaixa

    sessao_aberta = SessaoCaixa.objects.filter(
        usuario=instance.processed_by,
        status='aberta',
    ).first()

    if not sessao_aberta:
        SessaoCaixa.objects.create(usuario=instance.processed_by)

def bank_access(request):
    """
    Adiciona `user_has_bank_access` ao contexto global.
    True quando o usuário tem permissão global view_bank OU acesso
    a pelo menos um banco via UserBankAccess.can_view.
    """
    if not request.user.is_authenticated:
        return {'user_has_bank_access': False}

    if request.user.is_superuser or request.user.has_perm('banks.view_bank'):
        return {'user_has_bank_access': True}

    from .models import UserBankAccess
    has_access = UserBankAccess.objects.filter(
        user=request.user,
        can_view=True,
    ).exists()

    return {'user_has_bank_access': has_access}

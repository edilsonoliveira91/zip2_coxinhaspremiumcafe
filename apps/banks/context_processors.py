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

    # Usa a relação inversa do User — não importa o modelo diretamente,
    # evitando problemas de AppRegistry durante a inicialização do Django.
    try:
        has_access = request.user.bank_accesses.filter(can_view=True).exists()
    except Exception:
        has_access = False

    return {'user_has_bank_access': has_access}

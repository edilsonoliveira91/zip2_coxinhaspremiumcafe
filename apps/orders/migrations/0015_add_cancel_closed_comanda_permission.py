# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_pedido_impresso'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='comanda',
            options={
                'ordering': ['-created_at'],
                'permissions': [
                    ('view_order', 'Pode visualizar comandas'),
                    ('add_order', 'Pode criar comandas'),
                    ('change_order', 'Pode editar comandas'),
                    ('delete_order', 'Pode excluir comandas'),
                    ('cancel_closed_comanda', 'Pode cancelar comanda finalizada'),
                ],
                'verbose_name': 'Comanda',
                'verbose_name_plural': 'Comandas',
            },
        ),
    ]

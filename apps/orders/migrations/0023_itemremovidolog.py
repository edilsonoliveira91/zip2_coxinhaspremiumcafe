# Generated manually on 2026-06-02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0022_pedido_atendente_numero'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemRemovidoLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=100, verbose_name='Produto')),
                ('quantity', models.PositiveIntegerField(verbose_name='Quantidade')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço Unitário')),
                ('observations', models.TextField(blank=True, null=True, verbose_name='Observações')),
                ('comanda_numero', models.CharField(max_length=50, verbose_name='Comanda')),
                ('pedido_seq', models.PositiveIntegerField(verbose_name='Nº Pedido')),
                ('removido_em', models.DateTimeField(auto_now_add=True, verbose_name='Removido em')),
                ('removido_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='itens_removidos',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Removido por',
                )),
            ],
            options={
                'verbose_name': 'Item Removido',
                'verbose_name_plural': 'Itens Removidos',
                'ordering': ['-removido_em'],
            },
        ),
    ]

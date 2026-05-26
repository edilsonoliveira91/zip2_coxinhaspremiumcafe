from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_pedidoitem_product_protect_and_name_snapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ComandaPartialPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('payment_method', models.CharField(choices=[('dinheiro', 'Dinheiro'), ('cartao_debito', 'Cartão de Débito'), ('cartao_credito', 'Cartão de Crédito'), ('pix', 'PIX'), ('voucher', 'Voucher')], max_length=20, verbose_name='Forma de Pagamento')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Pago')),
                ('notes', models.CharField(blank=True, default='', max_length=255, verbose_name='Observações')),
                ('comanda', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partial_payments', to='orders.comanda', verbose_name='Comanda')),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_partial_payments', to=settings.AUTH_USER_MODEL, verbose_name='Registrado por')),
            ],
            options={
                'verbose_name': 'Pagamento Parcial de Comanda',
                'verbose_name_plural': 'Pagamentos Parciais de Comanda',
                'ordering': ['created_at'],
            },
        ),
    ]

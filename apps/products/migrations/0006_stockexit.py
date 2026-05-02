from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_stockentry'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockExit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='Quantidade')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pedido', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='stock_exits',
                    to='orders.pedido',
                    verbose_name='Pedido',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_exits',
                    to='products.product',
                    verbose_name='Produto',
                )),
            ],
            options={
                'verbose_name': 'Saída de Estoque',
                'verbose_name_plural': 'Saídas de Estoque',
                'ordering': ['-created_at'],
            },
        ),
    ]

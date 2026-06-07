from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('banks', '0001_initial_bank'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('deposito', 'Depósito'), ('pagamento', 'Pagamento'), ('transferencia', 'Transferência')], max_length=20)),
                ('descricao', models.CharField(max_length=200, verbose_name='Descrição')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Valor')),
                ('is_entrada', models.BooleanField(default=True, verbose_name='É entrada')),
                ('data', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Data')),
                ('observacao', models.TextField(blank=True, verbose_name='Observação')),
                ('bank', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='banks.bank')),
                ('banco_destino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions_recebidas', to='banks.bank', verbose_name='Banco Destino')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bank_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Transação',
                'verbose_name_plural': 'Transações',
                'ordering': ['-data', '-id'],
            },
        ),
    ]

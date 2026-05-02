# Generated manually

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checkouts', '0003_checkout_comanda'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SessaoCaixa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aberta_em', models.DateTimeField(auto_now_add=True, verbose_name='Aberta em')),
                ('fechada_em', models.DateTimeField(blank=True, null=True, verbose_name='Fechada em')),
                ('status', models.CharField(choices=[('aberta', 'Aberta'), ('fechada', 'Fechada')], default='aberta', max_length=10, verbose_name='Status')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessoes_caixa', to=settings.AUTH_USER_MODEL, verbose_name='Operador')),
            ],
            options={
                'verbose_name': 'Sessão de Caixa',
                'verbose_name_plural': 'Sessões de Caixa',
                'ordering': ['-aberta_em'],
            },
        ),
    ]

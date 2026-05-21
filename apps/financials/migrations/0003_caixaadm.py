from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0002_fechamento_caixa_diario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CaixaAdm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enviado_em', models.DateTimeField(auto_now_add=True, verbose_name='Enviado em')),
                ('fechamento', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='malote',
                    to='financials.fechamentocaixadiario',
                    verbose_name='Fechamento',
                )),
                ('enviado_por', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='malotes_enviados',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Enviado por',
                )),
            ],
            options={
                'verbose_name': 'Caixa ADM',
                'verbose_name_plural': 'Caixas ADM',
                'ordering': ['-enviado_em'],
            },
        ),
    ]

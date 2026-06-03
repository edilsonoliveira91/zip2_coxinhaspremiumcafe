# Generated manually on 2026-06-02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0008_alter_configcomissao_created_at_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Garcom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveSmallIntegerField(unique=True, verbose_name='Número do Garçom')),
                ('nome', models.CharField(max_length=100, verbose_name='Nome')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Cadastrado em')),
                ('criado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='garcons_cadastrados',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Cadastrado por',
                )),
            ],
            options={
                'verbose_name': 'Garçom',
                'verbose_name_plural': 'Garçons',
                'ordering': ['numero'],
            },
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0006_alter_systemconfig_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Adicionar campos TimeStampedModel a ConfigTempoEspera
        migrations.AddField(
            model_name='configtempoespera',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Criado em'),
        ),
        migrations.AddField(
            model_name='configtempoespera',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
        ),
        migrations.AddField(
            model_name='configtempoespera',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configtempoespera_created', to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
        migrations.AddField(
            model_name='configtempoespera',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configtempoespera_updated', to=settings.AUTH_USER_MODEL, verbose_name='Atualizado por'),
        ),
        migrations.AddField(
            model_name='configtempoespera',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
        
        # Adicionar campos TimeStampedModel a ConfigTrocoInicial
        migrations.AddField(
            model_name='configtrocoinicial',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Criado em'),
        ),
        migrations.AddField(
            model_name='configtrocoinicial',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
        ),
        migrations.AddField(
            model_name='configtrocoinicial',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configtrocoinicial_created', to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
        migrations.AddField(
            model_name='configtrocoinicial',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configtrocoinicial_updated', to=settings.AUTH_USER_MODEL, verbose_name='Atualizado por'),
        ),
        migrations.AddField(
            model_name='configtrocoinicial',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
        
        # Adicionar campos TimeStampedModel a ConfigQuebraCaixa
        migrations.AddField(
            model_name='configquebracaixa',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Criado em'),
        ),
        migrations.AddField(
            model_name='configquebracaixa',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
        ),
        migrations.AddField(
            model_name='configquebracaixa',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configquebracaixa_created', to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
        migrations.AddField(
            model_name='configquebracaixa',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configquebracaixa_updated', to=settings.AUTH_USER_MODEL, verbose_name='Atualizado por'),
        ),
        migrations.AddField(
            model_name='configquebracaixa',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
        
        # Adicionar campos TimeStampedModel a ConfigComissao
        migrations.AddField(
            model_name='configcomissao',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Criado em'),
        ),
        migrations.AddField(
            model_name='configcomissao',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
        ),
        migrations.AddField(
            model_name='configcomissao',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configcomissao_created', to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
        migrations.AddField(
            model_name='configcomissao',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configcomissao_updated', to=settings.AUTH_USER_MODEL, verbose_name='Atualizado por'),
        ),
        migrations.AddField(
            model_name='configcomissao',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
    ]

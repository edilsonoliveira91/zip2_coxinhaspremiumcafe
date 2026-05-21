from django.db import migrations, models
from decimal import Decimal


def migrar_dados(apps, schema_editor):
    SystemConfig = apps.get_model("config", "SystemConfig")
    ConfigTempoEspera = apps.get_model("config", "ConfigTempoEspera")
    ConfigTrocoInicial = apps.get_model("config", "ConfigTrocoInicial")
    ConfigQuebraCaixa = apps.get_model("config", "ConfigQuebraCaixa")
    ConfigComissao = apps.get_model("config", "ConfigComissao")

    try:
        src = SystemConfig.objects.get(pk=1)
        ConfigTempoEspera.objects.update_or_create(pk=1, defaults={"max_order_time_minutes": src.max_order_time_minutes})
        ConfigTrocoInicial.objects.update_or_create(pk=1, defaults={"troco_inicial": src.troco_inicial})
        ConfigQuebraCaixa.objects.update_or_create(pk=1, defaults={"quebra_positiva": src.quebra_positiva, "quebra_negativa": src.quebra_negativa})
        ConfigComissao.objects.update_or_create(pk=1, defaults={"comissao_percentual": src.comissao_percentual})
    except SystemConfig.DoesNotExist:
        pass  # banco vazio, os defaults das models já cuidam disso


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0004_comissao_percentual"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigTempoEspera",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("max_order_time_minutes", models.PositiveIntegerField(default=20, verbose_name="Tempo Máximo de Espera (minutos)")),
            ],
            options={"verbose_name": "Tempo de Espera", "verbose_name_plural": "Tempo de Espera"},
        ),
        migrations.CreateModel(
            name="ConfigTrocoInicial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("troco_inicial", models.DecimalField(decimal_places=2, default=Decimal("50.00"), max_digits=8, verbose_name="Troco Inicial (R$)")),
            ],
            options={"verbose_name": "Troco Inicial", "verbose_name_plural": "Troco Inicial"},
        ),
        migrations.CreateModel(
            name="ConfigQuebraCaixa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quebra_positiva", models.DecimalField(decimal_places=2, default=Decimal("5.00"), max_digits=8, verbose_name="Quebra de Caixa Positiva (R$)")),
                ("quebra_negativa", models.DecimalField(decimal_places=2, default=Decimal("5.00"), max_digits=8, verbose_name="Quebra de Caixa Negativa (R$)")),
            ],
            options={"verbose_name": "Quebra de Caixa", "verbose_name_plural": "Quebra de Caixa"},
        ),
        migrations.CreateModel(
            name="ConfigComissao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("comissao_percentual", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5, verbose_name="Comissão sobre Vendas (%)")),
            ],
            options={"verbose_name": "Comissão", "verbose_name_plural": "Comissão"},
        ),
        migrations.RunPython(migrar_dados, migrations.RunPython.noop),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0010_add_metodo_bandeira_datacaixa_transferencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='data_prevista_liquidacao',
            field=models.DateField(blank=True, null=True, verbose_name='Data prevista de liquidação'),
        ),
    ]

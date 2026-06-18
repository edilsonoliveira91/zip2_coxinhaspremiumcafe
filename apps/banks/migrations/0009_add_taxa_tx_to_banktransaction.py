from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banks', '0008_add_banktransaction_anexo'),
    ]

    operations = [
        migrations.AddField(
            model_name='banktransaction',
            name='taxa_tx',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                verbose_name='Taxa aplicada (R$)',
            ),
        ),
    ]

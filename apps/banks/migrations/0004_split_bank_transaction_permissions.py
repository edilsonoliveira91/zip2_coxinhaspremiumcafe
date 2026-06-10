from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banks', '0003_add_userbankaccess'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbankaccess',
            name='can_pay_transaction',
            field=models.BooleanField(default=False, verbose_name='Registrar pagamento'),
        ),
        migrations.AddField(
            model_name='userbankaccess',
            name='can_transfer_transaction',
            field=models.BooleanField(default=False, verbose_name='Transferir'),
        ),
    ]

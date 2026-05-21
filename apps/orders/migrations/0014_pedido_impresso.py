from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_alter_comanda_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='impresso',
            field=models.BooleanField(default=False, verbose_name='Impresso'),
        ),
    ]

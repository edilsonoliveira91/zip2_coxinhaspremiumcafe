from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_alter_aliq_pis_cofins_decimal'),
    ]

    operations = [
        migrations.AddField(
            model_name='adicional',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='adicionais',
                to='products.product',
                verbose_name='Produto',
            ),
        ),
    ]

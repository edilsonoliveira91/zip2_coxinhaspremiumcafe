from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0015_add_manage_product_availability_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='visivel_kiosk',
            field=models.BooleanField(default=True, verbose_name='Visível no Kiosk'),
        ),
    ]

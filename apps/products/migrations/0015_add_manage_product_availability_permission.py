from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_opcionalobrigatorio'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={
                'ordering': ['category', 'name'], 
                'permissions': [('manage_product_availability', 'Pode gerenciar disponibilidade de produtos e opcionais')],
                'verbose_name': 'Produto', 
                'verbose_name_plural': 'Produtos'
            },
        ),
    ]

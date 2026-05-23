from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_add_manage_nfce_fields_permission'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={
                'ordering': ['category', 'name'],
                'permissions': [
                    ('manage_nfce_fields', 'Pode editar campos NFC-e do produto'),
                ],
                'verbose_name': 'Produto',
                'verbose_name_plural': 'Produtos',
            },
        ),
    ]

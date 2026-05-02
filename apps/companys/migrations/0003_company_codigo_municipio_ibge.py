from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companys', '0002_alter_certificadodigital_valido_ate'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='codigo_municipio_ibge',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Código IBGE de 7 dígitos do município (ex: 3523800 para Itapetininga/SP)',
                max_length=7,
                verbose_name='Código IBGE do Município',
            ),
        ),
    ]

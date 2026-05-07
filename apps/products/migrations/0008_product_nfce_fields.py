# Generated manually

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_rawmaterial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='ncm',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='NCM'),
        ),
        migrations.AddField(
            model_name='product',
            name='cfop',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='CFOP'),
        ),
        migrations.AddField(
            model_name='product',
            name='cst_icms',
            field=models.CharField(blank=True, default='', max_length=5, verbose_name='CST ICMS'),
        ),
        migrations.AddField(
            model_name='product',
            name='base_calculo_icms',
            field=models.DecimalField(decimal_places=2, default=Decimal('100.00'), max_digits=5, verbose_name='% Base de Cálculo ICMS'),
        ),
        migrations.AddField(
            model_name='product',
            name='aliq_icms',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='Alíquota ICMS (%)'),
        ),
        migrations.AddField(
            model_name='product',
            name='codigo_cbenef',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Código CBENEF'),
        ),
        migrations.AddField(
            model_name='product',
            name='dados_adicionais_nfe',
            field=models.TextField(blank=True, default='', verbose_name='Dados Adicionais da NF-e'),
        ),
        migrations.AddField(
            model_name='product',
            name='cst_pis_cofins',
            field=models.CharField(blank=True, default='', max_length=5, verbose_name='CST PIS e COFINS'),
        ),
        migrations.AddField(
            model_name='product',
            name='aliq_cofins',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='Alíquota COFINS (%)'),
        ),
        migrations.AddField(
            model_name='product',
            name='cst_ibs_cbs',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='CST IBS CBS'),
        ),
        migrations.AddField(
            model_name='product',
            name='cclass',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='CCLASS'),
        ),
    ]

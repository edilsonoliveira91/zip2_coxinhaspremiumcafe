# Generated manually on 2026-05-04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_remove_comanda_numero_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comanda',
            name='status',
            field=models.CharField(choices=[('livre', 'Livre'), ('em_uso', 'Em Uso'), ('fechada', 'Fechada'), ('cancelada', 'Cancelada'), ('cortesia', 'Cortesia')], default='livre', max_length=20, verbose_name='Status'),
        ),
    ]

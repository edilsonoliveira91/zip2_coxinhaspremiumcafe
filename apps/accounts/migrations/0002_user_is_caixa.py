# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_caixa',
            field=models.BooleanField(default=False, help_text='Permite que este usuário opere o caixa e acesse o fechamento de caixa.', verbose_name='Operador de Caixa'),
        ),
    ]

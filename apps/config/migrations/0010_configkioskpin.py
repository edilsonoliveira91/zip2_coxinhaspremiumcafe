# Generated manually on 2026-06-05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0009_garcom'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigKioskPin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('pin', models.CharField(default='0000', help_text='PIN de 4 dígitos que o funcionário deve digitar para abrir uma mesa no kiosk.', max_length=4, verbose_name='PIN do Kiosk')),
            ],
            options={
                'verbose_name': 'PIN do Kiosk',
                'verbose_name_plural': 'PIN do Kiosk',
            },
        ),
    ]

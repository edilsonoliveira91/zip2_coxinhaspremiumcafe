from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_is_caixa'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='dashboard_home',
            field=models.CharField(
                choices=[
                    ('home', 'Dashboard Principal (Comandas)'),
                    ('ceo', 'Dashboard CEO'),
                    ('manage', 'Dashboard Gerencial'),
                ],
                default='home',
                help_text='Tela para a qual o usuário será redirecionado após o login.',
                max_length=20,
                verbose_name='Tela inicial',
            ),
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0017_comandapartialpayment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='comandapartialpayment',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comandapartialpayment_created',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Criado por',
            ),
        ),
        migrations.AddField(
            model_name='comandapartialpayment',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comandapartialpayment_updated',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Atualizado por',
            ),
        ),
        migrations.AddField(
            model_name='comandapartialpayment',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
    ]

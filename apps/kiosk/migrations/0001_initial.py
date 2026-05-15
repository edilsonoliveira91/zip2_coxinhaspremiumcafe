from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='KioskSlide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='kiosk/slides/', verbose_name='Imagem')),
                ('title', models.CharField(blank=True, max_length=120, verbose_name='Título (opcional)')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Slide do Kiosk',
                'verbose_name_plural': 'Slides do Kiosk',
                'ordering': ['order', 'id'],
            },
        ),
    ]

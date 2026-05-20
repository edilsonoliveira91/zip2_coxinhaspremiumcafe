from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='Iniciado em')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Finalizado em')),
                ('duration_seconds', models.FloatField(blank=True, null=True, verbose_name='Duração (s)')),
                ('direction', models.CharField(
                    choices=[
                        ('railway_to_local', 'Railway → Local'),
                        ('local_to_railway', 'Local → Railway'),
                        ('bilateral', 'Bilateral'),
                    ],
                    default='railway_to_local',
                    max_length=20,
                    verbose_name='Direção',
                )),
                ('status', models.CharField(
                    choices=[
                        ('running', 'Em andamento'),
                        ('success', 'Sucesso'),
                        ('partial', 'Parcial'),
                        ('error', 'Erro'),
                    ],
                    default='running',
                    max_length=10,
                    verbose_name='Status',
                )),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Mensagem de Erro')),
                ('records_downloaded', models.IntegerField(default=0, verbose_name='Registros baixados')),
                ('records_uploaded', models.IntegerField(default=0, verbose_name='Registros enviados')),
                ('records_created', models.IntegerField(default=0, verbose_name='Registros criados')),
                ('records_updated', models.IntegerField(default=0, verbose_name='Registros atualizados')),
                ('records_deleted', models.IntegerField(default=0, verbose_name='Registros desativados')),
                ('images_downloaded', models.IntegerField(default=0, verbose_name='Imagens baixadas')),
                ('tables_synced', models.TextField(blank=True, null=True, verbose_name='Tabelas sincronizadas')),
                ('sync_from_datetime', models.DateTimeField(blank=True, null=True, verbose_name='Filtro a partir de')),
                ('triggered_by', models.CharField(
                    choices=[
                        ('automatic', 'Automático'),
                        ('manual', 'Manual'),
                    ],
                    default='automatic',
                    max_length=10,
                    verbose_name='Disparado por',
                )),
                ('local_server_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP do servidor local')),
            ],
            options={
                'verbose_name': 'Log de Sync',
                'verbose_name_plural': 'Logs de Sync',
                'ordering': ['-started_at'],
            },
        ),
    ]

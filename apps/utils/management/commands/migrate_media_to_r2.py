import boto3
from pathlib import Path
from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Migra todos os arquivos de media do volume local para o Cloudflare R2'

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write(self.style.ERROR(f'MEDIA_ROOT nao encontrada: {media_root}'))
            return

        if not getattr(settings, 'AWS_S3_ENDPOINT_URL', None):
            self.stdout.write(self.style.ERROR('R2 nao configurado (AWS_S3_ENDPOINT_URL ausente)'))
            return

        s3 = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto',
        )
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        uploaded = 0
        skipped = 0
        errors = 0

        files = [f for f in media_root.rglob('*') if f.is_file()]
        self.stdout.write(f'Encontrados {len(files)} arquivos em {media_root}')

        for filepath in files:
            relative = filepath.relative_to(media_root)
            key = str(relative).replace('\\', '/')

            try:
                s3.head_object(Bucket=bucket, Key=key)
                skipped += 1
                self.stdout.write(f'  SKIP (ja existe): {key}')
                continue
            except ClientError as e:
                if e.response['Error']['Code'] != '404':
                    self.stdout.write(self.style.ERROR(f'  ERRO ao verificar {key}: {e}'))
                    errors += 1
                    continue

            try:
                s3.upload_file(str(filepath), bucket, key)
                uploaded += 1
                self.stdout.write(self.style.SUCCESS(f'  OK: {key}'))
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  ERRO ao enviar {key}: {e}'))

        self.stdout.write(f'\nConcluido: {uploaded} enviados, {skipped} ja existiam, {errors} erros')

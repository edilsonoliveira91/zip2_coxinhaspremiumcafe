from django.conf import settings
from django.core.files.storage import FileSystemStorage


local_media_storage = FileSystemStorage()


if settings.USE_R2_STORAGE:
    from storages.backends.s3boto3 import S3Boto3Storage

    class R2ImageStorage(S3Boto3Storage):
        file_overwrite = False
        default_acl = None


    image_media_storage = R2ImageStorage()
else:
    image_media_storage = local_media_storage

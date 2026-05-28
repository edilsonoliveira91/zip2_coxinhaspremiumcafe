from django.core.management.base import BaseCommand

from kiosk.models import KioskSlide
from products.models import Combo, Product
from utils.image_optimizer import compress_image_field


class Command(BaseCommand):
    help = "Compress image files for Product, Combo and KioskSlide models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit of records to process per model.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")
        total_processed = 0
        total_compressed = 0

        model_configs = [
            (Product, "image"),
            (Combo, "image"),
            (KioskSlide, "image"),
        ]

        for model, image_attr in model_configs:
            queryset = model.objects.exclude(**{f"{image_attr}": ""}).exclude(**{f"{image_attr}__isnull": True})
            if limit:
                queryset = queryset[:limit]

            processed = 0
            compressed = 0

            for obj in queryset.iterator():
                processed += 1
                image_field = getattr(obj, image_attr, None)
                if compress_image_field(image_field):
                    compressed += 1

            total_processed += processed
            total_compressed += compressed

            self.stdout.write(
                self.style.SUCCESS(
                    f"{model.__name__}: processed={processed}, compressed={compressed}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total processed={total_processed}, compressed={total_compressed}"
            )
        )

from django.apps import AppConfig


class CheckoutsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'checkouts'

    def ready(self):
        import checkouts.signals  # noqa: F401

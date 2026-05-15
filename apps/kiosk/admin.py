from django.contrib import admin
from .models import KioskSlide


@admin.register(KioskSlide)
class KioskSlideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    ordering = ('order', 'id')

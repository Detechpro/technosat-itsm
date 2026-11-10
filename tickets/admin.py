from django.contrib import admin

from .models import SlaPolicy


@admin.register(SlaPolicy)
class SlaPolicyAdmin(admin.ModelAdmin):
    list_display = ("priority", "response_minutes", "resolution_minutes")

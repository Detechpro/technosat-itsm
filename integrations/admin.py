from django.contrib import admin

from .models import InboundEvent, WebhookDelivery, WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    """Where n8n receives portal events. The signing secret is read from the environment, never stored here."""
    list_display = ("name", "url", "event_types", "secret_env", "enabled")
    list_filter = ("enabled",)
    fields = ("name", "url", "event_types", "secret_env", "enabled")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "endpoint", "event_type", "status", "attempts", "response_code")
    list_filter = ("status", "event_type")
    readonly_fields = [f.name for f in WebhookDelivery._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(InboundEvent)
class InboundEventAdmin(admin.ModelAdmin):
    list_display = ("received_at", "action", "event_id", "result")
    readonly_fields = [f.name for f in InboundEvent._meta.fields]

    def has_add_permission(self, request):
        return False

from rest_framework import serializers

from .models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    requester = serializers.CharField(source="requester.username", read_only=True)
    assignee = serializers.CharField(source="assignee.username", read_only=True, default=None)
    department = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = Ticket
        fields = ["number", "title", "description", "category", "priority", "status", "requester",
                  "assignee", "department", "due_date", "resolved_at", "closed_at", "created_at", "updated_at"]
        read_only_fields = fields

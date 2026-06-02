from django.conf import settings
from rest_framework.permissions import BasePermission


class ApiKeyPermission(BasePermission):
    def has_permission(self, request, view):
        api_key = request.headers.get("X-API-Key")
        return bool(api_key and api_key == settings.API_KEY)

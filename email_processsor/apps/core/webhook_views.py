# import json
# import logging
# import os

# from django.http import HttpResponse
# from django.utils.decorators import method_decorator
# from django.views import View
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework import status
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from .outlook_service import OutlookService, get_access_token
# from .permissions import ApiKeyPermission
# from .tasks import process_single_email_by_id

# logger = logging.getLogger(__name__)


# @method_decorator(csrf_exempt, name="dispatch")
# class GraphWebhookView(View):

#     def post(self, request):
#         validation_token = request.GET.get("validationToken")
#         if validation_token:
#             return HttpResponse(validation_token, content_type="text/plain", status=200)

#         try:
#             body = json.loads(request.body)
#         except json.JSONDecodeError:
#             return HttpResponse(status=400)

#         webhook_secret = os.getenv("WEBHOOK_SECRET")
#         for notification in body.get("value", []):
#             if notification.get("clientState") != webhook_secret:
#                 logger.warning("Graph webhook: invalid clientState, ignoring")
#                 continue
#             message_id = notification.get("resourceData", {}).get("id")
#             if message_id:
#                 process_single_email_by_id.delay(message_id)

#         return HttpResponse(status=202)


# class GraphSubscribeView(APIView):
#     permission_classes = [ApiKeyPermission]

#     def post(self, request):
#         webhook_url = os.getenv("WEBHOOK_URL")
#         webhook_secret = os.getenv("WEBHOOK_SECRET")
#         if not webhook_url or not webhook_secret:
#             return Response(
#                 {"error": "WEBHOOK_URL and WEBHOOK_SECRET must be set in environment"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )
#         try:
#             outlook = OutlookService(token=get_access_token())
#             data = outlook.create_subscription(webhook_url, webhook_secret)
#         except Exception as exc:
#             return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
#         return Response(
#             {"subscription_id": data["id"], "expires": data["expirationDateTime"]},
#             status=status.HTTP_201_CREATED,
#         )

import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Conversation, Message
from .providers import PROVIDERS, ProviderError, missing_credential, stream_reply


logger = logging.getLogger(__name__)
MAX_PROMPT_LENGTH = 20_000


def _provider_options():
    return [
        {
            "id": provider,
            "label": config["label"],
            "model": settings.LITCHAT_MODELS[provider],
            "key_name": config["key_name"],
            "configured": missing_credential(provider) is None,
        }
        for provider, config in PROVIDERS.items()
    ]


def _conversation_data(conversation):
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
    }


def _message_data(message):
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "provider": message.provider,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
    }


def _recover_abandoned_streams(conversation):
    conversation.messages.filter(status=Message.Status.STREAMING).update(
        status=Message.Status.INTERRUPTED
    )


def index(request):
    return render(
        request,
        "chat/index.html",
        {
            "conversations": Conversation.objects.all()[:40],
            "providers": _provider_options(),
        },
    )


@require_http_methods(["GET", "POST"])
def conversation_collection(request):
    if request.method == "GET":
        return JsonResponse(
            {"conversations": [_conversation_data(item) for item in Conversation.objects.all()[:100]]}
        )

    conversation = Conversation.objects.create()
    return JsonResponse(_conversation_data(conversation), status=201)


@require_http_methods(["GET", "DELETE"])
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.method == "DELETE":
        conversation.delete()
        return JsonResponse({"deleted": True})
    _recover_abandoned_streams(conversation)
    return JsonResponse(
        {
            **_conversation_data(conversation),
            "messages": [_message_data(message) for message in conversation.messages.all()],
        }
    )


def _event(event_type, **data):
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=True)
    return f"data: {payload}\n\n"


@require_http_methods(["GET", "POST"])
def conversation_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.method == "GET":
        _recover_abandoned_streams(conversation)
        return JsonResponse(
            {"messages": [_message_data(message) for message in conversation.messages.all()]}
        )

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Send a JSON object with your message."}, status=400)

    provider = payload.get("provider")
    content = payload.get("content")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        return JsonResponse({"error": "Choose a supported provider."}, status=400)
    if not isinstance(content, str) or not content.strip():
        return JsonResponse({"error": "Write a message before sending."}, status=400)
    content = content.strip()
    if len(content) > MAX_PROMPT_LENGTH:
        return JsonResponse({"error": "Messages must be 20,000 characters or fewer."}, status=400)

    missing_key = missing_credential(provider)
    if missing_key:
        return JsonResponse(
            {"error": f"Add {missing_key} to your local .env file, then restart LitChat."},
            status=503,
        )

    history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages.filter(status=Message.Status.COMPLETE)
        if message.content
    ]
    history.append({"role": Message.Role.USER, "content": content})

    with transaction.atomic():
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=content,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            provider=provider,
            status=Message.Status.STREAMING,
        )
        if conversation.title == "New conversation":
            conversation.title = " ".join(content.split())[:120]
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["title", "updated_at"])

    def stream_events():
        chunks = []
        try:
            for text in stream_reply(provider, history):
                chunks.append(text)
                yield _event("delta", text=text)
            assistant_message.content = "".join(chunks)
            assistant_message.status = Message.Status.COMPLETE
            assistant_message.save(update_fields=["content", "status"])
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=["updated_at"])
            yield _event("done", message_id=assistant_message.id)
        except GeneratorExit:
            assistant_message.content = "".join(chunks)
            assistant_message.status = Message.Status.INTERRUPTED
            assistant_message.save(update_fields=["content", "status"])
            raise
        except ProviderError as error:
            assistant_message.content = "".join(chunks)
            assistant_message.status = (
                Message.Status.INTERRUPTED if chunks else Message.Status.ERROR
            )
            assistant_message.save(update_fields=["content", "status"])
            logger.warning("Proxy request failed for %s: %s", provider, error)
            yield _event("error", message=str(error), partial=bool(chunks))
        except Exception as error:
            assistant_message.content = "".join(chunks)
            assistant_message.status = (
                Message.Status.INTERRUPTED if chunks else Message.Status.ERROR
            )
            assistant_message.save(update_fields=["content", "status"])
            logger.warning("Proxy stream ended unexpectedly (%s)", type(error).__name__)
            yield _event(
                "error",
                message="The response was interrupted. The request was not retried.",
                partial=bool(chunks),
            )

    response = StreamingHttpResponse(stream_events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["X-Content-Type-Options"] = "nosniff"
    return response

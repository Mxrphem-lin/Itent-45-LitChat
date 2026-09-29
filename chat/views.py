import hashlib
import json
import logging

from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import SignUpForm
from .models import Conversation, Message
from .providers import PROVIDERS, ProviderError, missing_credential, stream_reply


logger = logging.getLogger(__name__)
MAX_PROMPT_LENGTH = 20_000
User = get_user_model()
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60


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


class LitChatLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def _attempt_key(self):
        username = self.request.POST.get("username", "").strip().casefold()
        remote_addr = self.request.META.get("REMOTE_ADDR", "")
        digest = hashlib.sha256(f"{remote_addr}\0{username}".encode()).hexdigest()
        return f"litchat-login:{digest}"

    def post(self, request, *args, **kwargs):
        attempt_key = self._attempt_key()
        if cache.get(attempt_key, 0) >= LOGIN_FAILURE_LIMIT:
            form = self.get_form()
            form.add_error(None, "Too many failed sign-in attempts. Wait 15 minutes and try again.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        if self.request.POST.get("username", "").strip() and self.request.POST.get("password"):
            attempt_key = self._attempt_key()
            if not cache.add(
                attempt_key, 1, timeout=LOGIN_FAILURE_WINDOW_SECONDS
            ):
                try:
                    cache.incr(attempt_key)
                except ValueError:
                    cache.set(attempt_key, 1, timeout=LOGIN_FAILURE_WINDOW_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._attempt_key())
        return super().form_valid(form)


@never_cache
@login_required
def index(request):
    return render(
        request,
        "chat/index.html",
        {
            "conversations": Conversation.objects.filter(owner=request.user)[:40],
            "providers": _provider_options(),
        },
    )


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    setup_required = (
        not User.objects.filter(is_superuser=True).exists()
        or Conversation.objects.filter(owner__isnull=True).exists()
    )
    if setup_required:
        return render(request, "chat/account_setup_required.html", status=503)

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        django_messages.success(request, "Your account is ready. Sign in to start a conversation.")
        return redirect("login")
    return render(request, "chat/signup.html", {"form": form})


@never_cache
@require_http_methods(["GET", "POST"])
@login_required
def conversation_collection(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "conversations": [
                    _conversation_data(item)
                    for item in Conversation.objects.filter(owner=request.user)[:100]
                ]
            }
        )

    conversation = Conversation.objects.create(owner=request.user)
    return JsonResponse(_conversation_data(conversation), status=201)


@never_cache
@require_http_methods(["GET", "DELETE"])
@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation, id=conversation_id, owner=request.user
    )
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


@never_cache
@require_http_methods(["GET", "POST"])
@login_required
def conversation_messages(request, conversation_id):
    conversation = get_object_or_404(
        Conversation, id=conversation_id, owner=request.user
    )
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
            Message.objects.filter(pk=assistant_message.pk).update(
                content="".join(chunks), status=Message.Status.COMPLETE
            )
            Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
            yield _event("done", message_id=assistant_message.id)
        except GeneratorExit:
            Message.objects.filter(pk=assistant_message.pk).update(
                content="".join(chunks), status=Message.Status.INTERRUPTED
            )
            raise
        except ProviderError as error:
            Message.objects.filter(pk=assistant_message.pk).update(
                content="".join(chunks),
                status=Message.Status.INTERRUPTED if chunks else Message.Status.ERROR,
            )
            logger.warning("Proxy request failed for %s: %s", provider, error)
            yield _event("error", message=str(error), partial=bool(chunks))
        except Exception as error:
            Message.objects.filter(pk=assistant_message.pk).update(
                content="".join(chunks),
                status=Message.Status.INTERRUPTED if chunks else Message.Status.ERROR,
            )
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

import json
import os
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Conversation, Message
from .providers import ProviderError, stream_reply

User = get_user_model()


class ProviderAdapterTests(TestCase):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Continue"},
    ]

    def make_client_factory(self, handler):
        transport = httpx.MockTransport(handler)

        def factory(timeout):
            return httpx.Client(transport=transport, timeout=timeout)

        return factory

    def test_openai_chat_completions_request_and_stream(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = request.headers
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                text=(
                    'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
                    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                    'data: [DONE]\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )

        with patch.dict(os.environ, {"BUILD_OPENAI_KEY": "test-openai-key"}):
            chunks = list(
                stream_reply(
                    "openai", self.messages, self.make_client_factory(handler)
                )
            )

        self.assertEqual(chunks, ["Hello"])
        self.assertTrue(seen["url"].endswith("/openai/v1/chat/completions"))
        self.assertEqual(seen["headers"]["authorization"], "Bearer test-openai-key")
        self.assertEqual(seen["payload"]["model"], "gpt-5.6-luna")
        self.assertTrue(seen["payload"]["stream"])
        self.assertEqual(seen["payload"]["messages"], self.messages)

    def test_anthropic_messages_request_and_stream(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = request.headers
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                text=(
                    'event: content_block_delta\n'
                    'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n\n'
                    'event: message_stop\n'
                    'data: {"type":"message_stop"}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )

        with patch.dict(os.environ, {"BUILD_ANTHROPIC_KEY": "test-anthropic-key"}):
            chunks = list(
                stream_reply(
                    "anthropic", self.messages, self.make_client_factory(handler)
                )
            )

        self.assertEqual(chunks, ["Hello"])
        self.assertTrue(seen["url"].endswith("/anthropic/v1/messages"))
        self.assertEqual(seen["headers"]["x-api-key"], "test-anthropic-key")
        self.assertEqual(seen["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(seen["payload"]["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(seen["payload"]["messages"][1]["role"], "assistant")

    def test_google_gemini_request_and_stream(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = request.headers
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                text=(
                    'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]},"finishReason":"STOP"}]}\n\n'
                    'data: {"usageMetadata":{"totalTokenCount":3}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )

        with patch.dict(os.environ, {"BUILD_GOOGLE_KEY": "test-google-key"}):
            chunks = list(
                stream_reply("google", self.messages, self.make_client_factory(handler))
            )

        self.assertEqual(chunks, ["Hello"])
        self.assertIn("/google/v1beta/models/gemini-3.8-flash:streamGenerateContent", seen["url"])
        self.assertEqual(seen["headers"]["x-goog-api-key"], "test-google-key")
        self.assertEqual(seen["payload"]["contents"][1]["role"], "model")

    def test_missing_key_fails_without_request(self):
        with patch.dict(os.environ, {"BUILD_OPENAI_KEY": ""}):
            with self.assertRaisesRegex(ProviderError, "BUILD_OPENAI_KEY"):
                list(stream_reply("openai", self.messages))

    def test_upstream_error_does_not_echo_response_body_or_key(self):
        secret = "test-openai-secret"

        def handler(_request):
            return httpx.Response(401, text=f"invalid key {secret}")

        with patch.dict(os.environ, {"BUILD_OPENAI_KEY": secret}):
            with self.assertRaises(ProviderError) as raised:
                list(
                    stream_reply(
                        "openai", self.messages, self.make_client_factory(handler)
                    )
                )

        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("Check the matching key", str(raised.exception))

    def test_openai_stream_without_done_marker_is_incomplete(self):
        def handler(_request):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
                headers={"content-type": "text/event-stream"},
            )

        with patch.dict(os.environ, {"BUILD_OPENAI_KEY": "test-openai-key"}):
            with self.assertRaisesRegex(ProviderError, "interrupted before completion"):
                list(
                    stream_reply(
                        "openai", self.messages, self.make_client_factory(handler)
                    )
                )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ChatViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="LocalTestPass!84")
        self.client.force_login(self.user)
        self.conversation = Conversation.objects.create(owner=self.user)

    def post_message(self, client=None, provider="openai", content="Hello"):
        client = client or self.client
        return client.post(
            reverse("conversation-messages", args=[self.conversation.id]),
            data=json.dumps({"provider": provider, "content": content}),
            content_type="application/json",
        )

    def test_home_shows_chat_shell_and_provider_options(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LitChat")
        self.assertContains(response, "OpenAI")
        self.assertContains(response, "Anthropic")
        self.assertContains(response, "Google")
        self.assertContains(response, "shared DeepSeek Flash backend")
        self.assertIn("no-store", response.headers["Cache-Control"])

    @patch.dict(os.environ, {"BUILD_OPENAI_KEY": "never-render-this-secret"})
    def test_provider_key_is_not_rendered_into_the_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "never-render-this-secret")

    def test_create_list_load_and_delete_conversation(self):
        create = self.client.post(reverse("conversation-collection"))
        self.assertEqual(create.status_code, 201)
        created_id = create.json()["id"]

        detail = self.client.get(reverse("conversation-detail", args=[created_id]))
        self.assertEqual(detail.json()["messages"], [])

        delete = self.client.delete(reverse("conversation-detail", args=[created_id]))
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(Conversation.objects.filter(id=created_id).exists())

    def test_loading_conversation_marks_stale_stream_as_interrupted(self):
        message = Message.objects.create(
            conversation=self.conversation,
            role=Message.Role.ASSISTANT,
            provider="openai",
            content="Partial answer",
            status=Message.Status.STREAMING,
        )

        response = self.client.get(
            reverse("conversation-detail", args=[self.conversation.id])
        )

        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.status, Message.Status.INTERRUPTED)

    @patch.dict(os.environ, {"BUILD_OPENAI_KEY": "test-openai-key"})
    @patch("chat.views.stream_reply", return_value=iter(["A useful ", "answer."]))
    def test_message_stream_is_saved_with_provider(self, _stream_reply):
        response = self.post_message()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertIn("no-store", response["Cache-Control"])
        body = b"".join(response.streaming_content).decode()
        self.assertIn('"type": "delta"', body)
        self.assertIn('"type": "done"', body)

        messages = list(self.conversation.messages.all())
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, Message.Role.USER)
        self.assertEqual(messages[0].content, "Hello")
        self.assertEqual(messages[1].role, Message.Role.ASSISTANT)
        self.assertEqual(messages[1].provider, "openai")
        self.assertEqual(messages[1].content, "A useful answer.")
        self.assertEqual(messages[1].status, Message.Status.COMPLETE)

    def test_missing_key_is_actionable_and_does_not_save_prompt(self):
        with patch.dict(os.environ, {"BUILD_OPENAI_KEY": ""}):
            response = self.post_message()

        self.assertEqual(response.status_code, 503)
        self.assertIn("BUILD_OPENAI_KEY", response.json()["error"])
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_invalid_provider_and_empty_message_are_rejected(self):
        invalid = self.post_message(provider="unknown")
        empty = self.post_message(provider="openai", content="  ")
        malformed = self.client.post(
            reverse("conversation-messages", args=[self.conversation.id]),
            data=json.dumps({"provider": [], "content": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(malformed.status_code, 400)

    def test_non_object_json_is_rejected(self):
        response = self.client.post(
            reverse("conversation-messages", args=[self.conversation.id]),
            data="null",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_non_loopback_request_is_rejected(self):
        response = self.client.get(reverse("home"), REMOTE_ADDR="192.168.1.40")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"LitChat is available only from this device.")

    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.post_message(client=client)

        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"BUILD_OPENAI_KEY": "test-openai-key"})
    @patch("chat.views.stream_reply", return_value=iter(["Hello."]))
    def test_template_csrf_token_allows_local_chat_post(self, _stream_reply):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        page = client.get(reverse("home"))
        token = page.cookies["csrftoken"].value
        response = client.post(
            reverse("conversation-messages", args=[self.conversation.id]),
            data=json.dumps({"provider": "openai", "content": "Hello"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        b"".join(response.streaming_content)

    def test_anonymous_users_are_redirected_before_chat_data_is_returned(self):
        client = Client()

        home = client.get(reverse("home"))
        history = client.get(reverse("conversation-collection"))

        self.assertEqual(home.status_code, 302)
        self.assertIn(reverse("login"), home.url)
        self.assertIn("no-store", home.headers["Cache-Control"])
        self.assertEqual(history.status_code, 302)
        self.assertIn("no-store", history.headers["Cache-Control"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountFlowTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="owner",
            email="owner@example.invalid",
            password="OwnerLocalPass!84",
        )
        self.user = User.objects.create_user(
            username="reader",
            email="",
            password="ReaderLocalPass!84",
        )

    def test_signup_creates_only_a_normal_user(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-reader",
                "password1": "TidyRiver!74_Moon",
                "password2": "TidyRiver!74_Moon",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )

        self.assertRedirects(response, reverse("login"))
        created = User.objects.get(username="new-reader")
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.check_password("TidyRiver!74_Moon"))
        self.assertNotEqual(created.password, "TidyRiver!74_Moon")

    def test_signup_is_blocked_until_superuser_and_legacy_setup_are_ready(self):
        conversation = Conversation.objects.create(owner=None)
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "assign_legacy_conversations", status_code=503)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk, owner__isnull=True).exists())

    def test_login_logout_and_password_change(self):
        client = Client()
        login_response = client.post(
            reverse("login"),
            {"username": "reader", "password": "ReaderLocalPass!84"},
        )
        self.assertRedirects(login_response, reverse("home"))
        self.assertIn("no-store", login_response.headers["Cache-Control"])
        self.assertEqual(client.get(reverse("home")).status_code, 200)

        change_response = client.post(
            reverse("password_change"),
            {
                "old_password": "ReaderLocalPass!84",
                "new_password1": "FreshRiver!75_Cloud",
                "new_password2": "FreshRiver!75_Cloud",
            },
        )
        self.assertRedirects(change_response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("FreshRiver!75_Cloud"))

        logout_response = client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("login"))
        self.assertIn("no-store", logout_response.headers["Cache-Control"])
        self.assertEqual(client.get(reverse("home")).status_code, 302)

    def test_login_throttles_repeated_failed_attempts(self):
        cache.clear()
        client = Client()
        for _ in range(5):
            response = client.post(
                reverse("login"),
                {"username": "reader", "password": "incorrect-password"},
            )
            self.assertEqual(response.status_code, 200)

        throttled = client.post(
            reverse("login"),
            {"username": "reader", "password": "incorrect-password"},
        )
        self.assertEqual(throttled.status_code, 429)
        self.assertContains(throttled, "Too many failed sign-in attempts", status_code=429)

    def test_successful_login_clears_failed_attempt_throttle(self):
        cache.clear()
        client = Client()
        for _ in range(4):
            client.post(
                reverse("login"),
                {"username": "reader", "password": "incorrect-password"},
            )

        success = client.post(
            reverse("login"),
            {"username": "reader", "password": "ReaderLocalPass!84"},
        )
        self.assertEqual(success.status_code, 302)
        client.post(
            reverse("logout"),
        )
        after_reset = client.post(
            reverse("login"),
            {"username": "reader", "password": "incorrect-password"},
        )
        self.assertEqual(after_reset.status_code, 200)

    def test_admin_can_reset_and_delete_normal_accounts_but_not_manage_chats(self):
        conversation = Conversation.objects.create(
            owner=self.user, title="private prompt-derived conversation title"
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content="private test prompt",
        )
        admin_client = Client()
        admin_client.force_login(self.superuser)

        change_list = admin_client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(change_list.status_code, 200)
        self.assertNotContains(change_list, "private test prompt")
        self.assertNotContains(
            admin_client.get(reverse("admin:auth_user_add")),
            'name="is_superuser"',
        )

        admin_client.post(
            reverse("admin:auth_user_change", args=[self.user.pk]),
            {
                "username": self.user.username,
                "first_name": "",
                "last_name": "",
                "email": "",
                "is_active": "on",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

        password_url = reverse("admin:auth_user_password_change", args=[self.user.pk])
        password_response = admin_client.post(
            password_url,
            {"password1": "AdminReset!84_River", "password2": "AdminReset!84_River"},
        )
        self.assertEqual(password_response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AdminReset!84_River"))

        superuser_delete = admin_client.get(
            reverse("admin:auth_user_delete", args=[self.superuser.pk])
        )
        self.assertEqual(superuser_delete.status_code, 403)

        delete_url = reverse("admin:auth_user_delete", args=[self.user.pk])
        confirmation = admin_client.get(delete_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertNotContains(confirmation, "private prompt-derived conversation title")
        self.assertNotContains(confirmation, "private test prompt")
        self.assertContains(confirmation, "Delete account and conversations")
        deleted = admin_client.post(delete_url, {"post": "yes"})
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_superuser_link_is_hidden_from_normal_users(self):
        owner_client = Client()
        owner_client.force_login(self.superuser)
        owner_page = owner_client.get(reverse("home"))
        self.assertContains(owner_page, "Manage accounts")

        user_client = Client()
        user_client.force_login(self.user)
        user_page = user_client.get(reverse("home"))
        self.assertNotContains(user_page, "Manage accounts")

    def test_conversations_are_not_registered_in_admin(self):
        admin_client = Client()
        admin_client.force_login(self.superuser)
        response = admin_client.get("/admin/chat/conversation/")

        self.assertEqual(response.status_code, 404)

    def test_normal_user_cannot_access_admin_or_other_users_conversations(self):
        conversation = Conversation.objects.create(owner=self.superuser)
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content="secret to the owner only",
        )
        client = Client()
        client.force_login(self.user)

        admin_page = client.get(reverse("admin:auth_user_changelist"))
        self.assertIn(admin_page.status_code, (302, 403))
        history = client.get(reverse("conversation-collection"))
        self.assertEqual(history.json()["conversations"], [])
        detail = client.get(reverse("conversation-detail", args=[conversation.id]))
        messages = client.get(reverse("conversation-messages", args=[conversation.id]))
        deleted = client.delete(reverse("conversation-detail", args=[conversation.id]))
        sent = client.post(
            reverse("conversation-messages", args=[conversation.id]),
            data=json.dumps({"provider": "openai", "content": "No"}),
            content_type="application/json",
        )
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(messages.status_code, 404)
        self.assertEqual(deleted.status_code, 404)
        self.assertEqual(sent.status_code, 404)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_owner_scoped_responses_are_not_cacheable(self):
        conversation = Conversation.objects.create(owner=self.user)
        client = Client()
        client.force_login(self.user)
        response = client.get(
            reverse("conversation-detail", args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_legacy_assignment_preserves_content_and_is_idempotent(self):
        legacy = Conversation.objects.create(owner=None, title="Old local chat")
        message = Message.objects.create(
            conversation=legacy,
            role=Message.Role.USER,
            content="must not be printed by the command",
        )
        already_owned = Conversation.objects.create(owner=self.user)

        call_command("assign_legacy_conversations", username=self.superuser.username)
        call_command("assign_legacy_conversations", username=self.superuser.username)

        legacy.refresh_from_db()
        message.refresh_from_db()
        already_owned.refresh_from_db()
        self.assertEqual(legacy.owner, self.superuser)
        self.assertEqual(message.content, "must not be printed by the command")
        self.assertEqual(already_owned.owner, self.user)

    def test_legacy_assignment_rejects_normal_user(self):
        with self.assertRaises(CommandError):
            call_command("assign_legacy_conversations", username=self.user.username)


class InitialAccountSetupTests(TestCase):
    def test_signup_is_blocked_until_a_superuser_exists(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "createsuperuser", status_code=503)

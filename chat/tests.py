import json
import os
from unittest.mock import patch

import httpx
from django.test import Client, TestCase
from django.urls import reverse

from .models import Conversation, Message
from .providers import ProviderError, stream_reply


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


class ChatViewTests(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create()

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
        response = self.post_message(client=client)

        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"BUILD_OPENAI_KEY": "test-openai-key"})
    @patch("chat.views.stream_reply", return_value=iter(["Hello."]))
    def test_template_csrf_token_allows_local_chat_post(self, _stream_reply):
        client = Client(enforce_csrf_checks=True)
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

import json
import os

import httpx
from django.conf import settings


PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "key_name": "BUILD_OPENAI_KEY",
        "url": "https://proxy.litechat.ai/openai/v1/chat/completions",
    },
    "anthropic": {
        "label": "Anthropic",
        "key_name": "BUILD_ANTHROPIC_KEY",
        "url": "https://proxy.litechat.ai/anthropic/v1/messages",
    },
    "google": {
        "label": "Google",
        "key_name": "BUILD_GOOGLE_KEY",
    },
}


class ProviderError(Exception):
    pass


def missing_credential(provider):
    config = PROVIDERS.get(provider)
    if config is None:
        return None
    return config["key_name"] if not os.environ.get(config["key_name"]) else None


def _request_for(provider, messages):
    model = settings.LITCHAT_MODELS[provider]
    if provider == "openai":
        return (
            PROVIDERS[provider]["url"],
            {
                "Authorization": f"Bearer {os.environ['BUILD_OPENAI_KEY']}",
                "Content-Type": "application/json",
            },
            {
                "model": model,
                "messages": messages,
                "stream": True,
                "max_tokens": 2048,
                "reasoning_effort": "none",
            },
        )

    if provider == "anthropic":
        return (
            PROVIDERS[provider]["url"],
            {
                "x-api-key": os.environ["BUILD_ANTHROPIC_KEY"],
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            {
                "model": model,
                "messages": messages,
                "stream": True,
                "max_tokens": 2048,
                "thinking": {"type": "disabled"},
            },
        )

    if provider == "google":
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]
        url = (
            "https://proxy.litechat.ai/google/v1beta/models/"
            f"{model}:streamGenerateContent?alt=sse"
        )
        return (
            url,
            {
                "x-goog-api-key": os.environ["BUILD_GOOGLE_KEY"],
                "Content-Type": "application/json",
            },
            {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": 2048,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
        )

    raise ProviderError("Choose a supported provider.")


def _proxy_error(status_code):
    if status_code in (401, 403):
        return "The proxy rejected this provider key. Check the matching key in .env."
    if status_code == 429:
        return "The proxy is rate limiting requests. Wait a moment and try again."
    if status_code >= 500:
        return "The proxy or its upstream model is temporarily unavailable."
    return f"The proxy rejected the request (HTTP {status_code})."


def _data_events(response):
    data_lines = []
    for line in response.iter_lines():
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _openai_text_events(response):
    saw_finish_reason = False
    for data in _data_events(response):
        if data == "[DONE]":
            if not saw_finish_reason:
                raise ProviderError("The OpenAI-style stream ended without a finish reason.")
            return
        try:
            event = json.loads(data)
            choice = event.get("choices", [{}])[0]
            delta = choice.get("delta", {}).get("content")
            saw_finish_reason = saw_finish_reason or choice.get("finish_reason") is not None
        except (json.JSONDecodeError, IndexError, AttributeError, TypeError):
            continue
        if isinstance(delta, str) and delta:
            yield delta
    raise ProviderError("The OpenAI-style stream was interrupted before completion.")


def _anthropic_text_events(response):
    saw_message_stop = False
    for data in _data_events(response):
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "message_stop":
            saw_message_stop = True
            break
        if event.get("type") != "content_block_delta":
            continue
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            yield delta["text"]
    if not saw_message_stop:
        raise ProviderError("The Anthropic-style stream was interrupted before completion.")


def _google_text_events(response):
    saw_finish_reason = False
    for data in _data_events(response):
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        for candidate in event.get("candidates", []):
            saw_finish_reason = saw_finish_reason or candidate.get("finishReason") is not None
            for part in candidate.get("content", {}).get("parts", []):
                text = part.get("text")
                if isinstance(text, str) and text:
                    yield text
    if not saw_finish_reason:
        raise ProviderError("The Gemini-style stream was interrupted before completion.")


def stream_reply(provider, messages, client_factory=None):
    if provider not in PROVIDERS:
        raise ProviderError("Choose a supported provider.")
    missing_key = missing_credential(provider)
    if missing_key:
        raise ProviderError(f"Add {missing_key} to your local .env file.")

    url, headers, payload = _request_for(provider, messages)

    factory = client_factory or httpx.Client
    try:
        with factory(timeout=settings.LITCHAT_PROXY_TIMEOUT) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    raise ProviderError(_proxy_error(response.status_code))
                parser = {
                    "openai": _openai_text_events,
                    "anthropic": _anthropic_text_events,
                    "google": _google_text_events,
                }[provider]
                yield from parser(response)
    except ProviderError:
        raise
    except httpx.TimeoutException as error:
        raise ProviderError("The proxy request timed out. Try again when it is reachable.") from error
    except httpx.RequestError as error:
        raise ProviderError("Could not connect to the proxy. Check your connection and try again.") from error

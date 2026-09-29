# LitChat

LitChat is a single-user, local-only chat web app. It provides OpenAI-, Anthropic-, and Google-style simulated provider experiences through BUILD LLM Proxy. The proxy documents that the interfaces share a DeepSeek Flash backend; the selector changes the simulated interface/persona, not the underlying model weights.

For clone/download and platform-specific setup instructions, see [`docs/instructions.md`](../../docs/instructions.md).

## Run Locally

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Set the proxy keys in `.env`:

```dotenv
BUILD_OPENAI_KEY=...
BUILD_ANTHROPIC_KEY=...
BUILD_GOOGLE_KEY=...
```

Then initialize the local database and run the app:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Visit <http://127.0.0.1:8000/>. The loopback middleware rejects requests that do not originate on the local machine. The app has no login because it is not intended for LAN or internet access.

The UI can load without keys, but sending is disabled for a provider whose key is missing. Add the appropriate key to `.env` and restart the server. Do not paste keys into chat, browser code, or source files. `.env`, `.venv/`, generated Python files, and `db.sqlite3` are ignored by Git. `.env.example` contains placeholders only.

Run the test suite without real credentials or proxy requests:

```bash
.venv/bin/python manage.py test
```

## Interface

- Desktop: dark conversation rail with new-chat/history controls; warm light chat canvas; provider selector and model identifier in the header.
- Mobile: conversation rail opens as a drawer; chat and composer reflow to the viewport.
- Empty state: prompt suggestions; provider key readiness shown above the composer.
- Chat: Enter sends, Shift+Enter adds a line, responses stream, and Stop cancels the current fetch. Incomplete streams are not automatically retried.
- History: conversations and messages are stored in local SQLite and can be deleted. Messages are sent to `proxy.litechat.ai`; only history persistence is local.
- Safety note: assistant output may be incorrect; the UI identifies the shared simulated backend.

## Provider Configuration

The provider labels, model IDs, routes, headers, and SSE parsing live in `chat/providers.py`.

| Interface | Default model | Route | Authentication |
| --- | --- | --- | --- |
| OpenAI Chat Completions | `gpt-5.6-luna` | `/openai/v1/chat/completions` | `Authorization: Bearer` using `BUILD_OPENAI_KEY` |
| Anthropic Messages | `claude-haiku-4-5-20251001` | `/anthropic/v1/messages` | `x-api-key` using `BUILD_ANTHROPIC_KEY`; sends `anthropic-version: 2023-06-01` |
| Google Gemini Generate Content | `gemini-3.8-flash` | `/google/v1beta/models/{model}:streamGenerateContent?alt=sse` | `x-goog-api-key` using `BUILD_GOOGLE_KEY` |

Optional model overrides are `LITCHAT_OPENAI_MODEL`, `LITCHAT_ANTHROPIC_MODEL`, and `LITCHAT_GOOGLE_MODEL`. Proxy URLs are fixed in server code so browser input cannot redirect credentials to another host. Each adapter translates complete user/assistant history into the appropriate request format. Tools and multimodal requests are not sent.

## Architecture and Routes

- `litchat/settings.py`: Django settings, dotenv load, SQLite, fixed host allowlist, proxy model defaults, timeout.
- `chat/middleware.py`: loopback-only request guard.
- `chat/models.py`: UUID conversations and ordered user/assistant messages with provider and response status.
- `chat/providers.py`: proxy request construction, three protocol-specific SSE parsers, credential checks, and safe error mapping.
- `chat/views.py`: HTML page, local conversation CRUD, and normalized server-to-browser SSE events.
- `chat/templates/chat/index.html`, `chat/static/chat/`: accessible responsive interface and browser interaction.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/` | Render chat shell, history, provider/model options, and CSRF token. |
| GET / POST | `/api/conversations/` | List conversations / create an empty conversation. |
| GET / DELETE | `/api/conversations/{uuid}/` | Read a conversation / delete it and its messages. |
| GET / POST | `/api/conversations/{uuid}/messages/` | Read messages / persist a prompt and stream a provider response. |

The browser receives only provider labels/model IDs/key-variable names and whether each key is configured, never key values. The message endpoint requires Django CSRF validation. The server sends normalized SSE `delta`, `done`, and `error` events to the browser; provider-specific completion markers must be present before an assistant message is marked complete. Abandoned `streaming` messages are changed to `interrupted` when history is read.

## Verification

- `.venv/bin/python manage.py check`
- `.venv/bin/python manage.py makemigrations --check --dry-run`
- `.venv/bin/python manage.py test`
- `node --check chat/static/chat/app.js`

Tests use `httpx.MockTransport` or mocked provider streams. They validate provider routes/headers/payloads/SSE, message persistence, missing-key handling, loopback denial, CSRF, malformed input, and secret redaction without real credentials.

## Scope Limits

No registration, remote hosting, cloud sync, payments, subscriptions, token/cost meter, model catalog, tools, file/image/audio support, or automatic provider routing. If scope changes to network access, authentication and deployment hardening must be planned before enabling it.

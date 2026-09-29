# LitChat

LitChat is a local-only chat web app for multiple people sharing one machine. It provides OpenAI-, Anthropic-, and Google-style simulated provider experiences through BUILD LLM Proxy. The proxy documents that the interfaces share a DeepSeek Flash backend; the selector changes the simulated interface/persona, not the underlying model weights. Django accounts separate chat history in the local SQLite database.

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

Leave `DJANGO_SECRET_KEY` blank in `.env.example`; LitChat creates a persistent random value in the ignored `.env` on first startup. On POSIX systems it restricts `.env` to the current OS user.

Then initialize the local database and bootstrap the first superuser:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py assign_legacy_conversations --username YOUR_SUPERUSER_NAME
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

When upgrading an existing local installation, back up `db.sqlite3` outside the repo before migrating. The legacy-assignment command attaches existing ownerless conversations to the initial superuser without printing their contents. For a fresh database, it safely assigns zero conversations.

Visit <http://127.0.0.1:8000/>. Normal users can register from the sign-in page after superuser setup is complete. The loopback middleware rejects requests that do not originate on the local machine; the app is not intended for LAN or internet access.

The UI can load without keys, but sending is disabled for a provider whose key is missing. Add the appropriate key to `.env` and restart the server. All local accounts share these machine-level provider keys. Do not paste keys into chat, browser code, or source files. `.env`, `.venv/`, generated Python files, and `db.sqlite3` are ignored by Git. `.env.example` contains placeholders only.

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

## Accounts and Roles

- **Initial superuser:** Run `manage.py createsuperuser` once from the machine's terminal. Django may ask for an email address; LitChat does not send email. Then run `manage.py assign_legacy_conversations --username <username>` before allowing normal signups. Signup remains blocked until a superuser exists and ownerless legacy conversations have been assigned.
- **Normal user:** Select **Create a normal account** on the sign-in page, register a unique username/password, sign in, use LitChat, change their own password, and log out. Every chat request is restricted to the signed-in user's owner ID.
- **Superuser:** Can use LitChat and open **Manage accounts** from the account menu. Django Admin can create normal accounts, reset their passwords, and delete accounts. Deletion has a confirmation step and removes that user's chats. The Admin UI cannot promote a second superuser or delete/demote the sole superuser.
- **Chat privacy:** User and superuser chat pages show only their own conversations. Conversation/message models are not registered in Django Admin, and account deletion confirmation does not expose chat titles or message contents.
- **Session model:** Log out when another person will use the same browser profile; closing the browser expires its session cookie. Separate browser profiles can have separate sessions; LitChat does not enforce a machine-wide session lock.
- **Local-machine boundary:** App accounts do not prevent someone with OS-level access from reading local SQLite or `.env` files.

## Provider Configuration

The provider labels, model IDs, routes, headers, and SSE parsing live in `chat/providers.py`.

| Interface | Default model | Route | Authentication |
| --- | --- | --- | --- |
| OpenAI Chat Completions | `gpt-5.6-luna` | `/openai/v1/chat/completions` | `Authorization: Bearer` using `BUILD_OPENAI_KEY` |
| Anthropic Messages | `claude-haiku-4-5-20251001` | `/anthropic/v1/messages` | `x-api-key` using `BUILD_ANTHROPIC_KEY`; sends `anthropic-version: 2023-06-01` |
| Google Gemini Generate Content | `gemini-3.8-flash` | `/google/v1beta/models/{model}:streamGenerateContent?alt=sse` | `x-goog-api-key` using `BUILD_GOOGLE_KEY` |

Optional model overrides are `LITCHAT_OPENAI_MODEL`, `LITCHAT_ANTHROPIC_MODEL`, and `LITCHAT_GOOGLE_MODEL`. Proxy URLs are fixed in server code so browser input cannot redirect credentials to another host. Each adapter translates complete user/assistant history into the appropriate request format. Tools and multimodal requests are not sent.

## Architecture and Routes

- `litchat/settings.py`: Django settings, persistent dotenv signing key, SQLite, password validators, fixed host allowlist, proxy model defaults, timeout.
- `chat/middleware.py`: loopback-only request guard.
- `chat/models.py`: UUID conversations with nullable owner FK for staged legacy migration; ordered user/assistant messages with provider and response status.
- `chat/forms.py`, `chat/admin.py`: normal signup form and restricted Django UserAdmin.
- `chat/management/commands/assign_legacy_conversations.py`: assign old ownerless conversations to the initial superuser.
- `chat/providers.py`: proxy request construction, three protocol-specific SSE parsers, credential checks, and safe error mapping.
- `chat/views.py`: throttled sign-in, setup-gated normal registration, authenticated chat page, owner-scoped conversation CRUD, and normalized server-to-browser SSE events.
- `chat/templates/chat/index.html`, `chat/static/chat/`: accessible responsive interface and browser interaction.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/` | Authenticated chat shell and the current user's conversation history. |
| GET / POST | `/accounts/login/` | Sign in / authenticate an account. |
| GET / POST | `/accounts/signup/` | Register a normal user after superuser/legacy setup. |
| POST | `/accounts/logout/` | End the current browser session. |
| GET / POST | `/accounts/password/change/` | Change the signed-in user's password. |
| GET | `/admin/` | Django Admin account management for the superuser only. |
| GET / POST | `/api/conversations/` | List only the current user's conversations / create one owned by that user. |
| GET / DELETE | `/api/conversations/{uuid}/` | Read/delete only a conversation owned by the current user. |
| GET / POST | `/api/conversations/{uuid}/messages/` | Read/send only within a conversation owned by the current user. |

The browser receives only provider labels/model IDs/key-variable names and whether each key is configured, never key values. Authenticated pages and APIs are marked `private, no-store`; logout clears the chat display and restored pages reload. Failed sign-ins are throttled per username and loopback address. The message endpoint requires Django CSRF validation. The server sends normalized SSE `delta`, `done`, and `error` events to the browser; provider-specific completion markers must be present before an assistant message is marked complete. Abandoned `streaming` messages are changed to `interrupted` when history is read.

## Verification

- `.venv/bin/python manage.py check`
- `.venv/bin/python manage.py makemigrations --check --dry-run`
- `.venv/bin/python manage.py test`
- `node --check chat/static/chat/app.js`

Tests use `httpx.MockTransport` or mocked provider streams. They validate provider routes/headers/payloads/SSE, message persistence, missing-key handling, loopback denial, CSRF, malformed input, and secret redaction without real credentials.

## Scope Limits

No email verification/reset, OAuth/social login, remote hosting, cloud sync, payments, subscriptions, token/cost meter, model catalog, tools, file/image/audio support, automatic provider routing, or machine-wide single-session locking. If scope changes to network access, deployment hardening must be planned before enabling it.

# LitChat

LitChat is a local-only chat app with username/password accounts for people sharing one machine. It offers three simulated provider experiences through [BUILD LLM Proxy](https://proxy.litechat.ai), which documents a shared DeepSeek Flash backend. Each account has its own local conversation history.

## Run Locally

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Add your proxy credentials to `.env`:

```dotenv
BUILD_OPENAI_KEY=your-openai-interface-key
BUILD_ANTHROPIC_KEY=your-anthropic-interface-key
BUILD_GOOGLE_KEY=your-google-interface-key
```

Initialize the database, create the one superuser account, assign any pre-account conversations to that superuser, and start the server on loopback:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py assign_legacy_conversations --username YOUR_SUPERUSER
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. Normal users can create accounts from the signup page. The superuser manages accounts through **Manage accounts** in the account menu. The full guide explains role permissions and upgrading a database that already has conversations.

The real `.env` file, local database, and virtual environment are ignored by Git. Never commit or paste your keys into source files, browser code, or chat. LitChat generates and stores a persistent Django signing key in `.env` on first startup if `DJANGO_SECRET_KEY` is blank.

The app also starts without API keys so the UI can be explored; sending is disabled for any provider whose key is missing. No real keys or proxy calls are needed for tests:

```bash
.venv/bin/python manage.py test
```

## Scope

- Local accounts and per-user chat separation on one machine; no cloud sync, public network access, billing, or token/cost meter.
- Normal users self-register and manage only their own chats; the superuser manages accounts but not chat contents.
- One configured model ID for each proxy interface: OpenAI, Anthropic, and Google Gemini.
- Text chat with streamed responses and local conversation history.
- Provider API calls and credentials stay on the Django server.

See [`docs/instructions.md`](docs/instructions.md) for complete download and setup instructions, and `doc/wiki/litchat.md` for the current architecture, configuration, and route documentation.

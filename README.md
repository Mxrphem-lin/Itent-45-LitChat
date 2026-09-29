# LitChat

LitChat is a personal, local-only chat app for exploring three simulated provider experiences through [BUILD LLM Proxy](https://proxy.litechat.ai). The proxy documents that the interfaces share a DeepSeek Flash backend. Conversation history is stored in a local SQLite database.

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

Then run migrations and start the server on loopback:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. The real `.env` file and local database are ignored by Git. Never commit or paste your keys into source files, browser code, or chat.

The app also starts without API keys so the UI can be explored; sending is disabled for any provider whose key is missing. No real keys or proxy calls are needed for tests:

```bash
.venv/bin/python manage.py test
```

## Scope

- One local user; no sign-in, cloud sync, public network access, billing, or token/cost meter.
- One configured model ID for each proxy interface: OpenAI, Anthropic, and Google Gemini.
- Text chat with streamed responses and local conversation history.
- Provider API calls and credentials stay on the Django server.

See [`docs/instructions.md`](docs/instructions.md) for complete download and setup instructions, and `doc/wiki/litchat.md` for the current architecture, configuration, and route documentation.

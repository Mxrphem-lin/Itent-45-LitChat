# Run LitChat on Your Computer

This guide walks through downloading LitChat, installing its dependencies, adding your own proxy keys, and running the app locally. No Node.js installation is needed.

## Requirements

- Python 3.12 or newer
- An account and three interface keys for [BUILD LLM Proxy](https://proxy.litechat.ai)
- Windows PowerShell, or a macOS/Linux terminal

LitChat sends prompts to `proxy.litechat.ai`. The proxy simulates OpenAI-, Anthropic-, and Google-style experiences on a shared DeepSeek Flash backend. Conversation history is stored locally in SQLite.

## Download the Source

Recommended: clone the GitHub repository:

```bash
git clone https://github.com/Mxrphem-lin/Itent-45-LitChat.git
cd Itent-45-LitChat
```

Alternatively, open the repository on GitHub, choose **Code > Download ZIP**, extract the archive, and open a terminal in the extracted `Itent-45-LitChat-main` folder.

## Create a Virtual Environment

Use the command for your operating system.

### macOS and Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Add Your Proxy Keys

Create a local `.env` file by copying `.env.example`. The commands below do not replace an existing `.env` file.

macOS/Linux:

```bash
test -e .env || cp .env.example .env
```

Windows PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Open `.env` in a text editor and fill in the three keys for the matching BUILD LLM Proxy interfaces:

```dotenv
BUILD_OPENAI_KEY=your-openai-interface-key
BUILD_ANTHROPIC_KEY=your-anthropic-interface-key
BUILD_GOOGLE_KEY=your-google-interface-key
```

Use the keys expected by BUILD LLM Proxy for each interface. Do not use or paste these values into the browser, chat, source code, or GitHub. `.env` is ignored by Git; `.env.example` is safe to commit because it contains placeholders only. If you change a key while LitChat is running, restart the server.

The example file also lists optional model-ID overrides. The defaults already match the proxy documentation, so leave them unchanged unless you intentionally want a different supported model identifier.

## Initialize and Start LitChat

### macOS and Linux

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/> in your browser. Keep the server terminal open while using LitChat. Stop the server with `Ctrl+C`.

If port `8000` is already in use, choose another local port, for example `127.0.0.1:8001`, and open the matching URL.

## Use the App

- Start a conversation with **New conversation** or choose one of the suggested prompts.
- Choose an OpenAI-, Anthropic-, or Google-style simulated provider experience in the header. Each has one configured model.
- Type a prompt and press Enter to send. Use Shift+Enter for a line break.
- Responses stream into the conversation. Use **Stop** to cancel a response.
- Conversations remain in local `db.sqlite3` until deleted from the app. This database is not uploaded or committed by LitChat.

Although conversation history is stored locally, prompts and conversation context are sent to `proxy.litechat.ai` so it can generate responses. API keys are added by the server and are not sent to browser JavaScript.

## Run Tests

Tests use mock proxy responses and do not need real keys or make proxy requests.

macOS/Linux:

```bash
.venv/bin/python manage.py test
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## Troubleshooting

- **A provider is disabled:** Confirm its `BUILD_*_KEY` value is set in the workspace-root `.env`, save the file, and restart LitChat.
- **The proxy rejects a key (401/403):** Check that the key is for the selected proxy interface, is current, and has no surrounding quotes or extra spaces.
- **The proxy is rate limiting (429):** Wait briefly before trying again.
- **The proxy is unavailable (502/504 or connection error):** Check your internet connection and the proxy service. LitChat does not automatically retry an interrupted response.
- **The page does not open:** Confirm the runserver command is still running and use the exact local address and port shown in the terminal.
- **Database or migration issue:** Run `manage.py migrate` again from the project root using the virtual-environment Python command for your OS.

## Keep It Local

LitChat is designed for one person on one machine and has no sign-in. Run it with the `127.0.0.1` address shown above. Do not change the address to `0.0.0.0`, expose the port on your network, or deploy it publicly; that could let other people use your proxy keys and read or modify local chat history.

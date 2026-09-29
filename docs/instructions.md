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

Use the keys expected by BUILD LLM Proxy for each interface. Leave `DJANGO_SECRET_KEY` blank; LitChat generates a random signing key on first startup, saves it in `.env`, and restricts the file to your user account on macOS/Linux. Keep the same `.env` between runs so sessions stay valid. Do not use or paste keys into the browser, chat, source code, or GitHub. `.env` is ignored by Git; `.env.example` is safe to commit because it contains placeholders only. If you change a provider key while LitChat is running, restart the server.

The example file also lists optional model-ID overrides. The defaults already match the proxy documentation, so leave them unchanged unless you intentionally want a different supported model identifier. LitChat creates a persistent random `DJANGO_SECRET_KEY` in `.env` on first startup if the value is blank; on macOS/Linux it restricts `.env` permissions to your OS account.

## Initialize the Database and Create the Superuser

If you are upgrading an existing LitChat installation, stop the server and back up `db.sqlite3` outside the repository before migrating. This preserves conversations created before accounts were added.

macOS/Linux:

```bash
cp db.sqlite3 "$HOME/litchat-before-accounts.sqlite3"
```

Windows PowerShell:

```powershell
Copy-Item db.sqlite3 "$HOME\litchat-before-accounts.sqlite3"
```

Skip the backup command for a fresh download with no `db.sqlite3` file.

Run database migrations, then create the one superuser from the terminal. Django may also prompt for an email address; LitChat does not send email.

macOS/Linux:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py assign_legacy_conversations --username YOUR_SUPERUSER_NAME
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py assign_legacy_conversations --username YOUR_SUPERUSER_NAME
```

Replace `YOUR_SUPERUSER_NAME` with the username you chose in the previous command. The assignment command attaches old conversations to the superuser without printing their contents. On a fresh database with no old conversations it assigns zero and is safe to run.

## Start LitChat

### macOS and Linux

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/> in your browser. Keep the server terminal open while using LitChat. Stop the server with `Ctrl+C`.

If port `8000` is already in use, choose another local port, for example `127.0.0.1:8001`, and open the matching URL.

## Accounts and Roles

After the superuser setup is complete, normal users can select **Create a normal account** on the sign-in page. Each account uses a unique username and password; signup cannot grant administrator privileges.

- **Normal users** can sign in/out, use LitChat, view only their own conversation history, and change their own password. They cannot open account administration or view another account's chats.
- Passwords must be at least 10 characters and pass Django's standard password checks.
- **The superuser** can use LitChat like a normal user and select **Manage accounts** from the account menu to open Django Admin. There the superuser can create normal accounts, reset their passwords, and delete their accounts.
- **Deleting a normal account** requires confirmation and permanently deletes that user's conversations/messages too. The sole superuser cannot be deleted or demoted from the admin interface.
- **Chat privacy in Admin:** account management does not show conversation titles or message contents. The superuser's LitChat page shows only the superuser's own chats.
- **Switching users:** use the same browser profile and log out before the next person signs in. Closing the browser also expires its session cookie. Separate browser profiles can keep separate sessions; LitChat does not enforce a machine-wide single-session lock.
- **Provider keys:** all local accounts share the three server-side keys in `.env`; keys are not stored on user accounts.
- **Sign-in protection:** five failed password attempts for the same username/browser address are temporarily throttled; a successful login clears the counter.

Accounts are stored in this machine's SQLite database. This separates app sessions and chat views, but it does not protect `.env` or `db.sqlite3` from someone with operating-system access to the machine.

## Use the App

- Start a conversation with **New conversation** or choose one of the suggested prompts.
- Choose an OpenAI-, Anthropic-, or Google-style simulated provider experience in the header. Each has one configured model.
- Type a prompt and press Enter to send. Use Shift+Enter for a line break.
- Responses stream into the conversation. Use **Stop** to cancel a response.
- Conversations remain in local `db.sqlite3` until deleted from the app or their account is deleted. This database is not uploaded or committed by LitChat.

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
- **Too many failed sign-in attempts:** Wait 15 minutes before retrying. The throttle is local and applies per username/browser address.
- **The proxy rejects a key (401/403):** Check that the key is for the selected proxy interface, is current, and has no surrounding quotes or extra spaces.
- **The proxy is rate limiting (429):** Wait briefly before trying again.
- **The proxy is unavailable (502/504 or connection error):** Check your internet connection and the proxy service. LitChat does not automatically retry an interrupted response.
- **The page does not open:** Confirm the runserver command is still running and use the exact local address and port shown in the terminal.
- **Signup says owner setup is incomplete:** Create the superuser with `manage.py createsuperuser`, then run `manage.py assign_legacy_conversations --username YOUR_SUPERUSER_NAME`.
- **A normal user cannot find old chats:** Sign in as the superuser and rerun the legacy assignment command. It only assigns ownerless conversations and is idempotent.
- **Database or migration issue:** Back up `db.sqlite3` before migration, then run `manage.py migrate` from the project root using the virtual-environment Python command for your OS.

## Keep It Local

LitChat is designed for people sharing one machine. Run it with the `127.0.0.1` address shown above. Do not change the address to `0.0.0.0`, expose the port on your network, or deploy it publicly; that could let other people use your proxy keys and access local account data.

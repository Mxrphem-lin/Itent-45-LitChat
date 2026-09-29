# LitChat Personal Chat Implementation Plan

**Status: Draft**
**Study:** `doc/study/0001-v4_litchat_personal_feasibility.md`

## Goal

Build a personal, local-only Django chat web app with a responsive UI and three simulated provider interfaces through `proxy.litechat.ai`. Persist conversations locally, stream text replies, and keep credentials in a local ignored environment file.

## Decisions and Scope

- Python 3.12, Django, Django templates, vanilla JavaScript, SQLite, `httpx`, and environment-file loading.
- Bind the app to `127.0.0.1`; no registration, public/LAN access, monetization, billing, or token/cost tracking.
- Use documented API routes, model IDs, and keys: `BUILD_OPENAI_KEY`, `BUILD_ANTHROPIC_KEY`, and `BUILD_GOOGLE_KEY`.
- Browser requests must not contain provider credentials. The server selects a fixed provider configuration and makes all proxy calls.
- Store conversations and messages locally; allow new and deleted conversations.
- Mock external API traffic in tests; never require real keys or make paid proxy calls during checks.
- No frontend framework/build system. UI should be responsive, keyboard-accessible, and explain the simulated provider experience.

## Execution Checklist

### Project Foundation

- [x] Create the Django project and chat app with supported dependencies in `requirements.txt`.
- [x] Add a key-free `.env.example`, environment loading, safe local defaults, and `.gitignore` coverage for `.env`, SQLite databases, virtual environments, and generated Python files.
- [x] Configure Django to use SQLite and loopback-only development settings.
- [x] Add conversation and message models, migrations, timestamps, provider attribution, and incomplete/error states for streamed replies.

### Proxy Integration

- [x] Implement separate server-side adapters for OpenAI Chat Completions, Anthropic Messages, and Google Gemini Generate Content.
- [x] Read credentials from the environment; use the documented endpoint paths, provider headers, model IDs, and required Anthropic version header.
- [x] Serialize prior user/assistant conversation turns into each provider's documented request shape.
- [x] Parse each provider's SSE format into one internal stream event format for the browser.
- [x] Persist the user prompt before starting the stream; persist response chunks/status safely and mark completion only after a normal provider finish.
- [x] Surface missing keys and upstream errors without exposing secrets or automatically retrying a partial request.

### Web UI and UX

- [x] Build a clear LitChat shell with new chat, conversation history, provider selector, message list, and composer.
- [x] Show provider/model labels and a concise note that these are simulated provider experiences using the shared proxy backend.
- [x] Add streaming response rendering, disabled/loading states, stop/cancel behavior where safely supported, and useful error/retry guidance.
- [x] Make navigation usable on narrow screens and chat layout responsive on mobile and desktop.
- [x] Include accessible labels, keyboard operation, visible focus, sufficient contrast, and reduced-motion-friendly behavior.
- [x] Add empty, missing-key, network-failure, and empty-history states.

### Verification and Documentation

- [x] Add Django tests for routes, conversation CRUD, each provider request contract, SSE parsing, missing credentials, upstream failures, and secret redaction.
- [x] Run `python manage.py check`, migrations, and the test suite using a local isolated environment and mock responses.
- [x] Verify the development server binds to `127.0.0.1` and serves the app.
- [ ] Manually inspect the UI at desktop and mobile viewport widths and verify the core chat workflow with mocked responses.
- [x] Verify `.env` is ignored and no real secrets appear in tracked files, logs, or HTTP responses.
- [x] Create `doc/wiki/litchat.md` describing setup, environment variables, architecture, local routes, and proxy behavior.
- [ ] Mark this plan and its study `Status: Completed (Authoritative Source: doc/wiki/litchat.md)` after implementation and verification.
- [ ] Initialize/connect the local repository to the supplied empty GitHub remote, inspect status/diff/log, commit only intended files, and push the completed work without secrets.

## Feature Acceptance Criteria

1. **Local startup:** `python manage.py check` reports zero errors; migrations apply; the documented run command binds only to `127.0.0.1` and serves the home page.
2. **New conversation:** Selecting New Chat creates an empty conversation, focuses the composer, and adds the conversation to local history.
3. **Provider selection:** The user can select each simulated provider; the selected model label is visible and remains associated with each assistant response.
4. **OpenAI simulation:** A prompt sends a POST to `/openai/v1/chat/completions` with the configured `gpt-5.6-luna` default and Bearer key; returned SSE text renders incrementally.
5. **Anthropic simulation:** A prompt sends a POST to `/anthropic/v1/messages` with the configured `claude-haiku-4-5-20251001` default, `x-api-key`, and `anthropic-version`; returned SSE text renders incrementally.
6. **Google simulation:** A prompt sends a POST to the configured Gemini `:streamGenerateContent?alt=sse` route with `x-goog-api-key`; returned candidate text renders incrementally.
7. **Conversation context:** A second prompt includes earlier user and assistant turns using the selected provider's documented message format.
8. **Persistence/deletion:** Reloading restores conversations and messages; deleting a conversation removes its messages and history item.
9. **Missing key:** If the selected provider key is missing, the user sees a clear configuration instruction; no upstream call is made and no traceback/key value is exposed.
10. **Upstream/stream error:** A failed or interrupted stream displays an understandable error, does not claim completion, does not automatically duplicate the request, and preserves safe partial history where applicable.
11. **Responsive UX/accessibility:** Core navigation, provider choice, message reading, and sending work at desktop and mobile widths; controls are keyboard-accessible and visibly labeled.
12. **Secret safety:** `.env` is ignored, `.env.example` contains placeholders only, provider keys never appear in client requests/responses or logs, and tests run without real credentials.

## Risks / Notes

- The proxy explicitly documents a shared DeepSeek Flash backend behind the three simulated interfaces; UI labels and docs must not imply different model weights.
- Proxy SSE event formats vary, so each adapter must normalize events and handle completion/error markers correctly.
- The current workspace has no Git metadata and no local `.env`; do not read or commit any later-supplied secret file.
- Tests should use deterministic fake HTTP responses and must not depend on proxy availability.
- **Outstanding visual QA:** Playwright was installed temporarily for viewport checks, but Chromium could not start because the environment lacks `libglib-2.0.so.0`. HTTP-rendered HTML, responsive CSS media queries, browser-JavaScript syntax, and mocked backend APIs were verified; browser interactions and rendered desktop/mobile screenshots remain unverified.

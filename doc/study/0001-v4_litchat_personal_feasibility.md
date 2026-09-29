# LitChat Personal-Use Feasibility

**Status: Completed (Authoritative Source: doc/wiki/litchat.md)**

**Study date:** 2026-09-29
**Supersedes:** `0001-v3_litchat_personal_feasibility.md` as the current scope assessment

## Delta / Changelog

- **Clarification:** The owner accepts that the proxy uses DeepSeek Flash underneath all three API interfaces and intentionally simulates the OpenAI, Anthropic, and Google experiences. The shared underlying model is not a blocker.
- **Why:** Provider choice is about selecting one of the proxy's simulated interfaces/personas, not selecting separate foundation-model weights.
- **Direct comparison:** Version 3 treated the shared model as a possible product mismatch and asked whether it was acceptable. The owner confirmed it is intentional. The proxy integration remains three protocol adapters using the documented model identifiers and credentials.
- **Stack decision:** Django is approved. The app must include a complete, usable, responsive web UI/UX and run only on the owner's machine.
- **Credentials:** The owner will provide three proxy credentials later in a local environment file. The build must work without those secrets for automated tests, provide a key-free example file, and never commit the real environment file.

## Product Scope

LitChat is a local-only personal chat web app. The owner creates conversations, selects OpenAI, Anthropic, or Google (each represented by the proxy's simulated interface), sends text prompts, and sees assistant replies in a familiar chat experience. One proxy model identifier is configured per interface. Conversations are stored locally.

There is no account system, remote access, monetization, billing, token/cost meter, model catalog, model training, or legal/commercial analysis. The UI should identify the selected simulated provider experience clearly without implying that the underlying model weights are from that provider.

## Feasibility

This is technically feasible as a small Django application. The proxy documents three REST interfaces with distinct request/response shapes, headers, fixed model identifiers, and streaming support. A shared conversation UI can call a small provider adapter on the Django server. SQLite is sufficient for local conversation history. No key is required to develop the UI or run mocked adapter tests.

The repository conventions specify `python manage.py check` and `python manage.py runserver`; Django follows those conventions directly. The Python 3.12 runtime is available in the workspace. Django and `httpx` are not currently installed, so implementation will declare dependencies and use an isolated local virtual environment.

## Candidate MVP Boundary

- Responsive, single-user chat interface with conversation history and a new-chat action.
- Provider selector for the three documented simulated experiences; one model identifier for each.
- Text prompts, conversation context, assistant responses, and local conversation persistence.
- Streaming responses where supported by the proxy, with clear error and interruption handling.
- Server-side credentials loaded from a local environment file; no credentials in frontend code, logs, or committed files.
- Local-only server binding (`127.0.0.1`) and a key-free `.env.example`.
- Tests using mocked HTTP responses so no real proxy keys or paid calls are needed.

Exclude registration, shared users, public/LAN access, billing, token/cost tracking, tools, images/files/audio, and automatic model routing.

## Decisions and Scope

- **Answered:** The shared DeepSeek Flash backend with simulated provider experiences is intentional.
- **Answered:** Django is approved; include the necessary usable chat UI/UX.
- **Answered:** LitChat runs only on the owner's machine.
- **Answered:** Three credentials will be supplied by the owner later in a local environment file; never commit them.
- **Assumed:** Persist chats locally until the owner deletes them; no cloud sync or application-level backup.
- **Assumed:** Stream text replies because the proxy documents streaming and it improves the chat experience.
- **Assumed:** Default model identifiers come from the proxy docs and can be overridden through non-secret environment settings.
- **User-directed exclusion:** Legal/regulatory review, monetization, usage-cost calculations, and token meters are out of scope.

## Technical Approach

Use Django templates and minimal vanilla JavaScript for the frontend, Django ORM with SQLite for local conversations/messages, and `httpx` for backend calls to the proxy. Keep each provider's URL, headers, request serialization, streaming parser, and response parsing in a separate adapter. The browser sends only the selected provider, conversation ID, and prompt; the server chooses the fixed model and adds the appropriate secret key.

Bind the development server to `127.0.0.1`. Load keys from `.env` using a small environment loader, ignore `.env` in Git, and provide `.env.example` with blank placeholders only. If a provider key is missing, the app should show an actionable configuration message and automated tests should use mocked providers.

The UI should favor readability and a clear, responsive chat workflow: a persistent conversation rail on desktop, an accessible compact navigation pattern on mobile, a visible provider/model selector, distinct user/assistant messages, a clear composer/send state, streamed response feedback, and helpful empty/error states. Use a deliberate visual style rather than a generic dashboard layout; do not introduce a separate frontend build chain.

## Open Questions

- None blocking. Provider simulation, stack, local-only scope, and secret handling have been confirmed. Lower-risk UI and storage details are captured as assumptions and can be adjusted during review.

## Risks and Trade-offs

- **Secret leakage:** `.env` must be excluded from Git; logs, error responses, HTML, and JavaScript must not reveal credentials.
- **Local-only boundary:** Bind to loopback, not `0.0.0.0`; the app is not designed for LAN or internet access.
- **Provider protocol differences:** Shared UI does not remove the need for independent request/response and SSE parsing per interface.
- **Interrupted streams:** Do not automatically retry after partial output; persist partial/error state without claiming the answer completed.
- **Simulated provider identity:** The UI should communicate the selected simulated experience and avoid presenting it as a different underlying foundation model.
- **Repository state:** The workspace is not currently a Git checkout and the supplied remote is empty. Repository setup and secret checks are needed before the requested commit/push.

## Evidence and References

Proxy docs reviewed 2026-09-29; the site identifies API reference revision 2026-09-19.

- Proxy overview and shared-model statement: https://proxy.litechat.ai/docs
- OpenAI Chat Completions: https://proxy.litechat.ai/docs/openai/chat-completions
- Anthropic Messages: https://proxy.litechat.ai/docs/anthropic/messages
- Google Gemini Generate Content: https://proxy.litechat.ai/docs/google/gemini
- Project directives: `agents.md`

## Recommendation

Proceed with the Django implementation defined in the companion plan. Keep all provider secrets local and mocked during tests, and validate both desktop and mobile chat workflows before syncing the wiki and committing the finished project.

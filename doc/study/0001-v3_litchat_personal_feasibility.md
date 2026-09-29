# LitChat Personal-Use Feasibility

**Status: Draft**
**Study date:** 2026-09-29
**Supersedes:** `0001-v2_litchat_personal_feasibility.md` as the current scope assessment

## Delta / Changelog

- **Clarifications incorporated:** The app runs only on the owner's machine; provider/proxy credentials are server-side in a local environment file and must never be committed; no monetization, token metering, or legal review is in scope.
- **Proxy research:** The supplied proxy docs describe separate OpenAI, Anthropic, and Gemini API interfaces and credentials. However, they explicitly state that all three interfaces use DeepSeek Flash and do not reproduce the named providers' model behavior.
- **Why this matters:** The current proxy may not provide the distinct OpenAI, Anthropic, and Google models implied by the original provider picker. This needs confirmation before committing to its use.
- **Direct comparison:** Version 2 treated the proxy contract and local-only deployment as unknowns. The docs now provide the API contracts and local-only use is confirmed; the underlying-model mismatch and technology stack remain to be agreed.
- **Technology recommendation:** Prefer Django with server-rendered templates, minimal browser JavaScript, SQLite, and `httpx`. This is suitable for a small local app and aligns with the Django-specific verification commands in `agents.md`.

## Product Scope

LitChat is a personal, local-only chat web app. The owner enters text prompts, chooses one of three provider interfaces, and receives a response. One model identifier is configured per interface. Requests go through the owner's account at `https://proxy.litechat.ai`; LitChat does not train models or provide billing, monetization, token/cost tracking, public sign-up, or remote access.

The desired distinction between provider/model choices is not yet established for this proxy: its documentation says all interfaces use DeepSeek Flash and do not reproduce the named providers' model behavior.

## Proxy Findings

The proxy's getting-started page lists these interface defaults:

| Interface | Base URL / route | Model identifier | Credential header/environment example |
| --- | --- | --- | --- |
| OpenAI Chat Completions | `https://proxy.litechat.ai/openai/v1/chat/completions` | `gpt-5.6-luna` | `Authorization: Bearer ...` / `BUILD_OPENAI_KEY` |
| Anthropic Messages | `https://proxy.litechat.ai/anthropic/v1/messages` | `claude-haiku-4-5-20251001` | `x-api-key: ...` / `BUILD_ANTHROPIC_KEY` |
| Google Gemini Generate Content | `https://proxy.litechat.ai/google/v1beta/models/gemini-3.8-flash:generateContent` | In the URL | `x-goog-api-key: ...` / `BUILD_GOOGLE_KEY` |

The interfaces have different request/response formats and authentication headers, so LitChat needs a small adapter per interface even if the chat UI is shared. The docs support streaming for each interface. They say conversation history remains in the app and must be sent on each request; the proxy does not execute tool/function calls. The MVP can omit tools and multimodal features.

Most importantly, the docs state: "BUILD LLM Proxy uses DeepSeek Flash for all three provider interfaces. The interfaces do not reproduce the named providers' model behavior." Therefore, selecting one of these three interfaces may not select a genuinely distinct OpenAI, Anthropic, or Google model. The displayed model IDs should not be interpreted as confirmation of upstream model identity without further evidence from the proxy operator.

## Feasibility Summary

| Area | Assessment | Rationale |
| --- | --- | --- |
| Local chat application | Feasible | This is a small single-user app with text input, conversation history, and a provider-interface selector. |
| Proxy integration | Feasible | The docs specify three REST endpoints, credentials, request/response shapes, and streaming behavior. Each needs a small backend adapter. |
| Distinct provider models | Unconfirmed / possible product mismatch | The proxy explicitly describes one underlying DeepSeek Flash model across the three interfaces. If the purpose is to compare actual OpenAI, Anthropic, and Google models, this proxy does not meet that requirement according to its own docs. |
| Credential handling | Feasible | The server can load credentials from a local environment file, use them only for backend requests, and exclude the file from Git. |
| Technology | Feasible | Django is a cohesive fit for a local web app, SQLite persistence, and the `manage.py` verification conventions in `agents.md`. |

**Overall:** Building the local chat UI and connecting it to the documented proxy is technically straightforward. Whether that proxy satisfies the intended model-selection experience is the main product question. No implementation plan or code should assume that interface labels correspond to distinct underlying models until confirmed.

## Candidate MVP Boundary

- Local-only chat UI with a provider-interface selector.
- One configured model per interface using the proxy's documented model IDs.
- Text prompts and conversation history persisted in local SQLite.
- Server-side proxy requests with credentials loaded from the local environment file.
- Stream responses where practical; handle proxy errors and interrupted streams without unsafe automatic retries.
- New-chat and delete-conversation controls.

Exclude accounts, public access, billing, token/cost display, model catalogs, tools, file/image/audio inputs, and automatic routing. The MVP should state clearly which service and model behavior it actually uses; do not imply distinct upstream providers if the proxy does not provide them.

## Recommended Technology Stack

**Recommendation:** Django + Django templates + minimal vanilla JavaScript + SQLite + `httpx`.

- **Django:** Provides a maintainable server-rendered application, ORM/migrations, CSRF protections, and a straightforward local run command. It also matches the explicit `python manage.py check` and `python manage.py runserver` rendezvous requirements in `agents.md`.
- **Templates and vanilla JavaScript:** Enough for a chat interface and incremental response rendering without a separate React/Node build system. No client-side provider keys or direct proxy calls.
- **SQLite:** Appropriate for a single-user local app and sufficient for conversation/message history.
- **`httpx`:** Makes backend HTTP requests to the three documented proxy interfaces and can consume streamed responses. Keep provider-specific payload and response parsing in small isolated functions.
- **Local environment file:** Use the proxy's documented `BUILD_OPENAI_KEY`, `BUILD_ANTHROPIC_KEY`, and `BUILD_GOOGLE_KEY` names; keep the real file ignored by Git and provide only a key-free example. No secrets should be sent in chat or added to committed files.

**Alternative:** FastAPI + Jinja templates + SQLite can be leaner and naturally async for streaming. However, it would not satisfy the Django-specific checks in `agents.md` without changing those project directives and selecting equivalent verification commands. A React/Next.js frontend would add unnecessary build and dependency complexity for this local-only scope.

No `.env`-style file was present in the workspace during this review; no secrets were opened or read. The app can be scaffolded with a placeholder example and ignore rule, then use the owner's local secret file when supplied.

## Decisions and Scope

- **Answered:** Personal use only, running on the owner's machine.
- **Answered:** No monetization, token/cost meter, or legal analysis.
- **Answered:** Credentials are server-side in a local environment file and must not be committed.
- **Answered:** The user selects among three interfaces, with one configured model identifier per interface.
- **Assumed:** Persist conversations locally in SQLite; include delete controls.
- **Recommended:** Bind the development server to `127.0.0.1`; do not expose it on the LAN or public internet.
- **Recommended:** Use Django unless the owner prefers changing the Django-specific project verification convention and adopting FastAPI.

## Open Questions

1. **Question:** Are you aware that the proxy documentation says all three interfaces use DeepSeek Flash and do not reproduce OpenAI, Anthropic, or Google model behavior? Is this acceptable, or do you expect three distinct underlying models?
   **Why it matters:** It determines whether this proxy fulfills the primary provider-selection goal or whether the app needs a different service/endpoint configuration.
   **Recommended default:** If you specifically want genuine models from each provider, do not treat these three interface labels as equivalent to those upstream models; confirm the proxy's actual routing with its operator or use endpoints that genuinely route to each provider.
   **Status:** `blocking`

2. **Question:** Do you approve the recommended Django stack, or would you prefer FastAPI despite the Django-specific commands in `agents.md`?
   **Why it matters:** This selects the project structure, persistence integration, streaming implementation, and validation commands before the implementation plan is written.
   **Recommended default:** Django + templates + minimal JavaScript + SQLite + `httpx`, preserving the existing project directives and avoiding an unnecessary frontend build chain.
   **Status:** `blocking`

## Risks and Trade-offs

- **Model identity mismatch:** Proxy docs explicitly describe the same underlying DeepSeek Flash model for all three interfaces. The app may otherwise give the impression of switching among distinct providers when it only changes request protocol.
- **Protocol differences:** The three endpoints use different payload shapes and headers. Shared conversation UI still requires provider-specific serialization and response parsing.
- **Credential exposure:** Keep the app bound to localhost, keep secrets out of frontend code/logs, and ignore the real local environment file in Git.
- **Streaming failure handling:** The proxy docs warn against retrying automatically after partial output and note that usage can be unknown after failures. Do not add retry logic that might duplicate requests.
- **Public Git repository:** Never commit keys. The supplied GitHub repository is empty, and the current workspace is not a Git checkout; repository setup and secret-exclusion checks are required before any requested commit/push.

## Evidence and References

Proxy docs reviewed 2026-09-29; the site identifies API reference revision 2026-09-19.

- Getting started and shared underlying model note: https://proxy.litechat.ai/docs
- OpenAI Chat Completions: https://proxy.litechat.ai/docs/openai/chat-completions
- Anthropic Messages: https://proxy.litechat.ai/docs/anthropic/messages
- Google Gemini Generate Content: https://proxy.litechat.ai/docs/google/gemini
- Project directives: `agents.md`

## Recommendation and Next Discussion

The app itself is feasible. Before planning, confirm whether the proxy's stated DeepSeek Flash backend is acceptable for all three interface choices and select the stack. If Django is approved and the proxy behavior is acceptable, proceed with a local-only, server-rendered app using SQLite and server-side environment configuration. Do not begin coding until those decisions are agreed.

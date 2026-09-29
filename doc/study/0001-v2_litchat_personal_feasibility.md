# LitChat Personal-Use Feasibility

**Status: Draft**
**Study date:** 2026-09-29
**Supersedes:** `0001_litchat_feasibility.md` as the current scope assessment

## Delta / Changelog

- **Scope change:** Reframed LitChat from a public, monetized, multi-user service to a personal, single-user web app with no monetization.
- **Why:** The owner clarified that billing, token/cost tracking, country of launch, commercial use, and legal analysis are not requirements.
- **Direct comparison:** Version 1's wallet/payment architecture, unit economics, commercial provider approval, age/launch-market questions, and multi-user onboarding are out of scope. The current product is a chat interface that sends prompts through the owner's proxy credentials.
- **Provider selection:** The user chooses one of three providers; each provider has one configured model. There is no model catalog or model-level picker.
- **Remaining unknowns:** The proxy service/API contract and whether the app is local-only or remotely reachable still affect implementation and credential security.

## Problem and Proposed Product

LitChat is a personal chat web app. Its owner enters prompts, chooses OpenAI, Anthropic, or Google, and receives a response from the single model configured for that provider. Requests use credentials supplied by the owner and a third-party proxy to reach the models. LitChat is an API client/orchestrator, not a model-training project.

The intended interaction is text chat with conversation context. There is one user, no public sign-up, no payment, no subscription, and no in-app token or cost meter.

## Feasibility Summary

| Area | Assessment | Rationale |
| --- | --- | --- |
| Core chat | Feasible | A small web app can collect text, send conversation context to a configured endpoint, and display the response. |
| Provider integration | Feasible, proxy-dependent | The proxy's supported API format, endpoint paths, model identifiers, and authentication determine whether one shared adapter or separate provider adapters are needed. |
| Personal credentials | Feasible | Keep proxy keys on the server and out of browser code, chat history, logs, and Git. Environment-based configuration is a simple initial option. |
| Personal deployment | Feasible | Local-only operation avoids public accounts and limits exposure of the owner's credentials. A remotely reachable deployment needs authentication and secure transport. |
| Product/business concerns | Out of scope | Per the owner, LitChat is not commercial, has no monetization, and will not assess legal or market-launch considerations. |

**Overall:** Feasible as a small personal web application. The proxy contract and deployment location are the only material technical decisions needed before an implementation plan. A local-only first version is the simplest and safest default.

## Candidate MVP Boundary

Subject to the remaining technical decisions, a first version could include:

- A single-user chat screen with a provider selector for OpenAI, Anthropic, and Google.
- One server-configured model identifier per provider.
- Text prompts, assistant responses, and conversation context.
- Locally saved conversations, with controls to start and delete conversations.
- Server-side proxy credentials and configurable proxy endpoint/model settings.
- Clear handling of missing configuration, provider errors, and network failures.

Exclude user registration, billing, subscriptions, token/cost accounting, model catalogs, multiple models per provider, file/image/audio inputs, tools, automatic routing, and shared conversations. Streaming can be included if the proxy supports it cleanly; it is not a prerequisite for the core chat flow.

## Technical Approach and Security

Use a small server-rendered web application and keep the three provider integrations behind a narrow backend interface. The UI sends a provider choice and conversation identifier; the server loads the configured endpoint, model, and credential, makes the proxy request, and returns the response. Store conversations locally, for example in the app's database, but do not store credentials in conversation records.

Prefer owner-managed environment configuration for proxy URLs, model identifiers, and API keys in the first version. Keep the local secrets file out of Git and provide only a placeholder example file. Do not put keys in frontend JavaScript, browser storage, URLs, logs, error messages, or committed files. If the app is exposed beyond the owner's machine, require authentication and HTTPS before sending requests; a personal project is not automatically safe to expose publicly.

The repository workflow calls for `python manage.py check` and `python manage.py runserver`, so Django is the likely fit. The workspace currently has no Django application scaffold, so this is a convention-based recommendation rather than an existing-stack constraint.

## Decisions and Scope

- **Answered:** Personal use only; no monetization or commercial product requirement.
- **Answered:** No token/cost meter or in-app billing.
- **Answered:** Owner-supplied credentials are used to reach models via a third-party proxy.
- **Answered:** The user selects a provider, with exactly one model configured for each provider.
- **Assumed:** Conversations persist locally to support chat history; users can delete them.
- **Assumed:** No login is required if the app runs only on the owner's machine.
- **Recommended:** Start local-only, with keys and model IDs configured server-side through environment variables.
- **User-directed exclusion:** Legal/regulatory analysis and commercial-provider approval are not assessed in this personal-use study.

## Open Questions

1. **Question:** Which proxy service will LitChat call, and what are its base URL, request format, model IDs, authentication header, and streaming support for each of the three providers? Please provide public documentation or example request shapes, not secret API keys.
   **Why it matters:** A proxy may expose one OpenAI-compatible endpoint for all models or require separate provider-native request formats. This controls adapter design and whether provider-specific features or streaming are possible.
   **Recommended default:** Configure a separate base URL, model ID, and credential per provider; use the proxy's documented API contract and add only the adapters it requires.
   **Status:** `blocking`

2. **Question:** Will LitChat run only on your own machine (`localhost`), or should it be accessible from another device or over the public internet?
   **Why it matters:** Remote access changes authentication, HTTPS, secret storage, and deployment requirements. The API credentials must not be exposed to other users.
   **Recommended default:** Run locally on the owner's machine for the first version; add remote access only with explicit authentication and secure deployment.
   **Status:** `blocking`

3. **Question:** Should credentials and endpoint settings be entered in a server-side settings page, or provided in a local environment file?
   **Why it matters:** A settings page is convenient but requires secure persistence and masking of secrets. Environment configuration is simpler but requires editing a local file and restarting the server after changes.
   **Recommended default:** Use a local environment file for the first version; never commit the real file or its keys.
   **Status:** `assumed`

## Risks and Trade-offs

- **Proxy compatibility:** The implementation cannot be finalized until the actual proxy API shape and model names are known. A proxy change could require adapter changes.
- **Credential exposure:** A public or unauthenticated deployment could let others spend against the owner's proxy account. Keep keys server-side and default to local-only.
- **Conversation privacy:** Persisted history contains prompts and responses. Store it locally, avoid logging message contents, and provide deletion.
- **Provider behavior differences:** Context limits, response formats, errors, and streaming support may differ even when the UI presents one common chat experience.
- **Public repository:** The provided GitHub repository is empty, and the local workspace is not currently a Git checkout. Never commit the owner's real API/proxy keys; establish an ignore rule before adding configuration files.

## Recommendation and Next Discussion

Proceed with a small personal-use implementation after confirming the proxy API contract and whether local-only operation is acceptable. If confirmed, use Django, local conversation storage, server-side environment configuration, and one fixed model per provider. No payment or cost-accounting subsystem is needed. Create a separate implementation plan only after those technical defaults are agreed.

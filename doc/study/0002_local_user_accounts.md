# LitChat Local User Accounts Feasibility

**Status: Draft**
**Study date:** 2026-09-29
**Supersedes:** The no-account scope in `doc/study/0001-v4_litchat_personal_feasibility.md` for this proposed feature

## Delta / Changelog

- **Scope change:** Add username/password signup and login, normal-user chat separation, and a single superuser who can manage accounts.
- **Why:** LitChat will be used by different people in sequence on one local machine for the vibecoding midterm.
- **Direct comparison:** The current authoritative app has no authentication and treats all local conversations as one collection. The prior study explicitly excluded accounts. This proposal keeps LitChat local-only and non-monetized but introduces account roles, sessions, per-user data ownership, and an ownership migration for existing conversations.
- **Unchanged:** Django, SQLite, server-side shared proxy credentials, and loopback-only access remain the working baseline unless the open questions change them.

## Product Goal

Allow normal users to create a username/password account and use LitChat on one local machine. A single superuser can manage user accounts, including resetting passwords and deleting normal accounts. Users should be able to log out so another person using the same browser can sign in.

This is an app-level account boundary on the owner's machine, not a remotely hosted or OS-level multi-tenant service. It does not add monetization, email delivery, or public network access.

## Current State

- Django 5.2 and SQLite are already used.
- `django.contrib.auth`, `django.contrib.sessions`, and `django.contrib.admin` are not currently installed/configured; session and authentication middleware are absent.
- `Conversation` has no owner/user field. All conversation list, read, create, delete, and message endpoints currently operate on the same local collection.
- `LoopbackOnlyMiddleware` restricts HTTP requests to the local machine, but it is not user authentication.
- The workspace contains an ignored local `db.sqlite3`. Its contents were not inspected. It may contain conversations that need to be preserved and assigned an owner.

## Feasibility Summary

| Area | Assessment | Rationale |
| --- | --- | --- |
| Username/password accounts | Feasible | Django's built-in User, password hashers, forms, login/logout, and session support match this use case; custom password storage is unnecessary. |
| One superuser / normal users | Feasible with guarded role management | Django represents superusers as users with privileged flags. Signup must create normal users only, and the account-management UI must not expose privilege promotion. Bootstrap one superuser out of band. |
| Chat privacy between accounts | Feasible, security-critical | Add an owner FK to conversations and scope every HTML/API query and mutation by `request.user`. Hiding another user's chat in the UI alone is insufficient. |
| One-machine sequential use | Feasible | Django sessions naturally support login/logout in a shared browser. A machine-wide single-session lock is extra behavior and is not automatic. |
| Existing local data | Feasible, requires a migration decision | Existing conversations have no owner. A staged migration can preserve them and assign them to the initial superuser, but the desired ownership/deletion policy should be confirmed before schema changes. |

**Overall:** Feasible and a natural extension of the current Django app. Reuse Django's authentication system rather than inventing an account/password system. The main risks are accidentally exposing chats across users, weakening the one-superuser boundary, and mishandling existing local conversation data.

## Recommended Design

- Use Django's built-in user model, password hashers, and standard password validators. Passwords are stored as hashes, never plaintext. There is no current custom user model or profile requirement that justifies introducing one.
- Add Django auth, sessions, messages, and admin components with their required middleware and context processors.
- Create the first and only superuser with `manage.py createsuperuser`. Do not offer superuser creation from public signup.
- Provide normal self-registration with username/password confirmation. Server-side creation must always set normal-user privileges; never accept `is_staff` or `is_superuser` from submitted form data.
- Provide login, logout, and self-service password change. With no email service, password recovery for normal users is performed by the superuser.
- Use the Django admin account-management pages for a first version, with a custom UserAdmin that lets the superuser inspect accounts, change/reset passwords, and delete normal accounts, but does not allow creating/promoting additional superusers. Link to this area from LitChat only for the superuser.
- Do not register conversations/messages in the admin initially. Users see only their own chats; account administration does not imply an in-app right to browse chat contents.
- Add a non-null conversation owner relation after deciding how to backfill existing rows. Apply ownership filtering to every query and endpoint, including conversation UUID lookups, message reads, creates, deletes, and streaming requests.
- Deleting a normal account should require confirmation and, by default, delete that account's conversations/messages as well. Protect the sole superuser from self-deletion or demotion in the UI.
- Keep current provider credentials in the machine-level `.env`, shared by local accounts. They remain server-side and are not stored on user records.
- Keep `LoopbackOnlyMiddleware` and bind the server to `127.0.0.1`. Logout clears the current browser session; do not add remote hosting or LAN access.

## Data Migration Considerations

The existing `Conversation` model has no owner and the local SQLite database may have real chat history. Do not drop or recreate the database as part of account setup.

If the history should be preserved, a safe migration can first add a nullable owner FK, then assign existing ownerless conversations to the initial superuser through an explicit management step, verify the data, and only then enforce non-null ownership. All new conversations must be assigned to the authenticated user. If history is intentionally disposable, take a backup and document an explicit reset instead of silently deleting it.

## Assumptions

- **Assumed:** Normal-user signup is self-service on the local app, while superuser creation is an owner-run management command.
- **Assumed:** The built-in Django admin is acceptable for account management in the midterm; a branded admin dashboard can be added later if presentation requires it.
- **Assumed:** All normal accounts use the same three provider keys configured in the machine's `.env`; per-user API keys are not part of this feature.
- **Assumed:** Normal users may change their own password; only the superuser can reset another user's password or delete their account.
- **Assumed:** The first superuser account owns pre-existing conversations if the owner chooses to preserve them.

## Decisions and Scope

- **Confirmed by owner:** Keep all accounts and chats in the local machine's SQLite database; no hosting is planned.
- **Confirmed by owner:** Use one superuser and normal user accounts with username/password signup and login.
- **Confirmed by owner:** Users share one local machine and are expected to log out before another person uses the same browser.
- **Out of scope:** Email verification, email/password reset, OAuth/social login, remote registration, multiple superusers, per-user provider credentials, billing, and cloud sync.

## Open Questions

1. **Question:** Should conversations already in the local SQLite database be preserved and assigned to the first superuser, or discarded/reset when accounts are introduced?
   **Why it matters:** The current database has no owner relation. This determines whether the migration needs a backfill and requires a backup before applying it.
   **Recommended default:** Preserve existing conversations and assign them to the first superuser; do not inspect or delete them during migration.
   **Status:** `blocking`

2. **Question:** Does "User 1 must log out before User 2 logs in" mean a shared-browser workflow, or must LitChat enforce at most one active user session across every browser on the machine?
   **Why it matters:** Django logout naturally clears the shared browser session, but separate browser profiles can hold independent sessions. A machine-wide lock requires additional session tracking/invalidation behavior.
   **Recommended default:** Support the shared-browser logout/login workflow without a global session lock. Add a global lock only if enforcing one active account at a time is a firm requirement.
   **Status:** `blocking`

3. **Question:** Should the superuser be able to read normal users' chat contents, or only manage their accounts?
   **Why it matters:** Account-management rights do not necessarily imply access to private prompts and responses. This affects what the admin interface exposes.
   **Recommended default:** Do not register conversations/messages in the admin; each user sees only their own chats.
   **Status:** `blocking`

4. **Question:** When the superuser deletes a normal account, should that user's chat history be permanently deleted too?
   **Why it matters:** Cascading account deletion is destructive and determines data-retention behavior.
   **Recommended default:** Delete the user's conversations/messages after an explicit confirmation.
   **Status:** `blocking`

5. **Question:** Are machine-level proxy credentials shared by every account, as assumed, or should each local user configure separate provider keys?
   **Why it matters:** Per-user keys require secure credential storage and settings UI; shared keys keep the current simple `.env` configuration.
   **Recommended default:** Share the existing server-side `.env` keys across accounts; keep keys out of user records.
   **Status:** `assumed`

## Risks and Trade-offs

- **Cross-user data leak:** Every conversation/message operation must filter by authenticated owner, not only UUID or UI state. Test a user attempting to read, send to, or delete another user's conversation.
- **Privilege escalation:** Signup and user-management forms must never trust submitted role flags. Protect the only superuser against accidental demotion/deletion.
- **Existing data loss:** Schema changes can orphan or delete local chats if ownership/backfill is skipped. Back up `db.sqlite3` before migration and follow the agreed migration path.
- **Local-machine trust boundary:** App passwords protect the LitChat interface, not the SQLite file or `.env` from someone with OS-level access to the machine. This is not isolation from the machine owner.
- **Session confusion:** Shared-browser logout must be visible and reliable. Browser profiles may represent independent sessions unless a global lock is deliberately added.
- **Admin UX:** Django admin is quick and secure for account management but visually distinct from LitChat. A custom admin experience costs more implementation and testing effort.
- **Shared proxy account:** All users' prompts go through the owner's configured proxy credentials, while prompts are still sent to the proxy service. The app does not track per-user usage or cost.

## Evidence and References

- Django 5.2 authentication system: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- Django 5.2 admin site: https://docs.djangoproject.com/en/5.2/ref/contrib/admin/
- Current LitChat architecture and routes: `doc/wiki/litchat.md`

## Recommendation and Next Discussion

Proceed with Django's built-in auth and sessions, normal-user self-registration, a CLI-created superuser, and strict owner filtering for all chats. Use Django admin as the initial account-management interface and retain the local-only middleware. Before writing an implementation plan, resolve the blocking questions about existing chat history, machine-wide session exclusivity, superuser access to chat contents, and account-deletion retention.

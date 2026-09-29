# LitChat Local User Accounts Feasibility

**Status: Completed (Authoritative Source: doc/wiki/litchat.md)**
**Study date:** 2026-09-29
**Supersedes:** The no-account scope in `doc/study/0001-v4_litchat_personal_feasibility.md` for this proposed feature

## Delta / Changelog

- **Scope change:** Add username/password signup and login, normal-user chat separation, and a single superuser who can manage accounts.
- **Why:** LitChat will be used by different people in sequence on one local machine for the vibecoding midterm.
- **Direct comparison:** The current authoritative app has no authentication and treats all local conversations as one collection. The prior study explicitly excluded accounts. This proposal keeps LitChat local-only and non-monetized but introduces account roles, sessions, per-user data ownership, and an ownership migration for existing conversations.
- **Unchanged:** Django, SQLite, server-side shared proxy credentials, and loopback-only access remain the working baseline unless the open questions change them.
- **Owner decisions:** Preserve old conversations and assign them to the first superuser; use shared-browser logout rather than a global session lock; keep chat contents private from account administration; cascade account deletion to that user's chats after confirmation; and share the `.env` provider keys across users.

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
- Throttle repeated failed sign-ins per username/loopback client. Mark authenticated HTML/API responses private and non-cacheable, and clear the visible chat state during logout for shared-browser privacy.
- Use the Django admin account-management pages for a first version, with a custom UserAdmin that lets the superuser inspect accounts, change/reset passwords, and delete normal accounts, but does not allow creating/promoting additional superusers. Link to this area from LitChat only for the superuser.
- Do not register conversations/messages in the admin initially. Users see only their own chats; account administration does not imply an in-app right to browse chat contents.
- Add a non-null conversation owner relation after deciding how to backfill existing rows. Apply ownership filtering to every query and endpoint, including conversation UUID lookups, message reads, creates, deletes, and streaming requests.
- Deleting a normal account requires confirmation and deletes that account's conversations/messages. Protect the sole superuser from deletion or demotion in the UI.
- Keep current provider credentials in the machine-level `.env`, shared by local accounts. They remain server-side and are not stored on user records.
- Keep `LoopbackOnlyMiddleware` and bind the server to `127.0.0.1`. Logout clears the current browser session; do not add remote hosting or LAN access.

## Data Migration Considerations

The existing `Conversation` model has no owner and the local SQLite database may have real chat history. Do not drop or recreate the database as part of account setup.

Preserve the existing history. Add a nullable owner FK first, create the initial superuser, then run an explicit management command to assign all ownerless conversations to that superuser and verify the result. All new conversations must be assigned to the authenticated user. Keep the FK nullable only to support the staged upgrade; views must never expose ownerless rows to normal users.

## Assumptions

- **Assumed:** Normal-user signup is self-service on the local app, while superuser creation is an owner-run management command.
- **Assumed:** The built-in Django admin is acceptable for account management in the midterm; a branded admin dashboard can be added later if presentation requires it.
- **Assumed:** Normal users may change their own password; only the superuser can reset another user's password or delete their account.

## Decisions and Scope

- **Confirmed by owner:** Keep all accounts and chats in the local machine's SQLite database; no hosting is planned.
- **Confirmed by owner:** Use one superuser and normal user accounts with username/password signup and login.
- **Confirmed by owner:** Preserve existing conversations and assign them to the first superuser.
- **Confirmed by owner:** Users share one browser workflow and log out before the next person signs in; browser-close session expiry is enabled, with no global lock across separate browser profiles.
- **Confirmed by owner:** The superuser manages accounts, not other users' chat contents.
- **Confirmed by owner:** Deleting a normal account deletes its conversations after explicit confirmation.
- **Confirmed by owner:** All accounts share the provider keys in the machine's `.env`.
- **Confirmed by owner:** Use Django admin for account management; normal-user signup remains self-service.
- **Out of scope:** Email verification, email/password reset, OAuth/social login, remote registration, multiple superusers, per-user provider credentials, billing, and cloud sync.

## Open Questions

- None blocking. The owner confirmed the migration policy, session behavior, account-management boundary, deletion behavior, shared keys, and Django Admin choice.

## Risks and Trade-offs

- **Cross-user data leak:** Every conversation/message operation must filter by authenticated owner, not only UUID or UI state. Test a user attempting to read, send to, or delete another user's conversation.
- **Privilege escalation:** Signup and user-management forms must never trust submitted role flags. Protect the only superuser against accidental demotion/deletion.
- **Existing data loss:** Schema changes can orphan or delete local chats if ownership/backfill is skipped. Back up `db.sqlite3` before migration and follow the agreed migration path.
- **Local-machine trust boundary:** App passwords protect the LitChat interface, not the SQLite file or `.env` from someone with OS-level access to the machine. This is not isolation from the machine owner.
- **Session confusion:** Shared-browser logout must be visible and reliable. Browser profiles may represent independent sessions unless a global lock is deliberately added.
- **Stale browser cache / password guessing:** Do not cache authenticated chat responses; rate-limit repeated failed local sign-ins without logging credentials.
- **Admin UX:** Django admin is quick and secure for account management but visually distinct from LitChat. A custom admin experience costs more implementation and testing effort.
- **Shared proxy account:** All users' prompts go through the owner's configured proxy credentials, while prompts are still sent to the proxy service. The app does not track per-user usage or cost.

## Evidence and References

- Django 5.2 authentication system: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- Django 5.2 admin site: https://docs.djangoproject.com/en/5.2/ref/contrib/admin/
- Current LitChat architecture and routes: `doc/wiki/litchat.md`

## Recommendation and Next Discussion

Proceed with Django's built-in auth and sessions, normal-user self-registration, a CLI-created superuser, and strict owner filtering for all chats. Use Django admin for account management and retain the local-only middleware. The implementation plan must include a safe legacy-conversation assignment command and update `docs/instructions.md` with superuser/normal-user setup and role capabilities.

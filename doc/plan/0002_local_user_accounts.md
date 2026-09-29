# LitChat Local User Accounts Implementation Plan

**Status: Completed (Authoritative Source: doc/wiki/litchat.md)**
**Study:** `doc/study/0002_local_user_accounts.md`

## Delta / Changelog

- **New work:** Add local username/password signup/login, normal-user chat ownership, and one protected superuser account manager.
- **Why:** The owner approved sequential account use on one local machine for the vibecoding midterm.
- **Direct comparison:** Plan `0001_litchat_personal_chat.md` assumes one user and unowned conversations. This plan adds Django auth/sessions and a safe owner backfill while preserving the local-only app and shared `.env` provider keys.

## Goal

Add Django-native accounts to LitChat without hosting it or losing existing local conversations. The first superuser is created from the command line; normal users self-register. Each user can access only their own conversations. The superuser manages accounts through Django Admin but cannot browse chat contents.

## Decisions and Scope

- Continue using Django's built-in `User` model, auth/session framework, SQLite, and server-rendered templates. Expire the browser session cookie when the browser closes.
- Signup creates ordinary accounts only; role fields are never accepted from user input. Create the one superuser via `manage.py createsuperuser` and protect it from UI promotion/deletion paths.
- Use Django Admin for account management. Do not register conversations/messages in Admin.
- Add `Conversation.owner` as a nullable FK for the staged upgrade from the current database. Assign legacy ownerless conversations to the first superuser, then require ownership in all application views and API endpoints.
- Normal users can change their own password. The superuser can reset another user's password and delete normal accounts. Deletion requires confirmation and cascades to that user's conversations/messages.
- Accounts share the existing machine-level `.env` provider keys. Keep the loopback-only middleware; no global single-session lock, remote access, or LAN access.

## Execution Checklist

### Preserve and Migrate Local Data

- [x] Verify the current local `db.sqlite3` exists; make a timestamped backup outside the repository before any schema migration. Do not inspect or commit the database/backup.
- [x] Add `Conversation.owner` as a nullable FK to `settings.AUTH_USER_MODEL` in a non-destructive migration.
- [x] Add an idempotent `assign_legacy_conversations --username <superuser>` command that accepts only a superuser and assigns every ownerless conversation without reading/printing message contents.
- [x] Keep ownerless legacy rows hidden from normal users until the assignment command has completed.

### Django Authentication and Account UX

- [x] Install/configure Django auth, sessions, messages, admin, the required middleware/context processors, and standard password validators.
- [x] Generate and persist a random `DJANGO_SECRET_KEY` in ignored `.env` when blank so restarts do not invalidate sessions; restrict `.env` permissions on POSIX systems.
- [x] Add styled signup, login, logout, and self-service password-change flows with CSRF protection.
- [x] Add a local per-username/IP failed-login throttle; never log submitted passwords.
- [x] Mark authenticated HTML/API responses `private, no-store` and clear visible account/chat data when logging out so a shared browser cannot restore another user's conversation from cache.
- [x] Ensure signup creates normal accounts only (`is_staff=False`, `is_superuser=False`), validates/confirm passwords, and uses Django's password hashing.
- [x] Require login for the LitChat home page and every conversation/API endpoint.
- [x] Add an account menu with username, password change, logout, and a superuser-only Admin link.
- [x] Customize Django `UserAdmin` so the sole superuser can change/reset normal user passwords and delete normal accounts, but cannot promote accounts or delete/demote the sole superuser. Remove unsafe bulk deletion behavior.
- [x] Use a privacy-safe account deletion confirmation page that explains chat history will also be deleted but never lists conversation titles or message text.
- [x] Do not register `Conversation` or `Message` in Django Admin.

### Conversation Ownership

- [x] Set `owner=request.user` whenever a conversation is created.
- [x] Filter homepage history, conversation listing/detail/delete, message listing, and streamed sends by the authenticated owner.
- [x] Return not-found/denied responses when one user supplies another user's conversation UUID; do not reveal whether the conversation exists.
- [x] Confirm deleting a normal user cascades to only that user's conversations/messages.
- [x] Confirm the superuser sees only their own conversations in LitChat, while Admin account management exposes no chat content.

### Documentation and Verification

- [x] Add tests for signup/login/logout/password change, password validation/hash, privilege assignment, Admin permissions, and superuser protection.
- [x] Add cross-user isolation tests for listing, reading, messaging, and deleting guessed conversation IDs.
- [x] Test legacy assignment preserves all records, rejects a normal-user target, and is idempotent.
- [x] Test user deletion confirmation/cascade, CSRF, unauthenticated redirects, and loopback-only access.
- [x] Back up the local DB and apply migrations. Verify bootstrap/legacy assignment using an isolated test DB without creating owner credentials or displaying stored prompt text.
- [x] Run `python manage.py check`, migration checks, the full test suite, and the local server on `127.0.0.1`.
- [x] Update `docs/instructions.md` with first-superuser setup, legacy assignment for upgrades, normal-user signup/login, and separate superuser/user capabilities.
- [x] Update `doc/wiki/litchat.md` and README with authentication, roles, ownership, and new routes.
- [x] Mark this plan and study `Status: Completed (Authoritative Source: doc/wiki/litchat.md)` after acceptance criteria pass.
- [ ] Inspect Git status/diff/log, ensure `.env`, the live DB, and backup are not staged, commit intended files, and push to `main`.

## Feature Acceptance Criteria

1. **Bootstrap and legacy data:** `migrate` preserves the existing DB. After `createsuperuser`, `assign_legacy_conversations --username <superuser>` assigns all ownerless conversations to that account, changes no message text/count, is idempotent, and rejects a normal user.
2. **Signup and privilege safety:** A visitor can register a unique username/password. Mismatched or weak passwords are rejected. The new user is active and normal; crafted role fields cannot grant staff/superuser privileges.
3. **Login/logout:** Valid credentials create a local browser session; invalid credentials do not. Logout clears that browser session, the cookie expires when the browser closes, and authenticated pages/APIs redirect or reject anonymous access.
4. **Password changes:** A user can change their own password only after entering the current password. The superuser can reset a normal account's password from Admin. No plaintext passwords are stored.
5. **Admin boundary:** Only the superuser can access `/admin/` and manage accounts. Admin cannot promote a second superuser or delete/demote the sole superuser. Account lists and delete confirmation do not display conversation titles or message text. Normal users cannot access Admin.
6. **Cross-account chat isolation:** User A creates chats. After User B logs in, B cannot see them in HTML/list responses or read, send to, or delete them by guessing UUIDs. The superuser's chat page also shows only their own chats.
7. **Account deletion:** Admin shows an explicit confirmation; deleting a normal account removes only that user's conversations/messages and leaves other accounts/chats and the superuser intact.
8. **Local-only/security:** Requests from non-loopback clients remain blocked; CSRF is required; the Django signing key remains stable across restarts; authenticated responses are non-cacheable; repeated bad logins are throttled; proxy keys remain shared from `.env`, absent from user records and browser responses.
9. **User instructions:** A new clone's owner can follow `docs/instructions.md` to create the superuser, run the legacy assignment when upgrading, register a normal user, log in/out, and understand the actions each role can perform.

## Risks / Notes

- The local database may contain private conversation history. Back it up before migration; never use a destructive reset as a shortcut.
- The owner FK is nullable only for the staged upgrade. Normal users must never see ownerless data; no app-created conversation may be ownerless.
- App accounts do not protect `.env` or SQLite from anyone with OS-level access to this local machine.
- Django Admin is visually distinct from LitChat but is the lowest-risk account manager for this midterm scope.
- The local `db.sqlite3` schema is migrated and backed up, but no superuser was created by the implementation process. The owner must choose that account's credentials and run the documented `createsuperuser` and legacy-assignment commands before normal signup is enabled.
- Browser-level visual/BFCache interaction testing was unavailable because Chromium cannot load the environment's missing `libglib-2.0.so.0`; the server, templates, JS syntax, API flows, and responsive CSS were otherwise verified.
- Browser-level visual/BFCache testing could not run because Chromium is unavailable in this environment (`libglib-2.0.so.0` is missing); server, template, CSS/JS syntax, and backend flow tests pass.

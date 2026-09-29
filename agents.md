# Agent Directives & Conventions

This project follows a disciplined, evidence-based engineering process. All AI agents must adhere to these directives, scaling effort proportionally to task risk.

---

## 1. Operating Framework & Execution Loop

Execute changes using the 5-phase sequence:

study => plan => execute plan => rendezvous => sync docs

### Risk-Proportional Execution
* **High-Risk (Features, Schema Changes, Core Refactors):** Full process required. Create distinct Markdown files in `doc/study/` and `doc/plan/`.
* **Low-Risk (Small Fixes, Typos, Minor Tweaks):** Fast-track enabled. Combine study and plan into a single micro-file under `doc/plan/` (skip `doc/study/`).

---

## 2. Document Versioning & Immutability Rules

* **Zero Overwrites on Past Docs:** Never delete, overwrite, or edit completed historical study or plan documents. Once implemented, existing docs are read-only historical records.
* **Sequential Versioning:** For new iterations, major refactors, or feature updates affecting prior work, create a new file with an incremental version suffix or sequence number (e.g., `doc/study/0001-v2_feature_name.md` or `0002_feature_update.md`).
* **Mandatory Delta Section:** Every versioned study or plan document (`-v2`, `-v3`, etc.) MUST include a dedicated **Delta / Changelog** section at the top that highlights:
  * What was changed or refactored compared to the previous version(s).
  * Why the change was made (e.g., bug fix, scope change, optimization).
  * Direct comparison notes against past versions for easy diffing.

---

## 3. Phase Execution & Exit Criteria

### 1. Study (`doc/study/`)
* **Purpose:** Analyze requirements, check feasibility, evaluate trade-offs, and surface open ambiguities.
* **Open Questions Protocol:** All ambiguities must be logged in a dedicated **Open Questions** section inside the study doc using this format:
  * **Question:** What needs clarification?
  * **Why it matters:** Impact on design, scope, or performance.
  * **Recommended default:** The agent's proposed path forward.
  * **Status:** `blocking` (requires user input before proceeding), `answered` (user confirmed), or `assumed` (low-risk default applied, user notified).
* **Execution Rule for Questions:**
  * Interrupt the user **only** for `blocking` questions that materially alter design/scope.
  * For low-risk choices, apply the `assumed` default, document it, and proceed.
  * Once answered or confirmed, move the finalized decision into the study doc's **Decisions & Scope** section.
* **Exit Criteria:** All blocking questions resolved, explicit **Assumptions**, **Delta Section** (if v2+), and **Risks/Trade-offs** listed, marked as `Status: Draft` until plan creation.

### 2. Plan (`doc/plan/`)
* **Purpose:** Create a concrete, step-by-step checklist based on the study doc.
* **Exit Criteria:** Must include a **Delta Section** (if v2+) and an explicit **Feature Acceptance Criteria** section containing test cases to verify (e.g., login success/failure, form validation, route protection).

### 3. Execute Plan
* **Purpose:** Implement code iteratively according to the plan checklist.
* **Exit Criteria:** All plan tasks checked off (`- [x]`) and code runs without runtime/syntax errors.

### 4. Rendezvous
* **Purpose:** Integration handoff and stability verification.
* **Exit Criteria:** Pass explicit checks:
  * `python manage.py check` passes with 0 errors.
  * Server starts cleanly via `python manage.py runserver`.
  * Feature acceptance test cases manually verified.
  * Branch merged cleanly into `main`.

### 5. Sync Docs (`doc/wiki/`)
* **Purpose:** Keep living documentation synchronized with reality.
* **Exit Criteria:** Update `doc/wiki/` files in the same review cycle. Mark implemented study/plan files as `Status: Completed (Authoritative Source: doc/wiki/<file>.md)`.

---

## 4. Documentation Rules & Directory Structure

* **Brevity & Conciseness:** Keep documents short, dense, and directly actionable. Avoid conversational fluff or background repetition.
* **Single Source of Truth:** `doc/wiki/` is always the authoritative source for the current state of the app. `doc/study/` and `doc/plan/` are versioned historical records.
* **Directory Scoping:**
  * `doc/study/` - Feasibility, risks, trade-offs, versioned deltas, and embedded Open Questions.
  * `doc/plan/` - Step-by-step checklists, versioned deltas, and feature test acceptance criteria.
  * `doc/wiki/` - Authoritative living manual (routes, models, architecture).
  * `doc/instructions/` - Quickstart guides and environment execution steps.

---

## 5. Git & Code Standards

* **Conventional Commits:** Commit messages must strictly use standard scopes:
  * `feat:` New user-facing features or endpoints
  * `fix:` Bug fixes
  * `docs:` Documentation additions or syncs
  * `chore:` Scaffolding, dependency, or environment changes
  * `refactor:` Code cleanup without logic changes
* **Scope Discipline:** Do not modify files outside the active plan step without updating the plan doc first.
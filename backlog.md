# Backlog: Praxis Code v2 UI/UX adoption

**Source:** [`praxis-code-v2.zip`](./praxis-code-v2.zip) — 62-file React prototype ("Praxis Code — Homeschool Learning Management", AI Studio export, 2026-10-04).
**Vision context:** [`PRODUCT-VISION.md`](./PRODUCT-VISION.md) § "Frontend product vision — Praxis Code v2 UI/UX".
**Scope:** port the v2 **design language, components, and IA** into the product frontend; plan the **backend endpoints** the new surfaces need. Do **not** port the prototype's stack (React 19 / Tailwind v4 / `motion` / `@google/genai`) or its mock-data-as-content approach.

## Ownership map (multi-root)

| Workstream | Owning repo | Where |
| :--- | :--- | :--- |
| WS-1 tokens, WS-2/3/4 components, WS-5 views | `ed-tech-system` | `frontend/src/presentation/**`, `frontend/scripts/documented-routes.mjs` |
| WS-6 backend endpoints | `ed-tech-system-backend` | `supabase/migrations/**`, `services/**`, `API_ENDPOINTS.md`, contracts in `backend_cursor_log/` |
| Content touched by new flows | `ed-tech-system-mcp` (this repo) | authoring pipeline only — never `course/**` files |

**Done = gates green.** Every frontend stroke ends with `npm run gate:fast` (exit 0 in `ed-tech-system`); backend changes follow `gates.mdc` + backend repo CI. Budgets in `scripts/quality-baselines.json` tighten only; new routes must be added to `documented-routes.mjs` in the same PR (smoke + Playwright consume it).

---

## Decisions to lock before WS-1

| ID | Decision | Recommendation |
| :--- | :--- | :--- |
| D-1 | Theme direction: v2 is **light-first** (`#f8fafc` page, white cards); current tokens are dark-first glass | Ship v2 light as **default theme** and keep current dark as `[data-theme="dark"]`; both live in `tokens/colors.css` |
| D-2 | Branding: adopt "Praxis Code" naming + logo from zip assets | Keep repo/product naming unchanged; adopt layout/aesthetics only. Logo asset needs a local, license-clean replacement (zip uses a Google-hosted AI-Studio URL) |
| D-3 | Dependency policy: no React 19 / Tailwind v4 / `motion` / `@google/genai` upgrades in this effort | Confirmed — visual parity is achieved with Tailwind 3 + existing Radix/Zustand stack; animations via CSS transitions (`card-transition` pattern) |
| D-4 | Role model: prototype has student ⇄ educator switcher in-shell | Map to `tenant_memberships` roles; if the FE lacks a role switcher today, add BE-0 first — do not fake roles client-side |

---

## WS-1 — Design tokens (`ed-tech-system` · `frontend/src/presentation/design-system/tokens/`)

Extract the v2 aesthetic into CSS variables consumed via Tailwind aliases (rule: **no raw hex in features**). Extend `tokens/`, do not fork it.

| ID | Item | Source (zip) | Target |
| :--- | :--- | :--- | :--- |
| FE-101 | Color palette v2: page `#f8fafc`, card `#ffffff`, borders `slate-200/80`, text `slate-400..900`, sidebar `#090b10`, editor `#0d1117`, dark-btn `#0f172a` | `AppLayout.tsx`, `Sidebar.tsx`, `Card.tsx`, `LiveCodeEditor.tsx`, `Button.tsx` | `tokens/colors.css` (new `:root` light block per D-1; dark block = current) |
| FE-102 | Accent rebase: primary `blue-600` → hover `blue-700`, focus ring `blue-500`, active-nav shadow `shadow-blue-600/30` | `Button.tsx`, `Sidebar.tsx` | `tokens/colors.css` (`--accent-*`) |
| FE-103 | Feedback/status palette: `completed` emerald, `in-progress` amber (animated dot), `not-started` slate, `danger` rose, `fire` amber-on-dark | `Badge.tsx`, `LessonDetailView.tsx` | `tokens/colors.css` (`--warning-*` new; semantic aliases in `semantic.css`) |
| FE-104 | Gradients: CTA `purple-600→indigo-600→blue-600`; hero `blue-700→indigo-700→blue-800`; AI-panel `blue-50→indigo-50→purple-50` | `Button.tsx` (gradient), `WeeklyStreakBanner.tsx`, `AiPedagogicalAssistant.tsx` | `tokens/colors.css` (`--gradient-cta`, `--gradient-hero`, `--gradient-ai`) |
| FE-105 | Radius scale: controls `rounded-xl`, inner blocks `rounded-2xl`, cards/modals `rounded-3xl` | all components | `tokens/radius.css` |
| FE-106 | Elevation + motion: `shadow-xs..xl`, hover lift `-translate-y-0.5`, `card-transition: all .2s cubic-bezier(.4,0,.2,1)`, toast slide-in | `Card.tsx`, `index.css` (zip), `AppLayout.tsx` | `tokens/effects.css` + `.card-transition` utility in `foundation/` |
| FE-107 | Typography: Plus Jakarta Sans (UI) + Fira Code (mono), self-hosted (no Google Fonts CDN at runtime) | `index.css` (zip) | `tokens/typography.css` + font files under `foundation/fonts/` |
| FE-108 | Scrollbars: 6px slim, `slate` thumb (light) | `index.css` (zip) | `foundation/` global CSS |
| FE-109 | Token gate alignment: extend `frontend` unit tests / gate 14 budget only if new alias-count budget is added — **tighten only** | — | `scripts/quality-baselines.json` (only if needed) |

## WS-2 — Atoms (`design-system/components/`)

Map v2 atoms onto existing design-system components; restyle via tokens, keep public APIs Radix-compatible. Each item includes its unit-test update (rule: validator/component change ⇒ its test in the same PR).

| ID | Item | v2 source | Target component | Notes |
| :--- | :--- | :--- | :--- | :--- |
| FE-201 | `Button`: variants `primary/secondary/outline/ghost/success/dark/gradient`, sizes `xs..lg`, icon + `iconPosition`, `isLoading` spinner, `active:scale-98` | `atoms/Button.tsx` | `components/Button/` | Current Button keeps its API; add missing variants + loading state |
| FE-202 | `Badge` (new): status variants w/ optional pulse dot, `fire`, `score` | `atoms/Badge.tsx` | `components/Badge/` (new) | Consumes FE-103 aliases |
| FE-203 | `Avatar` (new): initials, gradient bg, online dot, sizes | `atoms/Avatar.tsx`, `LessonDetailView.tsx` | `components/Avatar/` (new) | |
| FE-204 | `Card`: variants `default/elevated/tinted/dark/gradient`, `hoverEffect` lift | `atoms/Card.tsx` | `components/Card/` | Map to FE-101 surfaces |
| FE-205 | `ProgressBar`: colors `blue/emerald/…`, size `xs..` | `atoms/ProgressBar.tsx` | `components/ProgressBar/` | |
| FE-206 | `TabPill` (new): pill tab w/ active fill | `atoms/TabPill.tsx` | `components/TabPill/` (new) or extend `Tabs/` | Prefer extending existing `Tabs/` if API fits |

## WS-3 — Molecules (`presentation/shared/` or feature-level)

| ID | Item | v2 source | Target | Needs backend |
| :--- | :--- | :--- | :--- | :--- |
| FE-301 | `MetricStatCard`: emoji/icon tile, category label, title, colored badge, onClick nav | `molecules/MetricStatCard.tsx` | `presentation/shared/` | no |
| FE-302 | `AudioNarratorPlayer`: play/pause pill + seek strip ("Lesson Narration") | `molecules/AudioNarratorPlayer.tsx` | `features/lesson-workspace/` | yes — audio asset storage (BE-5) |
| FE-303 | `VideoCard` + `VideoPlayerModal`: verified badge, channel, duration, embed | `molecules/VideoCard.tsx`, `organisms/VideoPlayerModal.tsx` | `features/lesson-workspace/` | no — reuse `curriculum.lesson_videos` |
| FE-304 | `QuizOptionCard` + `TestResultItem`: option select, pass/fail/pending states | `molecules/QuizOptionCard.tsx`, `molecules/TestResultItem.tsx` | `features/quiz/` | no — `learner.quiz_attempts` exists |
| FE-305 | `ChecklistItem`: hands-on project steps w/ progress rollup | `molecules/ChecklistItem.tsx` | `features/lesson-workspace/` | yes — project step state (BE-3) |
| FE-306 | `StudentProgressItem`: avatar, streak, XP/level, status text, alert | `molecules/StudentProgressItem.tsx` | `features/student-roster/` (new) | yes — BE-1 |
| FE-307 | `RoleSwitcher`: student ⇄ educator pill | `molecules/RoleSwitcher.tsx` | `features/shell/` | yes — BE-0 (real roles) |

## WS-4 — Organisms + template (shell & lesson workbench)

| ID | Item | v2 source | Target | Notes |
| :--- | :--- | :--- | :--- | :--- |
| FE-401 | Sidebar: dark `#090b10`, collapsible (`w-64 ⇄ w-20`), role-scoped nav, count badges, settings/help/sign-out footer | `organisms/Sidebar.tsx` | `features/shell/` + `app/AppLayout.tsx` | Route state stays in URL (`frontend-layers.mdc` #3) |
| FE-402 | `TopHeader`: breadcrumb/context + "Create Lesson" CTA slot | `organisms/TopHeader.tsx` | `features/shell/` | |
| FE-403 | Toast system: bottom-right dark pill, ping dot, auto-dismiss | `templates/AppLayout.tsx` (`toastMessage`) | `presentation/shared/toast/` (new) | Zustand store, not context-in-component |
| FE-404 | Streak/XP hero banner: gradient, weekly goal ring | `organisms/WeeklyStreakBanner.tsx` | `features/student-dashboard/` (new) | BE-1 |
| FE-405 | Weekly activity: list ⇄ kanban toggle, week selector | `organisms/WeeklyActivityList.tsx`, `WeeklyActivityKanban.tsx` | `features/weekly-plan/` (new) | BE-2 |
| FE-406 | Live code editor: Python/JS tabs, dark editor `#0d1117`, Run/Reset, 3-test suite strip, AI feedback panel | `organisms/LiveCodeEditor.tsx` | `features/lesson-workspace/` | BE-3 (real run + tests — prototype's `setTimeout` is fake) |
| FE-407 | Interactive visualizers (e.g. fraction pizza): manipulable lesson models | `organisms/InteractiveFractionPizza.tsx` | `features/lesson-workspace/visualizers/` | Driven by lesson project config from `curriculum.projects` |
| FE-408 | AI grading queue: filter chips, submission cards (code snippet / CV photo note), approve one/all | `organisms/AiGradingQueue.tsx` | `features/teacher-grading/` (new) | BE-4 |
| FE-409 | Weekly lesson planner: drag lessons into week grid | `organisms/WeeklyLessonPlanner.tsx` | `features/weekly-plan/` | BE-2 |
| FE-410 | AI pedagogical assistant: learning alerts, weekly highlights, "recommend support lesson" | `organisms/AiPedagogicalAssistant.tsx` | `features/teacher-insights/` (new) | BE-4/MCP — insights generated server-side, UI renders only |
| FE-411 | Modals: Create Lesson, Quiz Generator, Workspace (quiz/project/coding tabs) | `organisms/CreateLessonModal.tsx`, `QuizGeneratorModal.tsx`, `WorkspaceModal.tsx` | Radix `Dialog/` compositions | Create/quiz-gen call **MCP authoring pipeline** or `ai_generation_jobs` — never client-side LLM keys |
| FE-412 | `AppLayout` recomposition: page bg `#f8fafc`, content max-w `7xl`, `px-5..10 py-6..7` rhythm | `templates/AppLayout.tsx` | `app/AppLayout.tsx` | **Do not port** `BrowserChromeBar` (prototype decoration, not product) |

## WS-5 — Views & routes

| ID | Item | v2 source | Route | Notes |
| :--- | :--- | :--- | :--- | :--- |
| FE-501 | Student dashboard (streak + 3 stat cards + weekly activity) | `views/StudentDashboardView.tsx` | existing dashboard | |
| FE-502 | Lesson detail workbench (dual-panel 7:5, theory + tabs) | `views/LessonDetailView.tsx` | existing lesson route | Composition of FE-302..307, FE-406/407 |
| FE-503 | Teacher dashboard (4 metrics + grading queue + planner + assistant + roster) | `views/TeacherDashboardView.tsx` | new teacher dashboard route | |
| FE-504 | Role select screen | `views/RoleSelectView.tsx` | new `/role-select` or modal | Gated on BE-0 |
| FE-505 | Weekly plan view (grade horária) | `views/WeeklyPlanView.tsx` | new route | BE-2 |
| FE-506 | Resources view (videos + external links) | `views/ResourcesView.tsx` | new route | Reuses `lesson_web_links`, `lesson_videos` |
| FE-507 | Students roster view | `views/StudentsView.tsx` | new route | BE-1 |
| FE-508 | Register **every** new route in `documented-routes.mjs` (single source → smoke + Playwright follow) | — | `frontend/scripts/documented-routes.mjs` | Same PR as the route (quality-prevention.mdc §6.14) |

## WS-6 — Backend plan (`ed-tech-system-backend`)

Pattern: expand-first migrations + RLS per existing conventions (`learner.*`, `curriculum.*`, `public.*`); contracts written to `backend_cursor_log/contracts/<scope>/<date>-<n>/` before SQL (contract-to-sql skill); endpoints appended to `API_ENDPOINTS.md` in the same PR.

| ID | Item | Tables / endpoints (draft) | Feeds FE items | Priority |
| :--- | :--- | :--- | :--- | :--- |
| BE-0 | Role exposure for shell: confirm `tenant_memberships` RPC returns role(s) for the current user; add if missing | `GET get_my_membership_role` (or extend existing tenant RPC) | FE-307, FE-504 | P0 (blocks role switcher) |
| BE-1 | Gamification: streak, XP, level, weekly goal | `learner.gamification_profile` (user_id, streak_days, xp, level, weekly_goal_minutes, weekly_done_minutes) + `GET /rest/v1/…` view or RPC `get_my_gamification_profile`; teacher variant `list_students_gamification(tenant_id)` | FE-306, FE-404, FE-507 | P1 |
| BE-2 | Weekly plan: lesson slots per student/week | `learner.weekly_plan_slots` (user_id, lesson_id, weekday smallint, start_time, week_of date) + RPCs `get_my_weekly_plan(week_of)`, `upsert_weekly_plan_slot`, teacher `set_weekly_plan` | FE-405, FE-409, FE-505 | P1 |
| BE-3 | Live coding runs: persist code submissions + test results | `learner.code_submissions` (user_id, project_id, language, code, created_at) + `learner.code_run_results` (submission_id, test_case_id, status, stdout, duration_ms); execution service reuses `curriculum.test_boilerplates`/`project_test_cases`; edge function or worker `run-code` | FE-406, FE-305 | P1 (execution may be phased: manual-run first) |
| BE-4 | AI grading + insights (human-in-the-loop) | extend `learner.project_delivery_reviews` with `ai_suggested_score`, `ai_feedback`, `source ('ai'|'teacher')`, `approved_by`, `approved_at`; queue RPC `list_pending_ai_reviews(tenant_id)`; approve RPC `approve_ai_review(review_id, final_score)`; insights via `public.ai_generation_jobs` (job_type `pedagogical_insight`) rendered read-only | FE-408, FE-410, FE-503 | P1 |
| BE-5 | Lesson audio narration | `curriculum.lesson_audio` (lesson_id, locale, storage_path, duration_seconds) — Supabase Storage bucket `lesson-audio` (private, signed URLs); generation stays in MCP pipeline | FE-302 | P2 |
| BE-6 | External resources | already covered by `curriculum.lesson_web_links` + `lesson_videos`; add verified flag to `lesson_videos` if missing (`verified boolean default false`) | FE-303, FE-506 | P2 |

Backend order: contracts → migration (expand) → RPC + RLS → `API_ENDPOINTS.md` + `backend_cursor_log` contract doc → FE consumer in same cross-repo PR set (AGENTS.md rule 1).

---

## Execution order & milestones

```text
M1 Foundations   FE-101..109 (tokens) → FE-201..206 (atoms)          # every stroke: gate:fast
M2 Shell         FE-401..403, FE-412 + BE-0 + FE-307                  # role-gated nav live
M3 Student flow  FE-404/405, FE-501, FE-502 (+FE-302..306, 406/407)   # needs BE-1..3, BE-5
M4 Teacher flow  FE-408..411, FE-503 (needs BE-4) + FE-504..508
M5 Polish        budgets tighten, E2E via gate:deliver, drop mockData equivalents
```

**Definition of done (repo law):** `npm run gate:fast` exit 0 per stroke; `gate:core` before PR; `gate:deliver` at M5; `STATUS: complete` in `.gates/last-run/summary.json` is the only stop signal. Markdown checkboxes here are **context, never a verdict**.

## Explicit non-goals

- No React 19 / Tailwind v4 / `motion` / `@google/genai` adoption (D-3).
- No `BrowserChromeBar` (prototype chrome simulation).
- No client-held AI keys; no content authored as repo files (`course/**` stays deleted).
- No new `legacy:` files; `quality-baselines.json` budgets tighten only.

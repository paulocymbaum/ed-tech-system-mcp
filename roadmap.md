# Roadmap: Praxis Code v2 UI/UX adoption

**Source:** [`praxis-code-v2.zip`](./praxis-code-v2.zip) — 62-file React prototype ("Praxis Code — Homeschool Learning Management", AI Studio export, 2026-10-04).
**Vision context:** [`PRODUCT-VISION.md`](./PRODUCT-VISION.md) § "Frontend product vision — Praxis Code v2 UI/UX".
**Scope:** port the v2 **design language, components, and IA** into the product frontend; plan the **backend endpoints** the new surfaces need. Do **not** port the prototype's stack (React 19 / Tailwind v4 / `motion` / `@google/genai`) or its mock-data-as-content approach.

## Ownership map (multi-root)

| Workstream | Owning repo | Where |
| :--- | :--- | :--- |
| WS-1 tokens, WS-2/3/4 components, WS-5 views, WS-7 animation, WS-9 extrapolation, **WS-10 coverage matrix** | `ed-tech-system` | `frontend/src/presentation/**`, `frontend/scripts/documented-routes.mjs`, `tests/e2e/visual/**` |
| WS-6 backend endpoints | `ed-tech-system-backend` | `supabase/migrations/**`, `services/**`, `API_ENDPOINTS.md`, contracts in `backend_cursor_log/` |
| WS-8 design enforcement | `ed-tech-system` | `scripts/ci-steps/**`, `scripts/ci.sh`, `scripts/quality-baselines.json`, `tests/scripts/**`, `tests/e2e/visual/**` |
| **WS-11 legacy deletion** | `ed-tech-system` (FE) + `ed-tech-system-backend` (cutover precondition) | `frontend/src/application/**`, `frontend/src/presentation/features/course-legacy/**`, `frontend/scripts/**`, `scripts/graph/**` |
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
| FE-403 | Toast system: bottom-right dark pill, ping dot, auto-dismiss | `templates/AppLayout.tsx` (`toastMessage`) | `presentation/shared/toast/` (new) | **done 2026-10-04 (BL-113)** — Zustand store, not context-in-component |
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

## WS-7 — Animation & motion language (`ed-tech-system`)

**Prototype evidence:** `motion` v12 is declared in the zip's `package.json` but **never imported** — all motion is CSS/Tailwind (`transition`×54, `transition-all`×46, `duration-200`×20, `animate-pulse`×13, `fade-in`×5, `zoom-in-95`×2, `scale-98`×2, `scale-105`×2, `slide-in-from-bottom-5`×1, `animate-spin`×3, `animate-ping`×3, `duration-300/500` sidebar & large-surface). Motion therefore ships as **tokens + utilities, no JS animation library** (closes D-3 with evidence).

### Motion spec (extracted from zip)

| Pattern | Spec (duration · easing · transform) | v2 source | Consumed by |
| :--- | :--- | :--- | :--- |
| `motion-transition-base` | 200ms · `cubic-bezier(0.4, 0, 0.2, 1)` · all | `card-transition` utility (zip `index.css`), 20× `duration-200` | Cards, buttons, nav items, chips — the default |
| `motion-hover-lift` | 200ms · base ease · `translateY(-2px)` + `shadow-md` | `hover:-translate-y-0.5 hover:shadow-md` on metric/teacher cards | `Card` `hoverEffect`, `MetricStatCard`, dashboard metric tiles |
| `motion-press` | 200ms · base ease · `scale(0.98)` while active | `active:scale-98` (Button base), `scale-95` on some CTAs | `Button` all variants, filter chips |
| `motion-hover-grow` | 200ms · base ease · `scale(1.05)` | `hover:scale-105` | Avatars, icon buttons, streak-day cells |
| `motion-modal-overlay` | 150ms · fade to `rgba(0,0,0,.6)` | `animate-in fade-in duration-150` | All Radix `Dialog` overlays (`CreateLessonModal`, `QuizGeneratorModal`, `WorkspaceModal`) |
| `motion-modal-panel` | 200ms · `zoom-in-95` + fade | `zoom-in-95` | Dialog panels |
| `motion-toast` | 200ms · `slide-in-from-bottom-5` + fade | toast in `AppLayout.tsx` | Toast system (FE-403) |
| `motion-live-pulse` | `animate-pulse` (2s loop) · opacity | in-progress amber dot, "pending review" red dot, ping toast dot (`animate-ping`) | `Badge` in-progress, `AiGradingQueue`, status pills |
| `motion-spinner` | `animate-spin` 1s loop | `Button` `isLoading` | `Button`, async CTAs |
| `motion-collapse` | 300ms · width/layout (`w-64 ⇄ w-20`) | `Sidebar.tsx` `transition-all duration-300` | Sidebar collapse (FE-401) |
| `motion-large` | 500ms · hero/paint-in | `duration-500` occurrences | `WeeklyStreakBanner` entrance polish |

| ID | Item | Target | Notes |
| :--- | :--- | :--- | :--- |
| FE-701 | Motion token file: `tokens/motion.css` with `--motion-duration-{fast,base,slow,large}` (150/200/300/500), `--motion-ease-standard: cubic-bezier(0.4,0,0.2,1)`, `--motion-lift`, `--motion-press` | `design-system/tokens/motion.css` (new) | Extends `effects.css` (FE-106), never raw durations in features |
| FE-702 | Motion utilities in `foundation/`: `.motion-lift`, `.motion-press`, `.card-transition` (compat name for the v2 utility), keyframes `pulse`, `ping`, `spin`, `slide-in-bottom`, `zoom-in` | `foundation/` + `tailwind.config` keyframes | Tailwind 3 `tailwindcss-animate`-equivalent subset, hand-rolled (no new dep) |
| FE-703 | Component motion wiring: press on `Button`, lift on `Card`, `zoom-in-95` dialog panels, slide-in toast, pulse dots on badges — as part of WS-2/3/4 items | WS-2/3/4 targets | Motion is part of each component's acceptance, not a later pass |
| FE-704 | `prefers-reduced-motion`: global media query collapses durations to `0.01ms` and disables loop animations (pulse/ping) | `foundation/` global CSS | Zip has **no** reduced-motion handling — product requirement on top of v2 |
| FE-705 | Motion budget: total animated surfaces per view stay lean (gate 15 complexity + `motion-*` class budget if abused) | `scripts/quality-baselines.json` | Only if counts justify — tighten only |

## WS-8 — Design-system & aesthetics enforcement (poka-yoke)

New **mechanical sensors**, built exactly like gate `00-content-freeze` / `14-quality`: pure grep/count, exit 1 on violation, budgets recorded in `scripts/quality-baselines.json` (tighten only). Per AGENTS.md #6, each new gate step lands **in the same PR as its test** under `tests/scripts/`, and profiles are updated only in `scripts/ci.sh` `profile_steps()` (single source).

| ID | Item | Sensor (draft) | Budget key | Profile |
| :--- | :--- | :--- | :--- | :--- |
| FE-801 | No raw colors outside `design-system/`: scan `frontend/src/features/**`, `presentation/shared/**`, `presentation/app/**` for `#[0-9a-fA-F]{3,8}` (CSS hex) and `rgb(a?)(` literals | new `scripts/ci-steps/20-design-system.sh` (hard_fail) | `maxRawHexOutsideDesignSystem` — **done 2026-10-04 (BL-114): raw-hex hard-fail + `maxRawPaletteClasses`/`maxArbitraryColorClasses` budgets seeded at 0, wired into `fast`+`core`** | `fast` |
| FE-802 | No arbitrary-value Tailwind (`bg-[…]`, `text-[…]`, `w-[90vw]`-style) outside `design-system/` — forces token aliases | same gate step (hard_fail) | `maxArbitraryValueClasses` → 0 | `fast` |
| FE-803 | Token-alias completeness: vitest test that every `--surface-*`/`--accent-*`/`--gradient-*`/`--motion-*` var in `tokens/*.css` is exposed through the Tailwind alias map (and vice-versa: no alias pointing at a removed var) | `tests/frontend/design-tokens.test.mjs` (new) | n/a (test, not budget) | `fast` (09) |
| FE-804 | Import-boundary for design system: ESLint `import/no-restricted-paths` — features import design-system via the **barrel** (`presentation/design-system` index), never deep internals (`design-system/components/Button/…`) | `10-lint.sh` extension (rule: validator change ⇒ same-PR gate + test) | **done 2026-10-04 (BL-114)** — `no-restricted-imports` in `eslint.config.js`; one deep import migrated to barrel | eslint error = gate red | `fast` (10) |
| FE-805 | Component API conformance: new atoms/molecules must live in `design-system/components/<Name>/` with variants sourced from token maps; one-off styled components in features are flagged by a naming/count sensor (`maxFeatureLevelStyleObjects` if needed) | `20-design-system.sh` (count) | seed → tighten | `fast` |
| FE-806 | Visual regression: Playwright **screenshot diffs** for shell, student dashboard, lesson workbench, teacher dashboard at 1440px + 390px, dark + light themes | `13-e2e.sh` extension (screenshot specs under `tests/e2e/visual/`) | diff threshold in `quality-baselines.json` (`maxVisualDiffPx`) | `deliver` only (Playwright never on develop stroke) |
| FE-807 | Reduced-motion compliance: vitest asserts the global stylesheet contains the `prefers-reduced-motion` collapse + a component test with `matchMedia` mock verifying loop animations off | `tests/frontend/` | n/a | `fast` (09) |
| FE-808 | Baseline ratchet discipline: `quality-baselines.json` gains only tighten entries; any new budget lands in the same commit as the code that could exceed it (quality-prevention §6.15) — PR template checklist line | docs + PR template | — | — |

**Gate wiring (WS-8, once):** add `20-design-system.sh` to `profile_steps()` in `scripts/ci.sh` (`fast` + `core`), document it in `scripts/ci-steps/README.md` + `.cursor/rules/gates.mdc` quick reference (docs-in-same-PR rule, DD-01), add its contract test in `tests/scripts/`, and pre-commit stays on gate 14 → extend pre-commit to include the new step only if it stays <1s.

---

## WS-9 — Extrapolation: unprototyped product pages (`ed-tech-system`)

The prototype covers 7 views; the live frontend has **more surfaces than the zip** (verified against `AppRouter.tsx` + `documented-routes.mjs`). These get the v2 language by **extrapolation**: every unprototyped surface is restyled through tokens + the nearest v2 analog component. WS-8 makes this enforceable automatically — FE-801/802 (no raw hex / no arbitrary classes) and FE-806 (visual regression) scan **all** of `frontend/src/**`, so extrapolated pages are held to the same aesthetic with no extra gates.

### Extrapolation contract (how to style anything the zip doesn't show)

1. **Find the nearest v2 analog** (table below). If two analogs conflict, the more recent/specific v2 pattern wins.
2. **Tokens only**: color, radius, elevation, motion come from `tokens/*.css` aliases — never invented per page.
3. **Compose, don't create**: use WS-2/3 components; a new one-off pattern requires a `design-system/` addition with its own item ID (no stealth components).
4. **Motion defaults**: base transition 200ms + hover lift/press from WS-7 spec; no page-specific timings.
5. **Layout rhythm**: `rounded-3xl` cards, `max-w-7xl`, `px-5..10 py-6..7`, 7:5 / 12-col grids as in `AppLayout`/`LessonDetailView`.
6. **`course-legacy/` gets no investment** — tokens cascade for free; no restyling work item (rule: `legacy:` files carry a deletion milestone, count may not grow).

### Coverage map — live page → v2 analogs

| Live surface (route) | Existing components | v2 analogs to apply | Item |
| :--- | :--- | :--- | :--- |
| **Catalog** `/` (+`?tab=`) | `CatalogRoute`, `CatalogTabBar`, `CourseCard`, `CatalogEmptyState`, score summary | `MetricStatCard` hero tiles (points summary), `Card` elevated + `hoverEffect` lift on course cards, `TabPill` for courses/content-map tabs, empty state as `Card` `tinted` | FE-901 |
| **Content map** `/?tab=content-map` | `MindMapCanvas` (d3), `MindMapNode`, `useMindMapZoom`, leaf actions | Canvas page bg `#f8fafc` token; node cards → `Card` `tinted` + status `Badge` (score tiers via FE-103); zoom controls → ghost icon-button cluster with `motion-press`; leaf actions as `TabPill`/`Button` `outline` | FE-902 |
| **Course experience** `/course/:courseId` | `CourseReadmePanel`, `CourseTabBar`, `CourseScoreSummary`, `LessonList`, `ProjectList`, `ProjectStatusBadge` | Readme → `Card` default with v2 prose rhythm; score rows → `ProgressBar` (v2 variants) + `Badge` `score`; lesson/project lists → `WeeklyActivityList` row language (hover-lift rows, status badges, chevron affordance); `ProjectStatusBadge` → v2 `Badge` variants | FE-903 |
| **Module experience** `/course/:courseId/module/:moduleId` | `ModuleShellLayout`, `ModuleContentsDrawer`, score summary | Drawer → sidebar-family treatment (tinted-light default, FE-101 palette); main column → `Card` container with `rounded-3xl`; drawer items → active-nav pill pattern from v2 `Sidebar` (active `blue-600` fill) | FE-904 |
| **Quiz flow** inside lesson workspace | `QuizHost`, `QuizSessionPanel`, `QuizQuestionView`, `QuizProgressBar`, `QuizResultsPanel` | **Direct hit — zip has `QuizOptionCard` + `TestResultItem`**: adopt selected/correct/incorrect card states verbatim; progress → v2 `ProgressBar`; results → `Badge` `score` + emerald/slate/rose tier mapping (80/50 thresholds already in `scoreTier`); retry CTA → `Button` `primary` with `motion-press` | FE-905 |
| **Project delivery** (file explorer, preview, run-answer, delivery panel) | `ProjectFileExplorer`, `FilePreview`, `ProjectDeliveryPanel`, `ProjectRunAnswerPanel`, `DeliveryPromptToolbar` | File explorer/preview → dark editor family (FE-101 `#0d1117` surface, `Fira Code` FE-107); delivery panel → `Card` + `ChecklistItem` (FE-305); submit CTA → `Button` `success`; toolbar → `TabPill` group | FE-906 |
| **Shell chrome** | `AppShell`, `AppTopBar` (language, Pomodoro, theme) | v2 has sidebar + top header; current FE is top-bar-only → **decision D-5** governs; Pomodoro popover → `Card` `tinted` + `TabPill` controls; `LanguageSelector`/`ThemeToggle` → v2 ghost/outline icon buttons | FE-907 |
| **course-legacy** | `LegacyCourseRoute`, `ContentReaderDialog` | **None** — no restyle investment; token cascade only | — (non-goal) |

| ID | Item | Depends on | Milestone |
| :--- | :--- | :--- | :--- |
| FE-901 | Catalog restyle (tiles, card lift, TabPill tabs) | WS-1, FE-204, FE-301, FE-206 | M3 — **done 2026-10-04 (BL-115)** |
| FE-902 | Content map restyle (canvas bg, node cards, zoom controls) | WS-1, FE-204, FE-103 | M3 — **done 2026-10-04 (BL-115, verified conformant)** |
| FE-903 | Course experience restyle (readme card, score rows, activity-row lists) | WS-1, FE-205, FE-202 | M3 — **done 2026-10-04 (BL-115)** |
| FE-904 | Module experience restyle (drawer + active pills + card column) | WS-1, FE-401 pattern | M3 — **done 2026-10-04 (BL-115)** |
| FE-905 | Quiz flow restyle (option cards, progress, results tiering) | FE-304, FE-205, FE-202 | M3 — **done 2026-10-04 (BL-115)** |
| FE-906 | Project delivery restyle (dark file surfaces, checklist, toolbar) | FE-101/107, FE-305 | M3 — **done 2026-10-04 (BL-115)** |
| FE-907 | Shell chrome reconciliation per D-5 (Pomodoro, language, theme into v2 chrome) | FE-401, FE-402, D-5 | M2 — **done 2026-10-04 (BL-112)** |

### Decision to add

| ID | Decision | Recommendation |
| :--- | :--- | :--- |
| D-5 | Shell chrome: v2 shows **persistent sidebar + slim top header**; live FE has **top bar only**. Two nav models can't both be primary. | Adopt v2 sidebar as primary nav (M2, FE-401) scoped to learner routes; keep the slim top bar for context + utilities (Pomodoro, language, theme, avatar) restyled to v2 — mirrors the v2 `TopHeader` slot. Catalog/content-map stay sidebar entries; no route changes required (`documented-routes.mjs` untouched) |
| D-6 | Legacy course experience (`structure='legacy'`): restyle or delete? | **Delete, not restyle.** It is already condemned: `legacy:` headers cite "Delete with estrategiaLegacy", POKAYOKE-PLAN Wave 5.2 owns the decommission, and `maxLegacyFiles` budget is 5 (currently **at** 5). WS-9 restyles only the hierarchy path (`CourseOverviewRoute`); WS-11 executes the deletion after M4. No v2 design work is spent on code with an expiry date |

---

## WS-10 — Complete screen coverage matrix

**Every screen that exists in the product frontend** (from `AppRouter.tsx`, route features, and modals) mapped to its adoption item. A screen with no row here doesn't exist; a row without an item ID is a roadmap bug. Status values: `prototyped` (zip has a direct counterpart), `extrapolated` (WS-9 analog mapping), `unprototyped-new` (v2-only screens, FE build from scratch).

| # | Screen / surface | Route / mount point | Status | Adoption items |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Catalog — courses tab | `/` | extrapolated | FE-901 |
| 2 | Catalog — content-map tab | `/?tab=content-map` | extrapolated | FE-902 |
| 3 | Course overview (hierarchy) | `/course/:courseId` | extrapolated | FE-903 |
| 4 | Module experience | `/course/:courseId/module/:moduleId` | extrapolated | FE-904 |
| 5 | Lesson workspace — theory/explanation | `/course/:courseId/module/:moduleId/lesson/:lessonId` | prototyped | FE-502 (+FE-302, FE-407) |
| 6 | Lesson workspace — quiz session + results | same route | prototyped | FE-905, FE-304 |
| 7 | Lesson workspace — project delivery (explorer/preview/submit) | same route | extrapolated (dark family) | FE-906 |
| 8 | Shell — top bar + utilities (Pomodoro, language, theme) | `AppLayout` | extrapolated | FE-907, FE-412 |
| 9 | Shell — sidebar nav (new, per D-5) | `AppLayout` | unprototyped-new | FE-401 |
| 10 | Course-legacy flat-tab experience | `/course/:courseId` when `structure='legacy'` | **no adoption — deleted in WS-11** | — |
| 11 | Course-legacy content reader dialog | `AppLayout` mount when legacy course open | **no adoption — deleted in WS-11** | — |
| 12 | Teacher dashboard | new route (FE-503) | prototyped | FE-503, FE-408..411 |
| 13 | Role select | new route (FE-504) | prototyped | FE-504 |
| 14 | Weekly plan | new route (FE-505) | prototyped | FE-405, FE-409, FE-505 |
| 15 | Students roster | new route (FE-507) | prototyped | FE-507, FE-306 |
| 16 | Resources | new route (FE-506) | prototyped | FE-303, FE-506 |
| 17 | Toasts | global (`AppLayout`) | prototyped | FE-403 |
| 18 | Dialogs: create-lesson / quiz-generator / workspace | global (`AppLayout` slots) | prototyped | FE-411 |
| 19 | Async route boundary / error panels | route wrappers | extrapolated | FE-901 pattern (`Card` `tinted` empty/error state) — covered inside FE-901..907 restyles |

**Coverage rule:** FE-806 visual regression baselines are recorded **per screen in this table** — a screen without a baseline at M5 blocks `gate:deliver` (the check iterates this matrix, which lives in `tests/e2e/visual/screens.mjs` as the machine-readable mirror).

---

## WS-11 — Legacy deletion (post-implementation decommission)

**Governs the removal of the legacy course experience** after the v2 adoption is complete. Aligned with POKAYOKE-PLAN Wave 5.2 (PK-68) — this section does not redefine the milestone, it schedules the FE-design side of it. Core rule: **the legacy count may not grow** (`maxLegacyFiles: 5` in `quality-baselines.json`, currently at 5 — the next `legacy:` file needs prior budget tightening).

### Current legacy inventory (measured 2026-10-04 — exactly 5/5 budget)

| File | Marker | Consumer |
| :--- | :--- | :--- |
| `application/navigation/estrategiaLegacy.ts` | `legacy:` | `useAppNavigation` (hooks) |
| `application/navigation/tiposNavegacaoCurso.ts` | `legacy:` (PT-named contracts) | `estrategiaLegacy`, `estrategiaHierarquia` |
| `presentation/features/course-legacy/LegacyCourseRoute.tsx` | `legacy:` | `CourseExperienceRoute` (flat-course branch) |
| `presentation/features/course-legacy/ContentReaderDialog.tsx` | `legacy:` | `AppLayout` (mounts when legacy course open) |
| `scripts/graph/graph-index.mjs` | `legacy:` shim | catalog/graph generator (CJS import shim) |

Plus unmarked compat that dies with it: `application/stores/legacy/` (`courseExperienceStore`, `contentReaderStore`), `application/navigation/estrategiaHierarquia.ts` + test (PT-named pair), the `structure: "legacy"` branch in `CourseExperienceRoute.tsx` + the conditional in `AppLayout.tsx`, and the `structure: "legacy"` fallback in `frontend/scripts/generate-static-catalog.mjs`.

### Preconditions (all must hold before any deletion stroke)

1. **M4 complete** — teacher flow live; catalog/course-overview restyled (FE-903) so no screen depends on legacy visuals.
2. **Zero legacy courses in staging + production**: `select count(*) from courses where structure = 'legacy' and deleted_at is null` = **0**, or a data migration (`update courses set structure='hierarchy'`) applied and verified. Backend owns the migration (contract-to-SQL skill, expand-first); FE verifies via catalog before deleting UI guards.
3. **Coverage substitution**: FE-806 visual baselines for screens 1–4 exist (the legacy screens 10–11 are removed from the matrix in the same PR that deletes them).
4. **Backend cutover shipped**: `generate-static-catalog.mjs` no longer emits `structure: "legacy"` (Wave 5.2 catalog-generator compat) — otherwise the FE guard deletion breaks catalog generation.

### Deletion strokes (each = one PR, gate:fast → gate:core)

| ID | Item | Files touched | Sensor after |
| :--- | :--- | :--- | :--- |
| LD-1 | Catalog generator + graph shim first (support-side, no UI impact): remove `structure: "legacy"` fallback, inline `graph-index.mjs` CJS shim | `generate-static-catalog.mjs`, `scripts/graph/graph-index.mjs` (delete) | `legacy:` count 5 → **3** |
| LD-2 | FE guards + stores: delete flat-course branch in `CourseExperienceRoute`, conditional mount in `AppLayout`, `stores/legacy/*` | `CourseExperienceRoute.tsx`, `AppLayout.tsx`, `application/stores/legacy/` (delete) | count 3 → **2**; E2E navigation spec updated (legacy flat course case removed) |
| LD-3 | Legacy route + dialog: delete `course-legacy/` folder; `CourseExperienceRoute` renders `CourseOverviewRoute` unconditionally; `isHierarchyCourse` collapses to a type check | `course-legacy/**` (delete), `CourseExperienceRoute.tsx`, `documented-routes.mjs` (comment only — route path unchanged) | count 2 → **0** — `maxLegacyFiles` budget **tightened 5 → 0** in the same commit (PK-64 ratchet) |
| LD-4 | PT-named navigation contracts: delete `estrategiaLegacy.ts`, `tiposNavegacaoCurso.ts`, `estrategiaHierarquia.ts` (+ test); `useAppNavigation` uses the hierarchy strategy directly with English names (PK-71 rename rides this stroke, not before) | `application/navigation/**` (3 files deleted), `useAppNavigation.ts` | count stays 0; import-boundary lint (FE-804) green |

### Post-deletion invariants (permanently wired)

- `maxLegacyFiles: 0` in `quality-baselines.json` — any future `legacy:` marker fails gate 14; new debt needs an explicit budget change (tighten-only rule forbids silent reintroduction).
- `courses.structure` CHECK constraint drop (`'legacy'` enum value) is a **backend Wave 5.2** item — expand/contract discipline: FE deletes first, backend contracts the column in a later PR.
- This WS-10 matrix becomes the permanent screen census: new screens append a row + baseline, enforced by FE-806's matrix check.

---

## Execution order & milestones

```text
M1 Foundations   FE-101..109 (tokens) + FE-701/702 (motion tokens) → FE-201..206 (atoms)
                 └─ seed WS-8 budgets (FE-801/802 baseline counts) in the same commit as first feature imports
M2 Shell         FE-401..403, FE-412 + BE-0 + FE-307 + FE-907 (chrome reconciliation per D-5)
                 └─ FE-804 import-boundary lint live here
M3 Student flow  FE-404/405, FE-501, FE-502 (+FE-302..306, 406/407)   # needs BE-1..3, BE-5
                 ├─ FE-801/802 budgets ratcheted to 0 — raw hex/arbitrary classes forbidden from here on
                 └─ FE-901..906 extrapolation restyles (catalog, content map, course, module,
                    quiz, project delivery) — token cascade + analog components, no new gates
M4 Teacher flow  FE-408..411, FE-503 (needs BE-4) + FE-504..508
M5 Polish        FE-704/707 reduced-motion verified, FE-806 visual baselines recorded
                 for every screen in the WS-10 matrix (incl. extrapolated pages),
                 budgets tighten, E2E via gate:deliver, drop mockData equivalents
M6 Decommission  WS-11 legacy deletion (LD-1..LD-4) — after backend cutover +
                 zero `structure='legacy'` rows; ends with maxLegacyFiles 5 → 0 (Wave 5.2)
```

**Definition of done (repo law):** `npm run gate:fast` exit 0 per stroke; `gate:core` before PR; `gate:deliver` at M5 (now including visual regression FE-806); `STATUS: complete` in `.gates/last-run/summary.json` is the only stop signal. Markdown checkboxes here are **context, never a verdict**.

## Explicit non-goals

- No React 19 / Tailwind v4 / `motion` / `@google/genai` adoption (D-3 — confirmed by WS-7 evidence: the zip declares `motion` but never imports it).
- No `BrowserChromeBar` (prototype chrome simulation).
- No client-held AI keys; no content authored as repo files (`course/**` stays deleted).
- No new `legacy:` files; `quality-baselines.json` budgets tighten only.
- No JS animation library; motion is CSS tokens + utilities only (FE-701/702).
- No deep imports into `design-system/components/**` from features — barrel imports only (FE-804).
- No restyle work on `course-legacy/` — it is deleted in WS-11 (LD-2/LD-3), never restyled (D-6).
- No extrapolated page invents new tokens or one-off patterns — analog mapping only (WS-9 contract); new patterns require a `design-system/` item in this roadmap.
- `maxLegacyFiles` budget may only move 5 → 0 (in the LD-3 commit) — never upward (quality-prevention §6.15).

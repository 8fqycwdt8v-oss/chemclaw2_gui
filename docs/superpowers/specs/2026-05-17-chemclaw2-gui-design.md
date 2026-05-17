# chemclaw2_gui — Design

> **⚠️ SUPERSEDED (2026-05-17 — same day, later session).**
> This document describes a Next.js 15 + Tiptap direction that was reconsidered after
> further research into Streamlit's 2026 capabilities (streamlit-ketcher, streamlit-markdown,
> st.fragment, st.login OIDC). The approved direction is **Streamlit GUI + FastAPI BFF**
> with a **markdown-source wiki** and **Microsoft Entra ID** auth. See the current `CLAUDE.md`
> and `README.md` in the repo root for the actual design. This file is kept only for
> historical reference and should not be used to guide implementation.

**Date:** 2026-05-17
**Status:** Superseded
**Repo:** https://github.com/8fqycwdt8v-oss/chemclaw2_gui (empty, exists)
**Consumes:** https://github.com/8fqycwdt8v-oss/chemclaw2 (BE, untouched)

## 1. Purpose

Build the user-facing web GUI that consumes the existing chemclaw2 API contract.
The current chemclaw2 monorepo has API routes (`/api/chat`, `/api/search`, `/api/wiki`, `/api/health`),
auth, and one `WikiEditor.tsx` component — but no actual chat UI, no wiki reader,
no wiki list, no search UI. This repo is where those surfaces get built. The backend
is not modified.

## 2. Non-goals

- Modifying anything in the chemclaw2 monorepo.
- Re-implementing API endpoints; the FE is a consumer.
- A typed SDK package, monorepo conversion, or shared types package. Defer until measured.
- Admin/health dashboards, citation-pill Tiptap extension, real-time collab,
  in-browser RDKit, structure sketcher. Each is a known follow-up.
- SMILES → fingerprint conversion in the FE (deferred; users paste raw 2048-bit
  fingerprint strings in v1, full SMILES UX recovered later via a chemclaw2-side
  helper endpoint).

## 3. Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | Next.js 15 (App Router) | Mirrors chemclaw2 stack 1:1; lifts `WikiEditor.tsx` verbatim |
| Language | TypeScript 5.7 (strict) | Matches chemclaw2 `tsconfig.base.json` |
| UI | React 19 | Matches chemclaw2 |
| Styling | Tailwind 4 (`@import "tailwindcss"`) | Matches chemclaw2 `globals.css` |
| Editor | Tiptap 3.x (StarterKit + Placeholder) | Required to read/write the ProseMirror JSON stored by chemclaw2 |
| Auth | `@clerk/nextjs` (middleware + hooks) | chemclaw2 BE accepts both Clerk cookie and `Authorization: Bearer <JWT>`; FE sends Bearer JWT cross-origin |
| Deployment | Fly.io (standalone Next.js output) | Matches chemclaw2 deployment surface |
| Package mgr | pnpm 9.15.0 | Same as chemclaw2 |
| Node | 22 LTS | Same as chemclaw2 |

### Streamlit was evaluated and rejected

The dominant blocker is that chemclaw2 stores wiki pages as Tiptap/ProseMirror
JSON documents. No Python rich-block editor reads/writes that schema. Available
substitutes (streamlit-quill, st.markdown after lossy conversion, custom Tiptap
component wrapping React inside Streamlit) all either corrupt content or
re-introduce React. The wiki is one of two dominant surfaces, so this isn't a
peripheral concern. Streamlit's other costs (no Clerk integration, awkward
rerun model for SSE chat, deep-link friction, splits team across TS + Python
for ~3 engineers) reinforce the decision. Streamlit may still be the right
tool for a future Python chemist-scratchpad utility but not for this repo.

## 4. FE ↔ BE contract

The FE talks to chemclaw2 BE via cross-origin HTTPS with a Clerk session JWT
on every request. No FE proxy routes.

```
Browser (chemclaw2_gui on Fly)
   |
   |  await getClerkToken()        # @clerk/clerk-react
   |  fetch(API_BASE + path, { headers: { Authorization: `Bearer ${jwt}` }})
   v
chemclaw2 BE on Fly
   clerkMiddleware -> verifies Bearer JWT -> routes
```

Single env var: `NEXT_PUBLIC_CHEMCLAW2_API=https://chemclaw2.fly.dev`
(plus the standard Clerk publishable + secret keys).

### Endpoints consumed

| Endpoint | Method | Body / Params | FE caller |
|---|---|---|---|
| `/api/chat` | POST | `{prompt, sessionId?}` → SSE | `chat()` |
| `/api/search` | GET | `?q=&limit=` | `searchText()` |
| `/api/search` | POST | `{fingerprint_bits}` or `{rxn_fingerprint_bits}` | `searchByFingerprint()` |
| `/api/wiki` | GET | `?cursor=` or `?q=` | `listWiki()`, `searchWiki()` |
| `/api/wiki` | POST | `{slug,title,content,contentText,citations?}` | `createWiki()` |
| `/api/wiki/[slug]` | GET | – | `getWiki()` |
| `/api/wiki/[slug]` | PUT | `{title?,content?,contentText?,citations?}` | `updateWiki()` |
| `/api/health` | GET | – | not used in UI (BE health check is internal) |

### CORS prerequisite (chemclaw2-side change, NOT done in this repo)

chemclaw2 must respond to cross-origin requests from the GUI origin with at minimum:

```
Access-Control-Allow-Origin: https://chemclaw2-gui.fly.dev   (or whatever the deployed origin is)
Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400
```

…and the existing CSP `connect-src` in `apps/web/next.config.ts` does not constrain
the BE's outgoing CORS, but chemclaw2's middleware needs OPTIONS preflight handling
added. This is the **one external prerequisite** for the GUI to function in
production. Documented in README.md as a "before-you-deploy" note.

## 5. Surfaces (v1)

### 5.1 Auth shell
- `app/(auth)/sign-in/[[...sign-in]]/page.tsx` — `<SignIn />` drop-in (lifted from chemclaw2)
- `app/(auth)/sign-up/[[...sign-up]]/page.tsx` — `<SignUp />` drop-in
- `middleware.ts` — `clerkMiddleware` protecting everything except `/sign-*` and static assets
- `app/(app)/layout.tsx` — top nav (Chat | Wiki | Search) + `<UserButton />`

### 5.2 Chat (`/chat`)
- Composer: `<textarea>` + Send button, Enter-to-send / Shift-Enter newline
- Session id: generated on first message via `crypto.randomUUID()`, persisted in `sessionStorage` so refresh continues the session
- Stream rendering: parses SSE events from `/api/chat`; renders assistant text deltas, tool-call summaries, errors; stops on `[DONE]`
- Error events from BE surface their `errorId` for support correlation
- Out of scope for v1: message history list across sessions (chemclaw2 has no list-sessions endpoint), markdown rendering of assistant text (use whitespace-pre-wrap)

### 5.3 Wiki

| Route | UI |
|---|---|
| `/wiki` | List view: search box (calls `?q=`), paginated list (`?cursor=`), "New page" button |
| `/wiki/[slug]` | Read view: Tiptap in `editable:false` rendering `page.content`, header with title/updated-at, "Edit" link |
| `/wiki/[slug]/edit` | Edit view: lifted `WikiEditor`, saves via `PUT /api/wiki/[slug]` |
| `/wiki/new` | Slug + title inputs + `WikiEditor`, saves via `POST /api/wiki` |

`WikiEditor.tsx` is **lifted verbatim** from chemclaw2. Same renderer used for read and write (just `editable:false` for read).

### 5.4 Search (`/search`)
- Tab 1: text search → `GET /api/search?q=` → wiki hits list (each links to `/wiki/[slug]`)
- Tab 2: paste 2048-bit fingerprint → `POST /api/search` with `{fingerprint_bits}` → compound similarity results table
- Tab 3: paste 2048-bit reaction fingerprint → `POST /api/search` with `{rxn_fingerprint_bits}` → reaction similarity results table
- Validation: tabs 2/3 reject anything not matching `/^[01]{2048}$/`

### 5.5 Error / not-found
- Lifted from chemclaw2: `app/error.tsx`, `app/global-error.tsx`, `app/not-found.tsx`

## 6. Repo layout

```
chemclaw2_gui/
├── app/
│   ├── layout.tsx                # ClerkProvider + html/body
│   ├── globals.css               # @import "tailwindcss"
│   ├── page.tsx                  # redirect("/chat")
│   ├── error.tsx
│   ├── not-found.tsx
│   ├── global-error.tsx
│   ├── (auth)/
│   │   ├── sign-in/[[...sign-in]]/page.tsx
│   │   └── sign-up/[[...sign-up]]/page.tsx
│   └── (app)/
│       ├── layout.tsx            # nav + UserButton
│       ├── chat/page.tsx
│       ├── wiki/page.tsx
│       ├── wiki/[slug]/page.tsx
│       ├── wiki/[slug]/edit/page.tsx
│       ├── wiki/new/page.tsx
│       └── search/page.tsx
├── components/
│   ├── shell/{Nav,UserMenu}.tsx
│   ├── chat/{ChatComposer,MessageList,AgentEventView}.tsx
│   ├── wiki/{WikiEditor,WikiReader,WikiList}.tsx
│   └── search/{TextSearchPanel,FingerprintPanel}.tsx
├── lib/
│   ├── api.ts                    # fetch wrapper + typed endpoint methods
│   ├── sse.ts                    # SSE parser for chat
│   └── types.ts                  # WikiPage, AgentEvent, SearchResult — hand-mirror BE shapes
├── middleware.ts                 # clerkMiddleware
├── next.config.ts                # standalone, transpile @tiptap/*, CSP, security headers
├── package.json
├── tsconfig.json
├── eslint.config.mjs
├── .env.example
├── .gitignore
├── Dockerfile
├── fly.toml
├── README.md
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-17-chemclaw2-gui-design.md   (this file)
```

## 7. Testing & verification

- Typecheck: `pnpm typecheck` (`tsc --noEmit`)
- Lint: `pnpm lint`
- Manual: dev server up, sign in via Clerk, send a chat message and watch the stream, list+create+edit a wiki page, run a text search, paste a known 2048-bit fingerprint and confirm POST round-trips.
- No unit tests in v1: each surface is a thin shell over a single API endpoint. Add tests when a non-trivial transformation (e.g., SSE delta accumulation) develops bugs.

## 8. Deployment

- Mirrors chemclaw2: multi-stage Dockerfile, `output: 'standalone'`, Fly.io app
  named `chemclaw2-gui`, `/` health check (since this is a UI app — no
  `/api/health` route exists in the GUI itself; the redirect-to-chat returns 200).
- One Fly secret set: `NEXT_PUBLIC_CHEMCLAW2_API`, `CLERK_SECRET_KEY`,
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL`,
  `NEXT_PUBLIC_CLERK_SIGN_UP_URL`.
- Identical CSP/headers block to chemclaw2's `next.config.ts`, with
  `connect-src` extended to include the chemclaw2 API origin and Clerk.

## 9. Risks / known issues

- **CORS on chemclaw2 BE is a deployment prerequisite.** README will spell this out; not blocking local dev because Next dev server can proxy via `next.config.ts` `rewrites` for `dev` only (kept simple, documented).
- **SSE rendering of Claude Agent SDK events is loose-typed.** The BE forwards raw SDK event objects; we render `event.type` and known fields, fall back to a JSON-stringified collapse for unknown event types. Acceptable.
- **No optimistic concurrency on wiki edits in v1.** chemclaw2's BE has the version trigger but does not surface it via API; FE will not detect conflicting edits. Logged as a follow-up.
- **`crypto.randomUUID` requires secure context.** True in production, true on `localhost`. Safe.

## 10. Out-of-scope follow-ups (logged, not done)

- SMILES-in-the-browser via chemclaw2-side `compute_morgan_fp` helper endpoint
- Citation pill Tiptap node + reader rendering
- Conflict-aware wiki saves (needs BE to expose version)
- Markdown rendering of assistant chat text (currently `whitespace-pre-wrap`)
- Sub-agent / pause-for-clarification UI flows
- Python "chemist scratchpad" Streamlit sibling app

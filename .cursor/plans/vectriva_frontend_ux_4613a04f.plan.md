---
name: Vectriva Frontend UX
overview: Build a Next.js frontend with an admin dashboard for tenant configuration and an embeddable chat widget for customers, consuming the existing FastAPI backend.
todos: []
isProject: false
---

# Vectriva Frontend UX Plan

## Architecture Overview

```mermaid
flowchart TB
    subgraph AdminDashboard [Admin Dashboard - Next.js]
        Login[Login/Register]
        TenantSelect[Tenant Selector]
        Documents[Document Management]
        Config[Chatbot Config]
        Integrations[Google Calendar]
        APIKeys[API Key Management]
        Conversations[Conversation History]
    end

    subgraph Widget [Embeddable Chat Widget]
        ChatUI[Chat Interface]
        EmbedScript[Embed Script]
    end

    subgraph Backend [FastAPI Backend]
        AuthAPI[/api/auth]
        TenantAPI[/api/tenants]
        DocAPI[/api/tenants/:id/documents]
        ConfigAPI[/api/tenants/:id/config]
        IntAPI[/api/tenants/:id/integrations]
        ChatAPI[/api/chat]
    end

    Login --> AuthAPI
    TenantSelect --> TenantAPI
    Documents --> DocAPI
    Config --> ConfigAPI
    Integrations --> IntAPI
    ChatUI --> ChatAPI
    EmbedScript --> ChatUI
```



---

## 1. Project Structure

Create `frontend/` at project root (sibling to `src/`, `scripts/`):

```
frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx
│   ├── page.tsx            # Landing → redirect to login or dashboard
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx      # Sidebar, tenant selector
│   │   ├── page.tsx        # Overview / redirect to first tenant
│   │   └── [tenantId]/
│   │       ├── documents/
│   │       ├── config/
│   │       ├── integrations/
│   │       ├── api-keys/
│   │       └── conversations/
│   └── embed/
│       └── widget/         # Widget build output
├── components/
│   ├── ui/                 # Shadcn-style primitives
│   ├── dashboard/
│   └── widget/             # Chat widget components
├── lib/
│   ├── api.ts              # Fetch wrapper, auth headers
│   ├── auth.ts             # Token storage, refresh
│   └── types.ts            # API response types
├── public/
│   └── embed.js            # Standalone widget script for embedding
└── package.json
```

---

## 2. Admin Dashboard

### 2.1 Auth Flow

- **Pages**: `/login`, `/register`
- **Storage**: `localStorage` for `access_token`, `refresh_token`, `user_id`
- **API**: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`
- **Middleware**: Protect `/dashboard/`*; redirect unauthenticated to `/login`
- **Token refresh**: Intercept 401, call refresh, retry request

### 2.2 Layout & Tenant Selection

- **Layout**: Sidebar with nav: Documents, Config, Integrations, API Keys, Conversations
- **Tenant selector**: Dropdown at top; `GET /api/tenants` to list; store selected `tenantId` in URL (`/dashboard/[tenantId]/...`)
- **Create tenant**: Modal or page; `POST /api/tenants` with `{name, timezone}`

### 2.3 Documents

- **List**: `GET /api/tenants/{tenantId}/documents` — table with name, type, status, chunk_count, actions
- **Upload**: Drag-and-drop or file picker; `POST /api/tenants/{tenantId}/documents` (multipart)
- **Status**: Poll or show status badge (queued → processing → indexed | failed)
- **Chunks**: `GET /api/tenants/{tenantId}/documents/{docId}/chunks` — expandable list
- **Delete**: `DELETE /api/tenants/{tenantId}/documents/{docId}`

### 2.4 Chatbot Config

- **Fetch**: `GET /api/tenants/{tenantId}/config`
- **Update**: `PATCH /api/tenants/{tenantId}/config` (partial)
- **Fields**:
  - Persona: name, tone (professional/friendly/casual), custom instructions
  - Models: LLM provider/model, Embedding provider/model — use `GET /api/models/providers` and `GET /api/models/embeddings` for dropdowns
  - Business hours: JSON editor or day/time blocks
  - Escalation: failure count, negative sentiment toggle, email
  - Widget: primary color picker, position (bottom-right/left), welcome message

### 2.5 Integrations (Google Calendar)

- **Status**: `GET /api/tenants/{tenantId}/integrations/google/status`
- **Connect**: `GET /api/tenants/{tenantId}/integrations/google/auth-url` → redirect user to `auth_url`
- **Callback**: Backend handles `POST /api/integrations/google/callback`; redirect_uri points to a Next.js route that receives `?code=...&state=...` and POSTs to backend, then redirects to integrations page
- **Calendars**: `GET /api/tenants/{tenantId}/integrations/google/calendars` — list, select one
- **Set calendar**: `PUT /api/tenants/{tenantId}/integrations/google/calendar` with `{calendar_id}`
- **Disconnect**: `DELETE /api/tenants/{tenantId}/integrations/google`

### 2.6 API Keys

- **List**: `GET /api/tenants/{tenantId}/api-keys` — masked keys
- **Create**: `POST /api/tenants/{tenantId}/api-keys` with `{name}` — show full key once in modal (copy button)
- **Revoke**: `DELETE /api/tenants/{tenantId}/api-keys/{keyId}`

### 2.7 Conversations

- **List**: `GET /api/tenants/{tenantId}/conversations?page=1&page_size=20` — table with customer, message count, escalated, dates
- **Detail**: `GET /api/tenants/{tenantId}/conversations/{convId}` — full message thread
- **Tool calls**: `GET /api/tenants/{tenantId}/conversations/{convId}/tool-calls`
- **Retrievals**: `GET /api/tenants/{tenantId}/conversations/{convId}/retrievals`

### 2.8 Embed Code

- **Section** in Config or dedicated page: display a script tag and config snippet
- **Format**: `<script src="https://your-domain.com/embed.js" data-api-key="vect_live_xxx"></script>`
- **Widget URL**: `https://your-domain.com/embed` or configurable base URL

---

## 3. Embeddable Chat Widget

### 3.1 Build Output

- **Option A**: Next.js route `/embed` renders the widget; embed script loads an iframe pointing to it
- **Option B**: Separate Vite/React build for `embed.js` — smaller bundle, no Next.js runtime
- **Recommendation**: Option A for simplicity; single Next.js app serves both dashboard and widget

### 3.2 Widget Behavior

- **Trigger**: Floating button (position from config: bottom-right/left)
- **Expand**: Chat panel with welcome message
- **Messages**: User types → `POST /api/chat` with `X-API-Key`, `message`, `customer_email` (optional), `conversation_id` (for continuity)
- **Streaming**: Current API returns full response; consider adding SSE later for streaming
- **Styling**: `primary_color` from tenant config (or default)
- **Escalation**: Show "We've escalated to a human" when `is_escalated: true`

### 3.3 Embed Script

- **Minimal script** (`public/embed.js` or generated):
  - Reads `data-api-key` from script tag
  - Injects floating button + iframe/div
  - Iframe src: `https://app-url/embed?key=xxx` (or pass key via postMessage for security)
- **CORS**: Backend already has CORS; ensure `allow_origins` includes embed domains or `*` for dev

---

## 4. Tech Stack Details


| Layer      | Choice                                                                        |
| ---------- | ----------------------------------------------------------------------------- |
| Framework  | Next.js 15 (App Router)                                                       |
| Language   | TypeScript                                                                    |
| Styling    | Tailwind CSS                                                                  |
| Components | shadcn/ui (Radix primitives)                                                  |
| Forms      | React Hook Form + Zod                                                         |
| State      | React Query (TanStack Query) for server state; Zustand for UI state if needed |
| HTTP       | `fetch` with custom wrapper in `lib/api.ts`                                   |


---

## 5. Environment & API Base

- **Env**: `NEXT_PUBLIC_API_URL=http://localhost:8000` (or production URL)
- **API base**: All requests to `process.env.NEXT_PUBLIC_API_URL`
- **Auth header**: `Authorization: Bearer ${access_token}` for dashboard
- **API key header**: `X-API-Key: ${key}` for chat (widget)

---

## 6. OAuth Callback Handling

Backend `GOOGLE_REDIRECT_URI` must match. Two options:

1. **Backend callback**: `http://localhost:8000/api/integrations/google/callback` — Google redirects here with `?code=...&state=...`. Backend must handle GET (OAuth uses GET for redirect). Check backend: if it expects POST, we need a Next.js route that receives the redirect, extracts code/state, POSTs to backend, then redirects to dashboard.
2. **Next.js callback route**: `app/(dashboard)/[tenantId]/integrations/callback/page.tsx` — receives `?code=...&state=...`, calls backend `POST /api/integrations/google/callback` with `{code, state}`, then redirects to integrations page. In this case, `GOOGLE_REDIRECT_URI` would be `http://localhost:3000/dashboard/{tenantId}/integrations/callback` — but tenantId is in state, so we could use `http://localhost:3000/integrations/callback` and pass full state. Backend parses `state` as `tenant_id:token`.

**Recommendation**: Keep backend as callback URL (`http://localhost:8000/api/integrations/google/callback`). Google OAuth redirect is a GET request; backend must accept GET and extract `code` and `state` from query params. If backend currently expects POST body, add a GET handler that reads query params and processes the same way.

---

## 7. Implementation Order

1. **Scaffold** — Next.js app, Tailwind, shadcn, `lib/api.ts`, `lib/auth.ts`
2. **Auth** — Login, Register, token storage, protected layout
3. **Tenant selection** — List tenants, create tenant, URL-based tenantId
4. **Documents** — List, upload, status, chunks, delete
5. **Config** — Full config form with model dropdowns
6. **Integrations** — Connect Calendar, select calendar, disconnect
7. **API Keys** — Create, list, revoke, copy key
8. **Conversations** — List, detail, tool calls, retrievals
9. **Embed code** — Config section with script snippet
10. **Widget** — Floating button, chat UI, POST to chat API
11. **Embed script** — Minimal loader for third-party sites

---

## 8. Key Files to Create


| File                                                         | Purpose                               |
| ------------------------------------------------------------ | ------------------------------------- |
| [frontend/lib/api.ts]                                        | Fetch wrapper, auth headers, base URL |
| [frontend/lib/auth.ts]                                       | Token get/set/refresh, logout         |
| [frontend/app/(auth)/login/page.tsx]                         | Login form                            |
| [frontend/app/(auth)/register/page.tsx]                      | Register form                         |
| [frontend/app/(dashboard)/layout.tsx]                        | Sidebar, tenant selector              |
| [frontend/app/(dashboard)/[tenantId]/documents/page.tsx]     | Document list + upload                |
| [frontend/app/(dashboard)/[tenantId]/config/page.tsx]        | Config form                           |
| [frontend/app/(dashboard)/[tenantId]/integrations/page.tsx]  | Calendar connect                      |
| [frontend/app/(dashboard)/[tenantId]/api-keys/page.tsx]      | API key management                    |
| [frontend/app/(dashboard)/[tenantId]/conversations/page.tsx] | Conversation list + detail            |
| [frontend/app/embed/page.tsx]                                | Widget UI (iframe target)             |
| [frontend/public/embed.js]                                   | Embed script                          |


---

## 9. Backend Adjustments (if needed)

- **CORS**: Ensure `allow_origins` includes `http://localhost:3000` for dev
- **OAuth callback**: Verify backend accepts GET with query params for Google redirect
- **Widget endpoint**: Chat API already supports `X-API-Key`; no changes needed


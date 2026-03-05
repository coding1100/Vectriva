# Vectriva Frontend

Next.js 15 frontend for the Vectriva platform, including an admin dashboard and embeddable chat widget.

## Features

### Admin Dashboard
- **Authentication**: Login, registration, JWT token management with auto-refresh
- **Tenant Management**: Multi-tenant support with tenant selector and creation
- **Document Management**: Upload, list, view chunks, and delete documents
- **Configuration**: Full chatbot configuration (persona, models, escalation, widget)
- **Integrations**: Google Calendar OAuth connection and calendar selection
- **API Keys**: Create, view, and revoke API keys for widget embedding
- **Conversations**: View conversation history, messages, tool calls, and RAG retrievals
- **Embed Code**: Copy-paste embed code with API keys

### Embeddable Widget
- **Floating button**: Customizable position and color
- **Chat interface**: Message history, real-time responses
- **Customization**: Primary color, welcome message via config

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **Components**: shadcn/ui (Radix primitives)
- **Forms**: React Hook Form + Zod validation
- **State Management**: TanStack Query (React Query) for server state
- **HTTP Client**: Custom fetch wrapper with auth handling

## Getting Started

### Prerequisites

- Node.js 18+ (or compatible with Next.js 15)
- Backend API running at `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/          # Login page
│   │   └── register/       # Registration page
│   ├── (dashboard)/
│   │   ├── layout.tsx      # Protected layout with sidebar
│   │   ├── page.tsx        # Dashboard redirect
│   │   ├── create-tenant/  # Tenant creation
│   │   └── [tenantId]/
│   │       ├── documents/  # Document management
│   │       ├── config/     # Chatbot configuration
│   │       ├── integrations/ # Google Calendar
│   │       ├── api-keys/   # API key management
│   │       └── conversations/ # Conversation history
│   ├── embed/
│   │   └── page.tsx        # Embeddable widget UI
│   ├── layout.tsx          # Root layout with providers
│   └── page.tsx            # Landing page (redirect)
├── components/
│   ├── ui/                 # shadcn/ui components
│   ├── dashboard/
│   │   ├── sidebar.tsx     # Navigation sidebar
│   │   └── tenant-selector.tsx
│   └── providers.tsx       # React Query provider
├── lib/
│   ├── api.ts              # HTTP client with auth
│   ├── auth.ts             # Token management
│   ├── types.ts            # TypeScript types
│   └── utils.ts            # Utility functions
└── public/
    └── embed.js            # Widget embed script
```

## API Integration

The frontend consumes the following backend endpoints:

### Authentication
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`

### Tenants
- `GET /api/tenants`
- `POST /api/tenants`
- `GET /api/tenants/{tenant_id}/config`
- `PATCH /api/tenants/{tenant_id}/config`

### Documents
- `GET /api/tenants/{tenant_id}/documents`
- `POST /api/tenants/{tenant_id}/documents`
- `GET /api/tenants/{tenant_id}/documents/{doc_id}/chunks`
- `DELETE /api/tenants/{tenant_id}/documents/{doc_id}`

### Integrations
- `GET /api/tenants/{tenant_id}/integrations/google/status`
- `GET /api/tenants/{tenant_id}/integrations/google/auth-url`
- `GET /api/tenants/{tenant_id}/integrations/google/calendars`
- `PATCH /api/tenants/{tenant_id}/integrations/google/calendar`
- `DELETE /api/tenants/{tenant_id}/integrations/google`

### API Keys
- `GET /api/tenants/{tenant_id}/api-keys`
- `POST /api/tenants/{tenant_id}/api-keys`
- `DELETE /api/tenants/{tenant_id}/api-keys/{key_id}`

### Conversations
- `GET /api/tenants/{tenant_id}/conversations`
- `GET /api/tenants/{tenant_id}/conversations/{conv_id}`
- `GET /api/tenants/{tenant_id}/conversations/{conv_id}/tool-calls`
- `GET /api/tenants/{tenant_id}/conversations/{conv_id}/retrievals`

### Chat
- `POST /api/chat` (with `X-API-Key` header)

### Models
- `GET /api/models/providers`
- `GET /api/models/embeddings`

## Embedding the Widget

After creating an API key in the dashboard, use the embed code:

```html
<script src="http://localhost:3000/embed.js" data-api-key="vect_live_xxx"></script>
```

Optional attributes:
- `data-color="#3B82F6"` - Primary color (hex)
- `data-position="bottom-right"` - Widget position (bottom-right | bottom-left)
- `data-welcome="Hi there!"` - Custom welcome message

## Development Notes

### Authentication Flow
1. User logs in → receives `access_token` and `refresh_token`
2. Tokens stored in `localStorage`
3. API wrapper (`lib/api.ts`) automatically:
   - Attaches `Authorization: Bearer {token}` header
   - Intercepts 401 responses
   - Refreshes token and retries request
   - Redirects to login if refresh fails

### Protected Routes
The `(dashboard)` layout checks authentication on mount and redirects to `/login` if not authenticated.

### Tenant Context
All tenant-scoped routes include `[tenantId]` in the URL, ensuring proper isolation.

### Form Validation
All forms use React Hook Form + Zod for client-side validation matching backend Pydantic schemas.

## Troubleshooting

### CORS Errors
Ensure backend `allow_origins` in CORS middleware includes `http://localhost:3000`.

### Token Refresh Loop
If refresh loop occurs, clear `localStorage` and re-login:
```javascript
localStorage.clear();
```

### Widget Not Loading
Check:
1. `embed.js` is accessible at `http://localhost:3000/embed.js`
2. API key is valid and active
3. Backend is running and CORS allows embed origin

## License

Part of the Vectriva platform.

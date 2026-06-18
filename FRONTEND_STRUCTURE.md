# Frontend Folder Structure (Next.js 16 - No SRC)

The frontend uses **Next.js 16** with the **App Router** and **NO `src` folder** structure. All folders are at the root level of the frontend directory.

```
frontend/
├── app/                              # Next.js App Router (pages & layouts)
│   ├── layout.tsx                    # Root layout
│   ├── page.tsx                      # Home page
│   ├── favicon.ico
│   └── globals.css                   # Global styles
│
├── components/                       # React Components (organized by feature)
│   ├── auth/                         # Authentication components
│   │   └── (future: LoginForm, SignupForm, ProtectedRoute)
│   ├── dashboard/                    # Dashboard feature components
│   │   └── (future: DashboardCards, Charts, Metrics)
│   ├── transactions/                 # Transaction feature components
│   │   ├── TransactionList.tsx       # List of transactions
│   │   └── (future: TransactionForm, TransactionDetail, Filter)
│   ├── events/                       # Event feature components
│   │   └── (future: EventList, EventForm, EventDetail)
│   ├── chat/                         # Chat/RAG interface components
│   │   ├── ChatInterface.tsx         # Main chat component
│   │   └── (future: MessageList, InputBox)
│   └── common/                       # Shared components
│       ├── Header.tsx                # Navigation header
│       ├── Sidebar.tsx               # Sidebar navigation
│       └── (future: Button, Modal, Card, Input, etc.)
│
├── hooks/                            # Custom React Hooks
│   ├── index.ts                      # Export all hooks
│   ├── useAuth.ts                    # Authentication hook
│   ├── useTransactions.ts            # Transactions data hook
│   └── useChat.ts                    # Chat interface hook
│
├── lib/                              # Library code & utilities
│   ├── index.ts                      # Export all lib utilities
│   ├── api.ts                        # Axios API client with interceptors
│   ├── supabase.ts                   # Supabase client initialization
│   └── utils.ts                      # Utility functions (formatCurrency, debounce, etc.)
│
├── types/                            # TypeScript type definitions
│   └── index.ts                      # All type interfaces
│       ├── User
│       ├── Transaction
│       ├── Merchant
│       ├── Category
│       ├── Event
│       ├── Account
│       ├── ApiResponse
│       └── UploadJob
│
├── styles/                           # Global and shared styles
│   └── globals.css                   # Global CSS with Tailwind & CSS variables
│
├── utils/                            # Shared utilities
│   └── constants.ts                  # Application constants & config
│
├── public/                           # Static assets (images, icons, etc.)
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
│
├── package.json                      # Dependencies (Next.js, React, Tailwind, etc.)
├── tsconfig.json                     # TypeScript configuration (Next.js format)
├── next.config.ts                    # Next.js configuration
├── next-env.d.ts                     # TypeScript declarations for Next.js
├── postcss.config.mjs                # PostCSS configuration (for Tailwind)
├── eslint.config.mjs                 # ESLint configuration
└── README.md                         # Frontend documentation
```

## Folder Organization by Purpose

### `app/` - Next.js Pages & Layouts
- Contains all pages and layouts for the application
- Uses App Router (file-based routing)
- Each folder can have a `layout.tsx`, `page.tsx`, or dynamic routes
- Global styles and layout wrapper

### `components/` - React Components
Organized by feature, not by type (not `components/buttons`, `components/forms`, etc.)

**Current components:**
- `common/` - Reusable components across the app (Header, Sidebar)
- `auth/` - Login, signup, protected routes (TODO)
- `dashboard/` - Dashboard overview, charts, metrics (TODO)
- `transactions/` - Transaction list, form, filters (TODO)
- `events/` - Event creation, listing, detail (TODO)
- `chat/` - Chat interface and messaging (TODO)

### `hooks/` - Custom React Hooks
- `useAuth()` - Authentication state and actions
- `useTransactions()` - Fetch and manage transactions
- `useChat()` - Chat interface state and actions

### `lib/` - Library Code
- `api.ts` - Axios client with base URL, interceptors, auth token
- `supabase.ts` - Supabase client initialization
- `utils.ts` - Helper functions (formatCurrency, formatDate, debounce, etc.)

### `types/` - TypeScript Interfaces
- All type definitions in one place for easy import
- Main interfaces: User, Transaction, Merchant, Category, Event, Account

### `styles/` - Global Styles
- `globals.css` - Tailwind imports, CSS variables, base styles
- Uses CSS custom properties for theming (--primary, --text-primary, etc.)
- Dark mode support with `prefers-color-scheme`

### `utils/` - Shared Utilities
- `constants.ts` - API endpoints, category list, supported banks, file types, etc.

### `public/` - Static Assets
- Images, icons, SVGs used in the application
- Automatically optimized by Next.js

## Key Dependencies

```json
{
  "next": "16.2.9",
  "react": "19.2.4",
  "react-dom": "19.2.4",
  "tailwindcss": "^4",
  "@supabase/supabase-js": "^2.38.0",
  "axios": "^1.6.0",
  "@tanstack/react-query": "^5.0.0"  // TODO: Add if needed
}
```

## Import Paths (No Path Aliases Yet)

Since there's no `src` folder and the tsconfig doesn't have aliases configured yet, imports look like:

```typescript
// From components
import { useAuth } from '../hooks';
import { apiClient } from '../lib';
import { Transaction } from '../types';

// Or with relative paths
import Header from '../components/common/Header';
```

**Note:** We can add path aliases later if needed (e.g., `@/hooks`, `@/components`)

## Development Workflow

### Adding a New Page
```bash
# Create folder structure in app/
app/
├── dashboard/
│   ├── layout.tsx       # Layout for this section
│   └── page.tsx         # Page content
```

### Adding a New Feature Component
```bash
# Create feature folder in components/
components/
├── myfeature/
│   ├── MyFeatureMain.tsx
│   ├── MyFeatureDetail.tsx
│   └── MyFeatureForm.tsx
```

### Adding a New Custom Hook
```bash
# Create in hooks/
hooks/
├── useMyFeature.ts      # New hook
├── index.ts             # Export it here
```

### Adding Utilities
```bash
# Add to lib/ for reusable code, utils/ for constants/config
lib/
├── myutil.ts            # Helper function
```

## Next Steps

1. **Update path aliases** in `tsconfig.json` if using relative imports becomes tedious
2. **Add more placeholder components** in each feature folder
3. **Connect to backend API** through `lib/api.ts`
4. **Style with Tailwind** - all components ready for Tailwind classes
5. **Implement authentication** with `useAuth` hook

## Notes

- No `src` folder (as requested)
- Latest Next.js 16 and React 19
- Tailwind CSS v4 for styling
- Supabase for auth & database
- Axios for API calls
- TypeScript for type safety

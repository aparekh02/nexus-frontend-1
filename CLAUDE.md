# Nexus MVP - Architecture Documentation

## Overview

Nexus MVP is a multi-step onboarding application designed for founders to collect comprehensive project information. The application uses a modern tech stack with Next.js 14, TypeScript, Prisma, and Clerk authentication.

## Architecture

### Technology Stack

- **Frontend Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Database**: PostgreSQL
- **ORM**: Prisma
- **Authentication**: Clerk
- **Validation**: Zod
- **UI Library**: Radix UI + Tailwind CSS
- **Icons**: Lucide React

### Design Principles

1. **Security First**: All sensitive data (GitHub tokens) are encrypted using AES-256-GCM
2. **User Experience**: Auto-save functionality and resume capability
3. **Type Safety**: Full TypeScript coverage with Zod validation
4. **Progressive Enhancement**: Form works with and without JavaScript
5. **Accessibility**: Semantic HTML and ARIA labels throughout

## Data Model

### Onboarding Table

The core data model captures all required information across 4 steps:

```prisma
model Onboarding {
  id                    String   @id @default(cuid())
  userId                String   @unique // Links to Clerk user

  // Step 1: Project Basics
  projectDescription    String?  // Detailed project description
  targetUser            String?  // Target user persona
  problemSolved         String?  // Problem being addressed
  currentStage          String?  // Enum: Idea, MVP, Early Stage, Growth, Scaling

  // Step 2: GitHub Integration
  githubRepoUrl         String?  // Optional GitHub repository
  githubAccessToken     String?  // Encrypted access token

  // Step 3: Goals and Metrics
  shortTermGoals        String[] // Array of 3-6 month goals
  longTermGoals         String[] // Array of 1+ year goals
  kpis                  String[] // Key Performance Indicators
  constraints           String?  // Optional constraints

  // Step 4: Optional Info
  competitors           String[] // Competitor list
  industryCategory      String?  // Industry classification
  techStackPreferences  String[] // Preferred technologies

  // Metadata
  currentStep           Int      @default(1)  // For resume functionality
  isCompleted           Boolean  @default(false)
  createdAt             DateTime @default(now())
  updatedAt             DateTime @updatedAt

  @@index([userId])
}
```

## Application Flow

### 1. Authentication Flow

```
User visits /
  → Unauthenticated → /sign-in or /sign-up
  → Authenticated → /onboarding
  → Completed onboarding → /dashboard
```

### 2. Onboarding Flow

```
Step 1: Project Basics (Required)
  ↓
Step 2: GitHub Integration (Optional)
  ↓
Step 3: Goals & Metrics (Required)
  ↓
Step 4: Optional Info (Optional)
  ↓
Complete → Dashboard
```

### 3. Data Persistence Flow

```
User enters data
  → Client-side validation (Zod)
  → Auto-save on step change
  → POST /api/onboarding
  → Server-side validation
  → Encrypt sensitive data
  → Upsert to database
  → Return success
```

## Key Components

### Frontend Components

#### 1. Multi-Step Form (`/app/onboarding/page.tsx`)
- **Purpose**: Main orchestrator for the onboarding flow
- **Features**:
  - Progress tracking with visual indicators
  - Step-by-step validation
  - Auto-save and manual save
  - Resume from last step
  - Loading states

#### 2. Step Components
- **Step1Basics**: Project description, target user, problem, stage
- **Step2GitHub**: GitHub repository and access token
- **Step3Goals**: Dynamic lists for goals and KPIs
- **Step4Optional**: Competitors, industry, tech stack

#### 3. DynamicList Component
- **Purpose**: Reusable component for array inputs
- **Features**:
  - Add items via input + button or Enter key
  - Remove items individually
  - Validation error display
  - Clean, minimal UI

### Backend Components

#### 1. API Routes (`/app/api/onboarding/route.ts`)

**GET Endpoint**
- Retrieves user's onboarding data
- Decrypts GitHub token
- Returns null if no data exists

**POST Endpoint**
- Validates incoming data with Zod
- Encrypts GitHub token if provided
- Upserts data to database
- Returns saved data

#### 2. Encryption Service (`/lib/encryption.ts`)
- **Algorithm**: AES-256-GCM
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **Features**:
  - Random salt per encryption
  - Random IV per encryption
  - Authentication tags for integrity
  - Secure key storage via environment variables

#### 3. Validation Schemas (`/lib/validations.ts`)
- Individual schemas for each step
- Combined schema for full validation
- TypeScript type inference
- Helpful error messages

## Security Measures

### 1. Authentication
- Clerk handles all auth flows
- JWT-based session management
- Protected API routes with `auth()` middleware

### 2. Data Encryption
```typescript
GitHub Token Flow:
  Input (plain text)
    → Generate random salt
    → Derive key with PBKDF2
    → Generate random IV
    → Encrypt with AES-256-GCM
    → Attach auth tag
    → Store as base64
```

### 3. Input Validation
- Client-side: Zod schemas
- Server-side: Same Zod schemas
- XSS protection: React's built-in escaping
- SQL injection: Prisma's prepared statements

### 4. API Security
- Authentication required for all routes
- User can only access their own data
- Rate limiting (via Clerk)
- HTTPS enforced in production

## State Management

### Form State
- Local React state for form data
- Optimistic updates for better UX
- Server state synced on navigation

### Persistence Strategy
1. **Auto-save**: Triggered on step navigation
2. **Manual save**: Available on all steps
3. **Resume**: Load saved data on mount
4. **Validation**: Per-step before allowing navigation

## UI/UX Patterns

### 1. Progressive Disclosure
- Show only one step at a time
- Clear progress indicators
- Breadcrumb navigation

### 2. Helpful Feedback
- Inline validation errors
- Success messages
- Loading states
- Auto-save confirmation

### 3. Accessibility
- ARIA labels on form fields
- Keyboard navigation support
- Focus management
- Screen reader friendly

## Performance Optimizations

1. **Code Splitting**: Next.js automatic code splitting
2. **Lazy Loading**: Components loaded on demand
3. **Database Indexing**: userId indexed for fast lookups
4. **Prisma Connection Pooling**: Reuse database connections
5. **Client-side Caching**: Form data cached in state

## Error Handling

### Client-side
```typescript
try {
  await saveData()
} catch (error) {
  // Show user-friendly error message
  // Log to console for debugging
  // Allow retry
}
```

### Server-side
```typescript
try {
  await prisma.onboarding.upsert(...)
} catch (error) {
  // Log error
  // Return appropriate HTTP status
  // Send error message to client
}
```

## Future Enhancements

### Short-term
- [ ] Email notifications on completion
- [ ] Export data as PDF
- [ ] Admin dashboard
- [ ] Analytics tracking

### Long-term
- [ ] Multi-language support
- [ ] Custom branding
- [ ] Webhook integrations
- [ ] AI-powered suggestions
- [ ] Team collaboration features

## Development Workflow

### Local Development
```bash
npm run dev          # Start dev server
npm run db:studio    # Open Prisma Studio
npm run db:push      # Push schema changes
```

### Testing Strategy
- Unit tests for utilities
- Integration tests for API routes
- E2E tests for critical flows
- Manual QA for UX

### Deployment
- Vercel for hosting
- Vercel Postgres or Railway for database
- Environment variables via Vercel dashboard
- Automatic deployments on git push

## Monitoring & Observability

### Metrics to Track
- Onboarding completion rate
- Average time per step
- Drop-off points
- Error rates
- API response times

### Logging
- Server errors logged to console
- Client errors logged to console
- Production: Use service like Sentry

## Data Privacy

### GDPR Compliance
- User data encrypted at rest
- User can delete their data
- Clear privacy policy
- Data retention policies

### Data Access
- Only authenticated users access their data
- No data sharing with third parties
- Secure token storage
- Regular security audits

## Troubleshooting

### Common Issues

1. **Database connection fails**
   - Check DATABASE_URL format
   - Verify PostgreSQL is running
   - Check network connectivity

2. **Clerk authentication not working**
   - Verify API keys in .env
   - Check Clerk dashboard settings
   - Ensure middleware is configured

3. **Encryption errors**
   - Verify ENCRYPTION_KEY is set
   - Check key is base64 encoded
   - Ensure consistent key across deploys

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [Prisma Documentation](https://www.prisma.io/docs)
- [Clerk Documentation](https://clerk.com/docs)
- [Zod Documentation](https://zod.dev)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)

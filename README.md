# Nexus MVP - Multi-Step Onboarding

A comprehensive, founder-friendly multi-step onboarding form built with Next.js 14, TypeScript, Prisma, and Clerk authentication.

## Features

### 📋 Multi-Step Form
- **Step 1: Project Basics** - Collect project description, target user, problem being solved, and current stage
- **Step 2: GitHub Integration** - Optional GitHub repository URL and access token with secure encryption
- **Step 3: Goals & Metrics** - Dynamic lists for short-term goals, long-term goals, KPIs, and constraints
- **Step 4: Optional Info** - Competitors, industry category, and tech stack preferences

### 🔐 Security
- Clerk authentication for secure user management
- AES-256-GCM encryption for GitHub access tokens
- Server-side validation with Zod schemas
- Protected API routes

### 💾 Persistence
- Auto-save progress as users navigate between steps
- Manual save option on each step
- Resume capability - users can return later to complete onboarding
- PostgreSQL database with Prisma ORM

### 🎨 User Experience
- Clean, modern UI built with Tailwind CSS
- Real-time form validation with helpful error messages
- Progress bar showing completion percentage
- Step indicators with visual feedback
- Responsive design for all devices
- Loading states and smooth transitions

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Database**: PostgreSQL with Prisma
- **Authentication**: Clerk
- **Validation**: Zod
- **UI Components**: Radix UI + Tailwind CSS
- **Icons**: Lucide React

## Getting Started

### Prerequisites

- Node.js 18+ installed
- PostgreSQL database
- Clerk account for authentication

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd nexus-mvp
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**

   Copy `.env.example` to `.env` and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Required variables:
   - `DATABASE_URL` - Your PostgreSQL connection string
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - From Clerk dashboard
   - `CLERK_SECRET_KEY` - From Clerk dashboard
   - `ENCRYPTION_KEY` - Generate with: `openssl rand -base64 32`

4. **Set up the database**
   ```bash
   npm run db:push
   ```

5. **Run the development server**
   ```bash
   npm run dev
   ```

6. **Open your browser**

   Navigate to [http://localhost:3000](http://localhost:3000)

## Database Schema

The `Onboarding` model stores all user data:

```prisma
model Onboarding {
  id                    String   @id @default(cuid())
  userId                String   @unique

  // Step 1: Project Basics
  projectDescription    String?
  targetUser            String?
  problemSolved         String?
  currentStage          String?

  // Step 2: GitHub Integration
  githubRepoUrl         String?
  githubAccessToken     String? // Encrypted

  // Step 3: Goals and Metrics
  shortTermGoals        String[]
  longTermGoals         String[]
  kpis                  String[]
  constraints           String?

  // Step 4: Optional Info
  competitors           String[]
  industryCategory      String?
  techStackPreferences  String[]

  // Meta
  currentStep           Int      @default(1)
  isCompleted           Boolean  @default(false)
  createdAt             DateTime @default(now())
  updatedAt             DateTime @updatedAt
}
```

## Project Structure

```
nexus-mvp/
├── app/
│   ├── api/
│   │   └── onboarding/
│   │       └── route.ts         # API endpoints
│   ├── dashboard/
│   │   └── page.tsx             # Post-onboarding dashboard
│   ├── onboarding/
│   │   └── page.tsx             # Main onboarding form
│   ├── sign-in/
│   └── sign-up/
├── components/
│   ├── onboarding/
│   │   ├── step1-basics.tsx
│   │   ├── step2-github.tsx
│   │   ├── step3-goals.tsx
│   │   └── step4-optional.tsx
│   ├── ui/                      # Reusable UI components
│   └── dynamic-list.tsx         # Dynamic array input
├── lib/
│   ├── prisma.ts                # Prisma client
│   ├── encryption.ts            # Token encryption
│   └── validations.ts           # Zod schemas
├── prisma/
│   └── schema.prisma            # Database schema
└── utils/
    └── cn.ts                    # Utility functions
```

## Key Features Explained

### Form Validation

Each step has its own Zod schema for validation:
- Step 1 requires all fields (project basics)
- Step 2 validates GitHub URLs (optional)
- Step 3 requires at least one item in each goal/KPI list
- Step 4 is entirely optional

### Encryption

GitHub access tokens are encrypted using AES-256-GCM before storage:
- Uses PBKDF2 for key derivation
- Random salt and IV for each encryption
- Authentication tags for integrity verification

### Save & Resume

Users can save progress at any time:
- Auto-save when navigating between steps
- Manual save button on each step
- Current step is tracked in the database
- Users are redirected to their last step on return

### Dynamic Lists

The `DynamicList` component allows users to:
- Add items by typing and pressing Enter or clicking the plus button
- Remove items with the X button
- See validation errors for required lists

## API Routes

### GET /api/onboarding
Retrieves the current user's onboarding data.

**Response:**
```json
{
  "data": {
    "id": "...",
    "userId": "...",
    "projectDescription": "...",
    // ... all fields
  }
}
```

### POST /api/onboarding
Saves or updates onboarding data.

**Request Body:**
```json
{
  "projectDescription": "...",
  "targetUser": "...",
  // ... all form fields
  "currentStep": 2,
  "isCompleted": false
}
```

## Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Import project in Vercel
3. Add environment variables
4. Deploy

### Docker

```bash
# Build the image
docker build -t nexus-mvp .

# Run the container
docker run -p 3000:3000 nexus-mvp
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key | Yes |
| `CLERK_SECRET_KEY` | Clerk secret key | Yes |
| `ENCRYPTION_KEY` | Encryption key for tokens | Yes |

## Development

### Running Prisma Studio
```bash
npm run db:studio
```

### Generating Prisma Client
```bash
npm run db:generate
```

### Database Migration
```bash
npm run db:push
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please open an issue on GitHub.

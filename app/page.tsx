import { auth } from '@clerk/nextjs'
import { redirect } from 'next/navigation'
import Link from 'next/link'

export default async function Home() {
  const { userId } = auth()

  if (userId) {
    redirect('/onboarding')
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="mx-auto max-w-2xl px-4 text-center">
        <h1 className="mb-6 text-5xl font-bold tracking-tight text-gray-900">
          Welcome to Nexus MVP
        </h1>
        <p className="mb-8 text-xl text-gray-600">
          Get started with our comprehensive onboarding process designed for founders
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/sign-up"
            className="rounded-lg bg-blue-600 px-8 py-3 text-lg font-semibold text-white shadow-lg transition hover:bg-blue-700"
          >
            Get Started
          </Link>
          <Link
            href="/sign-in"
            className="rounded-lg border-2 border-blue-600 px-8 py-3 text-lg font-semibold text-blue-600 transition hover:bg-blue-50"
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  )
}

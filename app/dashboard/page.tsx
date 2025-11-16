import { auth } from '@clerk/nextjs'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'
import { UserButton } from '@clerk/nextjs'
import { CheckCircle2 } from 'lucide-react'

export default async function DashboardPage() {
  const { userId } = auth()

  if (!userId) {
    redirect('/sign-in')
  }

  const onboarding = await prisma.onboarding.findUnique({
    where: { userId },
  })

  if (!onboarding?.isCompleted) {
    redirect('/onboarding')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <UserButton afterSignOutUrl="/" />
        </div>

        {/* Success Message */}
        <div className="mb-8 rounded-lg border border-green-200 bg-green-50 p-6">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-8 w-8 text-green-600" />
            <div>
              <h2 className="text-xl font-semibold text-green-900">
                Onboarding Complete!
              </h2>
              <p className="text-green-700">
                Your project information has been saved successfully.
              </p>
            </div>
          </div>
        </div>

        {/* Onboarding Summary */}
        <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          <h2 className="mb-6 text-2xl font-bold text-gray-900">
            Project Summary
          </h2>

          <div className="space-y-6">
            {/* Project Basics */}
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Project Basics
              </h3>
              <div className="space-y-3">
                <div>
                  <span className="font-medium text-gray-700">
                    Description:
                  </span>
                  <p className="text-gray-600">{onboarding.projectDescription}</p>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    Target User:
                  </span>
                  <p className="text-gray-600">{onboarding.targetUser}</p>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    Problem Solved:
                  </span>
                  <p className="text-gray-600">{onboarding.problemSolved}</p>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    Current Stage:
                  </span>
                  <p className="text-gray-600">{onboarding.currentStage}</p>
                </div>
              </div>
            </div>

            {/* GitHub Integration */}
            {onboarding.githubRepoUrl && (
              <div>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  GitHub Integration
                </h3>
                <div>
                  <span className="font-medium text-gray-700">
                    Repository:
                  </span>
                  <a
                    href={onboarding.githubRepoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-2 text-blue-600 hover:underline"
                  >
                    {onboarding.githubRepoUrl}
                  </a>
                </div>
              </div>
            )}

            {/* Goals & Metrics */}
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Goals & Metrics
              </h3>
              <div className="space-y-3">
                <div>
                  <span className="font-medium text-gray-700">
                    Short-term Goals:
                  </span>
                  <ul className="mt-1 list-inside list-disc text-gray-600">
                    {onboarding.shortTermGoals.map((goal, i) => (
                      <li key={i}>{goal}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    Long-term Goals:
                  </span>
                  <ul className="mt-1 list-inside list-disc text-gray-600">
                    {onboarding.longTermGoals.map((goal, i) => (
                      <li key={i}>{goal}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="font-medium text-gray-700">KPIs:</span>
                  <ul className="mt-1 list-inside list-disc text-gray-600">
                    {onboarding.kpis.map((kpi, i) => (
                      <li key={i}>{kpi}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Optional Info */}
            {(onboarding.competitors.length > 0 ||
              onboarding.industryCategory ||
              onboarding.techStackPreferences.length > 0) && (
              <div>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Additional Information
                </h3>
                <div className="space-y-3">
                  {onboarding.competitors.length > 0 && (
                    <div>
                      <span className="font-medium text-gray-700">
                        Competitors:
                      </span>
                      <p className="text-gray-600">
                        {onboarding.competitors.join(', ')}
                      </p>
                    </div>
                  )}
                  {onboarding.industryCategory && (
                    <div>
                      <span className="font-medium text-gray-700">
                        Industry:
                      </span>
                      <p className="text-gray-600">
                        {onboarding.industryCategory}
                      </p>
                    </div>
                  )}
                  {onboarding.techStackPreferences.length > 0 && (
                    <div>
                      <span className="font-medium text-gray-700">
                        Tech Stack:
                      </span>
                      <p className="text-gray-600">
                        {onboarding.techStackPreferences.join(', ')}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

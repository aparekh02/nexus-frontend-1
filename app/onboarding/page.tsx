'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@clerk/nextjs'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Step1Basics } from '@/components/onboarding/step1-basics'
import { Step2GitHub } from '@/components/onboarding/step2-github'
import { Step3Goals } from '@/components/onboarding/step3-goals'
import { Step4Optional } from '@/components/onboarding/step4-optional'
import {
  step1Schema,
  step2Schema,
  step3Schema,
  step4Schema,
  OnboardingData,
} from '@/lib/validations'
import { ArrowLeft, ArrowRight, Check, Save, Loader2 } from 'lucide-react'

const STEPS = [
  { number: 1, title: 'Project Basics', schema: step1Schema },
  { number: 2, title: 'GitHub Integration', schema: step2Schema },
  { number: 3, title: 'Goals & Metrics', schema: step3Schema },
  { number: 4, title: 'Optional Info', schema: step4Schema },
]

export default function OnboardingPage() {
  const router = useRouter()
  const { user, isLoaded } = useUser()
  const [currentStep, setCurrentStep] = useState(1)
  const [formData, setFormData] = useState<Partial<OnboardingData>>({
    shortTermGoals: [],
    longTermGoals: [],
    kpis: [],
    competitors: [],
    techStackPreferences: [],
  })
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Load existing data on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await fetch('/api/onboarding')
        const { data } = await response.json()

        if (data) {
          setFormData({
            projectDescription: data.projectDescription || '',
            targetUser: data.targetUser || '',
            problemSolved: data.problemSolved || '',
            currentStage: data.currentStage || undefined,
            githubRepoUrl: data.githubRepoUrl || '',
            githubAccessToken: data.githubAccessToken || '',
            shortTermGoals: data.shortTermGoals || [],
            longTermGoals: data.longTermGoals || [],
            kpis: data.kpis || [],
            constraints: data.constraints || '',
            competitors: data.competitors || [],
            industryCategory: data.industryCategory || '',
            techStackPreferences: data.techStackPreferences || [],
          })
          setCurrentStep(data.currentStep || 1)
        }
      } catch (error) {
        console.error('Error loading onboarding data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    if (isLoaded && user) {
      loadData()
    }
  }, [isLoaded, user])

  const validateCurrentStep = () => {
    const currentSchema = STEPS[currentStep - 1].schema
    const result = currentSchema.safeParse(formData)

    if (!result.success) {
      const newErrors: Record<string, string> = {}
      result.error.issues.forEach((issue) => {
        if (issue.path[0]) {
          newErrors[issue.path[0].toString()] = issue.message
        }
      })
      setErrors(newErrors)
      return false
    }

    setErrors({})
    return true
  }

  const saveProgress = async (silent = false) => {
    if (!silent) setIsSaving(true)

    try {
      const response = await fetch('/api/onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          currentStep,
          isCompleted: false,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to save progress')
      }

      return true
    } catch (error) {
      console.error('Error saving progress:', error)
      return false
    } finally {
      if (!silent) setIsSaving(false)
    }
  }

  const handleNext = async () => {
    if (!validateCurrentStep()) {
      return
    }

    await saveProgress(true)

    if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1)
      window.scrollTo(0, 0)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
      window.scrollTo(0, 0)
    }
  }

  const handleSubmit = async () => {
    if (!validateCurrentStep()) {
      return
    }

    setIsSubmitting(true)

    try {
      const response = await fetch('/api/onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          currentStep,
          isCompleted: true,
        }),
      })

      if (!response.ok) {
        const { error } = await response.json()
        throw new Error(error || 'Failed to submit onboarding')
      }

      // Redirect to dashboard or success page
      router.push('/dashboard')
    } catch (error) {
      console.error('Error submitting onboarding:', error)
      alert('Failed to submit onboarding. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateFormData = (data: Partial<OnboardingData>) => {
    setFormData(data)
  }

  const progressPercentage = (currentStep / STEPS.length) * 100

  if (isLoading || !isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome, {user?.firstName || 'Founder'}!
          </h1>
          <p className="mt-2 text-gray-600">
            Let's get your project set up. This will only take a few minutes.
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">
              Step {currentStep} of {STEPS.length}
            </span>
            <span className="text-sm text-gray-500">
              {Math.round(progressPercentage)}% Complete
            </span>
          </div>
          <Progress value={progressPercentage} className="h-2" />
        </div>

        {/* Step Indicators */}
        <div className="mb-8 flex justify-between">
          {STEPS.map((step) => (
            <div
              key={step.number}
              className="flex flex-1 flex-col items-center"
            >
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${
                  step.number < currentStep
                    ? 'border-green-500 bg-green-500 text-white'
                    : step.number === currentStep
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : 'border-gray-300 bg-white text-gray-400'
                }`}
              >
                {step.number < currentStep ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <span className="text-sm font-semibold">{step.number}</span>
                )}
              </div>
              <span
                className={`mt-2 text-xs ${
                  step.number === currentStep
                    ? 'font-semibold text-blue-600'
                    : 'text-gray-500'
                }`}
              >
                {step.title}
              </span>
            </div>
          ))}
        </div>

        {/* Form Content */}
        <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          {currentStep === 1 && (
            <Step1Basics
              data={formData}
              onChange={updateFormData}
              errors={errors}
            />
          )}
          {currentStep === 2 && (
            <Step2GitHub
              data={formData}
              onChange={updateFormData}
              errors={errors}
            />
          )}
          {currentStep === 3 && (
            <Step3Goals
              data={formData}
              onChange={updateFormData}
              errors={errors}
            />
          )}
          {currentStep === 4 && (
            <Step4Optional
              data={formData}
              onChange={updateFormData}
              errors={errors}
            />
          )}
        </div>

        {/* Navigation */}
        <div className="mt-8 flex items-center justify-between">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 1}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>

          <Button
            variant="ghost"
            onClick={() => saveProgress()}
            disabled={isSaving}
            className="flex items-center gap-2"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {isSaving ? 'Saving...' : 'Save Progress'}
          </Button>

          {currentStep < STEPS.length ? (
            <Button onClick={handleNext} className="flex items-center gap-2">
              Next
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" />
                  Complete Onboarding
                </>
              )}
            </Button>
          )}
        </div>

        {/* Auto-save indicator */}
        <p className="mt-4 text-center text-xs text-gray-500">
          Your progress is automatically saved as you navigate between steps
        </p>
      </div>
    </div>
  )
}

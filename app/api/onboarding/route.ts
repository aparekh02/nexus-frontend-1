import { auth } from '@clerk/nextjs'
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { encrypt, decrypt } from '@/lib/encryption'
import { fullOnboardingSchema } from '@/lib/validations'

export async function GET() {
  try {
    const { userId } = auth()

    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const onboarding = await prisma.onboarding.findUnique({
      where: { userId },
    })

    if (!onboarding) {
      return NextResponse.json({ data: null })
    }

    // Decrypt the GitHub access token if it exists
    const data = {
      ...onboarding,
      githubAccessToken: onboarding.githubAccessToken
        ? decrypt(onboarding.githubAccessToken)
        : null,
    }

    return NextResponse.json({ data })
  } catch (error) {
    console.error('Error fetching onboarding data:', error)
    return NextResponse.json(
      { error: 'Failed to fetch onboarding data' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const { userId } = auth()

    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const { currentStep, isCompleted, ...formData } = body

    // Validate the data
    const validation = fullOnboardingSchema.safeParse(formData)

    if (!validation.success && isCompleted) {
      return NextResponse.json(
        { error: 'Validation failed', details: validation.error.issues },
        { status: 400 }
      )
    }

    // Encrypt the GitHub access token if it exists
    const dataToSave = {
      ...formData,
      githubAccessToken: formData.githubAccessToken
        ? encrypt(formData.githubAccessToken)
        : null,
      currentStep: currentStep || 1,
      isCompleted: isCompleted || false,
    }

    const onboarding = await prisma.onboarding.upsert({
      where: { userId },
      update: dataToSave,
      create: {
        userId,
        ...dataToSave,
      },
    })

    return NextResponse.json({ data: onboarding })
  } catch (error) {
    console.error('Error saving onboarding data:', error)
    return NextResponse.json(
      { error: 'Failed to save onboarding data' },
      { status: 500 }
    )
  }
}

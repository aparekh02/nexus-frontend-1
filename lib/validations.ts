import { z } from 'zod'

export const step1Schema = z.object({
  projectDescription: z.string().min(10, 'Please provide at least 10 characters'),
  targetUser: z.string().min(5, 'Please describe your target user'),
  problemSolved: z.string().min(10, 'Please describe the problem being solved'),
  currentStage: z.enum(['Idea', 'MVP', 'Early Stage', 'Growth', 'Scaling'], {
    required_error: 'Please select your current stage',
  }),
})

export const step2Schema = z.object({
  githubRepoUrl: z
    .string()
    .url('Please enter a valid URL')
    .regex(/^https?:\/\/(www\.)?github\.com\//, 'Must be a GitHub repository URL')
    .optional()
    .or(z.literal('')),
  githubAccessToken: z.string().optional(),
})

export const step3Schema = z.object({
  shortTermGoals: z.array(z.string()).min(1, 'Add at least one short-term goal'),
  longTermGoals: z.array(z.string()).min(1, 'Add at least one long-term goal'),
  kpis: z.array(z.string()).min(1, 'Add at least one KPI to track'),
  constraints: z.string().optional(),
})

export const step4Schema = z.object({
  competitors: z.array(z.string()),
  industryCategory: z.string().optional(),
  techStackPreferences: z.array(z.string()),
})

export const fullOnboardingSchema = z.object({
  ...step1Schema.shape,
  ...step2Schema.shape,
  ...step3Schema.shape,
  ...step4Schema.shape,
})

export type Step1Data = z.infer<typeof step1Schema>
export type Step2Data = z.infer<typeof step2Schema>
export type Step3Data = z.infer<typeof step3Schema>
export type Step4Data = z.infer<typeof step4Schema>
export type OnboardingData = z.infer<typeof fullOnboardingSchema>

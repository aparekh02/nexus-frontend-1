'use client'

import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Step1Data } from '@/lib/validations'

interface Step1Props {
  data: Partial<Step1Data>
  onChange: (data: Partial<Step1Data>) => void
  errors?: Partial<Record<keyof Step1Data, string>>
}

const stages = ['Idea', 'MVP', 'Early Stage', 'Growth', 'Scaling'] as const

export function Step1Basics({ data, onChange, errors }: Step1Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Project Basics</h2>
        <p className="mt-1 text-sm text-gray-600">
          Tell us about your project and what you're building
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="projectDescription">Project Description *</Label>
          <Textarea
            id="projectDescription"
            value={data.projectDescription || ''}
            onChange={(e) =>
              onChange({ ...data, projectDescription: e.target.value })
            }
            placeholder="Describe your project in detail..."
            className="mt-1.5"
            rows={4}
          />
          {errors?.projectDescription && (
            <p className="mt-1 text-sm text-red-500">
              {errors.projectDescription}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="targetUser">Target User *</Label>
          <Input
            id="targetUser"
            value={data.targetUser || ''}
            onChange={(e) => onChange({ ...data, targetUser: e.target.value })}
            placeholder="Who is your target user?"
            className="mt-1.5"
          />
          {errors?.targetUser && (
            <p className="mt-1 text-sm text-red-500">{errors.targetUser}</p>
          )}
        </div>

        <div>
          <Label htmlFor="problemSolved">Problem Being Solved *</Label>
          <Textarea
            id="problemSolved"
            value={data.problemSolved || ''}
            onChange={(e) =>
              onChange({ ...data, problemSolved: e.target.value })
            }
            placeholder="What problem does your project solve?"
            className="mt-1.5"
            rows={3}
          />
          {errors?.problemSolved && (
            <p className="mt-1 text-sm text-red-500">{errors.problemSolved}</p>
          )}
        </div>

        <div>
          <Label htmlFor="currentStage">Current Stage *</Label>
          <Select
            value={data.currentStage}
            onValueChange={(value) =>
              onChange({ ...data, currentStage: value as typeof stages[number] })
            }
          >
            <SelectTrigger className="mt-1.5">
              <SelectValue placeholder="Select your current stage" />
            </SelectTrigger>
            <SelectContent>
              {stages.map((stage) => (
                <SelectItem key={stage} value={stage}>
                  {stage}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors?.currentStage && (
            <p className="mt-1 text-sm text-red-500">{errors.currentStage}</p>
          )}
        </div>
      </div>
    </div>
  )
}

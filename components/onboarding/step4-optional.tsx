'use client'

import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { DynamicList } from '@/components/dynamic-list'
import { Step4Data } from '@/lib/validations'
import { Users, Building2, Code } from 'lucide-react'

interface Step4Props {
  data: Partial<Step4Data>
  onChange: (data: Partial<Step4Data>) => void
  errors?: Partial<Record<keyof Step4Data, string>>
}

export function Step4Optional({ data, onChange, errors }: Step4Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Optional Information</h2>
        <p className="mt-1 text-sm text-gray-600">
          Additional context to help us serve you better
        </p>
      </div>

      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Users className="h-4 w-4 text-orange-600" />
            <span className="font-medium">Competitors</span>
          </div>
          <DynamicList
            label=""
            items={data.competitors || []}
            onChange={(items) => onChange({ ...data, competitors: items })}
            placeholder="Add a competitor"
            error={errors?.competitors}
          />
          <p className="mt-1.5 text-xs text-gray-500">
            List companies or products you consider competitors
          </p>
        </div>

        <div>
          <Label htmlFor="industryCategory" className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-blue-600" />
            Industry Category
          </Label>
          <Input
            id="industryCategory"
            value={data.industryCategory || ''}
            onChange={(e) =>
              onChange({ ...data, industryCategory: e.target.value })
            }
            placeholder="e.g., SaaS, E-commerce, FinTech, HealthTech"
            className="mt-1.5"
          />
          {errors?.industryCategory && (
            <p className="mt-1 text-sm text-red-500">
              {errors.industryCategory}
            </p>
          )}
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Code className="h-4 w-4 text-green-600" />
            <span className="font-medium">Tech Stack Preferences</span>
          </div>
          <DynamicList
            label=""
            items={data.techStackPreferences || []}
            onChange={(items) =>
              onChange({ ...data, techStackPreferences: items })
            }
            placeholder="Add a technology (e.g., React, Python, PostgreSQL)"
            error={errors?.techStackPreferences}
          />
          <p className="mt-1.5 text-xs text-gray-500">
            Technologies you prefer or are currently using
          </p>
        </div>
      </div>
    </div>
  )
}

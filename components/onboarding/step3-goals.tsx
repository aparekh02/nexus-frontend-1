'use client'

import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { DynamicList } from '@/components/dynamic-list'
import { Step3Data } from '@/lib/validations'
import { Target, TrendingUp, BarChart3 } from 'lucide-react'

interface Step3Props {
  data: Partial<Step3Data>
  onChange: (data: Partial<Step3Data>) => void
  errors?: Partial<Record<keyof Step3Data, string>>
}

export function Step3Goals({ data, onChange, errors }: Step3Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Goals & Metrics</h2>
        <p className="mt-1 text-sm text-gray-600">
          Define your objectives and how you'll measure success
        </p>
      </div>

      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-4 w-4 text-blue-600" />
            <span className="font-medium">Short-term Goals *</span>
          </div>
          <DynamicList
            label=""
            items={data.shortTermGoals || []}
            onChange={(items) => onChange({ ...data, shortTermGoals: items })}
            placeholder="Add a short-term goal (3-6 months)"
            error={errors?.shortTermGoals}
          />
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-green-600" />
            <span className="font-medium">Long-term Goals *</span>
          </div>
          <DynamicList
            label=""
            items={data.longTermGoals || []}
            onChange={(items) => onChange({ ...data, longTermGoals: items })}
            placeholder="Add a long-term goal (1+ years)"
            error={errors?.longTermGoals}
          />
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="h-4 w-4 text-purple-600" />
            <span className="font-medium">Key Performance Indicators (KPIs) *</span>
          </div>
          <DynamicList
            label=""
            items={data.kpis || []}
            onChange={(items) => onChange({ ...data, kpis: items })}
            placeholder="Add a KPI to track (e.g., Monthly Active Users)"
            error={errors?.kpis}
          />
        </div>

        <div>
          <Label htmlFor="constraints">Constraints (Optional)</Label>
          <Textarea
            id="constraints"
            value={data.constraints || ''}
            onChange={(e) => onChange({ ...data, constraints: e.target.value })}
            placeholder="Any budget, time, or resource constraints?"
            className="mt-1.5"
            rows={3}
          />
          {errors?.constraints && (
            <p className="mt-1 text-sm text-red-500">{errors.constraints}</p>
          )}
        </div>
      </div>
    </div>
  )
}

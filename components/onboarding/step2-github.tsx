'use client'

import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Step2Data } from '@/lib/validations'
import { Github, Lock } from 'lucide-react'

interface Step2Props {
  data: Partial<Step2Data>
  onChange: (data: Partial<Step2Data>) => void
  errors?: Partial<Record<keyof Step2Data, string>>
}

export function Step2GitHub({ data, onChange, errors }: Step2Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">GitHub Integration</h2>
        <p className="mt-1 text-sm text-gray-600">
          Connect your GitHub repository to enable deeper insights (optional)
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="githubRepoUrl" className="flex items-center gap-2">
            <Github className="h-4 w-4" />
            GitHub Repository URL
          </Label>
          <Input
            id="githubRepoUrl"
            type="url"
            value={data.githubRepoUrl || ''}
            onChange={(e) =>
              onChange({ ...data, githubRepoUrl: e.target.value })
            }
            placeholder="https://github.com/username/repository"
            className="mt-1.5"
          />
          {errors?.githubRepoUrl && (
            <p className="mt-1 text-sm text-red-500">{errors.githubRepoUrl}</p>
          )}
          <p className="mt-1.5 text-xs text-gray-500">
            Enter the URL of your GitHub repository
          </p>
        </div>

        <div>
          <Label
            htmlFor="githubAccessToken"
            className="flex items-center gap-2"
          >
            <Lock className="h-4 w-4" />
            GitHub Access Token (Optional)
          </Label>
          <Input
            id="githubAccessToken"
            type="password"
            value={data.githubAccessToken || ''}
            onChange={(e) =>
              onChange({ ...data, githubAccessToken: e.target.value })
            }
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
            className="mt-1.5"
          />
          {errors?.githubAccessToken && (
            <p className="mt-1 text-sm text-red-500">
              {errors.githubAccessToken}
            </p>
          )}
          <p className="mt-1.5 text-xs text-gray-500">
            Provide a personal access token for private repositories. This will
            be encrypted and stored securely.
          </p>
        </div>

        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <h4 className="font-medium text-blue-900">Security Notice</h4>
          <p className="mt-1 text-sm text-blue-800">
            Your GitHub access token will be encrypted using industry-standard
            AES-256-GCM encryption before being stored. We never log or expose
            your token in plain text.
          </p>
        </div>
      </div>
    </div>
  )
}

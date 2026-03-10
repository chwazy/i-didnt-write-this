import { useState } from 'react'
import useStore from '../store/useStore'
import { X } from 'lucide-react'
import ModelSelector from './ModelSelector'

export default function AddProjectDialog({ open, onClose }) {
  const createProject = useStore((s) => s.createProject)
  const [form, setForm] = useState({
    name: '',
    repo_url: '',
    platform: 'github',
    git_host: '',
    pat: '',
    merge_option: '',
    default_model: 'claude-sonnet-4-6',
    notifications_enabled: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (!open) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const data = { ...form }
      if (!data.git_host) delete data.git_host
      data.merge_option = data.merge_option || null
      data.default_model = data.default_model || 'claude-sonnet-4-6'
      data.notifications_enabled = data.notifications_enabled === '' ? null : data.notifications_enabled === 'true'
      await createProject(data)
      setForm({ name: '', repo_url: '', platform: 'github', git_host: '', pat: '', merge_option: '', default_model: 'claude-sonnet-4-6', notifications_enabled: '' })
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const inputClass = "w-full px-3 py-2 bg-muted border border-input rounded-md text-foreground focus:outline-none focus:border-primary"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card border border-border rounded-lg w-full max-w-md mx-4 sm:mx-auto p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Add Project</h2>
          <button onClick={onClose} className="p-1 hover:bg-accent rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Project Name</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={inputClass}
              placeholder="My Project"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Repository URL</label>
            <input
              type="url"
              required
              value={form.repo_url}
              onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
              className={inputClass}
              placeholder="https://github.com/org/repo"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Platform</label>
            <select
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
              className={inputClass}
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
              <option value="azure">Azure DevOps</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">
              Git Host <span className="text-muted-foreground">(optional, for self-hosted)</span>
            </label>
            <input
              type="text"
              value={form.git_host}
              onChange={(e) => setForm({ ...form, git_host: e.target.value })}
              className={inputClass}
              placeholder="gitlab.mycompany.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Personal Access Token</label>
            <input
              type="password"
              required
              value={form.pat}
              onChange={(e) => setForm({ ...form, pat: e.target.value })}
              className={inputClass}
              placeholder="ghp_xxxxxxxxxxxx"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Merge Option</label>
            <select
              value={form.merge_option}
              onChange={(e) => setForm({ ...form, merge_option: e.target.value })}
              className={inputClass}
            >
              <option value="">Inherit from settings (default)</option>
              <option value="none">None — no merge or PR after completion</option>
              <option value="pull_request">Pull Request — open a PR to the base branch</option>
              <option value="auto_squash_merge">Auto Squash Merge — squash and merge into base branch</option>
            </select>
          </div>

          <ModelSelector
            value={form.default_model}
            onChange={(v) => setForm({ ...form, default_model: v })}
            label="Default model for tasks"
            className={inputClass}
          />

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Notifications</label>
            <select
              value={form.notifications_enabled}
              onChange={(e) => setForm({ ...form, notifications_enabled: e.target.value })}
              className={inputClass}
            >
              <option value="">Inherit from settings (default)</option>
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-accent-foreground border border-input rounded-md hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm text-primary-foreground bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50"
            >
              {submitting ? 'Adding...' : 'Add Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import useStore from '@/store/useStore'
import { Save } from 'lucide-react'
import ModelSelector from '@/components/ModelSelector'
import { useSettingsSave, inputClass } from './useSettingsSave'

export default function GeneralSettings() {
  const fetchSettings = useStore((s) => s.fetchSettings)
  const { settings, save, saving, feedback } = useSettingsSave()

  const [gitForm, setGitForm] = useState({ git_user_name: '', git_user_email: '', default_merge_option: 'none' })
  const [defaultModel, setDefaultModel] = useState('claude-sonnet-4-6')

  useEffect(() => { fetchSettings() }, [fetchSettings])

  useEffect(() => {
    if (settings) {
      setGitForm({
        git_user_name: settings.git_user_name || '',
        git_user_email: settings.git_user_email || '',
        default_merge_option: settings.default_merge_option || 'none',
      })
      setDefaultModel(settings.default_model || 'claude-sonnet-4-6')
    }
  }, [settings])

  const handleSave = () => {
    if (!gitForm.git_user_name.trim() || !gitForm.git_user_email.trim()) return
    save({ ...gitForm, default_model: defaultModel })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">General</h1>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Git Identity</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Default git commit author for all agent containers. Can be overridden per project or per task.
          </p>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Name</label>
              <input
                type="text"
                value={gitForm.git_user_name}
                onChange={(e) => setGitForm({ ...gitForm, git_user_name: e.target.value })}
                className={inputClass}
                placeholder="Claude"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Email</label>
              <input
                type="email"
                value={gitForm.git_user_email}
                onChange={(e) => setGitForm({ ...gitForm, git_user_email: e.target.value })}
                className={inputClass}
                placeholder="claude@agent.ai"
              />
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Default Merge Option</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Default merge behavior for all new tasks. Can be overridden per project or per task.
          </p>
          <select
            value={gitForm.default_merge_option}
            onChange={(e) => setGitForm({ ...gitForm, default_merge_option: e.target.value })}
            className={inputClass}
          >
            <option value="none">None — no merge or PR after completion</option>
            <option value="pull_request">Pull Request — open a PR to the base branch</option>
            <option value="auto_squash_merge">Auto Squash Merge — squash and merge into base branch</option>
          </select>
        </div>

        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Default AI Model</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Default Claude model for all agent tasks. Can be overridden per project or per task.
          </p>
          <ModelSelector
            value={defaultModel}
            onChange={setDefaultModel}
            className={inputClass}
          />
        </div>

        {feedback && (
          <p className={`text-sm ${feedback.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
            {feedback.message}
          </p>
        )}
        <div className="flex justify-end">
          <button
            disabled={saving}
            onClick={handleSave}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm text-primary-foreground bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

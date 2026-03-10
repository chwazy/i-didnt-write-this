import { useEffect, useState } from 'react'
import useStore from '@/store/useStore'
import { Save } from 'lucide-react'
import { useSettingsSave, inputClass } from './useSettingsSave'

export default function TasksSettings() {
  const fetchSettings = useStore((s) => s.fetchSettings)
  const { settings, save, saving, feedback } = useSettingsSave()

  const [retentionLimit, setRetentionLimit] = useState(0)
  const [maxConcurrent, setMaxConcurrent] = useState(0)

  useEffect(() => { fetchSettings() }, [fetchSettings])

  useEffect(() => {
    if (settings) {
      setRetentionLimit(settings.task_retention_limit ?? 0)
      setMaxConcurrent(settings.max_concurrent_tasks ?? 0)
    }
  }, [settings])

  const handleSave = () => {
    save({ task_retention_limit: retentionLimit, max_concurrent_tasks: maxConcurrent })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Tasks</h1>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Task Retention</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Maximum number of completed tasks to keep. Set to 0 for unlimited retention.
          </p>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Retention limit</label>
            <input
              type="number"
              min="0"
              value={retentionLimit}
              onChange={(e) => setRetentionLimit(Math.max(0, parseInt(e.target.value) || 0))}
              className={inputClass}
              placeholder="0"
            />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Concurrency</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Maximum number of tasks that can run simultaneously. Set to 0 for unlimited.
          </p>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Max concurrent tasks</label>
            <input
              type="number"
              min="0"
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(Math.max(0, parseInt(e.target.value) || 0))}
              className={inputClass}
              placeholder="0"
            />
          </div>
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

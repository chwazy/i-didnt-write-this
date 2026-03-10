import { useState } from 'react'
import useStore from '@/store/useStore'

export const inputClass = "w-full px-3 py-2 bg-muted border border-input rounded-md text-foreground focus:outline-none focus:border-primary"

export function useSettingsSave() {
  const settings = useStore((s) => s.settings)
  const updateSettings = useStore((s) => s.updateSettings)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState(null)

  const save = async (partialUpdate) => {
    setSaving(true)
    setFeedback(null)
    try {
      await updateSettings({
        git_user_name: settings?.git_user_name || 'Claude',
        git_user_email: settings?.git_user_email || 'claude@agent.ai',
        default_merge_option: settings?.default_merge_option || 'none',
        task_retention_limit: settings?.task_retention_limit ?? 0,
        max_concurrent_tasks: settings?.max_concurrent_tasks ?? 0,
        notifications_enabled: settings?.notifications_enabled ?? true,
        default_model: settings?.default_model,
        ...partialUpdate,
      })
      setFeedback({ type: 'success', message: 'Settings saved' })
    } catch (err) {
      setFeedback({ type: 'error', message: err.message })
    } finally {
      setSaving(false)
    }
  }

  return { settings, save, saving, feedback }
}

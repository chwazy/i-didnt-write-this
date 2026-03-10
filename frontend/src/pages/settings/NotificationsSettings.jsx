import { useEffect, useState } from 'react'
import useStore from '@/store/useStore'
import { Save } from 'lucide-react'
import { isNotificationSupported } from '@/lib/notifications'
import { useSettingsSave } from './useSettingsSave'

export default function NotificationsSettings() {
  const fetchSettings = useStore((s) => s.fetchSettings)
  const { settings, save, saving, feedback } = useSettingsSave()

  const [notificationsEnabled, setNotificationsEnabled] = useState(true)

  useEffect(() => { fetchSettings() }, [fetchSettings])

  useEffect(() => {
    if (settings) {
      setNotificationsEnabled(settings.notifications_enabled ?? true)
    }
  }, [settings])

  const handleSave = () => {
    save({ notifications_enabled: notificationsEnabled })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Notifications</h1>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Browser Notifications</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Receive OS-level notifications when a task finishes (completes or fails). Can be overridden per project.
          </p>
          {isNotificationSupported() ? (
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notificationsEnabled}
                  onChange={(e) => setNotificationsEnabled(e.target.checked)}
                  className="w-4 h-4 rounded border-input text-primary focus:ring-primary"
                />
                <span className="text-sm text-foreground">Enable browser notifications</span>
              </label>
              <div className="text-xs text-muted-foreground">
                {typeof Notification !== 'undefined' && Notification.permission === 'granted' && (
                  <span className="text-green-500">Browser permission: granted</span>
                )}
                {typeof Notification !== 'undefined' && Notification.permission === 'denied' && (
                  <span className="text-red-400">Browser permission: denied. You must enable notifications in your browser settings.</span>
                )}
                {typeof Notification !== 'undefined' && Notification.permission === 'default' && (
                  <span>Browser permission: not yet requested. You will be prompted when visiting the dashboard.</span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-yellow-500 dark:text-yellow-400">
              Browser notifications are not supported in this environment (requires HTTPS or localhost).
            </p>
          )}
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

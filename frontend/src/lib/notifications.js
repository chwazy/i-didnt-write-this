export function isNotificationSupported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

export async function requestNotificationPermission() {
  if (!isNotificationSupported()) return 'unsupported'
  if (Notification.permission === 'granted' || Notification.permission === 'denied') {
    return Notification.permission
  }
  try {
    return await Notification.requestPermission()
  } catch {
    return 'denied'
  }
}

export function sendNotification(title, options = {}) {
  if (!isNotificationSupported()) return
  if (Notification.permission !== 'granted') return
  try {
    const n = new Notification(title, {
      ...options,
    })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    // Silently ignore — e.g. non-secure context
  }
}

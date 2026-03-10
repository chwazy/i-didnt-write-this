import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export const MODEL_DISPLAY_NAMES = {
  'claude-sonnet-4-6': { full: 'Sonnet 4.6 - Balanced', short: 'Sonnet 4.6' },
  'claude-opus-4-6': { full: 'Opus 4.6 - Most capable', short: 'Opus 4.6' },
  'claude-haiku-4-5-20251001': { full: 'Haiku 4.5 - Simple tasks', short: 'Haiku 4.5' },
}

export function getModelDisplayName(modelId, format = 'full') {
  const model = MODEL_DISPLAY_NAMES[modelId]
  return model ? model[format] : modelId
}

export function relativeTime(dateStr) {
  const date = new Date(dateStr)
  const now = new Date()
  const seconds = Math.floor((now - date) / 1000)

  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function formatDuration(created, finished) {
  const start = new Date(created)
  const end = finished ? new Date(finished) : new Date()
  const seconds = Math.floor((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins < 60) return `${mins}m ${secs}s`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hrs}h ${remMins}m`
}

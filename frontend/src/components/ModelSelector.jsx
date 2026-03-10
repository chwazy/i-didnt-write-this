import { getModelDisplayName } from '../lib/utils'

const MODELS = [
  { value: "claude-sonnet-4-6",          label: "Sonnet 4.6 - Balanced" },
  { value: "claude-opus-4-6",            label: "Opus 4.6 - Most capable" },
  { value: "claude-haiku-4-5-20251001",  label: "Haiku 4.5 - Simple tasks" },
]

export const MODEL_LABELS = Object.fromEntries(
  MODELS.map(m => [m.value, getModelDisplayName(m.value, 'short')])
)

export default function ModelSelector({ value, onChange, label = "Model", className = "" }) {
  const inputClass = className || "w-full px-3 py-2 bg-muted border border-input rounded-md text-foreground focus:outline-none focus:border-primary"

  return (
    <div>
      <label className="block text-sm font-medium text-muted-foreground mb-1">{label}</label>
      <select
        value={value || "claude-sonnet-4-6"}
        onChange={e => onChange(e.target.value)}
        className={inputClass}
      >
        {MODELS.map(m => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
    </div>
  )
}

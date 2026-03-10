import useStore from '@/store/useStore'
import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

const themeColors = [
  { key: 'blue',   label: 'Blue',   swatch: '#3b82f6' },
  { key: 'purple', label: 'Purple', swatch: '#8b5cf6' },
  { key: 'rose',   label: 'Rose',   swatch: '#f43f5e' },
  { key: 'orange', label: 'Orange', swatch: '#f97316' },
  { key: 'green',  label: 'Green',  swatch: '#22c55e' },
  { key: 'zinc',   label: 'Zinc',   swatch: '#71717a' },
]

export default function AppearanceSettings() {
  const themeColor = useStore((s) => s.themeColor)
  const setThemeColor = useStore((s) => s.setThemeColor)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Appearance</h1>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-2">Color Theme</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Choose an accent color for buttons, active states, and interactive elements.
          </p>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            {themeColors.map(({ key, label, swatch }) => (
              <button
                key={key}
                onClick={() => setThemeColor(key)}
                className={cn(
                  'flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-colors',
                  themeColor === key
                    ? 'border-foreground'
                    : 'border-border hover:border-muted-foreground'
                )}
              >
                <div className="relative w-8 h-8 rounded-full" style={{ backgroundColor: swatch }}>
                  {themeColor === key && (
                    <Check className="absolute inset-0 m-auto w-4 h-4 text-white" strokeWidth={3} />
                  )}
                </div>
                <span className="text-xs text-muted-foreground">{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

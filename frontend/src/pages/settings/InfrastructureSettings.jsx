import { useEffect } from 'react'
import useStore from '@/store/useStore'
import { CheckCircle, XCircle, Info, BarChart2, AlertCircle } from 'lucide-react'

function StatusRow({ label, ok, detail }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{detail}</span>
        {ok ? (
          <CheckCircle className="w-4 h-4 text-green-400" />
        ) : (
          <XCircle className="w-4 h-4 text-red-400" />
        )}
      </div>
    </div>
  )
}

function UsageSummaryCard({ usage }) {
  if (!usage) return null

  const periodLabel = usage.period_start
    ? `${usage.period_start} – ${usage.period_end}`
    : null

  const formatTokens = (n) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return String(n)
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">API Usage</h2>
          {periodLabel && (
            <span className="text-xs text-muted-foreground">({periodLabel})</span>
          )}
        </div>
      </div>

      {usage.error ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{usage.error}</span>
        </div>
      ) : (
        <div className="flex flex-wrap gap-6">
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">Input tokens</p>
            <p className="text-lg font-semibold text-foreground">{formatTokens(usage.total_input_tokens)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">Output tokens</p>
            <p className="text-lg font-semibold text-foreground">{formatTokens(usage.total_output_tokens)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">Est. cost</p>
            <p className="text-lg font-semibold text-foreground">${usage.total_estimated_cost_usd.toFixed(2)}</p>
          </div>
          {usage.by_model.length > 1 && (
            <div className="w-full mt-1">
              <p className="text-xs text-muted-foreground mb-1.5">By model</p>
              <div className="flex flex-wrap gap-3">
                {usage.by_model.map((m) => (
                  <div key={m.model} className="text-xs text-muted-foreground bg-muted rounded px-2 py-1">
                    <span className="font-medium text-foreground">{m.model}</span>
                    {' · '}in {formatTokens(m.input_tokens)}
                    {' · '}out {formatTokens(m.output_tokens)}
                    {' · '}${m.estimated_cost_usd.toFixed(2)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function InfrastructureSettings() {
  const health = useStore((s) => s.health)
  const usage = useStore((s) => s.usage)
  const fetchHealth = useStore((s) => s.fetchHealth)
  const fetchUsage = useStore((s) => s.fetchUsage)

  useEffect(() => { fetchHealth(); fetchUsage() }, [fetchHealth, fetchUsage])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Infrastructure</h1>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">System Status</h2>
          {health ? (
            <div className="space-y-3">
              <StatusRow
                label="Backend API"
                ok={health.status === 'ok'}
                detail={health.status === 'ok' ? 'Running' : 'Error'}
              />
              <StatusRow
                label="Docker Connection"
                ok={health.docker}
                detail={health.docker ? 'Connected' : 'Not available'}
              />
              <StatusRow
                label="Anthropic API Key"
                ok={health.anthropic_api_key}
                detail={health.anthropic_api_key ? 'Configured' : 'Not set'}
              />
              <StatusRow
                label="Anthropic Admin API Key"
                ok={health.anthropic_admin_api_key}
                detail={health.anthropic_admin_api_key ? 'Configured' : 'Not set (required for usage dashboard)'}
              />
            </div>
          ) : (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </div>

        <UsageSummaryCard usage={usage} />

        <div className="bg-card border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">Utility Scripts</h2>
          <div className="text-sm text-muted-foreground space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-1">Anthropic API Key</h3>
              <p>Set the <code className="text-xs bg-muted px-1 rounded">ANTHROPIC_API_KEY</code> environment variable for both the backend (prompt generation) and agent containers (Claude CLI).</p>
              <div className="bg-background border border-border rounded p-3 font-mono text-xs text-foreground mt-2">
                <p>ANTHROPIC_API_KEY=sk-ant-... docker-compose up --build</p>
              </div>
              <div className="flex items-start gap-2 mt-2 text-muted-foreground">
                <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <p>You can also add it to a <code className="text-xs bg-muted px-1 rounded">.env</code> file in the project root. The key is required for both prompt generation and agent execution.</p>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-1">Anthropic Admin API Key (Usage Dashboard)</h3>
              <p>Set the <code className="text-xs bg-muted px-1 rounded">ANTHROPIC_ADMIN_API_KEY</code> environment variable to enable the API usage dashboard. This requires an Admin API key (<code className="text-xs bg-muted px-1 rounded">sk-ant-admin...</code>), which can be created in the Anthropic Console by organization admins.</p>
              <div className="bg-background border border-border rounded p-3 font-mono text-xs text-foreground mt-2">
                <p>ANTHROPIC_ADMIN_API_KEY=sk-ant-admin-... docker-compose up --build</p>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-1">Rebuild &amp; Restart Stack</h3>
              <p>Stops all running containers, rebuilds the agent Docker image, and restarts the full stack via docker-compose.</p>
              <div className="bg-background border border-border rounded p-3 font-mono text-xs text-foreground mt-2">
                <p>./rebuild.ps1</p>
              </div>
              <div className="flex items-start gap-2 mt-2 text-muted-foreground">
                <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <p>Useful after pulling new changes or modifying the agent configuration.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

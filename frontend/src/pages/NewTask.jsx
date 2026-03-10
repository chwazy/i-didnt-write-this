import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useStore from '../store/useStore'
import { api } from '../lib/api'
import { ChevronDown, ChevronRight } from 'lucide-react'
import ModelSelector from '../components/ModelSelector'

export default function NewTask() {
  const projects = useStore((s) => s.projects)
  const tasks = useStore((s) => s.tasks)
  const fetchProjects = useStore((s) => s.fetchProjects)
  const fetchTasks = useStore((s) => s.fetchTasks)
  const settings = useStore((s) => s.settings)
  const fetchSettings = useStore((s) => s.fetchSettings)
  const createTask = useStore((s) => s.createTask)
  const navigate = useNavigate()

  const [form, setForm] = useState({
    project_id: '',
    branch_name: 'main',
    task_description: '',
    merge_option: '',
    model: '',
    git_user_name: '',
    git_user_email: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const formRef = useRef(null)

  const [branches, setBranches] = useState([])
  const [branchesLoading, setBranchesLoading] = useState(false)
  const [branchesError, setBranchesError] = useState(null)

  useEffect(() => {
    fetchProjects()
    fetchTasks()
    fetchSettings()
  }, [fetchProjects, fetchTasks, fetchSettings])

  useEffect(() => {
    if (form.project_id || projects.length === 0 || tasks.length === 0) return
    const lastTask = tasks[0]
    if (projects.some(p => p.id === lastTask.project_id)) {
      const pid = String(lastTask.project_id)
      const selectedProject = projects.find(p => p.id === lastTask.project_id)
      const preferredBranch = selectedProject?.last_base_branch || 'main'
      setForm(f => ({ ...f, project_id: pid, branch_name: preferredBranch }))
    }
  }, [projects, tasks])

  useEffect(() => {
    if (!form.project_id) {
      setBranches([])
      setBranchesError(null)
      return
    }

    let cancelled = false
    setBranchesLoading(true)
    setBranchesError(null)

    api.getBranches(form.project_id)
      .then((data) => {
        if (cancelled) return
        setBranches(data)
        const selectedProject = projects.find(p => p.id === parseInt(form.project_id))
        const preferredBranch = selectedProject?.last_base_branch || 'main'
        if (data.length > 0) {
          if (data.includes(preferredBranch)) {
            setForm((f) => ({ ...f, branch_name: preferredBranch }))
          } else if (!data.includes(form.branch_name)) {
            setForm((f) => ({ ...f, branch_name: data[0] }))
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        setBranchesError('Could not load branches')
        setBranches([])
      })
      .finally(() => {
        if (!cancelled) setBranchesLoading(false)
      })

    return () => { cancelled = true }
  }, [form.project_id])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const data = {
        project_id: parseInt(form.project_id),
        branch_name: form.branch_name,
        task_description: form.task_description,
      }
      if (form.merge_option) data.merge_option = form.merge_option
      // Always include model (use form value, project default, or fallback)
      data.model = form.model || selectedProject?.default_model || 'claude-sonnet-4-6'
      if (form.git_user_name.trim()) data.git_user_name = form.git_user_name.trim()
      if (form.git_user_email.trim()) data.git_user_email = form.git_user_email.trim()

      // Start task creation without waiting for completion
      createTask(data).catch(err => {
        // If creation fails, the error will be logged but user already navigated
        console.error('Task creation failed:', err)
      })

      // Navigate immediately - user will see task appear on dashboard
      navigate('/')
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  const selectedProject = projects.find((p) => String(p.id) === String(form.project_id))
  const effectiveDefault = selectedProject?.merge_option || settings?.default_merge_option || 'none'
  const effectiveDefaultLabel = { none: 'None', pull_request: 'Pull Request', auto_squash_merge: 'Auto Squash Merge' }[effectiveDefault] || effectiveDefault

  const selectClass = "w-full px-3 py-2 bg-muted border border-input rounded-md text-foreground focus:outline-none focus:border-primary"

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">New Task</h1>

      <form ref={formRef} onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Project</label>
          <select
            required
            value={form.project_id}
            onChange={(e) => {
              const pid = e.target.value
              const selectedProject = projects.find(p => p.id === parseInt(pid))
              const preferredBranch = selectedProject?.last_base_branch || 'main'
              setForm({ ...form, project_id: pid, branch_name: preferredBranch })
            }}
            className={selectClass}
          >
            <option value="">Select a project...</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Base Branch</label>
          {branchesLoading ? (
            <div className={`${selectClass} flex items-center gap-2 text-muted-foreground`}>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Loading branches...
            </div>
          ) : branches.length > 0 ? (
            <select
              value={form.branch_name}
              onChange={(e) => setForm({ ...form, branch_name: e.target.value })}
              className={selectClass}
            >
              {branches.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={form.branch_name}
              onChange={(e) => setForm({ ...form, branch_name: e.target.value })}
              className={selectClass}
              placeholder="main"
            />
          )}
          {branchesError && (
            <p className="text-xs text-yellow-500 mt-1">{branchesError}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Task Description</label>
          <textarea
            required
            rows={8}
            value={form.task_description}
            onChange={(e) => setForm({ ...form, task_description: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                formRef.current?.requestSubmit()
              }
            }}
            className="w-full px-3 py-2 bg-muted border border-input rounded-md text-foreground focus:outline-none focus:border-primary resize-y"
            placeholder="Describe what the Claude agent should do..."
          />
          <p className="text-xs text-muted-foreground mt-1">Press Enter to start agent · Shift+Enter for new line</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Merge Option</label>
          <select
            value={form.merge_option}
            onChange={(e) => setForm({ ...form, merge_option: e.target.value })}
            className={selectClass}
          >
            <option value="">Use default ({effectiveDefaultLabel})</option>
            <option value="none">None — no merge or PR after completion</option>
            <option value="pull_request">Pull Request — open a PR to the base branch</option>
            <option value="auto_squash_merge">Auto Squash Merge — squash and merge into base branch</option>
          </select>
        </div>

        <ModelSelector
          value={form.model || selectedProject?.default_model || 'claude-sonnet-4-6'}
          onChange={(v) => setForm({ ...form, model: v })}
          className={selectClass}
        />

        <div className="border border-border rounded-lg">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 w-full px-4 py-3 text-sm font-medium text-muted-foreground hover:text-accent-foreground"
          >
            {showAdvanced ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            Advanced
          </button>
          {showAdvanced && (
            <div className="px-4 pb-4 space-y-4">
              <p className="text-xs text-muted-foreground">Leave blank to use the project or global git identity</p>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">Git User Name</label>
                <input
                  type="text"
                  value={form.git_user_name}
                  onChange={(e) => setForm({ ...form, git_user_name: e.target.value })}
                  className={selectClass}
                  placeholder="Inherit from project / settings"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">Git User Email</label>
                <input
                  type="email"
                  value={form.git_user_email}
                  onChange={(e) => setForm({ ...form, git_user_email: e.target.value })}
                  className={selectClass}
                  placeholder="Inherit from project / settings"
                />
              </div>
            </div>
          )}
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-accent-foreground border border-input rounded-md hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !form.project_id}
            className="px-6 py-2 text-sm text-primary-foreground bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50"
          >
            {submitting ? 'Starting Agent...' : 'Start Agent'}
          </button>
        </div>
      </form>
    </div>
  )
}

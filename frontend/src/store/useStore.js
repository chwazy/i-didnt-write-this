import { create } from 'zustand'
import { api } from '../lib/api'

function getInitialTheme() {
  const stored = localStorage.getItem('theme')
  if (stored) return stored
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function getInitialThemeColor() {
  return localStorage.getItem('theme-color') || 'blue'
}

const useStore = create((set, get) => ({
  projects: [],
  tasks: [],
  health: null,
  settings: null,
  usage: null,
  loading: false,
  theme: getInitialTheme(),
  themeColor: getInitialThemeColor(),

  setTheme: (theme) => {
    localStorage.setItem('theme', theme)
    set({ theme })
  },

  setThemeColor: (color) => {
    localStorage.setItem('theme-color', color)
    set({ themeColor: color })
  },

  fetchProjects: async () => {
    const projects = await api.getProjects()
    set({ projects })
  },

  fetchTasks: async () => {
    const tasks = await api.getTasks()
    set({ tasks })
  },

  fetchHealth: async () => {
    try {
      const health = await api.getHealth()
      set({ health })
    } catch {
      set({ health: { status: 'error', docker: false, anthropic_api_key: false, anthropic_admin_api_key: false } })
    }
  },

  fetchSettings: async () => {
    try {
      const settings = await api.getSettings()
      set({ settings })
    } catch {
      set({ settings: null })
    }
  },

  fetchUsage: async () => {
    try {
      const usage = await api.getUsage()
      set({ usage })
    } catch {
      set({ usage: null })
    }
  },

  updateSettings: async (data) => {
    const settings = await api.updateSettings(data)
    set({ settings })
    return settings
  },

  createProject: async (data) => {
    await api.createProject(data)
    await get().fetchProjects()
  },

  updateProject: async (id, data) => {
    await api.updateProject(id, data)
    await get().fetchProjects()
  },

  deleteProject: async (id) => {
    await api.deleteProject(id)
    await get().fetchProjects()
  },

  createTask: async (data) => {
    // Optimistically add task immediately with queued status
    const tempId = `temp-${Date.now()}`
    const optimisticTask = {
      id: tempId,
      project_id: data.project_id,
      branch_name: data.branch_name,
      title: 'Creating task...',
      task_description: data.task_description,
      merge_option: data.merge_option || 'none',
      model: data.model,
      status: 'queued',
      container_id: null,
      pr_url: null,
      warning: null,
      created_at: new Date().toISOString(),
      finished_at: null,
      project_name: get().projects.find(p => p.id === data.project_id)?.name,
    }

    // Add optimistic task immediately
    set((state) => ({ tasks: [optimisticTask, ...state.tasks] }))

    try {
      // Create task on backend
      const task = await api.createTask(data)

      // Replace optimistic task with real task
      set((state) => ({
        tasks: state.tasks.map(t => t.id === tempId ? task : t)
      }))

      // Refresh to ensure consistency
      get().fetchTasks()

      return task
    } catch (error) {
      // Remove optimistic task on error
      set((state) => ({
        tasks: state.tasks.filter(t => t.id !== tempId)
      }))
      throw error
    }
  },

  killTask: async (id) => {
    await api.killTask(id)
    await get().fetchTasks()
  },

  deleteTask: async (id) => {
    await api.killTask(id)
    await get().fetchTasks()
  },

  retryTask: async (id) => {
    const task = await api.retryTask(id)
    await get().fetchTasks()
    return task
  },
}))

export default useStore

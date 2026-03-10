import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import NewTask from './pages/NewTask'
import GeneralSettings from './pages/settings/GeneralSettings'
import AppearanceSettings from './pages/settings/AppearanceSettings'
import NotificationsSettings from './pages/settings/NotificationsSettings'
import TasksSettings from './pages/settings/TasksSettings'
import InfrastructureSettings from './pages/settings/InfrastructureSettings'
import AboutSettings from './pages/settings/AboutSettings'
import { Layout } from './components/Layout'
import useStore from './store/useStore'

export default function App() {
  const theme = useStore((s) => s.theme)
  const themeColor = useStore((s) => s.themeColor)

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeColor)
  }, [themeColor])

  return (
    <BrowserRouter>
      <div className="h-screen bg-background text-foreground">
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/tasks/new" element={<NewTask />} />
            <Route path="/settings" element={<Navigate to="/settings/general" replace />} />
            <Route path="/settings/general" element={<GeneralSettings />} />
            <Route path="/settings/appearance" element={<AppearanceSettings />} />
            <Route path="/settings/notifications" element={<NotificationsSettings />} />
            <Route path="/settings/tasks" element={<TasksSettings />} />
            <Route path="/settings/infrastructure" element={<InfrastructureSettings />} />
            <Route path="/settings/about" element={<AboutSettings />} />
          </Routes>
        </Layout>
      </div>
    </BrowserRouter>
  )
}

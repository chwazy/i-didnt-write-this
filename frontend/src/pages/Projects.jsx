import { useEffect, useState } from 'react'
import useStore from '../store/useStore'
import AddProjectDialog from '../components/AddProjectDialog'
import EditProjectDialog from '../components/EditProjectDialog'
import { Plus, Trash2, Globe, Pencil } from 'lucide-react'

const platformColors = {
  github: 'text-foreground',
  gitlab: 'text-orange-400',
  azure: 'text-blue-400',
}

export default function Projects() {
  const projects = useStore((s) => s.projects)
  const fetchProjects = useStore((s) => s.fetchProjects)
  const deleteProject = useStore((s) => s.deleteProject)
  const [showAdd, setShowAdd] = useState(false)
  const [editProject, setEditProject] = useState(null)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm text-primary-foreground bg-primary rounded-md hover:bg-primary-hover"
        >
          <Plus className="w-4 h-4" /> Add Project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-muted-foreground text-lg">No projects registered</p>
          <p className="text-muted-foreground text-sm mt-1">Add a project to start running agents</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <div
              key={project.id}
              className="bg-card border border-border rounded-lg p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-foreground">{project.name}</h3>
                <span className={`text-xs font-medium uppercase ${platformColors[project.platform]}`}>
                  {project.platform}
                </span>
              </div>

              <div className="space-y-1 text-sm text-muted-foreground mb-3">
                <div className="flex items-center gap-1 truncate">
                  <Globe className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate">{project.repo_url}</span>
                </div>
                {project.git_host && (
                  <p className="text-xs">Host: {project.git_host}</p>
                )}
              </div>

              <div className="flex justify-end gap-1">
                <button
                  onClick={() => setEditProject(project)}
                  className="p-1.5 text-muted-foreground hover:text-primary hover:bg-accent rounded"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => {
                    if (confirm('Delete this project? All associated tasks will also be deleted.')) {
                      deleteProject(project.id)
                    }
                  }}
                  className="p-1.5 text-muted-foreground hover:text-red-400 hover:bg-accent rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <AddProjectDialog open={showAdd} onClose={() => setShowAdd(false)} />
      <EditProjectDialog open={!!editProject} project={editProject} onClose={() => setEditProject(null)} />
    </div>
  )
}

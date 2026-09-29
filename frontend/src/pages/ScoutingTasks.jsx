import { useState, useEffect, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import { fetchScoutingTasks, fetchScoutingTask, updateScoutingTask } from '../api'

const USERS = {
  bd_manager: { id: '00000000-0000-0000-0000-000000000001', name: 'Priya Sharma' },
  bd_executive: { id: '00000000-0000-0000-0000-000000000002', name: 'Arjun Patel' },
}

const STATUS_STYLES = {
  assigned: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Assigned' },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'In Progress' },
  completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Completed' },
  cancelled: { bg: 'bg-gray-100', text: 'text-gray-500', label: 'Cancelled' },
}

function TaskCard({ task, onSelect, isSelected }) {
  const ss = STATUS_STYLES[task.status] || STATUS_STYLES.assigned
  return (
    <button
      onClick={() => onSelect(task.task_id)}
      className={`w-full text-left rounded-lg border p-3 transition-all ${
        isSelected ? 'border-savo-purple bg-savo-purple/5 shadow-sm' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-gray-800">{task.pincode}</span>
          <span className="text-xs text-gray-400">Hotspot #{task.hotspot_rank}</span>
        </div>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${ss.bg} ${ss.text}`}>{ss.label}</span>
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-3">
          <span>Score <span className="font-semibold text-gray-700">{task.hotspot_score}</span></span>
          <span>{task.executive_name}</span>
        </div>
        <span className="text-[10px] text-gray-400 tabular-nums">
          {new Date(task.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}{' '}
          {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      {task.notes && <p className="text-[10px] text-gray-400 mt-1 truncate">{task.notes}</p>}
    </button>
  )
}

function TaskDetail({ task, role, onStatusUpdate }) {
  const [updating, setUpdating] = useState(false)
  const ss = STATUS_STYLES[task.status] || STATUS_STYLES.assigned

  const transitions = task.status === 'assigned'
    ? [{ to: 'in_progress', label: 'Start Scouting', color: 'bg-amber-500 hover:bg-amber-600' }, { to: 'cancelled', label: 'Cancel', color: 'bg-gray-400 hover:bg-gray-500' }]
    : task.status === 'in_progress'
    ? [{ to: 'completed', label: 'Mark Complete', color: 'bg-emerald-500 hover:bg-emerald-600' }, { to: 'cancelled', label: 'Cancel', color: 'bg-gray-400 hover:bg-gray-500' }]
    : []

  const handleTransition = async (newStatus) => {
    setUpdating(true)
    try {
      await onStatusUpdate(task.task_id, newStatus)
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-lg font-bold text-gray-800">{task.pincode}</h3>
          <span className="text-sm text-gray-400">Hotspot #{task.hotspot_rank}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${ss.bg} ${ss.text}`}>{ss.label}</span>
        </div>
        <p className="text-xs text-gray-400">
          Created {new Date(task.created_at).toLocaleString()}
          {task.updated_at !== task.created_at && ` · Updated ${new Date(task.updated_at).toLocaleString()}`}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Hotspot Score</div>
          <div className="text-2xl font-bold text-savo-purple">{task.hotspot_score}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Location</div>
          <div className="text-sm font-mono text-gray-600">
            {task.centroid ? `${task.centroid.lat.toFixed(4)}, ${task.centroid.lng.toFixed(4)}` : '—'}
          </div>
        </div>
      </div>

      {task.hotspot_signals && (
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">Hotspot Signals</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {task.hotspot_signals.sub_scores && Object.entries(task.hotspot_signals.sub_scores).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-gray-500">{k.replace(/_/g, ' ')}</span>
                <span className="font-semibold text-gray-700 tabular-nums">{v}</span>
              </div>
            ))}
            {task.hotspot_signals.signals && Object.entries(task.hotspot_signals.signals).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-gray-500">{k.replace(/_/g, ' ')}</span>
                <span className="font-semibold text-gray-700 tabular-nums">{typeof v === 'boolean' ? (v ? 'Yes' : 'No') : v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-400 w-20">Assigned to</span>
          <span className="font-medium text-gray-700">{task.assigned_to.name}</span>
          <span className="text-gray-400">{task.assigned_to.email}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-400 w-20">Assigned by</span>
          <span className="font-medium text-gray-700">{task.assigned_by.name}</span>
          <span className="text-gray-400">{task.assigned_by.email}</span>
        </div>
        {task.notes && (
          <div className="text-xs">
            <span className="text-gray-400 w-20 inline-block">Notes</span>
            <span className="text-gray-600">{task.notes}</span>
          </div>
        )}
      </div>

      {transitions.length > 0 && (
        <div className="flex gap-2 pt-2 border-t border-gray-100">
          {transitions.map(t => (
            <button
              key={t.to}
              onClick={() => handleTransition(t.to)}
              disabled={updating}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors ${t.color} disabled:opacity-50`}
            >
              {updating ? '...' : t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ScoutingTasks() {
  const { role } = useOutletContext()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const currentUser = USERS[role]

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (role === 'bd_executive' && currentUser) {
        params.assigned_to = currentUser.id
      }
      const data = await fetchScoutingTasks(params)
      setTasks(data.tasks)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [role, currentUser])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  const selectTask = useCallback(async (taskId) => {
    setSelectedId(taskId)
    setDetailLoading(true)
    try {
      const data = await fetchScoutingTask(taskId)
      setDetail(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const handleStatusUpdate = useCallback(async (taskId, newStatus) => {
    await updateScoutingTask(taskId, { status: newStatus })
    const updated = await fetchScoutingTask(taskId)
    setDetail(updated)
    await loadTasks()
  }, [loadTasks])

  return (
    <div className="flex-1 flex min-h-0">
      <div className="w-[340px] border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-800">Scouting Tasks</h2>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {role === 'bd_executive' ? 'Your assigned tasks' : 'All scouting assignments'}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && (
            <div className="py-8 text-center">
              <div className="relative w-6 h-6 mx-auto">
                <div className="w-6 h-6 border-2 border-gray-200 rounded-full" />
                <div className="w-6 h-6 border-2 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
              </div>
              <p className="text-xs text-gray-400 mt-2">Loading tasks...</p>
            </div>
          )}
          {error && <div className="p-2 bg-red-50 rounded text-xs text-red-600">{error}</div>}
          {!loading && !error && tasks.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-400">No scouting tasks yet</p>
              <p className="text-[10px] text-gray-300 mt-1">
                {role === 'bd_manager'
                  ? 'Assign hotspots from Area Intelligence'
                  : 'Tasks assigned to you will appear here'}
              </p>
            </div>
          )}
          {tasks.map(t => (
            <TaskCard key={t.task_id} task={t} onSelect={selectTask} isSelected={selectedId === t.task_id} />
          ))}
        </div>
      </div>

      <div className="flex-1 bg-white flex items-start justify-center p-6 overflow-y-auto">
        {detailLoading && (
          <div className="py-12 text-center">
            <div className="relative w-8 h-8 mx-auto">
              <div className="w-8 h-8 border-2 border-gray-200 rounded-full" />
              <div className="w-8 h-8 border-2 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
            </div>
          </div>
        )}
        {!detailLoading && detail && (
          <div className="w-full max-w-lg">
            <TaskDetail task={detail} role={role} onStatusUpdate={handleStatusUpdate} />
          </div>
        )}
        {!detailLoading && !detail && (
          <div className="py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-savo-purple/5 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-savo-purple/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-sm text-gray-400 mt-3">Select a task to view details</p>
          </div>
        )}
      </div>
    </div>
  )
}

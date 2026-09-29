import { useState, useEffect } from 'react'
import { fetchAttentionItems } from '../api'

const ROLE_USERS = {
  bd_manager: '00000000-0000-0000-0000-000000000001',
  bd_executive: '00000000-0000-0000-0000-000000000002',
  survey_manager: '00000000-0000-0000-0000-000000000003',
  survey_executive: '00000000-0000-0000-0000-000000000004',
}

const PRIORITY_STYLES = {
  high: 'bg-red-50 border-red-200 text-red-800',
  medium: 'bg-amber-50 border-amber-200 text-amber-800',
  low: 'bg-blue-50 border-blue-200 text-blue-700',
}

const PRIORITY_DOT = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-400',
}

const TYPE_ICONS = {
  scouting_task: '📍',
  property_eval: '📊',
  catchment_needed: '🔄',
  catchment_study: '🗺️',
  assignment: '📋',
}

export default function NeedsAttention({ role }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchAttentionItems(ROLE_USERS[role], role)
      .then(data => { if (!cancelled) setItems(data.items || []) })
      .catch(() => { if (!cancelled) setItems([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [role])

  if (loading) return null
  if (items.length === 0) return null

  const highCount = items.filter(i => i.priority === 'high').length

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="max-w-screen-xl mx-auto px-4">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-between py-2 text-xs font-semibold text-gray-600 hover:text-gray-900 transition-colors"
        >
          <span className="flex items-center gap-2">
            <span>Needs Attention</span>
            <span className="px-1.5 py-0.5 rounded-full bg-savo-purple text-white text-[10px] font-bold">
              {items.length}
            </span>
            {highCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-bold">
                {highCount} urgent
              </span>
            )}
          </span>
          <span className="text-gray-400">{collapsed ? '▼' : '▲'}</span>
        </button>
        {!collapsed && (
          <div className="pb-3 grid gap-1.5">
            {items.map((item, i) => (
              <div
                key={i}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs ${PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.low}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIORITY_DOT[item.priority] || PRIORITY_DOT.low}`} />
                <span className="flex-shrink-0">{TYPE_ICONS[item.type] || '•'}</span>
                <span className="truncate">{item.title}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

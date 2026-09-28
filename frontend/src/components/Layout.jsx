import { useState } from 'react'
import { Outlet } from 'react-router-dom'

const ROLES = [
  { id: 'bd_manager', label: 'BD Manager' },
  { id: 'bd_executive', label: 'BD Executive' },
  { id: 'survey_manager', label: 'Survey Manager' },
  { id: 'survey_executive', label: 'Survey Executive' },
]

export default function Layout() {
  const [role, setRole] = useState('bd_manager')

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-savo-purple text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-savo-yellow font-bold text-xl">Savo SiteScout</span>
        </div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="bg-savo-purple-dark text-white border border-savo-purple-light rounded px-3 py-1 text-sm"
        >
          {ROLES.map((r) => (
            <option key={r.id} value={r.id}>{r.label}</option>
          ))}
        </select>
      </header>
      <main>
        <Outlet context={{ role }} />
      </main>
    </div>
  )
}

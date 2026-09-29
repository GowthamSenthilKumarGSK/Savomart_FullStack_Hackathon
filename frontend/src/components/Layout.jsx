import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'

const ROLES = [
  { id: 'bd_manager', label: 'BD Manager', icon: 'M' },
  { id: 'bd_executive', label: 'BD Executive', icon: 'E' },
  { id: 'survey_manager', label: 'Survey Manager', icon: 'M' },
  { id: 'survey_executive', label: 'Survey Executive', icon: 'E' },
]

export default function Layout() {
  const [role, setRole] = useState('bd_manager')
  const currentRole = ROLES.find(r => r.id === role)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-savo-purple h-12 px-4 flex items-center justify-between shadow-md relative z-50 flex-shrink-0">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-savo-yellow rounded flex items-center justify-center">
              <span className="text-savo-purple font-black text-sm">S</span>
            </div>
            <span className="text-white font-semibold text-sm tracking-wide">SiteScout</span>
          </div>
          <nav className="hidden sm:flex items-center gap-1">
            {[
              { to: '/areas', label: 'Area Intelligence' },
              { to: '/scouting', label: 'Scouting Tasks' },
              { to: '/catchment', label: 'Catchment Studies' },
            ].map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-white/20 text-white'
                      : 'text-white/70 hover:text-white hover:bg-white/10'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-white/10 rounded-lg px-2.5 py-1">
            <div className="w-5 h-5 rounded-full bg-savo-yellow flex items-center justify-center">
              <span className="text-savo-purple text-[10px] font-bold">{currentRole?.icon}</span>
            </div>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="bg-transparent text-white text-xs font-medium border-none outline-none cursor-pointer appearance-none pr-4"
              style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 5l3 3 3-3' stroke='white' stroke-width='1.5' fill='none'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0 center' }}
            >
              {ROLES.map((r) => (
                <option key={r.id} value={r.id} className="text-gray-900">{r.label}</option>
              ))}
            </select>
          </div>
        </div>
      </header>
      <main className="flex-1 flex flex-col">
        <Outlet context={{ role }} />
      </main>
    </div>
  )
}

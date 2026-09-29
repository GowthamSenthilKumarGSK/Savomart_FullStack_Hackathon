import { BrowserRouter, Routes, Route, Navigate, useOutletContext } from 'react-router-dom'
import Layout from './components/Layout'
import AreaExplorer from './pages/AreaExplorer'
import ScoutingTasks from './pages/ScoutingTasks'
import CatchmentStudies from './pages/CatchmentStudies'

const ROLE_HOME = {
  bd_manager: '/areas',
  bd_executive: '/scouting',
  survey_manager: '/catchment',
  survey_executive: '/catchment',
}

function RoleRedirect() {
  const { role } = useOutletContext()
  return <Navigate to={ROLE_HOME[role] || '/areas'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<RoleRedirect />} />
          <Route path="areas" element={<AreaExplorer />} />
          <Route path="scouting" element={<ScoutingTasks />} />
          <Route path="catchment" element={<CatchmentStudies />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import AreaExplorer from './pages/AreaExplorer'
import ScoutingTasks from './pages/ScoutingTasks'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/areas" replace />} />
          <Route path="areas" element={<AreaExplorer />} />
          <Route path="scouting" element={<ScoutingTasks />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

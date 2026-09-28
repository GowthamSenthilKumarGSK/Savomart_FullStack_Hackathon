import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

function Home() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-savo-purple">Savo SiteScout</h1>
      <p className="mt-2 text-gray-600">Expansion intelligence platform for Chennai</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

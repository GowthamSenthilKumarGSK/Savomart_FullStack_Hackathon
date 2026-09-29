import { useState, useEffect, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  fetchCatchmentStudies, fetchCatchmentStudy, createZoneAssignment,
  updateAssignmentStatus, fetchAssignmentRoads, submitLaneSurvey,
  fetchCatchmentInsight,
} from '../api'

const USERS = {
  survey_manager: { id: '00000000-0000-0000-0000-000000000003', name: 'Meena Krishnan' },
  survey_executive: { id: '00000000-0000-0000-0000-000000000004', name: 'Ravi Kumar' },
}

const STATUS_STYLES = {
  requested: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Requested' },
  planning: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Planning' },
  in_progress: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'In Progress' },
  completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Completed' },
}

const ASSIGNMENT_STATUS = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Pending' },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'In Progress' },
  completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Completed' },
}

const ZONE_COLORS = ['#782B90', '#2563EB', '#D97706', '#059669', '#DC2626', '#7C3AED']

const HOUSEHOLD_TYPES = ['apartments', 'individual', 'mixed']
const HOUSEHOLD_RANGES = ['<20', '20-50', '50-100', '100+']
const ROAD_CONDITIONS = ['excellent', 'good', 'fair', 'poor']
const FOOT_TRAFFIC_LEVELS = ['low', 'medium', 'high']
const SHOP_TYPE_OPTIONS = ['grocery', 'clothing', 'electronics', 'pharmacy', 'restaurant', 'hardware', 'other']

const propertyIcon = new L.Icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41],
})

function StudyCard({ study, onSelect, isSelected }) {
  const ss = STATUS_STYLES[study.status] || STATUS_STYLES.requested
  return (
    <button
      onClick={() => onSelect(study.study_id)}
      className={`w-full text-left rounded-lg border p-3 transition-all ${
        isSelected ? 'border-savo-purple bg-savo-purple/5 shadow-sm' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-gray-800">{study.property_pincode}</span>
          <span className="text-[10px] text-gray-400 truncate max-w-[140px]">{study.property_address}</span>
        </div>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${ss.bg} ${ss.text}`}>{ss.label}</span>
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-3">
          <span>{study.radius_m}m radius</span>
          <span>{study.assignment_count} zone{study.assignment_count !== 1 ? 's' : ''}</span>
        </div>
        <span className="text-[10px] text-gray-400 tabular-nums">
          {new Date(study.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
        </span>
      </div>
      <p className="text-[10px] text-gray-400 mt-0.5">Requested by {study.requested_by}</p>
    </button>
  )
}

function MapFitBounds({ boundary }) {
  const map = useMap()
  useEffect(() => {
    if (!boundary?.coordinates?.[0]) return
    const coords = boundary.coordinates[0].map(c => [c[1], c[0]])
    map.fitBounds(L.latLngBounds(coords), { padding: [30, 30] })
  }, [boundary, map])
  return null
}

function ZoneDrawer({ onAddPoint, drawing }) {
  useMapEvents({ click(e) { if (drawing) onAddPoint([e.latlng.lat, e.latlng.lng]) } })
  return null
}

function LaneSurveyForm({ road, assignmentId, onDone }) {
  const [form, setForm] = useState({
    household_type: '', household_count_range: '', shop_count: '',
    shop_types: [], road_condition: '', foot_traffic: '', notes: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }))
  const toggleShopType = (t) => setForm(prev => ({
    ...prev,
    shop_types: prev.shop_types.includes(t)
      ? prev.shop_types.filter(x => x !== t)
      : [...prev.shop_types, t],
  }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await submitLaneSurvey(assignmentId, {
        road_id: road.road_id,
        user_id: USERS.survey_executive.id,
        household_type: form.household_type || null,
        household_count_range: form.household_count_range || null,
        shop_count: form.shop_count ? parseInt(form.shop_count, 10) : null,
        shop_types: form.shop_types.length ? form.shop_types : null,
        road_condition: form.road_condition || null,
        foot_traffic: form.foot_traffic || null,
        notes: form.notes || null,
      })
      if (onDone) onDone()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const selectCls = "w-full px-2 py-1.5 text-xs border border-gray-200 rounded bg-white focus:border-savo-purple focus:outline-none"

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-savo-purple/20 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-gray-700">{road.name}</h4>
        <span className="text-[10px] text-gray-400">{road.road_type}</span>
      </div>
      {error && <div className="p-1.5 bg-red-50 rounded text-[10px] text-red-600">{error}</div>}

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-gray-500 block mb-0.5">Household Type</label>
          <select value={form.household_type} onChange={e => set('household_type', e.target.value)} className={selectCls}>
            <option value="">Select...</option>
            {HOUSEHOLD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 block mb-0.5">Household Count</label>
          <select value={form.household_count_range} onChange={e => set('household_count_range', e.target.value)} className={selectCls}>
            <option value="">Select...</option>
            {HOUSEHOLD_RANGES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 block mb-0.5">Road Condition</label>
          <select value={form.road_condition} onChange={e => set('road_condition', e.target.value)} className={selectCls}>
            <option value="">Select...</option>
            {ROAD_CONDITIONS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 block mb-0.5">Foot Traffic</label>
          <select value={form.foot_traffic} onChange={e => set('foot_traffic', e.target.value)} className={selectCls}>
            <option value="">Select...</option>
            {FOOT_TRAFFIC_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 block mb-0.5">Shop Count</label>
          <input type="number" min="0" value={form.shop_count} onChange={e => set('shop_count', e.target.value)}
            className={selectCls} placeholder="0" />
        </div>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 block mb-1">Shop Types</label>
        <div className="flex flex-wrap gap-1">
          {SHOP_TYPE_OPTIONS.map(t => (
            <button key={t} type="button" onClick={() => toggleShopType(t)}
              className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${
                form.shop_types.includes(t)
                  ? 'bg-savo-purple text-white border-savo-purple'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >{t}</button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 block mb-0.5">Notes</label>
        <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
          rows={2} className={selectCls} placeholder="Optional observations..." />
      </div>

      <div className="flex items-center gap-2">
        <button type="submit" disabled={submitting}
          className="px-3 py-1.5 bg-savo-purple text-white text-xs font-semibold rounded hover:bg-savo-purple-dark transition-colors disabled:opacity-50">
          {submitting ? 'Saving...' : road.surveyed ? 'Update Survey' : 'Submit Survey'}
        </button>
        <button type="button" onClick={() => onDone && onDone()}
          className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700">Cancel</button>
      </div>
    </form>
  )
}

function LaneSurveyPanel({ assignment, role, onRefresh }) {
  const [roads, setRoads] = useState(null)
  const [loading, setLoading] = useState(false)
  const [surveyingRoadId, setSurveyingRoadId] = useState(null)

  const isSurveyExec = role === 'survey_executive'
  const canSurvey = isSurveyExec && assignment.status === 'in_progress'

  const loadRoads = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAssignmentRoads(assignment.assignment_id)
      setRoads(data)
    } catch { setRoads(null) }
    finally { setLoading(false) }
  }, [assignment.assignment_id])

  useEffect(() => { loadRoads() }, [loadRoads])

  const handleSurveyDone = async () => {
    setSurveyingRoadId(null)
    await loadRoads()
    if (onRefresh) await onRefresh()
  }

  if (loading) return <p className="text-[10px] text-gray-400 py-2">Loading roads...</p>
  if (!roads) return null

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold text-gray-500">
          Roads: {roads.surveyed_count}/{roads.total_roads} surveyed
        </span>
        <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-savo-purple rounded-full transition-all"
            style={{ width: `${roads.total_roads ? (roads.surveyed_count / roads.total_roads * 100) : 0}%` }}
          />
        </div>
      </div>

      <div className="max-h-48 overflow-y-auto space-y-1">
        {roads.roads.map(road => (
          <div key={road.road_id}>
            {surveyingRoadId === road.road_id ? (
              <LaneSurveyForm road={road} assignmentId={assignment.assignment_id} onDone={handleSurveyDone} />
            ) : (
              <div className={`flex items-center justify-between px-2 py-1.5 rounded text-xs ${
                road.surveyed ? 'bg-emerald-50 border border-emerald-100' : 'bg-gray-50 border border-gray-100'
              }`}>
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${road.surveyed ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                  <span className="truncate text-gray-700">{road.name}</span>
                  <span className="text-[10px] text-gray-400 flex-shrink-0">{road.road_type}</span>
                </div>
                {canSurvey && (
                  <button
                    onClick={() => setSurveyingRoadId(road.road_id)}
                    className="text-[10px] font-semibold text-savo-purple hover:text-savo-purple-dark flex-shrink-0 ml-2"
                  >
                    {road.surveyed ? 'Edit' : 'Survey'}
                  </button>
                )}
                {!canSurvey && road.surveyed && (
                  <span className="text-[10px] text-emerald-600 flex-shrink-0 ml-2">Done</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function InsightBar({ label, items, colorMap }) {
  const total = Object.values(items).reduce((a, b) => a + b, 0)
  if (!total) return <p className="text-[10px] text-gray-400 italic">No data</p>
  return (
    <div>
      <div className="flex h-4 rounded overflow-hidden mb-1">
        {Object.entries(items).map(([k, v]) => (
          <div key={k} style={{ width: `${(v / total) * 100}%`, backgroundColor: colorMap[k] || '#94a3b8' }}
            title={`${k}: ${v}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {Object.entries(items).map(([k, v]) => (
          <span key={k} className="text-[10px] text-gray-600 flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm inline-block" style={{ backgroundColor: colorMap[k] || '#94a3b8' }} />
            {k}: {v} ({Math.round(v / total * 100)}%)
          </span>
        ))}
      </div>
    </div>
  )
}

const HOUSEHOLD_COLORS = { apartments: '#782B90', individual: '#2563EB', mixed: '#D97706' }
const CONDITION_COLORS = { excellent: '#059669', good: '#2563EB', fair: '#D97706', poor: '#DC2626' }
const TRAFFIC_COLORS = { low: '#94a3b8', medium: '#D97706', high: '#DC2626' }

function CatchmentInsightPanel({ studyId, studyStatus }) {
  const [insight, setInsight] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (studyStatus !== 'completed') return
    setLoading(true)
    fetchCatchmentInsight(studyId)
      .then(d => setInsight(d))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [studyId, studyStatus])

  if (studyStatus !== 'completed') return null
  if (loading) return <p className="text-[10px] text-gray-400 py-2">Loading insight...</p>
  if (error) return <div className="p-2 bg-red-50 rounded text-xs text-red-600">{error}</div>
  if (!insight) return null

  const { insight: ins } = insight
  const agg = ins.aggregated_data || {}

  return (
    <div className="bg-gradient-to-br from-savo-purple/5 to-white rounded-lg border border-savo-purple/20 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-bold text-gray-800">Catchment Insight</h4>
        <span className="text-[10px] text-gray-400">
          Generated {ins.created_at ? new Date(ins.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <div className="text-lg font-bold text-savo-purple">{ins.total_roads_surveyed}</div>
          <div className="text-[10px] text-gray-500">Roads Surveyed</div>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <div className="text-lg font-bold text-savo-purple">{ins.total_roads_in_area}</div>
          <div className="text-[10px] text-gray-500">Total Roads</div>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <div className="text-lg font-bold text-savo-purple">{ins.completion_pct}%</div>
          <div className="text-[10px] text-gray-500">Coverage</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg p-3 border border-gray-100 text-center">
          <div className="text-2xl font-bold text-savo-purple">{agg.total_shops ?? 0}</div>
          <div className="text-[10px] text-gray-500">Total Shops</div>
        </div>
        <div className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] font-semibold text-gray-600 mb-1.5">Shop Types</div>
          {Object.keys(agg.shop_type_distribution || {}).length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {Object.entries(agg.shop_type_distribution).sort((a, b) => b[1] - a[1]).map(([t, c]) => (
                <span key={t} className="px-1.5 py-0.5 rounded text-[10px] bg-savo-purple/10 text-savo-purple font-medium">
                  {t} ({c})
                </span>
              ))}
            </div>
          ) : <p className="text-[10px] text-gray-400 italic">No data</p>}
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <div className="text-[10px] font-semibold text-gray-600 mb-1">Household Mix</div>
          <InsightBar items={agg.household_types || {}} colorMap={HOUSEHOLD_COLORS} />
        </div>
        <div>
          <div className="text-[10px] font-semibold text-gray-600 mb-1">Road Condition</div>
          <InsightBar items={agg.road_conditions || {}} colorMap={CONDITION_COLORS} />
        </div>
        <div>
          <div className="text-[10px] font-semibold text-gray-600 mb-1">Foot Traffic</div>
          <InsightBar items={agg.foot_traffic || {}} colorMap={TRAFFIC_COLORS} />
        </div>
        <div>
          <div className="text-[10px] font-semibold text-gray-600 mb-1">Household Count Ranges</div>
          {Object.keys(agg.household_count_ranges || {}).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(agg.household_count_ranges).map(([range, count]) => (
                <div key={range} className="bg-white rounded px-2 py-1 border border-gray-100 text-center">
                  <div className="text-xs font-bold text-gray-700">{count}</div>
                  <div className="text-[10px] text-gray-400">{range}</div>
                </div>
              ))}
            </div>
          ) : <p className="text-[10px] text-gray-400 italic">No data</p>}
        </div>
      </div>

      <div className="pt-2 border-t border-gray-100">
        <div className="flex items-center gap-2 text-[10px] text-gray-400">
          <span>Property: {insight.property_pincode} — {insight.property_address}</span>
        </div>
      </div>
    </div>
  )
}

function StudyDetail({ study, role, onRefresh }) {
  const ss = STATUS_STYLES[study.status] || STATUS_STYLES.requested
  const prop = study.property || {}
  const [drawing, setDrawing] = useState(false)
  const [zonePoints, setZonePoints] = useState([])
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState(null)
  const [updatingId, setUpdatingId] = useState(null)
  const [expandedAssignment, setExpandedAssignment] = useState(null)

  const boundaryCoords = study.boundary?.coordinates?.[0]?.map(c => [c[1], c[0]]) || []
  const canAssign = role === 'survey_manager' && ['requested', 'planning', 'in_progress'].includes(study.status)
  const isSurveyExec = role === 'survey_executive'

  const myAssignments = isSurveyExec
    ? study.assignments?.filter(a => a.assigned_to === USERS.survey_executive.id) || []
    : study.assignments || []

  const handleAddPoint = (pt) => setZonePoints(prev => [...prev, pt])

  const handleAssign = async () => {
    if (zonePoints.length < 3) return
    setAssigning(true)
    setError(null)
    try {
      const coordinates = [[...zonePoints.map(p => [p[1], p[0]]), [zonePoints[0][1], zonePoints[0][0]]]]
      await createZoneAssignment(study.study_id, {
        assigned_to: USERS.survey_executive.id,
        assigned_by: USERS.survey_manager.id,
        zone_geojson: { type: 'Polygon', coordinates },
      })
      setZonePoints([])
      setDrawing(false)
      if (onRefresh) await onRefresh()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message)
    } finally {
      setAssigning(false)
    }
  }

  const handleStatusUpdate = async (assignmentId, newStatus) => {
    setUpdatingId(assignmentId)
    setError(null)
    try {
      const userId = isSurveyExec ? USERS.survey_executive.id : USERS.survey_manager.id
      await updateAssignmentStatus(assignmentId, { user_id: userId, new_status: newStatus })
      if (onRefresh) await onRefresh()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message)
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-lg font-bold text-gray-800">Catchment Study</h3>
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${ss.bg} ${ss.text}`}>{ss.label}</span>
        </div>
        <p className="text-xs text-gray-400">
          {prop.pincode} &middot; {prop.address} &middot; {study.radius_m}m radius &middot; {study.total_roads_in_area} roads
        </p>
      </div>

      {error && <div className="p-2 bg-red-50 rounded text-xs text-red-600">{error}</div>}

      <div className="rounded-lg overflow-hidden border border-gray-200" style={{ height: 280 }}>
        {boundaryCoords.length > 0 && (
          <MapContainer center={boundaryCoords[0]} zoom={15} style={{ height: '100%', width: '100%' }} className="z-0">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap' />
            <MapFitBounds boundary={study.boundary} />
            <Polygon positions={boundaryCoords} pathOptions={{ color: '#782B90', weight: 2, fillOpacity: 0.05, dashArray: '6 4' }} />
            {prop.location && <Marker position={[prop.location.lat, prop.location.lng]} icon={propertyIcon} />}
            {study.assignments?.map((a, i) => {
              const zc = a.zone_boundary?.coordinates?.[0]?.map(c => [c[1], c[0]]) || []
              return zc.length ? (
                <Polygon key={a.assignment_id} positions={zc} pathOptions={{
                  color: ZONE_COLORS[i % ZONE_COLORS.length], weight: 2,
                  fillOpacity: a.status === 'completed' ? 0.3 : 0.15,
                }} />
              ) : null
            })}
            {zonePoints.length > 0 && (
              <Polygon positions={zonePoints} pathOptions={{ color: '#DC2626', weight: 2, fillOpacity: 0.1, dashArray: '4 4' }} />
            )}
            <ZoneDrawer onAddPoint={handleAddPoint} drawing={drawing} />
          </MapContainer>
        )}
      </div>

      {canAssign && (
        <div className="flex items-center gap-2 flex-wrap">
          {!drawing ? (
            <button onClick={() => { setDrawing(true); setZonePoints([]) }}
              className="px-3 py-1.5 bg-savo-purple text-white text-xs font-semibold rounded hover:bg-savo-purple-dark transition-colors">
              Draw Zone
            </button>
          ) : (
            <>
              <span className="text-[10px] text-gray-500">Click map to add points ({zonePoints.length} placed)</span>
              {zonePoints.length >= 3 && (
                <button onClick={handleAssign} disabled={assigning}
                  className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded hover:bg-emerald-700 transition-colors disabled:opacity-50">
                  {assigning ? 'Assigning...' : `Assign to ${USERS.survey_executive.name}`}
                </button>
              )}
              {zonePoints.length > 0 && (
                <button onClick={() => setZonePoints(prev => prev.slice(0, -1))}
                  className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700">Undo</button>
              )}
              <button onClick={() => { setDrawing(false); setZonePoints([]) }}
                className="px-2 py-1.5 text-xs text-red-500 hover:text-red-700">Cancel</button>
            </>
          )}
        </div>
      )}

      <div className="space-y-2">
        <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">
          {isSurveyExec ? 'My Assignments' : 'Zone Assignments'} ({myAssignments.length})
        </div>
        {myAssignments.length === 0 && study.status === 'requested' && (
          <div className="bg-amber-50 rounded-lg p-3 border border-amber-100 text-center">
            <p className="text-xs text-amber-700">Awaiting zone assignment by Survey Manager</p>
          </div>
        )}
        {myAssignments.map((a, i) => {
          const as = ASSIGNMENT_STATUS[a.status] || ASSIGNMENT_STATUS.pending
          const nextStatus = a.status === 'pending' ? 'in_progress' : a.status === 'in_progress' ? 'completed' : null
          const canUpdate = (isSurveyExec && a.assigned_to === USERS.survey_executive.id) || role === 'survey_manager'
          const isExpanded = expandedAssignment === a.assignment_id

          return (
            <div key={a.assignment_id} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
              <div
                className="flex items-center justify-between mb-1 cursor-pointer"
                onClick={() => setExpandedAssignment(isExpanded ? null : a.assignment_id)}
              >
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: ZONE_COLORS[i % ZONE_COLORS.length] }} />
                  <span className="text-sm font-medium text-gray-700">{a.executive_name}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${as.bg} ${as.text}`}>{as.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400">{a.survey_count} surveys</span>
                  <svg className={`w-3 h-3 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {nextStatus && canUpdate && (
                <button
                  onClick={() => handleStatusUpdate(a.assignment_id, nextStatus)}
                  disabled={updatingId === a.assignment_id}
                  className="mt-1 px-2.5 py-1 text-[10px] font-semibold bg-savo-purple text-white rounded hover:bg-savo-purple-dark transition-colors disabled:opacity-50"
                >
                  {updatingId === a.assignment_id ? 'Updating...' : nextStatus === 'in_progress' ? 'Start Survey' : 'Mark Complete'}
                </button>
              )}

              {isExpanded && (
                <LaneSurveyPanel assignment={a} role={role} onRefresh={onRefresh} />
              )}
            </div>
          )
        })}
      </div>

      <CatchmentInsightPanel studyId={study.study_id} studyStatus={study.status} />
    </div>
  )
}

export default function CatchmentStudies() {
  const { role } = useOutletContext()
  const [studies, setStudies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadStudies = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchCatchmentStudies()
      setStudies(data.studies)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadStudies() }, [loadStudies])

  const loadDetail = useCallback(async (studyId) => {
    setDetailLoading(true)
    try {
      const data = await fetchCatchmentStudy(studyId)
      setDetail(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const selectStudy = useCallback(async (studyId) => {
    setSelectedId(studyId)
    await loadDetail(studyId)
  }, [loadDetail])

  const handleRefresh = useCallback(async () => {
    if (selectedId) await loadDetail(selectedId)
    await loadStudies()
  }, [selectedId, loadDetail, loadStudies])

  return (
    <div className="flex-1 flex min-h-0">
      <div className="w-[340px] border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-800">Catchment Studies</h2>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {role === 'survey_manager' ? 'Manage zones & assignments' : role === 'survey_executive' ? 'Your survey assignments' : 'All catchment studies'}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && (
            <div className="py-8 text-center">
              <div className="relative w-6 h-6 mx-auto">
                <div className="w-6 h-6 border-2 border-gray-200 rounded-full" />
                <div className="w-6 h-6 border-2 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
              </div>
              <p className="text-xs text-gray-400 mt-2">Loading studies...</p>
            </div>
          )}
          {error && <div className="p-2 bg-red-50 rounded text-xs text-red-600">{error}</div>}
          {!loading && !error && studies.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-400">No catchment studies yet</p>
              <p className="text-[10px] text-gray-300 mt-1">BD Managers can request studies from scouted properties</p>
            </div>
          )}
          {studies.map(s => (
            <StudyCard key={s.study_id} study={s} onSelect={selectStudy} isSelected={selectedId === s.study_id} />
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
          <div className="w-full max-w-2xl">
            <StudyDetail study={detail} role={role} onRefresh={handleRefresh} />
          </div>
        )}
        {!detailLoading && !detail && (
          <div className="py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-savo-purple/5 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-savo-purple/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <p className="text-sm text-gray-400 mt-3">Select a study to view details</p>
          </div>
        )}
      </div>
    </div>
  )
}

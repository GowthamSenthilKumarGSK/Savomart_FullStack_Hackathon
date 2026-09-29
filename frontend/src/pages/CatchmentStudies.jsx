import { useState, useEffect, useCallback, useRef } from 'react'
import { useOutletContext } from 'react-router-dom'
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchCatchmentStudies, fetchCatchmentStudy, createZoneAssignment, updateAssignmentStatus } from '../api'

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
    const bounds = L.latLngBounds(coords)
    map.fitBounds(bounds, { padding: [30, 30] })
  }, [boundary, map])
  return null
}

function ZoneDrawer({ onAddPoint, drawing }) {
  useMapEvents({
    click(e) {
      if (drawing) onAddPoint([e.latlng.lat, e.latlng.lng])
    },
  })
  return null
}

function StudyDetail({ study, role, onRefresh }) {
  const ss = STATUS_STYLES[study.status] || STATUS_STYLES.requested
  const prop = study.property || {}
  const [drawing, setDrawing] = useState(false)
  const [zonePoints, setZonePoints] = useState([])
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState(null)
  const [updatingId, setUpdatingId] = useState(null)

  const boundaryCoords = study.boundary?.coordinates?.[0]?.map(c => [c[1], c[0]]) || []
  const canAssign = role === 'survey_manager' && ['requested', 'planning', 'in_progress'].includes(study.status)
  const isSurveyExec = role === 'survey_executive'

  const myAssignments = isSurveyExec
    ? study.assignments?.filter(a => a.assigned_to === USERS.survey_executive.id) || []
    : study.assignments || []

  const handleAddPoint = (pt) => {
    setZonePoints(prev => [...prev, pt])
  }

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

      <div className="rounded-lg overflow-hidden border border-gray-200" style={{ height: 320 }}>
        {boundaryCoords.length > 0 && (
          <MapContainer
            center={boundaryCoords[0]}
            zoom={15}
            style={{ height: '100%', width: '100%' }}
            className="z-0"
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap'
            />
            <MapFitBounds boundary={study.boundary} />
            <Polygon
              positions={boundaryCoords}
              pathOptions={{ color: '#782B90', weight: 2, fillOpacity: 0.05, dashArray: '6 4' }}
            />
            {prop.location && (
              <Marker position={[prop.location.lat, prop.location.lng]} icon={propertyIcon} />
            )}
            {study.assignments?.map((a, i) => {
              const zoneCoords = a.zone_boundary?.coordinates?.[0]?.map(c => [c[1], c[0]]) || []
              if (!zoneCoords.length) return null
              return (
                <Polygon
                  key={a.assignment_id}
                  positions={zoneCoords}
                  pathOptions={{
                    color: ZONE_COLORS[i % ZONE_COLORS.length],
                    weight: 2,
                    fillOpacity: a.status === 'completed' ? 0.3 : 0.15,
                  }}
                />
              )
            })}
            {zonePoints.length > 0 && (
              <Polygon
                positions={zonePoints}
                pathOptions={{ color: '#DC2626', weight: 2, fillOpacity: 0.1, dashArray: '4 4' }}
              />
            )}
            <ZoneDrawer onAddPoint={handleAddPoint} drawing={drawing} />
          </MapContainer>
        )}
      </div>

      {canAssign && (
        <div className="flex items-center gap-2 flex-wrap">
          {!drawing ? (
            <button
              onClick={() => { setDrawing(true); setZonePoints([]) }}
              className="px-3 py-1.5 bg-savo-purple text-white text-xs font-semibold rounded hover:bg-savo-purple-dark transition-colors"
            >
              Draw Zone
            </button>
          ) : (
            <>
              <span className="text-[10px] text-gray-500">Click map to add points ({zonePoints.length} placed)</span>
              {zonePoints.length >= 3 && (
                <button
                  onClick={handleAssign}
                  disabled={assigning}
                  className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded hover:bg-emerald-700 transition-colors disabled:opacity-50"
                >
                  {assigning ? 'Assigning...' : `Assign to ${USERS.survey_executive.name}`}
                </button>
              )}
              {zonePoints.length > 0 && (
                <button
                  onClick={() => setZonePoints(prev => prev.slice(0, -1))}
                  className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                >
                  Undo
                </button>
              )}
              <button
                onClick={() => { setDrawing(false); setZonePoints([]) }}
                className="px-2 py-1.5 text-xs text-red-500 hover:text-red-700"
              >
                Cancel
              </button>
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

          return (
            <div key={a.assignment_id} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: ZONE_COLORS[i % ZONE_COLORS.length] }}
                  />
                  <span className="text-sm font-medium text-gray-700">{a.executive_name}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${as.bg} ${as.text}`}>{as.label}</span>
                </div>
                <span className="text-[10px] text-gray-400">{a.survey_count} surveys</span>
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
            </div>
          )
        })}
      </div>
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

  useEffect(() => {
    loadStudies()
  }, [loadStudies])

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
              <p className="text-[10px] text-gray-300 mt-1">
                BD Managers can request studies from scouted properties
              </p>
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

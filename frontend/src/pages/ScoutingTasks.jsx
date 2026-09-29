import { useState, useEffect, useCallback, useRef } from 'react'
import { useOutletContext } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchScoutingTasks, fetchScoutingTask, updateScoutingTask, submitProperty, getEvaluation, runEvaluation, requestCatchmentStudy } from '../api'

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

const BUILDING_TYPES = [
  { value: '', label: 'Select type...' },
  { value: 'standalone', label: 'Standalone' },
  { value: 'mall', label: 'Mall / Shopping Centre' },
  { value: 'high_street', label: 'High Street' },
  { value: 'residential', label: 'Residential Complex' },
  { value: 'commercial_complex', label: 'Commercial Complex' },
]

const propertyIcon = new L.Icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
})

function DraggableMarker({ position, onMove }) {
  const markerRef = useRef(null)
  useMapEvents({
    click(e) {
      onMove([e.latlng.lat, e.latlng.lng])
    },
  })
  return (
    <Marker
      position={position}
      icon={propertyIcon}
      draggable
      ref={markerRef}
      eventHandlers={{
        dragend() {
          const m = markerRef.current
          if (m) {
            const ll = m.getLatLng()
            onMove([ll.lat, ll.lng])
          }
        },
      }}
    />
  )
}

function resizeImage(file, maxDim = 800, maxBytes = 200000) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let w = img.width, h = img.height
        if (w > maxDim || h > maxDim) {
          if (w > h) { h = Math.round(h * maxDim / w); w = maxDim }
          else { w = Math.round(w * maxDim / h); h = maxDim }
        }
        canvas.width = w
        canvas.height = h
        canvas.getContext('2d').drawImage(img, 0, 0, w, h)
        let quality = 0.8
        let result = canvas.toDataURL('image/jpeg', quality)
        while (result.length > maxBytes && quality > 0.2) {
          quality -= 0.1
          result = canvas.toDataURL('image/jpeg', quality)
        }
        resolve(result)
      }
      img.src = e.target.result
    }
    reader.readAsDataURL(file)
  })
}

function PropertyForm({ task, userId, onSubmitted, onCancel }) {
  const [pos, setPos] = useState(
    task.centroid ? [task.centroid.lat, task.centroid.lng] : [13.06, 80.24]
  )
  const [form, setForm] = useState({
    address: '',
    rent_monthly: '',
    carpet_area_sqft: '',
    frontage_ft: '',
    floor: '',
    building_type: '',
    contact_name: '',
    contact_phone: '',
    notes: '',
  })
  const [photos, setPhotos] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [duplicates, setDuplicates] = useState(null)
  const [geoLocating, setGeoLocating] = useState(false)

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handlePhotos = async (e) => {
    const files = Array.from(e.target.files).slice(0, 3 - photos.length)
    const resized = await Promise.all(files.map(f => resizeImage(f)))
    setPhotos(prev => [...prev, ...resized].slice(0, 3))
  }

  const removePhoto = (idx) => setPhotos(prev => prev.filter((_, i) => i !== idx))

  const useGeolocation = () => {
    if (!navigator.geolocation) return
    setGeoLocating(true)
    navigator.geolocation.getCurrentPosition(
      (p) => { setPos([p.coords.latitude, p.coords.longitude]); setGeoLocating(false) },
      () => { setGeoLocating(false) },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }

  const handleSubmit = async (force = false) => {
    if (!form.address.trim()) { setError('Address is required'); return }
    setSubmitting(true)
    setError(null)
    setDuplicates(null)
    try {
      const payload = {
        lat: pos[0],
        lng: pos[1],
        address: form.address.trim(),
        rent_monthly: form.rent_monthly ? parseFloat(form.rent_monthly) : null,
        carpet_area_sqft: form.carpet_area_sqft ? parseFloat(form.carpet_area_sqft) : null,
        frontage_ft: form.frontage_ft ? parseFloat(form.frontage_ft) : null,
        floor: form.floor ? parseInt(form.floor) : null,
        building_type: form.building_type || null,
        contact_name: form.contact_name.trim() || null,
        contact_phone: form.contact_phone.trim() || null,
        photos: photos.length > 0 ? photos : null,
        notes: form.notes.trim() || null,
        submitted_by: userId,
        force,
      }
      const result = await submitProperty(task.task_id, payload)
      onSubmitted(result)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409 && detail?.duplicates) {
        setDuplicates(detail.duplicates)
      } else {
        setError(typeof detail === 'string' ? detail : detail?.message || err.message)
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-gray-800">Submit Property — {task.pincode}</h3>
        <button onClick={onCancel} className="text-xs text-gray-400 hover:text-gray-600">← Back</button>
      </div>

      <div className="rounded-lg overflow-hidden border border-gray-200" style={{ height: 200 }}>
        <MapContainer
          center={pos}
          zoom={16}
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <DraggableMarker position={pos} onMove={setPos} />
        </MapContainer>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-gray-400 font-mono">{pos[0].toFixed(5)}, {pos[1].toFixed(5)}</span>
        <button
          onClick={useGeolocation}
          disabled={geoLocating}
          className="text-[10px] text-savo-purple hover:underline disabled:opacity-50"
        >
          {geoLocating ? 'Locating...' : '📍 Use my location'}
        </button>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 uppercase tracking-wider">Address *</label>
        <input
          value={form.address}
          onChange={set('address')}
          className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple focus:border-savo-purple outline-none"
          placeholder="Full property address"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Rent (₹/month)</label>
          <input type="number" value={form.rent_monthly} onChange={set('rent_monthly')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="25000" />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Carpet Area (sq ft)</label>
          <input type="number" value={form.carpet_area_sqft} onChange={set('carpet_area_sqft')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="500" />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Frontage (ft)</label>
          <input type="number" value={form.frontage_ft} onChange={set('frontage_ft')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="20" />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Floor</label>
          <input type="number" value={form.floor} onChange={set('floor')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="0" />
        </div>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 uppercase tracking-wider">Building Type</label>
        <select value={form.building_type} onChange={set('building_type')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none bg-white">
          {BUILDING_TYPES.map(bt => <option key={bt.value} value={bt.value}>{bt.label}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Contact Name</label>
          <input value={form.contact_name} onChange={set('contact_name')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="Owner / Agent" />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider">Contact Phone</label>
          <input value={form.contact_phone} onChange={set('contact_phone')} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none" placeholder="+91..." />
        </div>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 uppercase tracking-wider">Photos (max 3)</label>
        <div className="flex gap-2 mt-1 flex-wrap">
          {photos.map((p, i) => (
            <div key={i} className="relative w-16 h-16 rounded border border-gray-200 overflow-hidden">
              <img src={p} alt="" className="w-full h-full object-cover" />
              <button onClick={() => removePhoto(i)} className="absolute top-0 right-0 bg-red-500 text-white text-[8px] w-4 h-4 flex items-center justify-center rounded-bl">×</button>
            </div>
          ))}
          {photos.length < 3 && (
            <label className="w-16 h-16 rounded border-2 border-dashed border-gray-300 flex items-center justify-center cursor-pointer hover:border-savo-purple transition-colors">
              <span className="text-gray-400 text-lg">+</span>
              <input type="file" accept="image/*" capture="environment" onChange={handlePhotos} className="hidden" />
            </label>
          )}
        </div>
      </div>

      <div>
        <label className="text-[10px] text-gray-500 uppercase tracking-wider">Notes</label>
        <textarea value={form.notes} onChange={set('notes')} rows={2} className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-savo-purple outline-none resize-none" placeholder="Observations about the property..." />
      </div>

      {error && <div className="p-2 bg-red-50 rounded text-xs text-red-600">{error}</div>}

      {duplicates && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
          <p className="text-xs font-medium text-amber-800">Nearby properties found within 50m:</p>
          {duplicates.map(d => (
            <div key={d.property_id} className="text-[11px] text-amber-700">
              • {d.address} ({d.stage}, {d.distance_m}m away)
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => handleSubmit(true)}
              disabled={submitting}
              className="px-3 py-1 rounded text-xs font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50"
            >
              {submitting ? '...' : 'Submit Anyway'}
            </button>
            <button
              onClick={() => setDuplicates(null)}
              className="px-3 py-1 rounded text-xs font-medium bg-gray-200 text-gray-600 hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!duplicates && (
        <button
          onClick={() => handleSubmit(false)}
          disabled={submitting || !form.address.trim()}
          className="w-full py-2 rounded-lg bg-savo-purple text-white text-xs font-semibold hover:bg-savo-purple-dark transition-colors disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : 'Submit Property'}
        </button>
      )}
    </div>
  )
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

const GRADE_COLORS = {
  A: { bg: 'bg-emerald-100', text: 'text-emerald-700', bar: 'bg-emerald-500' },
  B: { bg: 'bg-blue-100', text: 'text-blue-700', bar: 'bg-blue-500' },
  C: { bg: 'bg-amber-100', text: 'text-amber-700', bar: 'bg-amber-500' },
  D: { bg: 'bg-orange-100', text: 'text-orange-700', bar: 'bg-orange-500' },
  F: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-500' },
}

const DIMENSION_LABELS = {
  residential_catchment_proxies: 'Residential & Catchment Proxies',
  commercial_context: 'Commercial Context',
  accessibility: 'Accessibility',
  savomart_fit: 'Savomart Fit',
  property_attributes: 'Property Attributes',
}

const METRIC_TYPE_BADGE = {
  direct: { bg: 'bg-blue-50', text: 'text-blue-600', label: 'Direct' },
  derived: { bg: 'bg-purple-50', text: 'text-purple-600', label: 'Derived' },
  proxy: { bg: 'bg-amber-50', text: 'text-amber-600', label: 'Proxy' },
}

function EvaluationCard({ propertyId }) {
  const [evaluation, setEvaluation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!propertyId) return
    setLoading(true)
    getEvaluation(propertyId)
      .then(setEvaluation)
      .catch(() => setEvaluation(null))
      .finally(() => setLoading(false))
  }, [propertyId])

  const handleRunEvaluation = async () => {
    setRunning(true)
    setError(null)
    try {
      const result = await runEvaluation(propertyId)
      setEvaluation(result)
    } catch (err) {
      setError(err.response?.data?.detail || 'Evaluation could not be completed')
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
        <div className="text-[10px] text-gray-400 uppercase tracking-wider">Property Evaluation</div>
        <p className="text-xs text-gray-400 mt-2">Loading evaluation...</p>
      </div>
    )
  }

  if (!evaluation) {
    return (
      <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 space-y-2">
        <div className="text-[10px] text-gray-400 uppercase tracking-wider">Property Evaluation</div>
        <p className="text-xs text-gray-500">Evaluation not yet available.</p>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <button
          onClick={handleRunEvaluation}
          disabled={running}
          className="px-3 py-1 rounded text-xs font-medium bg-savo-purple text-white hover:bg-savo-purple-dark disabled:opacity-50"
        >
          {running ? 'Running...' : 'Run Evaluation'}
        </button>
      </div>
    )
  }

  const gc = GRADE_COLORS[evaluation.grade] || GRADE_COLORS.C
  const subScores = evaluation.sub_scores || {}
  const rawData = evaluation.raw_data || {}

  return (
    <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[10px] text-indigo-600 uppercase tracking-wider font-semibold">Property Evaluation</div>
        <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-indigo-400 hover:text-indigo-600">
          {expanded ? 'Collapse' : 'Details'}
        </button>
      </div>

      <div className="flex items-center gap-3">
        <div className="text-3xl font-bold text-gray-800">{evaluation.overall_score}</div>
        <div>
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${gc.bg} ${gc.text}`}>Grade {evaluation.grade}</span>
          <span className="text-[10px] text-gray-400 ml-2">/ 100</span>
        </div>
      </div>

      <div className="space-y-1.5">
        {Object.entries(subScores).map(([key, dim]) => {
          const dgc = GRADE_COLORS[dim.grade] || GRADE_COLORS.C
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[10px] text-gray-600">{DIMENSION_LABELS[key] || key}</span>
                <span className="text-[10px] font-semibold text-gray-700">{dim.score}</span>
              </div>
              <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${dgc.bar}`} style={{ width: `${dim.score}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      {rawData.positive_signals && rawData.positive_signals.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Positive Signals</div>
          <div className="flex flex-wrap gap-1">
            {rawData.positive_signals.map((s, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px]">{s}</span>
            ))}
          </div>
        </div>
      )}

      {rawData.risks && rawData.risks.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Risks & Concerns</div>
          <div className="flex flex-wrap gap-1">
            {rawData.risks.map((r, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-red-50 text-red-600 rounded text-[10px]">{r}</span>
            ))}
          </div>
        </div>
      )}

      {rawData.recommendation && (
        <div className="bg-white rounded p-2 border border-indigo-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">Recommendation</div>
          <p className="text-xs text-gray-700">{rawData.recommendation}</p>
        </div>
      )}

      {rawData.field_derived?.rent_per_sqft != null && (
        <div className="text-xs text-gray-500">
          Rent per sq ft: <span className="font-semibold text-gray-700">₹{rawData.field_derived.rent_per_sqft}</span>/mo
          <span className="text-[10px] text-gray-400 ml-1">(field-derived, not scored)</span>
        </div>
      )}

      {expanded && (
        <div className="space-y-3 pt-2 border-t border-indigo-100">
          {Object.entries(subScores).map(([key, dim]) => (
            <div key={key}>
              <div className="text-[10px] font-semibold text-gray-600 mb-1">{DIMENSION_LABELS[key] || key}</div>
              <div className="space-y-0.5">
                {dim.metrics && Object.entries(dim.metrics).map(([mk, mv]) => {
                  const tb = METRIC_TYPE_BADGE[mv.type] || METRIC_TYPE_BADGE.direct
                  return (
                    <div key={mk} className="flex items-center justify-between text-[10px]">
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-500">{mk.replace(/_/g, ' ')}</span>
                        <span className={`px-1 rounded ${tb.bg} ${tb.text}`}>{tb.label}</span>
                        {mv.missing && <span className="px-1 rounded bg-yellow-50 text-yellow-600">Missing</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400">{mv.value != null ? mv.value : '—'}</span>
                        <span className="font-semibold text-gray-700 w-6 text-right">{mv.normalized}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}

          {rawData.scoring_notes && (
            <div className="text-[9px] text-gray-400 space-y-0.5 pt-1 border-t border-indigo-50">
              {Object.entries(rawData.scoring_notes).map(([k, v]) => (
                <p key={k}>{v}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TaskDetail({ task, role, onStatusUpdate, onSubmitProperty, onTaskRefresh }) {
  const [updating, setUpdating] = useState(false)
  const [requestingStudy, setRequestingStudy] = useState(false)
  const [studyError, setStudyError] = useState(null)
  const ss = STATUS_STYLES[task.status] || STATUS_STYLES.assigned

  const transitions = task.status === 'assigned'
    ? [{ to: 'in_progress', label: 'Start Scouting', color: 'bg-amber-500 hover:bg-amber-600' }, { to: 'cancelled', label: 'Cancel', color: 'bg-gray-400 hover:bg-gray-500' }]
    : task.status === 'in_progress'
    ? [{ to: 'cancelled', label: 'Cancel', color: 'bg-gray-400 hover:bg-gray-500' }]
    : []

  const handleTransition = async (newStatus) => {
    setUpdating(true)
    try {
      await onStatusUpdate(task.task_id, newStatus)
    } finally {
      setUpdating(false)
    }
  }

  const handleRequestStudy = async () => {
    if (!task.property?.id) return
    setRequestingStudy(true)
    setStudyError(null)
    try {
      await requestCatchmentStudy({
        property_id: task.property.id,
        requested_by: USERS.bd_manager.id,
        radius_m: 500,
      })
      if (onTaskRefresh) await onTaskRefresh(task.task_id)
    } catch (err) {
      const detail = err.response?.data?.detail
      setStudyError(typeof detail === 'string' ? detail : detail?.message || err.message)
    } finally {
      setRequestingStudy(false)
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

      {task.property && (
        <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-100 space-y-2">
          <div className="text-[10px] text-emerald-600 uppercase tracking-wider font-semibold">Linked Property</div>
          <div className="text-sm font-medium text-gray-800">{task.property.address}</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Stage</span>
              <span className="font-semibold text-gray-700">{task.property.stage}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Pincode</span>
              <span className="font-semibold text-gray-700">{task.property.pincode}</span>
            </div>
            {task.property.rent_monthly && (
              <div className="flex justify-between">
                <span className="text-gray-500">Rent</span>
                <span className="font-semibold text-gray-700">₹{task.property.rent_monthly.toLocaleString()}/mo</span>
              </div>
            )}
            {task.property.carpet_area_sqft && (
              <div className="flex justify-between">
                <span className="text-gray-500">Area</span>
                <span className="font-semibold text-gray-700">{task.property.carpet_area_sqft} sq ft</span>
              </div>
            )}
            {task.property.building_type && (
              <div className="flex justify-between">
                <span className="text-gray-500">Type</span>
                <span className="font-semibold text-gray-700">{task.property.building_type}</span>
              </div>
            )}
            {task.property.contact_name && (
              <div className="flex justify-between">
                <span className="text-gray-500">Contact</span>
                <span className="font-semibold text-gray-700">{task.property.contact_name}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {task.property && <EvaluationCard propertyId={task.property.id} />}

      {task.timeline && task.timeline.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">Timeline</div>
          <div className="space-y-2">
            <div className="flex items-start gap-2 text-xs">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
              <div>
                <span className="text-gray-700 font-medium">Assigned</span>
                <span className="text-gray-400 ml-1">{new Date(task.created_at).toLocaleString()}</span>
              </div>
            </div>
            {task.timeline.map((ev, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${ev.to_stage === 'scouted' ? 'bg-emerald-400' : 'bg-gray-400'}`} />
                <div>
                  <span className="text-gray-700 font-medium">{ev.to_stage === 'scouted' ? 'Property Submitted' : `${ev.from_stage} → ${ev.to_stage}`}</span>
                  {ev.changed_by && <span className="text-gray-400 ml-1">by {ev.changed_by}</span>}
                  <span className="text-gray-400 ml-1">{new Date(ev.at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {studyError && <div className="p-2 bg-red-50 rounded text-xs text-red-600">{studyError}</div>}

      <div className="flex gap-2 pt-2 border-t border-gray-100">
        {role === 'bd_executive' && task.status === 'in_progress' && (
          <button
            onClick={onSubmitProperty}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-savo-purple hover:bg-savo-purple-dark transition-colors"
          >
            Submit Property
          </button>
        )}
        {role === 'bd_manager' && task.property && task.property.stage === 'scouted' && (
          <button
            onClick={handleRequestStudy}
            disabled={requestingStudy}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            {requestingStudy ? 'Requesting...' : 'Request Catchment Study'}
          </button>
        )}
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
  const [showPropertyForm, setShowPropertyForm] = useState(false)

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
    setShowPropertyForm(false)
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

  const handlePropertySubmitted = useCallback(async (result) => {
    setShowPropertyForm(false)
    const updated = await fetchScoutingTask(result.task_id)
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
        {!detailLoading && detail && !showPropertyForm && (
          <div className="w-full max-w-lg">
            <TaskDetail
              task={detail}
              role={role}
              onStatusUpdate={handleStatusUpdate}
              onSubmitProperty={() => setShowPropertyForm(true)}
              onTaskRefresh={selectTask}
            />
          </div>
        )}
        {!detailLoading && detail && showPropertyForm && (
          <div className="w-full max-w-lg">
            <PropertyForm
              task={detail}
              userId={currentUser?.id}
              onSubmitted={handlePropertySubmitted}
              onCancel={() => setShowPropertyForm(false)}
            />
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

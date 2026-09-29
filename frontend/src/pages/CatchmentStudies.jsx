import { useState, useEffect, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import { fetchCatchmentStudies, fetchCatchmentStudy } from '../api'

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
          <span>{study.assignment_count} assignment{study.assignment_count !== 1 ? 's' : ''}</span>
        </div>
        <span className="text-[10px] text-gray-400 tabular-nums">
          {new Date(study.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
        </span>
      </div>
      <p className="text-[10px] text-gray-400 mt-0.5">Requested by {study.requested_by}</p>
    </button>
  )
}

function StudyDetail({ study }) {
  const ss = STATUS_STYLES[study.status] || STATUS_STYLES.requested
  const prop = study.property || {}

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-lg font-bold text-gray-800">Catchment Study</h3>
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${ss.bg} ${ss.text}`}>{ss.label}</span>
        </div>
        <p className="text-xs text-gray-400">
          Requested {new Date(study.created_at).toLocaleString()} by {study.requested_by}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Radius</div>
          <div className="text-2xl font-bold text-savo-purple">{study.radius_m}<span className="text-sm font-normal text-gray-400">m</span></div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Roads in Area</div>
          <div className="text-2xl font-bold text-gray-700">{study.total_roads_in_area}</div>
        </div>
      </div>

      <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100 space-y-2">
        <div className="text-[10px] text-indigo-600 uppercase tracking-wider font-semibold">Property</div>
        <div className="text-sm font-medium text-gray-800">{prop.address}</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-500">Pincode</span>
            <span className="font-semibold text-gray-700">{prop.pincode}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Stage</span>
            <span className="font-semibold text-gray-700">{prop.stage}</span>
          </div>
          {prop.rent_monthly && (
            <div className="flex justify-between">
              <span className="text-gray-500">Rent</span>
              <span className="font-semibold text-gray-700">₹{prop.rent_monthly.toLocaleString()}/mo</span>
            </div>
          )}
          {prop.carpet_area_sqft && (
            <div className="flex justify-between">
              <span className="text-gray-500">Area</span>
              <span className="font-semibold text-gray-700">{prop.carpet_area_sqft} sq ft</span>
            </div>
          )}
          {prop.building_type && (
            <div className="flex justify-between">
              <span className="text-gray-500">Type</span>
              <span className="font-semibold text-gray-700">{prop.building_type}</span>
            </div>
          )}
          {prop.location && (
            <div className="flex justify-between">
              <span className="text-gray-500">Location</span>
              <span className="font-semibold text-gray-700 font-mono text-[10px]">
                {prop.location.lat.toFixed(4)}, {prop.location.lng.toFixed(4)}
              </span>
            </div>
          )}
        </div>
      </div>

      {study.assignments && study.assignments.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">
            Assignments ({study.assignments.length})
          </div>
          <div className="space-y-2">
            {study.assignments.map(a => {
              const as = ASSIGNMENT_STATUS[a.status] || ASSIGNMENT_STATUS.pending
              return (
                <div key={a.assignment_id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-700">{a.executive_name}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${as.bg} ${as.text}`}>{as.label}</span>
                  </div>
                  <span className="text-gray-400">{a.survey_count} surveys</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {study.assignments && study.assignments.length === 0 && study.status === 'requested' && (
        <div className="bg-amber-50 rounded-lg p-3 border border-amber-100 text-center">
          <p className="text-xs text-amber-700">Awaiting zone assignment by Survey Manager</p>
        </div>
      )}
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

  const selectStudy = useCallback(async (studyId) => {
    setSelectedId(studyId)
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

  return (
    <div className="flex-1 flex min-h-0">
      <div className="w-[340px] border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-800">Catchment Studies</h2>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {role === 'survey_manager' ? 'Manage catchment studies' : 'All catchment studies'}
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
          <div className="w-full max-w-lg">
            <StudyDetail study={detail} />
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

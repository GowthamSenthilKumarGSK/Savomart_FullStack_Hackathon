import { useState, useEffect, useRef, useCallback } from 'react'
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchPincodeBoundaries, fetchPincodeDetail, fetchStores, fetchFitnessReport, fetchHotspots, fetchExplanation } from '../api'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const storeIcon = new L.Icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  className: 'store-marker',
})

const CHENNAI_CENTER = [13.06, 80.24]
const CHENNAI_ZOOM = 12

const STYLE_DEFAULT = { color: '#782B90', weight: 1, fillColor: '#9B4DB3', fillOpacity: 0.1 }
const STYLE_HOVER = { color: '#782B90', weight: 2, fillColor: '#9B4DB3', fillOpacity: 0.25 }
const STYLE_SELECTED = { color: '#FFF200', weight: 3, fillColor: '#782B90', fillOpacity: 0.35 }

const HOTSPOT_COLORS = ['#e11d48', '#f97316', '#eab308', '#22c55e', '#3b82f6']
const HOTSPOT_STYLE = (rank, active) => ({
  color: HOTSPOT_COLORS[rank - 1] || '#782B90',
  weight: active ? 3 : 2,
  fillColor: HOTSPOT_COLORS[rank - 1] || '#782B90',
  fillOpacity: active ? 0.45 : 0.25,
  dashArray: active ? null : '4 4',
})

const HOTSPOT_DIM_LABELS = {
  commercial_activity: 'Commercial Activity',
  competitive_gap: 'Competitive Gap',
  savomart_gap: 'Savomart Gap',
  accessibility: 'Accessibility',
}

const GRADE_COLORS = {
  A: { bg: 'bg-emerald-500', text: 'text-emerald-600', ring: 'ring-emerald-200', light: 'bg-emerald-50' },
  B: { bg: 'bg-blue-500', text: 'text-blue-600', ring: 'ring-blue-200', light: 'bg-blue-50' },
  C: { bg: 'bg-amber-500', text: 'text-amber-600', ring: 'ring-amber-200', light: 'bg-amber-50' },
  D: { bg: 'bg-orange-500', text: 'text-orange-600', ring: 'ring-orange-200', light: 'bg-orange-50' },
  F: { bg: 'bg-red-500', text: 'text-red-600', ring: 'ring-red-200', light: 'bg-red-50' },
}

const DIMENSION_LABELS = {
  market_opportunity: { label: 'Market Opportunity', icon: '📊' },
  commercial_vitality: { label: 'Commercial Vitality', icon: '🏪' },
  accessibility: { label: 'Accessibility', icon: '🛣️' },
  residential_signal: { label: 'Residential Signal', icon: '🏠' },
  amenity_infrastructure: { label: 'Amenity Infrastructure', icon: '🏥' },
}

const METRIC_LABELS = {
  grocery_competitor_count: 'Grocery competitors',
  grocery_density_per_km2: 'Grocery density / km²',
  nearest_savomart_m: 'Nearest Savomart (m)',
  savomart_in_pincode: 'Savomart stores in area',
  poi_density_per_km2: 'POI density / km²',
  shop_count: 'Total shops',
  food_count: 'Restaurants & cafes',
  shop_diversity: 'Shop type diversity',
  commercial_building_count: 'Commercial buildings',
  road_network_km: 'Road network (km)',
  road_density_km_per_km2: 'Road density km/km²',
  major_road_count: 'Major road segments',
  residential_building_count: 'Residential buildings',
  apartment_density_per_km2: 'Apartment density / km²',
  school_college_count: 'Schools & colleges',
  bank_atm_count: 'Banks & ATMs',
  healthcare_count: 'Healthcare facilities',
  fuel_count: 'Fuel stations',
  amenity_diversity: 'Amenity type diversity',
}

const TYPE_BADGE = {
  direct: { label: 'Direct', cls: 'bg-emerald-100 text-emerald-700' },
  derived: { label: 'Derived', cls: 'bg-blue-100 text-blue-700' },
  proxy: { label: 'Proxy', cls: 'bg-amber-100 text-amber-700' },
}

function FlyTo({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center, zoom || 14, { duration: 0.8 })
  }, [center, zoom, map])
  return null
}

function PincodeSearch({ pincodes, onSelect }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  const filtered = query.length >= 2
    ? pincodes.filter(p =>
        p.properties.pincode.includes(query) ||
        (p.properties.name || '').toLowerCase().includes(query.toLowerCase())
      ).slice(0, 20)
    : []

  return (
    <div className="relative">
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Search pincode or area..."
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-savo-purple/40 focus:border-savo-purple focus:bg-white transition-all"
        />
      </div>
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-64 overflow-y-auto">
          {filtered.map(f => (
            <li
              key={f.properties.pincode}
              onMouseDown={(e) => { e.preventDefault(); onSelect(f.properties.pincode); setQuery(f.properties.pincode); setOpen(false) }}
              className="px-3 py-2.5 hover:bg-savo-purple/5 cursor-pointer text-sm flex items-center gap-2 border-b border-gray-50 last:border-0"
            >
              <span className="font-mono font-semibold text-savo-purple">{f.properties.pincode}</span>
              <span className="text-gray-500 truncate">{f.properties.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function MetricCard({ value, label, accent }) {
  return (
    <div className={`rounded-lg p-3 text-center ${accent ? 'bg-savo-purple text-white' : 'bg-gray-50'}`}>
      <div className={`text-xl font-bold tabular-nums ${accent ? '' : 'text-gray-900'}`}>{value}</div>
      <div className={`text-[11px] font-medium uppercase tracking-wider mt-0.5 ${accent ? 'text-white/70' : 'text-gray-500'}`}>{label}</div>
    </div>
  )
}

function SummarySection({ title, items, max }) {
  const entries = Object.entries(items)
  if (entries.length === 0) return null
  const shown = max ? entries.slice(0, max) : entries
  const remaining = entries.length - shown.length

  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</h4>
      <div className="space-y-1.5">
        {shown.map(([name, count]) => (
          <div key={name} className="flex items-center justify-between text-sm">
            <span className="text-gray-600 capitalize truncate mr-2">{name}</span>
            <span className="font-medium text-gray-900 tabular-nums">{count}</span>
          </div>
        ))}
        {remaining > 0 && (
          <div className="text-xs text-gray-400 pt-0.5">+{remaining} more</div>
        )}
      </div>
    </div>
  )
}

function ScoreRing({ score, grade, size = 'lg' }) {
  const gc = GRADE_COLORS[grade] || GRADE_COLORS.C
  const circumference = 2 * Math.PI * 42
  const offset = circumference - (score / 100) * circumference
  const isLg = size === 'lg'

  return (
    <div className={`relative ${isLg ? 'w-28 h-28' : 'w-16 h-16'}`}>
      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="42" fill="none" stroke="#e5e7eb" strokeWidth="6" />
        <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor"
          className={gc.text} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-bold tabular-nums ${isLg ? 'text-2xl' : 'text-sm'} text-gray-900`}>{score}</span>
        {isLg && <span className={`text-xs font-semibold ${gc.text}`}>{grade}</span>}
      </div>
    </div>
  )
}

function DimensionBar({ name, data }) {
  const dim = DIMENSION_LABELS[name] || { label: name, icon: '📋' }
  const gc = data.score >= 80 ? GRADE_COLORS.A
    : data.score >= 60 ? GRADE_COLORS.B
    : data.score >= 40 ? GRADE_COLORS.C
    : data.score >= 20 ? GRADE_COLORS.D
    : GRADE_COLORS.F

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">{dim.icon}</span>
          <span className="text-sm font-medium text-gray-700">{dim.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400 tabular-nums">{Math.round(data.weight * 100)}%</span>
          <span className={`text-sm font-bold tabular-nums ${gc.text}`}>{data.score}</span>
        </div>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${gc.bg} transition-all duration-700 ease-out`}
          style={{ width: `${data.score}%` }}
        />
      </div>
    </div>
  )
}

function DimensionMetrics({ metrics }) {
  return (
    <div className="space-y-1.5 pl-1">
      {Object.entries(metrics).map(([key, m]) => {
        const badge = TYPE_BADGE[m.type] || TYPE_BADGE.direct
        const label = METRIC_LABELS[key] || key.replace(/_/g, ' ')
        const val = typeof m.value === 'number'
          ? (Number.isInteger(m.value) ? m.value : m.value.toFixed(1))
          : m.value
        return (
          <div key={key} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-gray-500 truncate">{label}</span>
              <span className={`px-1 py-0.5 rounded text-[9px] font-medium flex-shrink-0 ${badge.cls}`}>
                {badge.label}
              </span>
            </div>
            <span className="font-semibold text-gray-800 tabular-nums ml-2">{val}</span>
          </div>
        )
      })}
    </div>
  )
}

function ExplanationSection({ explanation, loading, error, onGenerate, unavailable }) {
  if (loading) {
    return (
      <div className="py-4 text-center">
        <div className="relative w-8 h-8 mx-auto">
          <div className="w-8 h-8 border-3 border-savo-purple/20 rounded-full" />
          <div className="w-8 h-8 border-3 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
        </div>
        <p className="text-xs text-gray-500 mt-2">Generating AI explanation...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-3 bg-red-50 rounded-lg border border-red-100">
        <p className="text-xs text-red-700 font-medium">Explanation failed</p>
        <p className="text-[10px] text-red-500 mt-0.5">{error}</p>
        <button onClick={onGenerate} className="mt-1.5 text-[10px] text-red-600 hover:underline font-medium">Retry</button>
      </div>
    )
  }

  if (unavailable) {
    return (
      <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 text-center">
        <p className="text-xs text-gray-500">AI explanation unavailable</p>
        <p className="text-[10px] text-gray-400 mt-0.5">LLM not configured. Deterministic scores above are complete.</p>
      </div>
    )
  }

  if (!explanation) {
    return (
      <button
        onClick={onGenerate}
        className="w-full py-2 bg-gray-50 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-100 transition-colors flex items-center justify-center gap-1.5 border border-gray-200"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        Generate AI Explanation
      </button>
    )
  }

  return (
    <div className="space-y-2.5 p-3 bg-gradient-to-b from-savo-purple/5 to-transparent rounded-lg border border-savo-purple/10">
      <div className="flex items-center gap-1.5">
        <svg className="w-3.5 h-3.5 text-savo-purple" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span className="text-xs font-semibold text-savo-purple">AI Explanation</span>
      </div>

      <p className="text-xs text-gray-700 leading-relaxed">{explanation.area_summary}</p>

      {explanation.positive_signals.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wider mb-1">Positive Signals</div>
          <ul className="space-y-0.5">
            {explanation.positive_signals.map((s, i) => (
              <li key={i} className="text-[11px] text-gray-600 flex gap-1.5">
                <span className="text-emerald-500 flex-shrink-0 mt-0.5">+</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {explanation.risks.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider mb-1">Risks & Watch-outs</div>
          <ul className="space-y-0.5">
            {explanation.risks.map((r, i) => (
              <li key={i} className="text-[11px] text-gray-600 flex gap-1.5">
                <span className="text-amber-500 flex-shrink-0 mt-0.5">!</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {explanation.scouting_focus && (
        <div>
          <div className="text-[10px] font-semibold text-savo-purple uppercase tracking-wider mb-1">Scouting Focus</div>
          <p className="text-[11px] text-gray-600">{explanation.scouting_focus}</p>
        </div>
      )}

      <p className="text-[9px] text-gray-400 italic pt-1 border-t border-gray-100">
        AI-generated from report data only. All numbers come from the deterministic analysis above.
      </p>
    </div>
  )
}

function FitnessReport({ report, explanation, explanationLoading, explanationError, explanationUnavailable, onGenerateExplanation }) {
  const [expanded, setExpanded] = useState(null)
  const gc = GRADE_COLORS[report.grade] || GRADE_COLORS.C
  const ts = new Date(report.generated_at)

  return (
    <div className="space-y-4">
      <div className={`${gc.light} rounded-xl p-4 flex items-center gap-4`}>
        <ScoreRing score={report.overall_score} grade={report.grade} />
        <div className="flex-1 min-w-0">
          <div className="text-lg font-bold text-gray-900">Area Fitness Score</div>
          <div className="text-sm text-gray-500 mt-0.5">{report.name}</div>
          <div className="text-xs text-gray-400 mt-1 tabular-nums font-mono">{report.pincode}</div>
        </div>
      </div>

      <div className="space-y-3">
        {Object.entries(report.sub_scores).map(([name, data]) => (
          <div key={name}>
            <button
              onClick={() => setExpanded(expanded === name ? null : name)}
              className="w-full text-left"
            >
              <DimensionBar name={name} data={data} />
            </button>
            {expanded === name && (
              <div className="mt-2 mb-1 p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                <DimensionMetrics metrics={data.metrics} />
              </div>
            )}
          </div>
        ))}
      </div>

      <ExplanationSection
        explanation={explanation}
        loading={explanationLoading}
        error={explanationError}
        unavailable={explanationUnavailable}
        onGenerate={onGenerateExplanation}
      />

      <div className="pt-2 border-t border-gray-100 space-y-2">
        <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{ts.toLocaleDateString()} {ts.toLocaleTimeString()}</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {report.data_sources.map(s => (
            <span key={s} className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-[9px] font-mono">{s}</span>
          ))}
        </div>
        <details className="text-[10px] text-gray-400">
          <summary className="cursor-pointer hover:text-gray-600">Methodology</summary>
          <p className="mt-1 leading-relaxed">
            Scores use winsorized percentile normalization (5th–95th) across all Chennai pincodes.
            Dimension weights (Market 30%, Commercial 25%, Accessibility 20%, Residential 15%, Amenity 10%)
            are product-design assumptions for grocery retail expansion, not statistically calibrated.
            Only OSM and Savomart data are used. No population, income, rent, or footfall data is available.
          </p>
        </details>
      </div>
    </div>
  )
}

function HotspotCard({ hotspot, active, onClick }) {
  const color = HOTSPOT_COLORS[hotspot.rank - 1] || '#782B90'
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg border p-3 transition-all ${
        active ? 'border-gray-400 bg-gray-50 shadow-sm' : 'border-gray-150 hover:border-gray-300 hover:bg-gray-50/50'
      }`}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
          style={{ backgroundColor: color }}
        >
          {hotspot.rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-gray-900 tabular-nums">Score: {hotspot.hotspot_score}</div>
        </div>
        <span className="text-[10px] text-gray-400 tabular-nums">{hotspot.signals.poi_count} POIs</span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {Object.entries(hotspot.sub_scores).map(([key, val]) => (
          <div key={key} className="flex items-center justify-between text-[11px]">
            <span className="text-gray-500 truncate">{HOTSPOT_DIM_LABELS[key] || key}</span>
            <span className="font-semibold text-gray-700 tabular-nums ml-1">{val}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-2 text-[10px] text-gray-400">
        <span>Savomart: {hotspot.signals.nearest_savomart_m}m</span>
        <span>Grocery: {hotspot.signals.nearest_grocery_competitor_m}m</span>
        {hotspot.signals.has_major_road && <span className="text-amber-600 font-medium">Major road</span>}
      </div>
    </button>
  )
}

function HotspotPanel({ data, loading, error, onRetry, activeHotspot, onSelectHotspot }) {
  if (loading) {
    return (
      <div className="py-5 text-center">
        <div className="relative w-8 h-8 mx-auto">
          <div className="w-8 h-8 border-3 border-savo-purple/20 rounded-full" />
          <div className="w-8 h-8 border-3 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
        </div>
        <p className="text-xs text-gray-500 mt-2">Identifying scouting hotspots...</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="p-3 bg-red-50 rounded-lg border border-red-100">
        <p className="text-sm text-red-700 font-medium">Hotspot analysis failed</p>
        <p className="text-xs text-red-500 mt-0.5">{error}</p>
        <button onClick={onRetry} className="mt-2 text-xs text-red-600 hover:underline font-medium">Retry</button>
      </div>
    )
  }
  if (!data) return null
  if (data.hotspots.length === 0) {
    return (
      <div className="p-3 bg-amber-50 rounded-lg border border-amber-100 text-center">
        <p className="text-sm text-amber-700 font-medium">No scouting hotspots found</p>
        <p className="text-xs text-amber-600 mt-0.5">This area has insufficient data or existing coverage.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Top Scouting Hotspots</h4>
        <span className="text-[10px] text-gray-400 tabular-nums">
          {data.qualified_cells} of {data.total_cells} cells qualified
        </span>
      </div>
      <div className="space-y-2">
        {data.hotspots.map(h => (
          <HotspotCard
            key={h.cell_id}
            hotspot={h}
            active={activeHotspot === h.cell_id}
            onClick={() => onSelectHotspot(activeHotspot === h.cell_id ? null : h.cell_id)}
          />
        ))}
      </div>
      <div className="text-[10px] text-gray-400 leading-relaxed pt-1 border-t border-gray-100">
        Hotspot scores are relative scouting priorities within this pincode, not success probabilities.
        Weights: Commercial 30%, Competitive Gap 30%, Savomart Gap 20%, Accessibility 20%.
      </div>
    </div>
  )
}

function HotspotMapOverlay({ data, activeHotspot, onSelectHotspot }) {
  if (!data || data.hotspots.length === 0) return null

  return (
    <>
      {data.hotspots.map(h => (
        <GeoJSON
          key={`hotspot-${h.cell_id}`}
          data={{ type: 'Feature', geometry: h.geometry, properties: { cell_id: h.cell_id, rank: h.rank, score: h.hotspot_score } }}
          style={() => HOTSPOT_STYLE(h.rank, activeHotspot === h.cell_id)}
          onEachFeature={(feature, layer) => {
            layer.bindTooltip(`#${h.rank} — Score ${h.hotspot_score}`, { sticky: true })
            layer.on({ click: () => onSelectHotspot(activeHotspot === h.cell_id ? null : h.cell_id) })
          }}
        />
      ))}
    </>
  )
}

function DetailPanel({ detail, loading, onClose, onAnalyze, fitness, fitnessLoading, fitnessError, hotspots, hotspotsLoading, hotspotsError, onFindHotspots, activeHotspot, onSelectHotspot, explanation, explanationLoading, explanationError, explanationUnavailable, onGenerateExplanation }) {
  if (loading) {
    return (
      <div className="p-5">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="h-4 bg-gray-100 rounded w-2/3" />
          <div className="grid grid-cols-3 gap-2">
            <div className="h-16 bg-gray-100 rounded-lg" />
            <div className="h-16 bg-gray-100 rounded-lg" />
            <div className="h-16 bg-gray-100 rounded-lg" />
          </div>
        </div>
      </div>
    )
  }
  if (!detail) return null

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-2xl font-bold text-gray-900 tabular-nums">{detail.pincode}</h3>
            {detail.savomart_stores.length > 0 && (
              <span className="px-1.5 py-0.5 bg-savo-yellow text-savo-purple text-[10px] font-bold rounded uppercase">
                {detail.savomart_stores.length} store{detail.savomart_stores.length > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{detail.name}</p>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <MetricCard value={detail.area_km2} label="Area km²" accent />
        <MetricCard value={detail.total_pois} label="POIs" />
        <MetricCard value={detail.total_roads} label="Roads" />
      </div>

      {!fitness && !fitnessLoading && (
        <button
          onClick={onAnalyze}
          className="w-full py-2.5 bg-savo-purple text-white rounded-lg text-sm font-medium hover:bg-savo-purple-dark transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Analyze Area Fitness
        </button>
      )}

      {fitnessLoading && (
        <div className="py-6 text-center">
          <div className="relative w-10 h-10 mx-auto">
            <div className="w-10 h-10 border-4 border-savo-purple/20 rounded-full" />
            <div className="w-10 h-10 border-4 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
          </div>
          <p className="text-sm text-gray-500 mt-3">Analyzing area fitness...</p>
          <p className="text-xs text-gray-400 mt-0.5">Computing spatial metrics across all pincodes</p>
        </div>
      )}

      {fitnessError && (
        <div className="p-3 bg-red-50 rounded-lg border border-red-100">
          <p className="text-sm text-red-700 font-medium">Analysis failed</p>
          <p className="text-xs text-red-500 mt-0.5">{fitnessError}</p>
          <button onClick={onAnalyze}
            className="mt-2 text-xs text-red-600 hover:underline font-medium">
            Retry
          </button>
        </div>
      )}

      {fitness && (
        <FitnessReport
          report={fitness}
          explanation={explanation}
          explanationLoading={explanationLoading}
          explanationError={explanationError}
          explanationUnavailable={explanationUnavailable}
          onGenerateExplanation={onGenerateExplanation}
        />
      )}

      {fitness && !hotspots && !hotspotsLoading && (
        <button
          onClick={onFindHotspots}
          className="w-full py-2.5 bg-savo-purple/10 text-savo-purple rounded-lg text-sm font-medium hover:bg-savo-purple/20 transition-colors flex items-center justify-center gap-2 border border-savo-purple/20"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Find Scouting Hotspots
        </button>
      )}

      <HotspotPanel
        data={hotspots}
        loading={hotspotsLoading}
        error={hotspotsError}
        onRetry={onFindHotspots}
        activeHotspot={activeHotspot}
        onSelectHotspot={onSelectHotspot}
      />

      {!fitness && !fitnessLoading && (
        <>
          {detail.savomart_stores.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Savomart Stores</h4>
              <div className="space-y-1.5">
                {detail.savomart_stores.map(s => (
                  <div key={s.store_id} className="flex items-center gap-2 text-sm bg-savo-yellow/10 border border-savo-yellow/30 rounded-lg px-3 py-2">
                    <div className="w-2 h-2 bg-savo-purple rounded-full flex-shrink-0" />
                    <span className="text-gray-700 font-medium">{s.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <SummarySection title="POI Breakdown" items={detail.poi_summary} />
          <SummarySection title="Road Types" items={detail.road_summary} max={8} />
        </>
      )}
    </div>
  )
}

export default function AreaExplorer() {
  const [boundaries, setBoundaries] = useState(null)
  const [stores, setStores] = useState(null)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [fitness, setFitness] = useState(null)
  const [fitnessLoading, setFitnessLoading] = useState(false)
  const [fitnessError, setFitnessError] = useState(null)
  const [hotspots, setHotspots] = useState(null)
  const [hotspotsLoading, setHotspotsLoading] = useState(false)
  const [hotspotsError, setHotspotsError] = useState(null)
  const [activeHotspot, setActiveHotspot] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [explanationLoading, setExplanationLoading] = useState(false)
  const [explanationError, setExplanationError] = useState(null)
  const [explanationUnavailable, setExplanationUnavailable] = useState(false)
  const geoJsonRef = useRef(null)

  useEffect(() => {
    Promise.all([fetchPincodeBoundaries(), fetchStores()])
      .then(([b, s]) => { setBoundaries(b); setStores(s); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [])

  const selectPincode = useCallback(async (pincode) => {
    setSelected(pincode)
    setDetailLoading(true)
    setDetail(null)
    setFitness(null)
    setFitnessError(null)
    setHotspots(null)
    setHotspotsError(null)
    setActiveHotspot(null)
    setExplanation(null)
    setExplanationError(null)
    setExplanationUnavailable(false)
    try {
      const d = await fetchPincodeDetail(pincode)
      setDetail(d)
      if (d.centroid) {
        setFlyTarget([d.centroid.coordinates[1], d.centroid.coordinates[0]])
      }
    } catch (err) {
      setError(`Failed to load pincode ${pincode}: ${err.message}`)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const analyzeFitness = useCallback(async () => {
    if (!selected) return
    setFitnessLoading(true)
    setFitnessError(null)
    try {
      const report = await fetchFitnessReport(selected)
      setFitness(report)
    } catch (err) {
      setFitnessError(err.response?.data?.detail || err.message)
    } finally {
      setFitnessLoading(false)
    }
  }, [selected])

  const generateExplanation = useCallback(async () => {
    if (!selected || !fitness?.report_id) return
    setExplanationLoading(true)
    setExplanationError(null)
    setExplanationUnavailable(false)
    try {
      const res = await fetchExplanation(selected, fitness.report_id)
      if (res.explanation) {
        setExplanation(res.explanation)
      } else {
        setExplanationUnavailable(true)
      }
    } catch (err) {
      setExplanationError(err.response?.data?.detail || err.message)
    } finally {
      setExplanationLoading(false)
    }
  }, [selected, fitness])

  const findHotspots = useCallback(async () => {
    if (!selected) return
    setHotspotsLoading(true)
    setHotspotsError(null)
    setActiveHotspot(null)
    try {
      const data = await fetchHotspots(selected)
      setHotspots(data)
    } catch (err) {
      setHotspotsError(err.response?.data?.detail || err.message)
    } finally {
      setHotspotsLoading(false)
    }
  }, [selected])

  const clearSelection = useCallback(() => {
    setSelected(null)
    setDetail(null)
    setFitness(null)
    setFitnessError(null)
    setHotspots(null)
    setHotspotsError(null)
    setActiveHotspot(null)
    setExplanation(null)
    setExplanationError(null)
    setExplanationUnavailable(false)
  }, [])

  const onEachFeature = useCallback((feature, layer) => {
    layer.on({
      mouseover: (e) => {
        if (feature.properties.pincode !== selected) {
          e.target.setStyle(STYLE_HOVER)
        }
      },
      mouseout: (e) => {
        if (feature.properties.pincode !== selected) {
          e.target.setStyle(STYLE_DEFAULT)
        }
      },
      click: () => selectPincode(feature.properties.pincode),
    })
    layer.bindTooltip(`${feature.properties.pincode} — ${feature.properties.name || ''}`, { sticky: true })
  }, [selected, selectPincode])

  const style = useCallback((feature) => {
    return feature.properties.pincode === selected ? STYLE_SELECTED : STYLE_DEFAULT
  }, [selected])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <div className="text-center">
          <div className="relative">
            <div className="w-12 h-12 border-4 border-savo-purple/20 rounded-full" />
            <div className="w-12 h-12 border-4 border-savo-purple border-t-transparent rounded-full animate-spin absolute inset-0" />
          </div>
          <p className="mt-4 text-sm text-gray-500 font-medium">Loading Chennai map data</p>
          <p className="text-xs text-gray-400 mt-1">Fetching boundaries and store locations...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto">
            <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <p className="text-gray-800 font-semibold mt-3">Failed to load map data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <button onClick={() => window.location.reload()} className="mt-4 px-4 py-2 bg-savo-purple text-white rounded-lg text-sm font-medium hover:bg-savo-purple-dark transition-colors">
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-48px)]">
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col overflow-hidden shadow-sm">
        <div className="p-3 border-b border-gray-100 space-y-2">
          <PincodeSearch
            pincodes={boundaries?.features || []}
            onSelect={selectPincode}
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gray-400">{boundaries?.features?.length || 0} pincodes</span>
            {selected && (
              <button
                onClick={clearSelection}
                className="text-[11px] text-savo-purple hover:underline font-medium"
              >
                Clear selection
              </button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {(selected || detailLoading) ? (
            <DetailPanel
              detail={detail}
              loading={detailLoading}
              onClose={clearSelection}
              onAnalyze={analyzeFitness}
              fitness={fitness}
              fitnessLoading={fitnessLoading}
              fitnessError={fitnessError}
              hotspots={hotspots}
              hotspotsLoading={hotspotsLoading}
              hotspotsError={hotspotsError}
              onFindHotspots={findHotspots}
              activeHotspot={activeHotspot}
              onSelectHotspot={setActiveHotspot}
              explanation={explanation}
              explanationLoading={explanationLoading}
              explanationError={explanationError}
              explanationUnavailable={explanationUnavailable}
              onGenerateExplanation={generateExplanation}
            />
          ) : (
            <div className="p-5 text-center">
              <div className="w-10 h-10 rounded-full bg-savo-purple/5 flex items-center justify-center mx-auto">
                <svg className="w-5 h-5 text-savo-purple/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
              </div>
              <p className="text-sm text-gray-500 mt-3">Select a pincode on the map or search above</p>
              <p className="text-xs text-gray-400 mt-1">View area intelligence, POI density, and store presence</p>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 relative">
        <MapContainer center={CHENNAI_CENTER} zoom={CHENNAI_ZOOM} className="h-full w-full" zoomControl={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {boundaries && (
            <GeoJSON
              key={selected || 'all'}
              ref={geoJsonRef}
              data={boundaries}
              style={style}
              onEachFeature={onEachFeature}
            />
          )}
          {stores?.features?.map(f => (
            <Marker
              key={f.properties.store_id}
              position={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
              icon={storeIcon}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-bold">{f.properties.name}</div>
                  <div className="text-gray-500">{f.properties.address}</div>
                </div>
              </Popup>
            </Marker>
          ))}
          <HotspotMapOverlay data={hotspots} activeHotspot={activeHotspot} onSelectHotspot={setActiveHotspot} />
          {flyTarget && <FlyTo center={flyTarget} zoom={14} />}
        </MapContainer>
      </div>
    </div>
  )
}

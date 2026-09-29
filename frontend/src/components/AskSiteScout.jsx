import { useState } from 'react'
import { askSiteScout } from '../api'

const EXAMPLES = [
  'Compare areas 600034 and 600006',
  'Which areas have the best fitness score?',
  'Explain the evaluation score for the property at Usman Road',
  'What is the catchment study status?',
]

export default function AskSiteScout() {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleAsk(q) {
    const text = q || question
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await askSiteScout(text.trim())
      setResult(data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-50 w-12 h-12 rounded-full bg-savo-purple text-white shadow-lg hover:bg-savo-purple-dark transition-colors flex items-center justify-center text-lg font-bold"
        title="Ask SiteScout"
      >
        ?
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 max-h-[70vh] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
      <div className="bg-savo-purple px-4 py-2.5 flex items-center justify-between flex-shrink-0">
        <span className="text-white text-sm font-semibold">Ask SiteScout</span>
        <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white text-lg leading-none">&times;</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {!result && !loading && !error && (
          <div className="space-y-1.5">
            <p className="text-xs text-gray-500">Try one of these:</p>
            {EXAMPLES.map((ex, i) => (
              <button
                key={i}
                onClick={() => { setQuestion(ex); handleAsk(ex) }}
                className="block w-full text-left px-3 py-1.5 rounded-md bg-gray-50 hover:bg-savo-purple/5 text-xs text-gray-700 border border-gray-100 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-4 justify-center">
            <span className="animate-spin w-4 h-4 border-2 border-savo-purple border-t-transparent rounded-full" />
            Analyzing...
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">{error}</div>
        )}

        {result && (
          <div className="space-y-2">
            {result.query_type === 'unsupported' && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-[10px] text-amber-700">Unsupported query type</div>
            )}
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-800 whitespace-pre-wrap leading-relaxed">
              {result.answer}
            </div>
            {result.sources && result.sources.length > 0 && (
              <div className="border-t border-gray-100 pt-2">
                <p className="text-[10px] font-semibold text-gray-400 uppercase mb-1">Data Sources</p>
                <div className="space-y-1">
                  {result.sources.map((s, i) => (
                    <div key={i} className="text-[10px] text-gray-500 bg-gray-50 rounded px-2 py-1">
                      {s.type === 'area_report' && `Area ${s.pincode} — Score: ${s.score}/100`}
                      {s.type === 'property_evaluation' && `${s.address} — Score: ${s.score}/100`}
                      {s.type === 'catchment_study' && `${s.address} — ${s.status}`}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button
              onClick={() => { setResult(null); setQuestion('') }}
              className="text-xs text-savo-purple hover:underline"
            >
              Ask another question
            </button>
          </div>
        )}
      </div>

      <div className="border-t border-gray-200 p-2 flex gap-2 flex-shrink-0">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAsk()}
          placeholder="Ask about areas, properties, catchment..."
          className="flex-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-savo-purple"
          disabled={loading}
          maxLength={500}
        />
        <button
          onClick={() => handleAsk()}
          disabled={loading || !question.trim()}
          className="px-3 py-1.5 bg-savo-purple text-white text-xs font-medium rounded-lg hover:bg-savo-purple-dark disabled:opacity-50 transition-colors"
        >
          Ask
        </button>
      </div>
    </div>
  )
}

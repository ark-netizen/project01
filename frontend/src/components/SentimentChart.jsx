import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  긍정: '#22c55e',
  중립: '#94a3b8',
  부정: '#ef4444',
}

const KEY_MAP = { 긍정: 'positive', 중립: 'neutral', 부정: 'negative' }

export default function SentimentChart({ summary, selectedSentiment, onSelect }) {
  if (!summary || summary.total === 0) return null

  const data = [
    { name: '긍정', value: summary.positive, pct: summary.positive_pct },
    { name: '중립', value: summary.neutral, pct: summary.neutral_pct },
    { name: '부정', value: summary.negative, pct: summary.negative_pct },
  ].filter(d => d.value > 0)

  function handleClick(name) {
    if (!onSelect) return
    const key = KEY_MAP[name]
    onSelect(selectedSentiment === key ? null : key)
  }

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-700">감성 분포</h3>
        {selectedSentiment && onSelect && (
          <button onClick={() => onSelect(null)}
            className="text-xs text-gray-400 hover:text-gray-600 underline">
            필터 해제
          </button>
        )}
      </div>

      <div className="flex flex-col md:flex-row items-center gap-6">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              onClick={(entry) => handleClick(entry.name)}
              style={{ cursor: onSelect ? 'pointer' : 'default' }}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={COLORS[entry.name]}
                  opacity={selectedSentiment && selectedSentiment !== KEY_MAP[entry.name] ? 0.3 : 1}
                  stroke={selectedSentiment === KEY_MAP[entry.name] ? '#1e293b' : 'none'}
                  strokeWidth={selectedSentiment === KEY_MAP[entry.name] ? 2 : 0}
                />
              ))}
            </Pie>
            <Tooltip formatter={(val, name) => [`${val}건`, name]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex flex-col gap-3 min-w-[160px]">
          {[
            { label: '긍정', key: 'positive', pct: summary.positive_pct, count: summary.positive, color: 'text-green-500', border: 'border-green-200 bg-green-50' },
            { label: '중립', key: 'neutral',  pct: summary.neutral_pct,  count: summary.neutral,  color: 'text-slate-400', border: 'border-slate-200 bg-slate-50' },
            { label: '부정', key: 'negative', pct: summary.negative_pct, count: summary.negative, color: 'text-red-500',   border: 'border-red-200 bg-red-50' },
          ].map(({ label, key, pct, count, color, border }) => (
            <button
              key={label}
              type="button"
              onClick={() => handleClick(label)}
              className={`flex items-center justify-between gap-4 px-3 py-2 rounded-xl border transition
                ${selectedSentiment === key ? border + ' shadow-sm' : 'border-transparent hover:bg-gray-50'}
                ${onSelect ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <span className={`font-bold text-sm ${color}`}>{label}</span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 text-sm">{count}건</span>
                <span className={`font-semibold ${color}`}>{pct}%</span>
              </div>
            </button>
          ))}
          <div className="border-t pt-2 text-sm text-gray-400 px-3">총 {summary.total}건</div>
        </div>
      </div>
    </div>
  )
}

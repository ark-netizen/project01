import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#6366f1','#8b5cf6','#a78bfa','#3b82f6','#60a5fa','#34d399','#fbbf24','#f87171','#fb923c','#e879f9',
                 '#6366f1','#8b5cf6','#a78bfa','#3b82f6','#60a5fa','#34d399','#fbbf24','#f87171','#fb923c','#e879f9']

export default function KeywordChart({ keywords, selectedKeyword, onSelect }) {
  if (!keywords || keywords.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-700">주요 키워드 Top {keywords.length}</h3>
        {selectedKeyword && (
          <button
            onClick={() => onSelect?.(null)}
            className="text-xs text-indigo-500 hover:text-indigo-700 underline"
          >
            필터 해제
          </button>
        )}
      </div>
      {selectedKeyword && (
        <p className="text-xs text-indigo-600 bg-indigo-50 rounded-lg px-3 py-1.5 mb-3">
          「{selectedKeyword}」포함 댓글만 표시 중
        </p>
      )}
      <ResponsiveContainer width="100%" height={Math.max(200, keywords.length * 34)}>
        <BarChart
          layout="vertical"
          data={keywords}
          margin={{ left: 8, right: 32, top: 4, bottom: 4 }}
        >
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="word"
            width={100}
            tick={{ fontSize: 13 }}
            tickFormatter={v => v.length > 12 ? v.slice(0, 11) + '…' : v}
          />
          <Tooltip formatter={(val) => [`${val}회`, '등장 횟수']} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} style={{ cursor: 'pointer' }}>
            {keywords.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.word === selectedKeyword ? '#4f46e5' : COLORS[idx % COLORS.length]}
                opacity={selectedKeyword && entry.word !== selectedKeyword ? 0.4 : 1}
                onClick={() => onSelect?.(entry.word === selectedKeyword ? null : entry.word)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

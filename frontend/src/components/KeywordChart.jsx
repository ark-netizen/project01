import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#6366f1','#8b5cf6','#a78bfa','#3b82f6','#60a5fa','#34d399','#fbbf24','#f87171','#fb923c','#e879f9',
                 '#6366f1','#8b5cf6','#a78bfa','#3b82f6','#60a5fa','#34d399','#fbbf24','#f87171','#fb923c','#e879f9']

export default function KeywordChart({ keywords }) {
  if (!keywords || keywords.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">주요 키워드 Top {keywords.length}</h3>
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
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {keywords.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

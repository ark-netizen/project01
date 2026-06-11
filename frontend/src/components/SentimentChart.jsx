import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  긍정: '#22c55e',
  중립: '#94a3b8',
  부정: '#ef4444',
}

export default function SentimentChart({ summary }) {
  if (!summary || summary.total === 0) return null

  const data = [
    { name: '긍정', value: summary.positive, pct: summary.positive_pct },
    { name: '중립', value: summary.neutral, pct: summary.neutral_pct },
    { name: '부정', value: summary.negative, pct: summary.negative_pct },
  ].filter(d => d.value > 0)

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">감성 분포</h3>

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
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={COLORS[entry.name]} />
              ))}
            </Pie>
            <Tooltip formatter={(val, name) => [`${val}건`, name]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex flex-col gap-3 min-w-[160px]">
          {[
            { label: '긍정', key: 'positive', pct: summary.positive_pct, count: summary.positive, color: 'text-green-500' },
            { label: '중립', key: 'neutral', pct: summary.neutral_pct, count: summary.neutral, color: 'text-slate-400' },
            { label: '부정', key: 'negative', pct: summary.negative_pct, count: summary.negative, color: 'text-red-500' },
          ].map(({ label, pct, count, color }) => (
            <div key={label} className="flex items-center justify-between gap-4">
              <span className={`font-bold text-sm ${color}`}>{label}</span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 text-sm">{count}건</span>
                <span className={`font-semibold ${color}`}>{pct}%</span>
              </div>
            </div>
          ))}
          <div className="border-t pt-2 text-sm text-gray-400">총 {summary.total}건</div>
        </div>
      </div>
    </div>
  )
}

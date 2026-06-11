import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#e0e7ff', '#f0f4ff', '#f8fafc', '#f1f5f9']

export default function TopAccounts({ accounts, type }) {
  if (!accounts || accounts.length === 0) return null

  const label = type === 'twitter' ? '@계정' : '채널/사용자'

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">
        가장 많이 언급된 {label} Top {accounts.length}
      </h3>

      <ResponsiveContainer width="100%" height={Math.max(180, accounts.length * 36)}>
        <BarChart
          layout="vertical"
          data={accounts}
          margin={{ left: 8, right: 24, top: 4, bottom: 4 }}
        >
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="account"
            width={130}
            tick={{ fontSize: 12 }}
            tickFormatter={v => (v.length > 16 ? v.slice(0, 15) + '…' : v)}
          />
          <Tooltip
            formatter={(val) => [`${val}건`, '등장 횟수']}
            labelFormatter={(label) => `@${label}`}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {accounts.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#e0e7ff']

export default function TopAccounts({ accounts, type, vertical = false }) {
  if (!accounts || accounts.length === 0) return null

  const label = type === 'twitter' ? '@계정' : '채널/사용자'

  if (vertical) {
    return (
      <div className="bg-white rounded-2xl shadow p-5 flex flex-col gap-3">
        <h3 className="text-base font-semibold text-gray-700">
          많이 언급된 {label} Top {accounts.length}
        </h3>
        <ol className="flex flex-col gap-2">
          {accounts.map((item, idx) => (
            <li key={idx} className="flex items-center gap-2">
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0`}
                style={{ background: COLORS[idx % COLORS.length] }}>
                {idx + 1}
              </span>
              <span className="text-sm text-gray-700 truncate flex-1" title={item.account}>
                {item.account.length > 18 ? item.account.slice(0, 17) + '…' : item.account}
              </span>
              <span className="text-xs text-gray-400 shrink-0">{item.count}건</span>
            </li>
          ))}
        </ol>
      </div>
    )
  }

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

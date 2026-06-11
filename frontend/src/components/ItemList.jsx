const BADGE = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-slate-100 text-slate-600',
  negative: 'bg-red-100 text-red-600',
}

const LABEL_KO = { positive: '긍정', neutral: '중립', negative: '부정' }

export default function ItemList({ items, type }) {
  if (!items || items.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">
        {type === 'twitter' ? '트윗 목록' : '댓글 목록'}
      </h3>

      <div className="flex flex-col gap-3 max-h-[480px] overflow-y-auto pr-1">
        {items.map((item, idx) => {
          const label = item.sentiment?.label ?? 'neutral'
          const score = item.sentiment?.score ?? 0
          const lang = item.sentiment?.language ?? ''

          return (
            <div
              key={item.id || idx}
              className="border border-gray-100 rounded-xl p-4 hover:shadow-sm transition"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-gray-800 flex-1 leading-relaxed">{item.text}</p>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${BADGE[label]}`}>
                  {LABEL_KO[label]}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                <span>@{item.user || item.author}</span>
                {item.created_at && <span>{item.created_at}</span>}
                {item.time && <span>{item.time}</span>}
                <span>신뢰도 {Math.round(score * 100)}%</span>
                {lang && lang !== 'unknown' && (
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">{lang === 'ko' ? '한국어' : '영어'}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

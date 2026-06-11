const BADGE = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-slate-100 text-slate-600',
  negative: 'bg-red-100 text-red-600',
}

const LABEL_KO = { positive: '긍정', neutral: '중립', negative: '부정' }

export default function ItemList({ items, type, filterKeyword, filterSentiment }) {
  if (!items || items.length === 0) return null

  let filtered = items
  if (filterKeyword) filtered = filtered.filter(item => item.text?.toLowerCase().includes(filterKeyword.toLowerCase()))
  if (filterSentiment) filtered = filtered.filter(item => (item.sentiment?.label ?? 'neutral') === filterSentiment)

  const SENTIMENT_LABEL = { positive: '긍정', neutral: '중립', negative: '부정' }
  const isFiltered = filterKeyword || filterSentiment

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-700">
          {type === 'twitter' ? '트윗 목록' : '댓글 목록'}
        </h3>
        {isFiltered && (
          <span className="text-xs text-indigo-600 bg-indigo-50 rounded-full px-2.5 py-1">
            {filtered.length}건 / 전체 {items.length}건
            {filterSentiment && ` · ${SENTIMENT_LABEL[filterSentiment]}`}
          </span>
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">「{filterKeyword}」포함 댓글이 없습니다.</p>
      ) : (
        <div className="flex flex-col gap-3 max-h-[480px] overflow-y-auto pr-1">
          {filtered.map((item, idx) => {
            const label = item.sentiment?.label ?? 'neutral'
            const score = item.sentiment?.score ?? 0

            return (
              <div
                key={item.id || idx}
                className="border border-gray-100 rounded-xl p-4 hover:shadow-sm transition"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-gray-800 flex-1 leading-relaxed">
                    {filterKeyword
                      ? highlightKeyword(item.text, filterKeyword)
                      : item.text}
                  </p>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${BADGE[label]}`}>
                    {LABEL_KO[label]}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                  <span>@{item.user || item.author}</span>
                  {item.created_at && <span>{item.created_at}</span>}
                  {item.time && <span>{item.time}</span>}
                  <span>신뢰도 {Math.round(score * 100)}%</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function highlightKeyword(text, keyword) {
  if (!text || !keyword) return text
  const parts = text.split(new RegExp(`(${keyword})`, 'gi'))
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase()
      ? <mark key={i} className="bg-indigo-100 text-indigo-800 rounded px-0.5">{part}</mark>
      : part
  )
}

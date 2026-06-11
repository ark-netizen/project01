import { useState } from 'react'
import { api } from '../api'

const BADGE = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-slate-100 text-slate-600',
  negative: 'bg-red-100 text-red-600',
}

const LABEL_KO = { positive: '긍정', neutral: '중립', negative: '부정' }

export default function ItemList({ items, type, filterKeyword, filterSentiment }) {
  const [translations, setTranslations] = useState({})
  const [translating, setTranslating] = useState({})

  if (!items || items.length === 0) return null

  let filtered = items
  if (filterKeyword) filtered = filtered.filter(item => item.text?.toLowerCase().includes(filterKeyword.toLowerCase()))
  if (filterSentiment) filtered = filtered.filter(item => (item.sentiment?.label ?? 'neutral') === filterSentiment)

  const SENTIMENT_LABEL = { positive: '긍정', neutral: '중립', negative: '부정' }
  const isFiltered = filterKeyword || filterSentiment

  async function handleTranslate(idx, text) {
    if (translations[idx] !== undefined) {
      setTranslations(t => { const n = { ...t }; delete n[idx]; return n })
      return
    }
    setTranslating(t => ({ ...t, [idx]: true }))
    try {
      const res = await fetch(api('/api/translate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await res.json()
      setTranslations(t => ({ ...t, [idx]: data.translated }))
    } catch {
      setTranslations(t => ({ ...t, [idx]: '번역 실패' }))
    } finally {
      setTranslating(t => ({ ...t, [idx]: false }))
    }
  }

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
        <p className="text-sm text-gray-400 text-center py-6">
          {filterKeyword ? `「${filterKeyword}」포함 ` : ''}{filterSentiment ? `${SENTIMENT_LABEL[filterSentiment]} ` : ''}댓글이 없습니다.
        </p>
      ) : (
        <div className="flex flex-col gap-3 max-h-[480px] overflow-y-auto pr-1">
          {filtered.map((item, idx) => {
            const label = item.sentiment?.label ?? 'neutral'
            const score = item.sentiment?.score ?? 0

            return (
              <div key={item.id || idx} className="border border-gray-100 rounded-xl p-4 hover:shadow-sm transition">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-gray-800 flex-1 leading-relaxed">
                    {filterKeyword ? highlightKeyword(item.text, filterKeyword) : item.text}
                  </p>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => handleTranslate(idx, item.text)}
                      disabled={translating[idx]}
                      className="text-xs px-2 py-0.5 rounded-full border border-gray-200 text-gray-400 hover:text-blue-500 hover:border-blue-300 transition disabled:opacity-40"
                    >
                      {translating[idx] ? '...' : translations[idx] !== undefined ? '원문' : '번역'}
                    </button>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${BADGE[label]}`}>
                      {LABEL_KO[label]}
                    </span>
                  </div>
                </div>
                {translations[idx] !== undefined && (
                  <p className="text-sm text-blue-600 mt-2 pl-1 border-l-2 border-blue-200 italic leading-relaxed">
                    {translations[idx]}
                  </p>
                )}
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

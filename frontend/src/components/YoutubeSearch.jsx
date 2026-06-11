import { useState } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import TopAccounts from './TopAccounts'
import ItemList from './ItemList'

export default function YoutubeSearch() {
  const [url, setUrl] = useState('')
  const [maxCount, setMaxCount] = useState(100)
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleAnalyze(e) {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch(api('/api/youtube/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          max_count: maxCount,
          since: since || null,
          until: until || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '오류 발생')
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleAnalyze} className="bg-white rounded-2xl shadow p-6 flex flex-col gap-4">
        <h2 className="text-xl font-bold text-gray-800">YouTube 댓글 감성분석</h2>

        <input
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="YouTube URL 입력 (예: https://www.youtube.com/watch?v=xxxxx)"
          className="border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
        />

        <div className="flex gap-3 items-center flex-wrap">
          <select
            value={maxCount}
            onChange={e => setMaxCount(Number(e.target.value))}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none"
          >
            <option value={50}>50건</option>
            <option value={100}>100건</option>
            <option value={200}>200건</option>
          </select>

          <span className="text-sm text-gray-500 shrink-0">기간</span>
          <input
            type="date"
            value={since}
            onChange={e => setSince(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          <span className="text-gray-400 text-sm">~</span>
          <input
            type="date"
            value={until}
            onChange={e => setUntil(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          {(since || until) && (
            <button type="button" onClick={() => { setSince(''); setUntil('') }}
              className="text-xs text-gray-400 hover:text-gray-600 underline shrink-0">
              초기화
            </button>
          )}

          <button
            type="submit"
            disabled={loading}
            className="ml-auto bg-red-500 hover:bg-red-600 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm"
          >
            {loading ? '분석 중...' : '분석'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-5 py-4 text-sm">{error}</div>
      )}
      {loading && (
        <div className="text-center py-12 text-gray-400 text-sm">YouTube 댓글 크롤링 및 감성분석 중입니다...</div>
      )}
      {result && (
        <>
          <SentimentChart summary={result.summary} />
          <TopAccounts accounts={result.summary.top_accounts} type="youtube" />
          <ItemList items={result.items} type="youtube" />
        </>
      )}
    </div>
  )
}

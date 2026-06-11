import { useState } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import TopAccounts from './TopAccounts'
import KeywordChart from './KeywordChart'
import ItemList from './ItemList'

export default function YoutubeSearch() {
  const [mode, setMode] = useState('keyword') // 'keyword' | 'url'
  const [keyword, setKeyword] = useState('')
  const [url, setUrl] = useState('')
  const [maxVideos, setMaxVideos] = useState(10)
  const [maxPerVideo, setMaxPerVideo] = useState(30)
  const [maxCount, setMaxCount] = useState(100)
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleAnalyze(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const body = {
        mode,
        since: since || null,
        until: until || null,
        ...(mode === 'keyword'
          ? { keyword, max_videos: maxVideos, max_per_video: maxPerVideo }
          : { url, max_count: maxCount }),
      }
      const res = await fetch(api('/api/youtube/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
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

        {/* 모드 전환 */}
        <div className="flex gap-2">
          {[['keyword', '키워드 검색'], ['url', 'URL 직접 입력']].map(([val, label]) => (
            <button
              key={val}
              type="button"
              onClick={() => setMode(val)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition
                ${mode === val ? 'bg-red-500 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === 'keyword' ? (
          <div className="flex gap-3 flex-wrap">
            <input
              type="text"
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              placeholder="키워드 입력 (예: 아이폰, 삼성, 먹방)"
              className="flex-1 min-w-0 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              required
            />
            <select value={maxVideos} onChange={e => setMaxVideos(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none">
              <option value={5}>영상 5개</option>
              <option value={10}>영상 10개</option>
              <option value={20}>영상 20개</option>
            </select>
            <select value={maxPerVideo} onChange={e => setMaxPerVideo(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none">
              <option value={20}>영상당 20댓글</option>
              <option value={30}>영상당 30댓글</option>
              <option value={50}>영상당 50댓글</option>
            </select>
          </div>
        ) : (
          <div className="flex gap-3">
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=xxxxx"
              className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              required
            />
            <select value={maxCount} onChange={e => setMaxCount(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none">
              <option value={50}>50건</option>
              <option value={100}>100건</option>
              <option value={200}>200건</option>
            </select>
          </div>
        )}

        {/* 날짜 범위 */}
        <div className="flex gap-3 items-center flex-wrap">
          <span className="text-sm text-gray-500 shrink-0">기간</span>
          <input type="date" value={since} onChange={e => setSince(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400" />
          <span className="text-gray-400 text-sm">~</span>
          <input type="date" value={until} onChange={e => setUntil(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400" />
          {(since || until) && (
            <button type="button" onClick={() => { setSince(''); setUntil('') }}
              className="text-xs text-gray-400 hover:text-gray-600 underline shrink-0">초기화</button>
          )}
          <button type="submit" disabled={loading}
            className="ml-auto bg-red-500 hover:bg-red-600 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm">
            {loading ? '분석 중...' : '분석'}
          </button>
        </div>
      </form>

      {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-5 py-4 text-sm">{error}</div>}

      {loading && (
        <div className="text-center py-12 text-gray-400 text-sm">
          {mode === 'keyword' ? `YouTube 상위 ${maxVideos}개 영상 댓글 크롤링 중...` : 'YouTube 댓글 크롤링 중...'}
          <br /><span className="text-xs">감성분석까지 1~2분 소요될 수 있습니다.</span>
        </div>
      )}

      {result && (
        <>
          {/* 키워드 검색 시 수집된 영상 목록 */}
          {result.videos && result.videos.length > 0 && (
            <div className="bg-white rounded-2xl shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-3">분석한 영상 ({result.videos.length}개)</h3>
              <div className="flex flex-col gap-2">
                {result.videos.map(v => (
                  <a key={v.id} href={v.url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-between text-sm hover:bg-gray-50 rounded-lg px-3 py-2 transition">
                    <span className="text-gray-800 truncate flex-1">{v.title}</span>
                    <span className="text-gray-400 shrink-0 ml-4">{v.channel}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
          <SentimentChart summary={result.summary} />
          <KeywordChart keywords={result.keywords} />
          <TopAccounts accounts={result.summary.top_accounts} type="youtube" />
          <ItemList items={result.items} type="youtube" />
        </>
      )}
    </div>
  )
}

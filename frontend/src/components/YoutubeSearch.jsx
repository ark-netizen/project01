import { useState, useRef } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import TopAccounts from './TopAccounts'
import KeywordChart from './KeywordChart'
import ItemList from './ItemList'

const STEP_LABELS = {
  search:   '영상 검색 중...',
  found:    '영상 발견됨',
  crawl:    '댓글 수집 중...',
  analyze:  '감성 분석 중...',
  keywords: '키워드 추출 중...',
}

export default function YoutubeSearch() {
  const [mode, setMode] = useState('keyword')
  const [keyword, setKeyword] = useState('')
  const [url, setUrl] = useState('')
  const [maxVideos, setMaxVideos] = useState(10)
  const [maxPerVideo, setMaxPerVideo] = useState(30)
  const [maxCount, setMaxCount] = useState(100)
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')

  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [selectedKeyword, setSelectedKeyword] = useState(null)
  const today = new Date().toISOString().split('T')[0]
  const pollRef = useRef(null)

  function stopPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  function handleStop() {
    stopPoll()
    setLoading(false)
    setProgress(null)
  }

  async function handleAnalyze(e) {
    e.preventDefault()
    stopPoll()
    setLoading(true)
    setError('')
    setResult(null)
    setProgress(null)

    if (mode === 'keyword') {
      // 1단계: 작업 시작
      const params = new URLSearchParams({
        keyword,
        max_videos: maxVideos,
        max_per_video: maxPerVideo,
        ...(since && { since }),
        ...(until && { until }),
      })
      try {
        const res = await fetch(api(`/api/youtube/analyze-keyword?${params}`), { method: 'POST' })
        if (!res.ok) {
          const d = await res.json()
          throw new Error(d.detail || '분석 시작 실패')
        }
        const { job_id } = await res.json()

        // 2단계: 2초마다 상태 폴링
        pollRef.current = setInterval(async () => {
          try {
            const jobRes = await fetch(api(`/api/youtube/job/${job_id}`))
            if (!jobRes.ok) {
              setError('작업 상태 조회 실패')
              stopPoll()
              setLoading(false)
              return
            }
            const job = await jobRes.json()

            setProgress({ step: job.step, msg: job.msg, current: job.current, total: job.total })

            if (job.status === 'done') {
              const r = job.result
              if (r?.sentiment_error) setError(`감성분석 오류: ${r.sentiment_error}`)
              setResult(r)
              stopPoll()
              setLoading(false)
              setProgress(null)
            } else if (job.status === 'error') {
              setError(job.error || '알 수 없는 오류')
              stopPoll()
              setLoading(false)
              setProgress(null)
            }
          } catch {
            setError('서버 연결 오류. 잠시 후 다시 시도해주세요.')
            stopPoll()
            setLoading(false)
          }
        }, 2000)

      } catch (err) {
        setError(err.message)
        setLoading(false)
      }

    } else {
      // URL 모드: 일반 POST
      try {
        setProgress({ step: 'crawl', msg: '댓글 수집 중...' })
        const res = await fetch(api('/api/youtube/analyze'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, max_count: maxCount, since: since || null, until: until || null }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '오류 발생')
        if (data.sentiment_error) setError(`감성분석 오류: ${data.sentiment_error}`)
        setResult(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
        setProgress(null)
      }
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleAnalyze} className="bg-white rounded-2xl shadow p-6 flex flex-col gap-4">
        <h2 className="text-xl font-bold text-gray-800">YouTube 댓글 감성분석</h2>

        <div className="flex gap-2">
          {[['keyword', '키워드 검색'], ['url', 'URL 직접 입력']].map(([val, label]) => (
            <button key={val} type="button" onClick={() => setMode(val)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition
                ${mode === val ? 'bg-red-500 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
              {label}
            </button>
          ))}
        </div>

        {mode === 'keyword' ? (
          <div className="flex gap-3 flex-wrap">
            <input type="text" value={keyword} onChange={e => setKeyword(e.target.value)}
              placeholder="키워드 입력 (예: 아이폰, 삼성, 먹방)"
              className="flex-1 min-w-0 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              required />
            <select value={maxVideos} onChange={e => setMaxVideos(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
              <option value={5}>영상 5개</option>
              <option value={10}>영상 10개</option>
              <option value={20}>영상 20개</option>
            </select>
            <select value={maxPerVideo} onChange={e => setMaxPerVideo(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
              <option value={20}>영상당 20댓글</option>
              <option value={30}>영상당 30댓글</option>
              <option value={50}>영상당 50댓글</option>
            </select>
          </div>
        ) : (
          <div className="flex gap-3">
            <input type="text" value={url} onChange={e => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=xxxxx"
              className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              required />
            <select value={maxCount} onChange={e => setMaxCount(Number(e.target.value))}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
              <option value={50}>50건</option>
              <option value={100}>100건</option>
              <option value={200}>200건</option>
            </select>
          </div>
        )}

        <div className="flex gap-3 items-center flex-wrap">
          <span className="text-sm text-gray-500 shrink-0">기간</span>
          <input type="date" value={since} max={today} onChange={e => setSince(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400" />
          <span className="text-gray-400 text-sm">~</span>
          <input type="date" value={until} max={today} onChange={e => setUntil(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400" />
          {(since || until) && (
            <button type="button" onClick={() => { setSince(''); setUntil('') }}
              className="text-xs text-gray-400 hover:text-gray-600 underline shrink-0">초기화</button>
          )}
          {loading ? (
            <button type="button" onClick={handleStop}
              className="ml-auto bg-gray-400 hover:bg-gray-500 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm">
              중단
            </button>
          ) : (
            <button type="submit"
              className="ml-auto bg-red-500 hover:bg-red-600 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm">
              분석
            </button>
          )}
        </div>
      </form>

      {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-5 py-4 text-sm">{error}</div>}

      {loading && (
        <div className="bg-white rounded-2xl shadow p-6">
          <div className="flex items-center gap-3 mb-4">
            <svg className="animate-spin h-5 w-5 text-red-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            <span className="text-sm font-medium text-gray-700">
              {progress?.msg || STEP_LABELS[progress?.step] || '분석 시작 중...'}
            </span>
          </div>

          {/* 단계별 진행 바 */}
          <div className="flex gap-1 mb-3">
            {['search', 'crawl', 'analyze', 'keywords'].map((s) => {
              const order = ['search', 'found', 'crawl', 'analyze', 'keywords']
              const current = order.indexOf(progress?.step ?? '')
              const me = order.indexOf(s)
              return (
                <div key={s} className={`h-1.5 flex-1 rounded-full transition-all
                  ${current > me ? 'bg-red-500' : current === me ? 'bg-red-300 animate-pulse' : 'bg-gray-200'}`} />
              )
            })}
          </div>

          {/* 댓글 수집 진행률 */}
          {progress?.step === 'crawl' && progress.total > 0 && (
            <div className="mt-2">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{progress.current}/{progress.total} 영상</span>
                <span>{Math.round(progress.current / progress.total * 100)}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-400 rounded-full transition-all"
                  style={{ width: `${progress.current / progress.total * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          {result.videos?.length > 0 && (
            <div className="bg-white rounded-2xl shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-3">분석한 영상 ({result.videos.length}개)</h3>
              <div className="flex flex-col gap-1">
                {result.videos.map(v => (
                  <a key={v.id} href={v.url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-between text-sm hover:bg-gray-50 rounded-lg px-3 py-2 transition">
                    <span className="text-gray-800 truncate flex-1">{v.title}</span>
                    <span className="text-gray-400 shrink-0 ml-4 text-xs">{v.channel}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-5 items-start">
            <div className="flex-1 flex flex-col gap-5 min-w-0">
              <SentimentChart summary={result.summary} />
              <KeywordChart keywords={result.keywords} selectedKeyword={selectedKeyword} onSelect={setSelectedKeyword} />
            </div>
            {result.summary?.top_accounts?.length > 0 && (
              <div className="w-52 shrink-0">
                <TopAccounts accounts={result.summary.top_accounts} type="youtube" vertical />
              </div>
            )}
          </div>
          <ItemList items={result.items} type="youtube" filterKeyword={selectedKeyword} />
        </>
      )}
    </div>
  )
}

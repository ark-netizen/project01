import { useState, useRef } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import KeywordChart from './KeywordChart'
import ItemList from './ItemList'

const COOLDOWN_SEC = 10

export default function CombinedSearch() {
  const [keyword, setKeyword] = useState('')
  const [count, setCount] = useState(30)
  const [maxPerVideo, setMaxPerVideo] = useState(20)

  const [twLoading, setTwLoading] = useState(false)
  const [ytLoading, setYtLoading] = useState(false)
  const [twResult, setTwResult] = useState(null)
  const [ytResult, setYtResult] = useState(null)
  const [twError, setTwError] = useState('')
  const [ytError, setYtError] = useState('')
  const [ytProgress, setYtProgress] = useState(null)
  const [twReady, setTwReady] = useState(null)

  const [twKeyword, setTwKeyword] = useState(null)
  const [ytKeyword, setYtKeyword] = useState(null)
  const [twSentiment, setTwSentiment] = useState(null)
  const [ytSentiment, setYtSentiment] = useState(null)
  const [cooldown, setCooldown] = useState(0)

  const pollRef = useRef(null)
  const cooldownRef = useRef(null)

  useState(() => {
    fetch(api('/api/twitter/status')).then(r => r.json()).then(d => setTwReady(d.ready)).catch(() => setTwReady(false))
  }, [])

  function stopPoll() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  function startCooldown() {
    setCooldown(COOLDOWN_SEC)
    cooldownRef.current = setInterval(() => {
      setCooldown(prev => { if (prev <= 1) { clearInterval(cooldownRef.current); return 0 } return prev - 1 })
    }, 1000)
  }

  async function handleSearch(e) {
    e.preventDefault()
    if (!keyword.trim() || cooldown > 0) return
    stopPoll()
    setTwResult(null); setYtResult(null)
    setTwError(''); setYtError('')
    setTwKeyword(null); setYtKeyword(null)
    setTwSentiment(null); setYtSentiment(null)
    setYtProgress(null)

    if (twReady) searchTwitter()
    searchYoutube()
    startCooldown()
  }

  async function searchTwitter() {
    setTwLoading(true)
    try {
      const res = await fetch(api(`/api/twitter/search?keyword=${encodeURIComponent(keyword)}&count=${count}`))
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '오류')
      setTwResult(data)
    } catch (e) { setTwError(e.message) }
    finally { setTwLoading(false) }
  }

  async function searchYoutube() {
    setYtLoading(true)
    try {
      const res = await fetch(api(`/api/youtube/analyze-keyword?keyword=${encodeURIComponent(keyword)}&max_videos=5&max_per_video=${maxPerVideo}`), { method: 'POST' })
      const { job_id } = await res.json()
      pollRef.current = setInterval(async () => {
        const jr = await fetch(api(`/api/youtube/job/${job_id}`))
        const job = await jr.json()
        setYtProgress({ step: job.step, msg: job.msg, current: job.current, total: job.total })
        if (job.status === 'done') {
          setYtResult(job.result); stopPoll(); setYtLoading(false); setYtProgress(null)
        } else if (job.status === 'error') {
          setYtError(job.error || '오류'); stopPoll(); setYtLoading(false); setYtProgress(null)
        }
      }, 2000)
    } catch (e) { setYtError(e.message); setYtLoading(false) }
  }

  const canSearch = keyword.trim() && cooldown === 0 && !twLoading && !ytLoading

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSearch} className="bg-white rounded-2xl shadow p-6 flex flex-col gap-4">
        <h2 className="text-xl font-bold text-gray-800">통합 감성분석</h2>
        <div className="flex gap-3 flex-wrap">
          <input type="text" value={keyword} onChange={e => setKeyword(e.target.value)}
            placeholder="키워드 입력 (Twitter + YouTube 동시 검색)"
            className="flex-1 min-w-0 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400" />
          <select value={count} onChange={e => setCount(Number(e.target.value))}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            <option value={10}>트윗 10</option>
            <option value={30}>트윗 30</option>
            <option value={50}>트윗 50</option>
          </select>
          <select value={maxPerVideo} onChange={e => setMaxPerVideo(Number(e.target.value))}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            <option value={20}>영상당 댓글 20</option>
            <option value={30}>영상당 댓글 30</option>
          </select>
          <button type="submit" disabled={!canSearch}
            className="bg-purple-500 hover:bg-purple-600 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm min-w-[90px]">
            {cooldown > 0 ? `${cooldown}초 대기` : (twLoading || ytLoading) ? '분석 중...' : '통합 분석'}
          </button>
        </div>
        {!twReady && <p className="text-xs text-amber-500">⚠ Twitter 서비스 미설정 — YouTube만 분석됩니다</p>}
      </form>

      <div className="grid grid-cols-2 gap-5">
        {/* Twitter 패널 */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-blue-600">𝕏 Twitter</span>
            {twLoading && <span className="text-xs text-gray-400 animate-pulse">분석 중...</span>}
          </div>
          {twError && <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-4 py-3 text-xs">{twError}</div>}
          {twResult && <>
            <SentimentChart summary={twResult.summary} selectedSentiment={twSentiment} onSelect={setTwSentiment} />
            <KeywordChart keywords={twResult.keywords} selectedKeyword={twKeyword} onSelect={setTwKeyword} />
            <ItemList items={twResult.items} type="twitter" filterKeyword={twKeyword} filterSentiment={twSentiment} />
          </>}
          {!twResult && !twLoading && !twError && (
            <div className="bg-white rounded-2xl shadow p-6 text-center text-gray-300 text-sm">Twitter 결과</div>
          )}
        </div>

        {/* YouTube 패널 */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-red-500">▶ YouTube</span>
            {ytLoading && <span className="text-xs text-gray-400 animate-pulse">{ytProgress?.msg || '분석 중...'}</span>}
          </div>
          {ytError && <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-4 py-3 text-xs">{ytError}</div>}
          {ytResult && <>
            <SentimentChart summary={ytResult.summary} selectedSentiment={ytSentiment} onSelect={setYtSentiment} />
            <KeywordChart keywords={ytResult.keywords} selectedKeyword={ytKeyword} onSelect={setYtKeyword} />
            <ItemList items={ytResult.items} type="youtube" filterKeyword={ytKeyword} filterSentiment={ytSentiment} />
          </>}
          {!ytResult && !ytLoading && !ytError && (
            <div className="bg-white rounded-2xl shadow p-6 text-center text-gray-300 text-sm">YouTube 결과</div>
          )}
        </div>
      </div>
    </div>
  )
}

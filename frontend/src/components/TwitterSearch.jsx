import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import TopAccounts from './TopAccounts'
import KeywordChart from './KeywordChart'
import ItemList from './ItemList'

const COOLDOWN_SEC = 10

export default function TwitterSearch() {
  const [ready, setReady] = useState(null) // null=확인중, true=준비됨, false=미설정
  const [keyword, setKeyword] = useState('')
  const [count, setCount] = useState(30)
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState('')
  const [loadingStepIdx, setLoadingStepIdx] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [selectedKeyword, setSelectedKeyword] = useState(null)
  const [cooldown, setCooldown] = useState(0)
  const cooldownRef = useRef(null)
  const today = new Date().toISOString().split('T')[0]

  useEffect(() => {
    fetch(api('/api/twitter/status'))
      .then(r => r.json())
      .then(d => setReady(d.ready))
      .catch(() => setReady(false))
  }, [])

  function startCooldown() {
    setCooldown(COOLDOWN_SEC)
    cooldownRef.current = setInterval(() => {
      setCooldown(prev => {
        if (prev <= 1) {
          clearInterval(cooldownRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  useEffect(() => () => clearInterval(cooldownRef.current), [])

  async function handleSearch(e) {
    e.preventDefault()
    if (!keyword.trim() || loading || cooldown > 0) return
    setLoading(true)
    setError('')
    setResult(null)
    setSelectedKeyword(null)

    const steps = ['트윗 수집 중...', '감성 분석 중...', '키워드 추출 중...']
    let idx = 0
    setLoadingStep(steps[0])
    setLoadingStepIdx(0)
    const timer = setInterval(() => {
      idx = Math.min(idx + 1, steps.length - 1)
      setLoadingStep(steps[idx])
      setLoadingStepIdx(idx)
    }, 4000)

    try {
      const params = new URLSearchParams({
        keyword, count,
        ...(since && { since }),
        ...(until && { until }),
      })
      const res = await fetch(api(`/api/twitter/search?${params}`))
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '오류 발생')
      if (data.sentiment_error) setError(`감성분석 오류: ${data.sentiment_error}`)
      setResult(data)
      startCooldown()
    } catch (err) {
      setError(err.message)
    } finally {
      clearInterval(timer)
      setLoading(false)
    }
  }

  if (ready === null) {
    return (
      <div className="bg-white rounded-2xl shadow p-8 flex items-center justify-center text-gray-400 text-sm gap-3">
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Twitter 서비스 확인 중...
      </div>
    )
  }

  if (ready === false) {
    return (
      <div className="bg-white rounded-2xl shadow p-8 max-w-md mx-auto text-center">
        <div className="text-4xl mb-4">🔧</div>
        <h2 className="text-lg font-bold text-gray-700 mb-2">Twitter 서비스 준비 중</h2>
        <p className="text-sm text-gray-400">
          서버에 Twitter 인증 정보가 설정되지 않았습니다.<br />
          Render 환경변수에 <code className="bg-gray-100 px-1 rounded">TWITTER_AUTH_TOKEN</code>과{' '}
          <code className="bg-gray-100 px-1 rounded">TWITTER_CT0</code>를 등록해주세요.
        </p>
      </div>
    )
  }

  const canSearch = !loading && cooldown === 0 && keyword.trim().length > 0

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSearch} className="bg-white rounded-2xl shadow p-6 flex flex-col gap-4">
        <h2 className="text-xl font-bold text-gray-800">Twitter 키워드 감성분석</h2>

        <div className="flex gap-3">
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="키워드 입력 (예: 삼성전자, AI, ChatGPT)"
            className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <select
            value={count}
            onChange={e => setCount(Number(e.target.value))}
            className="border border-gray-200 rounded-xl px-3 py-3 text-sm focus:outline-none"
          >
            <option value={10}>10건</option>
            <option value={30}>30건</option>
            <option value={50}>50건</option>
          </select>
        </div>

        <div className="flex gap-3 items-center">
          <span className="text-sm text-gray-500 shrink-0">기간</span>
          <input
            type="date"
            value={since}
            max={today}
            onChange={e => setSince(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <span className="text-gray-400 text-sm">~</span>
          <input
            type="date"
            value={until}
            max={today}
            onChange={e => setUntil(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          {(since || until) && (
            <button type="button" onClick={() => { setSince(''); setUntil('') }}
              className="text-xs text-gray-400 hover:text-gray-600 underline shrink-0">
              초기화
            </button>
          )}
          <button
            type="submit"
            disabled={!canSearch}
            className="ml-auto bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm min-w-[90px]"
          >
            {loading ? '분석 중...' : cooldown > 0 ? `${cooldown}초 대기` : '분석'}
          </button>
        </div>

        {cooldown > 0 && !loading && (
          <p className="text-xs text-gray-400 text-right -mt-2">연속 검색 방지: {cooldown}초 후 재검색 가능</p>
        )}
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-5 py-4 text-sm">{error}</div>
      )}
      {loading && (
        <div className="bg-white rounded-2xl shadow p-6">
          <div className="flex items-center gap-3 mb-4">
            <svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            <span className="text-sm font-medium text-gray-700">{loadingStep}</span>
          </div>
          <div className="flex gap-1">
            {['트윗 수집', '감성 분석', '키워드 추출'].map((s, i) => (
              <div key={s} className={`h-1.5 flex-1 rounded-full transition-all duration-500
                ${loadingStepIdx > i ? 'bg-blue-500' : loadingStepIdx === i ? 'bg-blue-300 animate-pulse' : 'bg-gray-200'}`} />
            ))}
          </div>
        </div>
      )}
      {result && (
        <>
          <SentimentChart summary={result.summary} />
          <KeywordChart keywords={result.keywords} selectedKeyword={selectedKeyword} onSelect={setSelectedKeyword} />
          <TopAccounts accounts={result.summary.top_accounts} type="twitter" />
          <ItemList items={result.items} type="twitter" filterKeyword={selectedKeyword} />
        </>
      )}
    </div>
  )
}

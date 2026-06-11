import { useState, useEffect } from 'react'
import { api } from '../api'
import SentimentChart from './SentimentChart'
import TopAccounts from './TopAccounts'
import ItemList from './ItemList'

export default function TwitterSearch() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [loginForm, setLoginForm] = useState({ username: '', email: '', password: '' })
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')

  const [keyword, setKeyword] = useState('')
  const [count, setCount] = useState(50)
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(api('/api/twitter/status'))
      .then(r => r.json())
      .then(d => setLoggedIn(d.logged_in))
      .catch(() => {})
  }, [])

  async function handleLogin(e) {
    e.preventDefault()
    setLoginLoading(true)
    setLoginError('')
    try {
      const res = await fetch(api('/api/twitter/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '로그인 실패')
      setLoggedIn(true)
      setLoginForm({ username: '', email: '', password: '' })
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleLogout() {
    await fetch(api('/api/twitter/logout'), { method: 'POST' })
    setLoggedIn(false)
    setResult(null)
  }

  async function handleSearch(e) {
    e.preventDefault()
    if (!keyword.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const params = new URLSearchParams({
        keyword,
        count,
        ...(since && { since }),
        ...(until && { until }),
      })
      const res = await fetch(api(`/api/twitter/search?${params}`))
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '오류 발생')
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!loggedIn) {
    return (
      <div className="bg-white rounded-2xl shadow p-8 max-w-md mx-auto">
        <h2 className="text-xl font-bold text-gray-800 mb-1">Twitter 로그인</h2>
        <p className="text-sm text-gray-400 mb-6">
          입력한 정보는 서버 메모리에만 유지되며 저장되지 않습니다.
        </p>
        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <input
            type="text"
            placeholder="Twitter 사용자명 (@없이)"
            value={loginForm.username}
            onChange={e => setLoginForm(f => ({ ...f, username: e.target.value }))}
            className="border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            required
          />
          <input
            type="email"
            placeholder="이메일"
            value={loginForm.email}
            onChange={e => setLoginForm(f => ({ ...f, email: e.target.value }))}
            className="border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            required
          />
          <input
            type="password"
            placeholder="비밀번호"
            value={loginForm.password}
            onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
            className="border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            required
          />
          {loginError && <p className="text-red-500 text-sm">{loginError}</p>}
          <button
            type="submit"
            disabled={loginLoading}
            className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition text-sm"
          >
            {loginLoading ? '로그인 중...' : '로그인'}
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSearch} className="bg-white rounded-2xl shadow p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">Twitter 키워드 감성분석</h2>
          <button type="button" onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600 underline">
            로그아웃
          </button>
        </div>

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
            <option value={100}>100건</option>
          </select>
        </div>

        {/* 날짜 범위 */}
        <div className="flex gap-3 items-center">
          <span className="text-sm text-gray-500 shrink-0">기간</span>
          <input
            type="date"
            value={since}
            onChange={e => setSince(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <span className="text-gray-400 text-sm">~</span>
          <input
            type="date"
            value={until}
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
            disabled={loading}
            className="ml-auto bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-xl transition text-sm"
          >
            {loading ? '분석 중...' : '분석'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-5 py-4 text-sm">{error}</div>
      )}
      {loading && (
        <div className="text-center py-12 text-gray-400 text-sm">트윗 크롤링 및 감성분석 중입니다...</div>
      )}
      {result && (
        <>
          <SentimentChart summary={result.summary} />
          <TopAccounts accounts={result.summary.top_accounts} type="twitter" />
          <ItemList items={result.items} type="twitter" />
        </>
      )}
    </div>
  )
}

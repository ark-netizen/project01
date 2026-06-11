import { useState } from 'react'
import TwitterSearch from './components/TwitterSearch'
import YoutubeSearch from './components/YoutubeSearch'
import CombinedSearch from './components/CombinedSearch'

const TABS = [
  { id: 'twitter', label: 'Twitter', icon: '𝕏', color: 'blue' },
  { id: 'youtube', label: 'YouTube', icon: '▶', color: 'red' },
  { id: 'combined', label: '통합검색', icon: '⚡', color: 'purple' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('twitter')

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-5">
          <h1 className="text-2xl font-bold text-gray-900">감성 분석 대시보드</h1>
          <p className="text-sm text-gray-500 mt-1">Twitter 키워드 · YouTube 댓글 실시간 감성분석</p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex gap-2 mb-8">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition
                ${activeTab === tab.id
                  ? tab.color === 'blue' ? 'bg-blue-500 text-white shadow'
                    : tab.color === 'red' ? 'bg-red-500 text-white shadow'
                    : 'bg-purple-500 text-white shadow'
                  : 'bg-white text-gray-500 border border-gray-200 hover:bg-gray-50'
                }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'twitter' && <TwitterSearch />}
        {activeTab === 'youtube' && <YoutubeSearch />}
        {activeTab === 'combined' && <CombinedSearch />}
      </main>
    </div>
  )
}

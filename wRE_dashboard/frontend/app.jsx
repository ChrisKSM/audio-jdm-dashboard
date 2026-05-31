const { useState, useEffect, useCallback, useMemo } = React

function apiUrl(path) {
  const normalized = path.replace(/^\//, '')
  const base =
    window.__BASE_PATH__ ||
    (window.location.pathname.endsWith('/')
      ? window.location.pathname
      : window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1))
  return base + normalized
}

const LG_RED = '#A50034'

const STATUS_COLORS = {
  default: 'bg-slate-100 text-slate-700 border-slate-200',
  progress: 'bg-blue-50 text-blue-700 border-blue-200',
  done: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  warn: 'bg-amber-50 text-amber-700 border-amber-200',
}

function statusBadgeClass(status) {
  const s = (status || '').toLowerCase()
  if (s.includes('closed') || s.includes('delivered') || s.includes('done')) return STATUS_COLORS.done
  if (s.includes('progress') || s.includes('develop') || s.includes('review')) return STATUS_COLORS.progress
  if (s.includes('draft') || s.includes('open')) return STATUS_COLORS.warn
  return STATUS_COLORS.default
}

function SectionCard({ title, subtitle, children, action }) {
  return (
    <section className="bg-white border border-surface-border rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-surface-border">
        <div>
          <h2 className="text-sm font-bold text-gray-900">{title}</h2>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5 font-medium">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function ProgressBar({ progress, label }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-gray-600 font-medium">
        <span>{label}</span>
        <span>{progress}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${progress}%`, backgroundColor: LG_RED }}
        />
      </div>
    </div>
  )
}

function InitiativeCard({ initiative, expanded, onToggle }) {
  const epicCount = initiative.epics?.length || 0
  const storyCount = (initiative.epics || []).reduce((sum, e) => sum + (e.stories?.length || 0), 0)

  return (
    <div className="border border-surface-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-4 py-3 hover:bg-surface-page transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <a
                href={initiative.url}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-xs font-bold text-lg-red hover:underline"
              >
                {initiative.key}
              </a>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${statusBadgeClass(initiative.status)}`}>
                {initiative.status}
              </span>
              {initiative.status_color && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 font-semibold">
                  {initiative.status_color}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-800 font-medium mt-1 truncate">{initiative.summary}</p>
            <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-500 font-medium">
              {initiative.duedate && <span>Due: {initiative.duedate}</span>}
              {epicCount > 0 && <span>Epic {epicCount}</span>}
              {storyCount > 0 && <span>Story {storyCount}</span>}
            </div>
          </div>
          <span className="text-gray-400 text-xs shrink-0">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && initiative.epics?.length > 0 && (
        <div className="border-t border-surface-border bg-surface-page px-4 py-3 space-y-3">
          {initiative.epics.map((epic) => (
            <div key={epic.key} className="bg-white border border-surface-border rounded-lg p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <a href={epic.url} target="_blank" rel="noreferrer" className="text-xs font-bold text-blue-700 hover:underline">
                  {epic.key}
                </a>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${statusBadgeClass(epic.status)}`}>
                  {epic.status}
                </span>
              </div>
              <p className="text-xs text-gray-700 mt-1 font-medium">{epic.summary}</p>
              {epic.stories?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {epic.stories.map((story) => (
                    <div key={story.key} className="flex items-center gap-2 text-[11px] text-gray-600">
                      <a href={story.url} target="_blank" rel="noreferrer" className="font-bold text-gray-800 hover:text-lg-red">
                        {story.key}
                      </a>
                      <span className="truncate flex-1">{story.summary}</span>
                      {story.planned_sp != null && <span className="shrink-0">{story.planned_sp} SP</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PersonPanel({ person, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const [expandedKeys, setExpandedKeys] = useState({})
  const count = person.initiatives?.length || 0

  const toggleInit = (key) => {
    setExpandedKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <SectionCard
      title={`${person.display_name} (${person.name})`}
      subtitle={`Initiative ${count}건`}
      action={
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-xs font-semibold text-gray-600 hover:text-gray-900 px-2 py-1 rounded border border-surface-border"
        >
          {open ? '접기' : '펼치기'}
        </button>
      }
    >
      {open ? (
        count === 0 ? (
          <p className="text-sm text-gray-500">표시할 Initiative가 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {person.initiatives.map((init) => (
              <InitiativeCard
                key={init.key}
                initiative={init}
                expanded={!!expandedKeys[init.key]}
                onToggle={() => toggleInit(init.key)}
              />
            ))}
          </div>
        )
      ) : (
        <p className="text-xs text-gray-500">Initiative {count}건 — 펼치기를 눌러 확인하세요.</p>
      )}
    </SectionCard>
  )
}

function Sidebar({ open, onToggle, parts, selectedMembers, onToggleMember, onSelectAll, onClearAll }) {
  return (
    <>
      {open && <div className="fixed inset-0 bg-black/30 z-20 lg:hidden" onClick={onToggle} />}
      <aside
        className={`fixed top-0 left-0 h-full z-30 flex flex-col bg-white border-r border-surface-border transition-all duration-200 ${
          open ? 'w-64' : 'w-16'
        }`}
      >
        <div className="flex items-center gap-3 px-4 h-16 border-b border-surface-border shrink-0">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0" style={{ backgroundColor: LG_RED }}>
            <span className="text-white text-xs font-bold">JDM</span>
          </div>
          {open && (
            <div className="min-w-0">
              <span className="font-bold text-gray-900 text-sm whitespace-nowrap block">Audio JDM</span>
              <span className="text-[10px] text-gray-500 font-medium">모델 현황</span>
            </div>
          )}
          <button onClick={onToggle} className="ml-auto text-gray-400 hover:text-gray-700" aria-label="사이드바 토글">
            {open ? '✕' : '☰'}
          </button>
        </div>

        {open && (
          <div className="px-3 pt-4 pb-2 shrink-0">
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2 px-1">Part</p>
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-page border border-surface-border">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: LG_RED }} />
              <span className="text-sm text-gray-700 font-medium truncate">오디오SW PO 파트</span>
            </div>
          </div>
        )}

        <nav className="flex-1 px-3 pt-2 overflow-y-auto">
          {open && (
            <div className="flex items-center justify-between mb-2 px-1">
              <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">구성원</p>
              <div className="flex gap-1">
                <button type="button" onClick={onSelectAll} className="text-[10px] text-lg-red font-semibold">전체</button>
                <span className="text-gray-300">|</span>
                <button type="button" onClick={onClearAll} className="text-[10px] text-gray-500 font-semibold">해제</button>
              </div>
            </div>
          )}

          {(parts[0]?.members || []).map((member) => {
            const active = selectedMembers.has(member.id)
            return (
              <button
                key={member.id}
                type="button"
                onClick={() => onToggleMember(member.id)}
                title={`${member.name} (${member.id})`}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors border-l-[3px] mb-1 ${
                  active
                    ? 'bg-lg-red-light text-gray-900 border-lg-red'
                    : 'text-gray-600 hover:bg-surface-page border-transparent'
                }`}
              >
                <span
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                    active ? 'text-white' : 'bg-gray-100 text-gray-600'
                  }`}
                  style={active ? { backgroundColor: LG_RED } : undefined}
                >
                  {member.name.slice(0, 1)}
                </span>
                {open && (
                  <span className="truncate text-left">
                    {member.name}
                    <span className="block text-[10px] text-gray-400 font-medium">{member.id}</span>
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </aside>
    </>
  )
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [parts, setParts] = useState([])
  const [selectedMembers, setSelectedMembers] = useState(new Set())
  const [quickMode, setQuickMode] = useState(true)
  const [source, setSource] = useState('jira')
  const [fetching, setFetching] = useState(false)
  const [progress, setProgress] = useState(0)
  const [taskLabel, setTaskLabel] = useState('')
  const [error, setError] = useState('')
  const [dashboard, setDashboard] = useState(null)
  const [syncInfo, setSyncInfo] = useState(null)
  const [filterMember, setFilterMember] = useState('all')

  useEffect(() => {
    fetch(apiUrl('api/team-members'))
      .then((r) => r.json())
      .then((data) => {
        setParts(data)
        const allIds = data.flatMap((p) => p.members.map((m) => m.id))
        setSelectedMembers(new Set(allIds))
      })
      .catch((e) => setError(String(e)))

    fetch(apiUrl('api/sync-info'))
      .then((r) => r.json())
      .then(setSyncInfo)
      .catch(() => {})
  }, [])

  const selectedList = useMemo(() => Array.from(selectedMembers), [selectedMembers])

  const toggleMember = (id) => {
    setSelectedMembers((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const pollStatus = useCallback(async () => {
    const statusRes = await fetch(apiUrl('api/fetch-status'))
    const status = await statusRes.json()
    setProgress(status.progress || 0)
    setTaskLabel(status.current_task || '')

    if (status.running) {
      setTimeout(pollStatus, 800)
      return
    }

    setFetching(false)
    if (status.error) {
      setError(status.error)
      return
    }

    const dataRes = await fetch(apiUrl('api/dashboard-data'))
    if (!dataRes.ok) {
      setError(await dataRes.text())
      return
    }
    setDashboard(await dataRes.json())
    setError('')
  }, [])

  const startSearch = async () => {
    if (selectedList.length === 0) {
      setError('최소 1명의 구성원을 선택하세요.')
      return
    }
    setFetching(true)
    setError('')
    setDashboard(null)
    setProgress(0)
    setTaskLabel('시작...')

    const res = await fetch(apiUrl('api/fetch-data'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ members: selectedList, source, quick: quickMode }),
    })
    if (!res.ok) {
      setFetching(false)
      setError((await res.json()).detail || '검색 시작 실패')
      return
    }
    pollStatus()
  }

  const cancelSearch = async () => {
    await fetch(apiUrl('api/cancel-search'), { method: 'POST' })
  }

  const filteredPersons = useMemo(() => {
    if (!dashboard?.persons) return []
    if (filterMember === 'all') return dashboard.persons
    return dashboard.persons.filter((p) => p.name === filterMember)
  }, [dashboard, filterMember])

  const totalInitiatives = useMemo(
    () => (dashboard?.persons || []).reduce((sum, p) => sum + (p.initiatives?.length || 0), 0),
    [dashboard]
  )

  return (
    <div className="min-h-screen bg-surface-page text-gray-900">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        parts={parts}
        selectedMembers={selectedMembers}
        onToggleMember={toggleMember}
        onSelectAll={() => setSelectedMembers(new Set(parts.flatMap((p) => p.members.map((m) => m.id))))}
        onClearAll={() => setSelectedMembers(new Set())}
      />

      <main className={`transition-all duration-200 min-h-screen ${sidebarOpen ? 'ml-64' : 'ml-16'}`}>
        <header
          className={`fixed top-0 right-0 z-10 flex items-center justify-between h-16 px-6 bg-white/95 backdrop-blur border-b border-surface-border transition-all duration-200 ${
            sidebarOpen ? 'left-64' : 'left-16'
          }`}
        >
          <div>
            <h1 className="text-gray-900 font-bold text-base leading-tight">Audio JDM 모델 현황 대시보드</h1>
            <p className="text-gray-500 text-xs mt-0.5 font-medium">파트원별 Initiative 현황 — TVPLAT 프로젝트</p>
          </div>
          <div className="flex items-center gap-2">
            {syncInfo?.full_sync && (
              <span className="text-[10px] text-gray-500 hidden md:block">
                Mongo 동기화: {syncInfo.full_sync}
              </span>
            )}
            <button
              type="button"
              onClick={startSearch}
              disabled={fetching}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white disabled:opacity-60"
              style={{ backgroundColor: LG_RED }}
            >
              {fetching ? '검색 중...' : 'Initiative 검색'}
            </button>
          </div>
        </header>

        <div className="pt-16 p-6 space-y-5 max-w-7xl">
          <SectionCard
            title="검색 옵션"
            subtitle="선택한 구성원의 Initiative를 Jira 또는 MongoDB 캐시에서 조회합니다."
          >
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700 font-medium">
                <input type="radio" checked={source === 'jira'} onChange={() => setSource('jira')} />
                Jira 실시간
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 font-medium">
                <input type="radio" checked={source === 'mongodb'} onChange={() => setSource('mongodb')} />
                MongoDB 캐시
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 font-medium">
                <input type="checkbox" checked={quickMode} onChange={(e) => setQuickMode(e.target.checked)} />
                빠른 검색 (Initiative만, Epic/Story 생략)
              </label>
              <span className="text-xs text-gray-500 font-medium">선택 {selectedList.length}명</span>
              {fetching && (
                <button type="button" onClick={cancelSearch} className="text-xs text-gray-600 underline">
                  취소
                </button>
              )}
            </div>
            {fetching && <div className="mt-4"><ProgressBar progress={progress} label={taskLabel} /></div>}
            {error && <p className="mt-3 text-sm text-red-600 font-medium">{error}</p>}
          </SectionCard>

          {dashboard && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-white border border-surface-border rounded-xl p-4">
                  <p className="text-xs text-gray-500 font-semibold uppercase">구성원</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1">{dashboard.persons.length}</p>
                </div>
                <div className="bg-white border border-surface-border rounded-xl p-4">
                  <p className="text-xs text-gray-500 font-semibold uppercase">Initiative</p>
                  <p className="text-2xl font-bold mt-1" style={{ color: LG_RED }}>{totalInitiatives}</p>
                </div>
                <div className="bg-white border border-surface-border rounded-xl p-4">
                  <p className="text-xs text-gray-500 font-semibold uppercase">필터</p>
                  <select
                    className="mt-2 w-full text-sm border border-surface-border rounded-lg px-3 py-2 bg-white"
                    value={filterMember}
                    onChange={(e) => setFilterMember(e.target.value)}
                  >
                    <option value="all">전체 구성원</option>
                    {dashboard.persons.map((p) => (
                      <option key={p.name} value={p.name}>{p.display_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                {filteredPersons.map((person, idx) => (
                  <PersonPanel key={person.name} person={person} defaultOpen={idx < 3 || filterMember !== 'all'} />
                ))}
              </div>
            </>
          )}

          {!dashboard && !fetching && !error && (
            <div className="text-center py-16 text-gray-500">
              <p className="text-sm font-medium">왼쪽에서 구성원을 선택하고 Initiative 검색을 실행하세요.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

const root = ReactDOM.createRoot(document.getElementById('root'))
root.render(<App />)

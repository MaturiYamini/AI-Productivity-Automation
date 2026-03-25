import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API = 'http://127.0.0.1:5000/api'

const priorityBadge = {
  High: 'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300',
  Medium: 'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300',
  Low: 'bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-300',
}

const notifIcon = { reminder: '⏰', 'due-soon': '🔔', overdue: '🚨' }

function fmtDate(v) {
  if (!v) return 'No deadline'
  return new Date(v).toLocaleString()
}

function fmtAgo(v) {
  const diff = Math.floor((Date.now() - new Date(v)) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function NavBtn({ id, active, onClick, children, badge }) {
  return (
    <button
      onClick={() => onClick(id)}
      className={`relative rounded-lg px-4 py-2 text-sm font-medium ${
        active === id
          ? 'bg-indigo-600 text-white'
          : 'border border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800'
      }`}
    >
      {children}
      {badge > 0 && (
        <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </button>
  )
}

function TaskCard({ task, onComplete, onCalendar, onSetDeadline }) {
  const overdue = task.time_remaining === 'Overdue'
  const [showDL, setShowDL] = useState(false)
  const [dlInput, setDlInput] = useState('')
  return (
    <div className={`rounded-xl border p-3 ${
      task.priority === 'High' || overdue
        ? 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20'
        : 'border-slate-200 dark:border-slate-700'
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">{task.title}</p>
        <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${priorityBadge[task.priority]}`}>
          {task.priority}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Deadline: {fmtDate(task.deadline)}</p>
      <p className={`text-xs font-medium ${overdue ? 'text-red-600' : 'text-slate-500 dark:text-slate-400'}`}>
        {task.time_remaining}
      </p>
      {!task.deadline && onSetDeadline && (
        <div className="mt-2">
          {!showDL
            ? <button onClick={() => setShowDL(true)} className="rounded-lg border border-amber-400 bg-amber-50 px-3 py-1 text-xs text-amber-700 hover:bg-amber-100">⚠ Set Deadline</button>
            : <div className="flex gap-1">
                <input type="datetime-local" value={dlInput} onChange={e => setDlInput(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800" />
                <button onClick={() => { onSetDeadline(task.id, dlInput); setShowDL(false) }} disabled={!dlInput}
                  className="rounded-lg bg-indigo-600 px-2 py-1 text-xs text-white disabled:opacity-50">Save</button>
                <button onClick={() => setShowDL(false)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs">✕</button>
              </div>
          }
        </div>
      )}
      {onComplete && (
        <div className="mt-2 flex gap-2">
          <button onClick={() => onComplete(task.id)}
            className="rounded-lg border border-slate-300 px-3 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800">
            Mark Completed
          </button>
          {onCalendar && (
            <button onClick={() => onCalendar(task.id)}
              className="rounded-lg bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700">
              Add to Calendar
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function GmailEmailRow({ em, onSetDeadline, tasks }) {
  const [expanded, setExpanded] = useState(false)
  const [dlInput, setDlInput] = useState('')
  const [selectedTask, setSelectedTask] = useState('')
  const [saved, setSaved] = useState(false)

  // Tasks that came from this email's subject (rough match)
  const relatedTasks = tasks.filter(t =>
    t.status === 'pending' && em.tasks_added > 0 &&
    t.title && em.subject && t.title.toLowerCase().includes(em.subject.toLowerCase().slice(0, 20))
  )

  async function scheduleTask() {
    if (!selectedTask || !dlInput) return
    await onSetDeadline(parseInt(selectedTask), dlInput)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="rounded-xl border border-red-100 bg-red-50/50 p-3 dark:border-red-900/30 dark:bg-red-900/10">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold truncate">{em.subject}</p>
          <p className="text-xs text-slate-500 truncate">{em.sender}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {em.tasks_added > 0 && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
              +{em.tasks_added} task{em.tasks_added > 1 ? 's' : ''}
            </span>
          )}
          <span className="text-xs text-slate-400">{fmtAgo(em.received_at)}</span>
          <button onClick={() => setExpanded(p => !p)}
            className="text-xs text-red-500 hover:underline">
            {expanded ? 'Hide' : 'View'}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 space-y-2">
          {em.snippet && (
            <p className="rounded-lg bg-white/80 p-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {em.snippet}
            </p>
          )}

          {/* Inline task scheduler */}
          <div className="rounded-lg border border-red-200 bg-white p-2 dark:border-red-800 dark:bg-slate-900">
            <p className="mb-1.5 text-xs font-semibold text-red-600">📅 Schedule a Task from this Email</p>
            <div className="flex flex-wrap gap-2">
              <select value={selectedTask} onChange={e => setSelectedTask(e.target.value)}
                className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800">
                <option value="">Select task…</option>
                {tasks.filter(t => t.status === 'pending').map(t => (
                  <option key={t.id} value={t.id}>{t.title.slice(0, 60)}</option>
                ))}
              </select>
              <input type="datetime-local" value={dlInput} onChange={e => setDlInput(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800" />
              <button onClick={scheduleTask} disabled={!selectedTask || !dlInput}
                className="rounded-lg bg-red-500 px-3 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-40">
                {saved ? '✓ Saved' : 'Set Deadline'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState('home')
  const [dark, setDark] = useState(false)
  const [inputText, setInputText] = useState('')
  const [summary, setSummary] = useState(null)
  const [tasks, setTasks] = useState([])
  const [todayTasks, setTodayTasks] = useState([])
  const [notifications, setNotifications] = useState([])
  const [unseenCount, setUnseenCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [listening, setListening] = useState(false)
  const [gmailStatus, setGmailStatus] = useState(null)
  const [gmailSyncing, setGmailSyncing] = useState(false)
  const [gmailEmails, setGmailEmails] = useState([])
  const [gmailExpanded, setGmailExpanded] = useState(false)
  const prevUnseenRef = useRef(0)

  useEffect(() => { document.documentElement.classList.toggle('dark', dark) }, [dark])

  function playNotifSound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.setValueAtTime(880, ctx.currentTime)
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15)
      gain.gain.setValueAtTime(0.4, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.4)
    } catch (_) {}
  }

  const pendingTasks = useMemo(() => tasks.filter(t => t.status !== 'completed'), [tasks])
  const completedTasks = useMemo(() => tasks.filter(t => t.status === 'completed'), [tasks])
  const urgentCount = useMemo(
    () => tasks.filter(t => t.priority === 'High' || t.time_remaining === 'Overdue').length,
    [tasks]
  )

  const fetchGmailStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/gmail/status`)
      if (res.ok) setGmailStatus(await res.json())
    } catch (_) {}
  }, [])

  const fetchGmailEmails = useCallback(async () => {
    try {
      const res = await fetch(`${API}/gmail/emails`)
      if (res.ok) setGmailEmails(await res.json())
    } catch (_) {}
  }, [])

  const fetchAll = useCallback(async () => {
    try {
      const [tRes, todayRes, countRes] = await Promise.all([
        fetch(`${API}/tasks`),
        fetch(`${API}/today`),
        fetch(`${API}/notifications/unseen-count`),
      ])
      if (tRes.ok) setTasks(await tRes.json())
      if (todayRes.ok) setTodayTasks(await todayRes.json())
      if (countRes.ok) setUnseenCount((await countRes.json()).count)
    } catch (_) {}
  }, [])

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await fetch(`${API}/notifications`)
      if (res.ok) setNotifications(await res.json())
    } catch (_) {}
  }, [])

  const [work, setWork] = useState([])
  const [workTitle, setWorkTitle] = useState('')
  const [workNotes, setWorkNotes] = useState('')
  const [workDeadline, setWorkDeadline] = useState('')
  const [workPriority, setWorkPriority] = useState('Medium')

  const fetchWork = useCallback(async () => {
    try {
      const res = await fetch(`${API}/work`)
      if (res.ok) setWork(await res.json())
    } catch (_) {}
  }, [])

  useEffect(() => {
    fetchAll()
    fetchGmailStatus()
    fetchGmailEmails()
    fetchWork()
    const t1 = setInterval(() => { fetchAll(); fetchWork() }, 30000)
    return () => clearInterval(t1)
  }, [fetchAll, fetchGmailStatus, fetchGmailEmails, fetchWork])

  // Load work items when panel is opened
  useEffect(() => {
    if (page === 'work') fetchWork()
  }, [page, fetchWork])

  async function handleCreateWork(e) {
    e.preventDefault()
    if (!workTitle.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/work`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: workTitle, notes: workNotes,
          deadline: workDeadline, priority: workPriority
        }),
      })
      if (res.ok) {
        setWorkTitle(''); setWorkNotes(''); setWorkDeadline(''); setWorkPriority('Medium')
        await fetchWork()
      }
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function completeWork(id) {
    await fetch(`${API}/work/${id}/complete`, { method: 'PATCH' })
    await fetchWork()
  }

  async function deleteWork(id) {
    await fetch(`${API}/work/${id}`, { method: 'DELETE' })
    await fetchWork()
  }

  // Poll unseen count every 15s for live bell badge + sound
  useEffect(() => {
    const t2 = setInterval(async () => {
      try {
        const res = await fetch(`${API}/notifications/unseen-count`)
        if (res.ok) {
          const { count } = await res.json()
          if (count > prevUnseenRef.current) playNotifSound()
          prevUnseenRef.current = count
          setUnseenCount(count)
        }
      } catch (_) {}
    }, 15000)
    return () => clearInterval(t2)
  }, [])

  // Load notifications when panel is opened
  useEffect(() => {
    if (page === 'notifications') fetchNotifications()
  }, [page, fetchNotifications])

  async function handleProcess() {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText }),
      })
      if (!res.ok) throw new Error('Failed to process input')
      const data = await res.json()
      setSummary(data.summary)
      setTasks(data.tasks)
      await fetchAll()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function onUpload(e) {
    const file = e.target.files?.[0]; if (!file) return
    setLoading(true); setError('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API}/process-file`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to process file')
      setSummary(data.summary); setTasks(data.tasks)
      await fetchAll()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function completeTask(id) {
    await fetch(`${API}/tasks/${id}/complete`, { method: 'PATCH' })
    await fetchAll()
  }

  async function setTaskDeadline(id, deadline) {
    await fetch(`${API}/tasks/${id}/deadline`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deadline }),
    })
    await fetchAll()
  }

  async function addToCalendar(id) {
    try {
      const res = await fetch(`${API}/tasks/${id}/calendar-link`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)
      window.open(data.url, '_blank')
    } catch (e) { setError(e.message) }
  }

  async function markNotifSeen(id) {
    await fetch(`${API}/notifications/${id}/seen`, { method: 'PATCH' })
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, seen: true } : n))
    setUnseenCount(prev => Math.max(0, prev - 1))
  }

  async function markAllSeen() {
    await fetch(`${API}/notifications/mark-all-seen`, { method: 'PATCH' })
    setNotifications(prev => prev.map(n => ({ ...n, seen: true })))
    setUnseenCount(0)
  }

  async function clearSeen() {
    await fetch(`${API}/notifications/clear`, { method: 'DELETE' })
    setNotifications(prev => prev.filter(n => !n.seen))
  }

  const [syncMsg, setSyncMsg] = useState('')

  async function syncGmail() {
    setGmailSyncing(true)
    setError('')
    setSyncMsg('')
    try {
      const res = await fetch(`${API}/gmail/sync`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) { 
        setError(`Sync Error: ${data.error || 'Connection failed'}`)
        return 
      }
      await Promise.all([fetchAll(), fetchGmailStatus(), fetchGmailEmails()])
      setGmailExpanded(true)
      if (data.added > 0) {
        setSyncMsg(`Success! Added ${data.added} new task${data.added > 1 ? 's' : ''}.`)
        setTimeout(() => setSyncMsg(''), 5000)
      } else {
        setSyncMsg('Synced. No new tasks found.')
        setTimeout(() => setSyncMsg(''), 3000)
      }
    } catch (e) { 
      setError(`Sync failed: ${e.message}`)
    } finally { 
      setGmailSyncing(false) 
    }
  }

  function startVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { setError('Voice input not supported in this browser.'); return }
    const r = new SR(); r.lang = 'en-US'; r.interimResults = false
    setListening(true)
    r.onresult = e => setInputText(p => `${p}\n${e.results[0][0].transcript}`.trim())
    r.onerror = () => setError('Voice input failed.')
    r.onend = () => setListening(false)
    r.start()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-7xl space-y-4">

        {/* Header */}
        <header className="flex items-center justify-between rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 p-4 shadow-sm">
          <div className="w-full text-center">
            <h1 className="text-4xl font-bold text-white">AI Productivity Assistant</h1>
            <p className="text-base text-indigo-100">Summarize · Tasks · Reminders · Notifications</p>
          </div>
        </header>

        {/* Nav */}
        <nav className="flex flex-wrap gap-2 rounded-2xl border border-indigo-200 bg-white/80 backdrop-blur p-2 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          {[
            { id: 'home', label: 'AI Summarizer' },
            { id: 'tasks', label: 'Task Dashboard' },
            { id: 'work', label: 'My Work' },
            { id: 'completed', label: 'Completed' },
          ].map(({ id, label }) => (
            <NavBtn key={id} id={id} active={page} onClick={setPage}>{label}</NavBtn>
          ))}
          <NavBtn id="notifications" active={page} onClick={setPage} badge={unseenCount}>
            🔔 Notifications
          </NavBtn>
        </nav>

        {/* ── Home ── */}
        {page === 'home' && (
          <div className="grid gap-4 lg:grid-cols-3">
            {/* Input */}
            <section className="rounded-2xl border border-indigo-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <h2 className="mb-2 text-lg font-semibold">Input</h2>
              <textarea
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                placeholder="Paste lecture notes, emails, assignment messages..."
                className="h-48 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <input type="file" accept="*/*" onChange={onUpload} className="text-sm" />
                <button onClick={startVoice}
                  className="rounded-xl border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800">
                  {listening ? '🎙 Listening…' : '🎙 Voice'}
                </button>
                <button onClick={handleProcess} disabled={loading || !inputText.trim()}
                  className="rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50">
                  {loading ? 'Processing…' : 'Analyze'}
                </button>
              </div>
              {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            </section>

            {/* Summary */}
            <section className="rounded-2xl border border-purple-200 bg-white/90 p-4 shadow-sm lg:col-span-2 dark:border-slate-700 dark:bg-slate-900">
              <h2 className="mb-2 text-lg font-semibold">Summary Output</h2>
              {!summary ? (
                <p className="text-sm text-slate-500">No summary yet. Add text and click Analyze.</p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <p className="font-semibold">Short Summary</p>
                    <p className="text-sm">{summary.short_summary}</p>
                  </div>
                  <div>
                    <p className="font-semibold">Bullet Points</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {summary.bullets?.map((b, i) => <li key={i}>{b}</li>)}
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold">Key Highlights</p>
                    <div className="flex flex-wrap gap-2">
                      {summary.highlights?.map((h, i) => (
                        <span key={i} className="rounded-full bg-indigo-100 px-3 py-1 text-xs text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">{h}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* Today's Schedule */}
            <section className="rounded-2xl border border-pink-200 bg-white/90 p-4 shadow-sm lg:col-span-3 dark:border-slate-700 dark:bg-slate-900">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold">📅 Today's Schedule</h2>
                <span className="text-xs text-slate-500 dark:text-slate-400">Top priority tasks for today</span>
              </div>
              {todayTasks.length === 0 ? (
                <p className="text-sm text-slate-500">No tasks scheduled for today.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {todayTasks.map(task => (
                    <TaskCard key={task.id} task={task} onComplete={completeTask} onCalendar={addToCalendar} onSetDeadline={setTaskDeadline} />
                  ))}
                </div>
              )}
            </section>

            {/* Gmail */}
            <section className="rounded-2xl border border-red-200 bg-white/90 p-4 shadow-sm lg:col-span-3 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">📧</span>
                  <div>
                    <h2 className="text-lg font-semibold text-red-600">Gmail Integration</h2>
                    {gmailStatus?.connected
                      ? <p className="text-xs text-slate-500">Connected: {gmailStatus.email} · Auto-syncs every 5 min</p>
                      : <p className="text-xs text-slate-500">Add GMAIL_USER &amp; GMAIL_APP_PASSWORD to backend/.env</p>
                    }
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {gmailStatus?.connected
                    ? <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">✓ Connected</span>
                    : <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-600">Not configured</span>
                  }
                  {gmailEmails.length > 0 && (
                    <button onClick={() => setGmailExpanded(p => !p)}
                      className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                      {gmailExpanded ? '▲ Hide' : `▼ Show ${gmailEmails.length} emails`}
                    </button>
                  )}
                  <button onClick={syncGmail} disabled={!gmailStatus?.connected || gmailSyncing}
                    className="rounded-lg bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600 disabled:opacity-40">
                    {gmailSyncing ? 'Syncing…' : '🔄 Sync Now'}
                  </button>
                </div>
              </div>
              
              {syncMsg && <p className="mt-2 text-sm font-medium text-green-600 animate-bounce">{syncMsg}</p>}
              {error && error.includes('Sync') && <p className="mt-2 text-sm font-medium text-red-600">{error}</p>}

              {gmailExpanded && gmailEmails.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Fetched Emails</p>
                  {gmailEmails.map(em => (
                    <GmailEmailRow key={em.id} em={em} onSetDeadline={setTaskDeadline} tasks={tasks} />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ── My Work ── */}
        {page === 'work' && (
          <div className="grid gap-4 lg:grid-cols-3">
            <section className="rounded-2xl border border-indigo-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <h2 className="mb-3 text-lg font-semibold text-indigo-700">Add Work Item</h2>
              <form onSubmit={handleCreateWork} className="space-y-3">
                <input type="text" placeholder="Task title..." value={workTitle} onChange={e => setWorkTitle(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 p-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800" />
                <textarea placeholder="Notes (optional)..." value={workNotes} onChange={e => setWorkNotes(e.target.value)}
                  className="h-24 w-full rounded-xl border border-slate-300 p-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800" />
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="text-[10px] uppercase text-slate-500">Deadline</label>
                    <input type="datetime-local" value={workDeadline} onChange={e => setWorkDeadline(e.target.value)}
                      className="w-full rounded border border-slate-300 p-1 text-xs dark:border-slate-600 dark:bg-slate-800" />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase text-slate-500">Priority</label>
                    <select value={workPriority} onChange={e => setWorkPriority(e.target.value)}
                      className="w-full rounded border border-slate-300 p-1 text-xs dark:border-slate-600 dark:bg-slate-800">
                      <option>High</option><option>Medium</option><option>Low</option>
                    </select>
                  </div>
                </div>
                <button type="submit" disabled={loading || !workTitle.trim()}
                  className="w-full rounded-xl bg-indigo-600 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50">
                  {loading ? 'Adding...' : 'Add to List'}
                </button>
              </form>
            </section>

            <section className="rounded-2xl border border-indigo-200 bg-white/90 p-4 shadow-sm lg:col-span-2 dark:border-slate-700 dark:bg-slate-900">
              <h2 className="mb-3 text-lg font-semibold text-indigo-700">Active Items</h2>
              <div className="space-y-2">
                {work.filter(w => w.status !== 'completed').length === 0 ? (
                  <p className="text-sm text-slate-500">No active work items.</p>
                ) : (
                  work.filter(w => w.status !== 'completed').map(w => (
                    <div key={w.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium">{w.title}</p>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${priorityBadge[w.priority]}`}>
                          {w.priority}
                        </span>
                      </div>
                      {w.notes && <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{w.notes}</p>}
                      <div className="mt-2 flex items-center justify-between">
                        <p className="text-[10px] text-slate-400">Deadline: {fmtDate(w.deadline)}</p>
                        <div className="flex gap-2">
                          <button onClick={() => completeWork(w.id)} className="text-xs text-emerald-600 hover:underline">Complete</button>
                          <button onClick={() => deleteWork(w.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        )}
        {page === 'tasks' && (
          <section className="rounded-2xl border border-indigo-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-indigo-700">Task Dashboard</h2>
              <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-300">
                Urgent/Overdue: {urgentCount}
              </span>
            </div>
            <div className="space-y-2">
              {pendingTasks.length === 0 ? (
                <p className="text-sm text-slate-500">No pending tasks.</p>
              ) : (
                pendingTasks.map(task => (
                  <TaskCard key={task.id} task={task} onComplete={completeTask} onCalendar={addToCalendar} onSetDeadline={setTaskDeadline} />
                ))
              )}
            </div>
          </section>
        )}

        {/* ── Completed ── */}
        {page === 'completed' && (
          <section className="rounded-2xl border border-emerald-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="mb-3 text-lg font-semibold text-emerald-700">Completed Tasks</h2>
            <div className="space-y-2">
              {completedTasks.length === 0 ? (
                <p className="text-sm text-slate-500">No completed tasks yet.</p>
              ) : (
                completedTasks.map(task => (
                  <div key={task.id} className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-700 dark:bg-emerald-900/20">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{task.title}</p>
                      <span className="rounded-full border border-emerald-300 bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                        ✓ Done
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">Deadline: {fmtDate(task.deadline)}</p>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        {/* ── Notifications ── */}
        {page === 'notifications' && (
          <section className="rounded-2xl border border-orange-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold text-orange-600">🔔 Notifications</h2>
              <div className="flex gap-2">
                {unseenCount > 0 && (
                  <button onClick={markAllSeen}
                    className="rounded-lg bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-700">
                    Mark all read
                  </button>
                )}
                <button onClick={clearSeen}
                  className="rounded-lg border border-slate-300 px-3 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800">
                  Clear read
                </button>
              </div>
            </div>

            {notifications.length === 0 ? (
              <p className="text-sm text-slate-500">No notifications yet. Reminders will appear here automatically when deadlines approach.</p>
            ) : (
              <div className="space-y-2">
                {notifications.map(n => (
                  <div key={n.id}
                    className={`flex items-start gap-3 rounded-xl border p-3 transition-opacity ${
                      n.seen
                        ? 'border-slate-200 opacity-60 dark:border-slate-700'
                        : n.notif_type === 'overdue'
                          ? 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20'
                          : n.notif_type === 'due-soon'
                            ? 'border-orange-300 bg-orange-50 dark:border-orange-700 dark:bg-orange-900/20'
                            : 'border-indigo-200 bg-indigo-50 dark:border-indigo-700 dark:bg-indigo-900/20'
                    }`}
                  >
                    <span className="mt-0.5 text-lg">{notifIcon[n.notif_type] || '📌'}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold">{n.title}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{n.message}</p>
                      <p className="mt-1 text-xs text-slate-400">{fmtAgo(n.created_at)}</p>
                    </div>
                    {!n.seen && (
                      <button onClick={() => markNotifSeen(n.id)}
                        className="shrink-0 rounded-lg border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800">
                        Dismiss
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

      </div>
    </div>
  )
}

'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { sendChat, listTools, ChatResponse, ToolListResponse } from '@/lib/api'
import { TOOL_ICONS, QUICK_PILLS, EXAMPLE_CHAT_STARTERS, formatToolName, getConfidenceColor, CATEGORY_META } from '@/lib/tools'

// ─── Types ────────────────────────────────────────────────────────────────────
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolUsed?: string
  confidence?: number
  workflowSteps?: string[]
  timestamp: Date
  isTyping?: boolean
}

// ─── Tiny helpers ─────────────────────────────────────────────────────────────
let _id = 0
const uid = () => `msg_${++_id}_${Date.now()}`

function resize(el: HTMLTextAreaElement) {
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function TypingBubble() {
  return (
    <div style={{ background: '#111', border: '1px solid #1e1e1e', borderRadius: '4px 14px 14px 14px', padding: '12px 16px', display: 'inline-block' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {[0, 150, 300].map(d => (
          <span key={d} className="typing-dot" style={{ animationDelay: `${d}ms` }} />
        ))}
      </div>
    </div>
  )
}

function AvatarYo({ size = 30 }: { size?: number }) {
  return (
    <div style={{ width: size, height: size, borderRadius: '50%', flexShrink: 0, padding: 2, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)' }}>
      <div style={{ width: '100%', height: '100%', borderRadius: '50%', background: '#0e0e0e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 900, color: '#fff', letterSpacing: '-0.5px' }}>
        YO
      </div>
    </div>
  )
}

function UserAvatar({ name }: { name: string }) {
  const initials = name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'U'
  return (
    <div style={{ width: 30, height: 30, borderRadius: '50%', flexShrink: 0, background: '#1a2e2b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: '#00c9a7', letterSpacing: '-0.5px' }}>
      {initials}
    </div>
  )
}

function WorkflowBadge({ steps }: { steps: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 8 }}>
      <button onClick={() => setOpen(p => !p)}
        style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#444', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'inherit' }}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polyline points={open ? '18 15 12 9 6 15' : '6 9 12 15 18 9'} />
        </svg>
        {open ? 'Hide' : 'Show'} agent pipeline ({steps.length} steps)
      </button>
      {open && (
        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 3, borderLeft: '2px solid #1e1e1e', paddingLeft: 10 }}>
          {steps.map((s, i) => (
            <p key={i} style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: s.startsWith('✓') ? '#00c9a7' : s.startsWith('✗') ? '#ef4444' : '#f59e0b', lineHeight: 1.4 }}>
              {s}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const NAV = [
  { icon: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z', label: 'Chat', active: true, tag: 'path' },
  { icon: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z', label: 'Tools', active: false, tag: 'path' },
  { icon: '22 12 18 12 15 21 9 3 6 12 2 12', label: 'Progress', active: false, tag: 'poly' },
  { icon: 'M11 11m-8 0a8 8 0 1 0 16 0 8 8 0 1 0-16 0zM21 21l-4.35-4.35', label: 'Search', active: false, tag: 'path' },
  { icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6', label: 'Notes', active: false, tag: 'path' },
  { icon: 'M18 20v-10M12 20v-16M6 20v-6', label: 'Analytics', active: false, tag: 'path' },
  { icon: 'M2 4h20v16H2V4zM2 9h20', label: 'Cards', active: false, tag: 'path' },
]

function Sidebar({ onSignOut, userName }: { onSignOut: () => void; userName: string }) {
  return (
    <aside style={{ width: 54, flexShrink: 0, background: '#0e0e0e', borderRight: '1px solid #1a1a1a', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '14px 0', gap: 4, zIndex: 10 }}>
      {/* Logo mark */}
      <div style={{ width: 34, height: 34, borderRadius: 9, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)', padding: 2, marginBottom: 8, cursor: 'pointer', flexShrink: 0 }}>
        <div style={{ width: '100%', height: '100%', borderRadius: 7, background: '#0e0e0e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 900, color: '#fff' }}>YO</div>
      </div>

      <div style={{ width: 28, height: 1, background: '#1e1e1e', margin: '4px 0' }} />

      {NAV.map((n) => (
        <button key={n.label} title={n.label}
          style={{ width: 38, height: 38, borderRadius: 10, background: n.active ? '#1a2e2b' : 'transparent', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'background 0.15s', flexShrink: 0 }}
          onMouseEnter={e => { if (!n.active) (e.currentTarget as HTMLElement).style.background = '#1a1a1a' }}
          onMouseLeave={e => { if (!n.active) (e.currentTarget as HTMLElement).style.background = 'transparent' }}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={n.active ? '#00c9a7' : '#3a3a3a'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {n.tag === 'poly' ? <polyline points={n.icon} /> : <path d={n.icon} />}
          </svg>
        </button>
      ))}

      {/* Bottom */}
      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
        <div style={{ width: 28, height: 1, background: '#1e1e1e', margin: '4px 0' }} />

        {/* User avatar button */}
        <div title={userName}
          style={{ width: 30, height: 30, borderRadius: '50%', background: '#1a2e2b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#00c9a7', cursor: 'default', letterSpacing: '-0.5px' }}>
          {userName.slice(0, 2).toUpperCase() || 'U'}
        </div>

        {/* Sign out */}
        <button onClick={onSignOut} title="Sign out"
          style={{ width: 38, height: 38, borderRadius: 10, background: 'transparent', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'background 0.15s' }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#1a1a1a' }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3a3a3a" strokeWidth="2" strokeLinecap="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
          </svg>
        </button>
      </div>
    </aside>
  )
}

// ─── Tool panel (right sidebar) ───────────────────────────────────────────────
function ToolPanel({ tools, byCategory, lastWorkflow, lastParams }: {
  tools: ToolListResponse['tools']
  byCategory: Record<string, string[]>
  lastWorkflow: string[]
  lastParams: Record<string, unknown>
}) {
  const [tab, setTab] = useState<'tools' | 'pipeline'>('tools')

  return (
    <aside style={{ width: 240, flexShrink: 0, background: '#0a0a0a', borderLeft: '1px solid #1a1a1a', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1a1a1a', flexShrink: 0 }}>
        {(['tools', 'pipeline'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ flex: 1, height: 40, background: 'none', border: 'none', borderBottom: tab === t ? '2px solid #00c9a7' : '2px solid transparent', color: tab === t ? '#00c9a7' : '#444', fontSize: 12, fontWeight: 500, cursor: 'pointer', textTransform: 'capitalize', fontFamily: 'inherit', transition: 'color 0.15s' }}>
            {t === 'tools' ? '⚙️ Tools' : '⚡ Pipeline'}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 10px' }}>
        {tab === 'tools' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {Object.entries(byCategory).map(([cat, names]) => {
              const meta = CATEGORY_META[cat] || { label: cat, color: '#666' }
              return (
                <div key={cat}>
                  <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: meta.color, marginBottom: 6, paddingLeft: 4 }}>
                    {meta.label}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {names.map(name => (
                      <div key={name}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 8, cursor: 'pointer', transition: 'background 0.15s' }}
                        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#161616' }}
                        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}>
                        <span style={{ fontSize: 14 }}>{TOOL_ICONS[name] || '🔧'}</span>
                        <span style={{ fontSize: 12, color: '#777', lineHeight: 1.3 }}>{formatToolName(name)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {lastWorkflow.length === 0 ? (
              <p style={{ fontSize: 12, color: '#333', textAlign: 'center', marginTop: 24, lineHeight: 1.6 }}>
                Send a message to see the LangGraph pipeline trace here.
              </p>
            ) : (
              <>
                {lastWorkflow.map((s, i) => (
                  <div key={i} style={{ padding: '7px 9px', borderRadius: 8, background: s.startsWith('✓') ? 'rgba(0,201,167,0.05)' : s.startsWith('✗') ? 'rgba(239,68,68,0.05)' : 'rgba(245,158,11,0.05)', border: `1px solid ${s.startsWith('✓') ? 'rgba(0,201,167,0.1)' : s.startsWith('✗') ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)'}` }}>
                    <p style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: s.startsWith('✓') ? '#00c9a7' : s.startsWith('✗') ? '#ef4444' : '#f59e0b', lineHeight: 1.45, wordBreak: 'break-word' }}>{s}</p>
                  </div>
                ))}

                {Object.keys(lastParams).length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <p style={{ fontSize: 10, color: '#444', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Extracted Params</p>
                    <pre style={{ fontSize: 11, background: '#111', border: '1px solid #1e1e1e', borderRadius: 8, padding: '8px 10px', color: '#666', overflowX: 'auto', fontFamily: "'DM Mono', monospace", lineHeight: 1.5 }}>
                      {JSON.stringify(lastParams, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}

// ─── Input box ────────────────────────────────────────────────────────────────
function ChatInput({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const ref = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const val = ref.current?.value?.trim() || ''
    if (!val || disabled) return
    onSend(val)
    if (ref.current) { ref.current.value = ''; ref.current.style.height = 'auto' }
  }

  return (
    <div className="chat-box" style={{ padding: '14px 16px 48px', position: 'relative' }}>
      <textarea
        ref={ref}
        rows={1}
        placeholder="Ask anything..."
        disabled={disabled}
        onInput={e => resize(e.currentTarget as HTMLTextAreaElement)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
        style={{ width: '100%', fontSize: 14, lineHeight: 1.55, resize: 'none', maxHeight: 120, color: '#e8e8e8', background: 'transparent', border: 'none', outline: 'none', fontFamily: 'inherit' }}
      />
      <div style={{ position: 'absolute', bottom: 12, left: 12, right: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button style={{ width: 32, height: 32, borderRadius: '50%', background: 'transparent', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#333' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={{ width: 32, height: 32, borderRadius: '50%', background: 'transparent', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#333' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
          </button>
          <button onClick={submit} disabled={disabled}
            className="btn-teal"
            style={{ width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {disabled
              ? <div style={{ width: 15, height: 15, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.2)', borderTopColor: '#000', animation: 'spin 0.8s linear infinite' }} />
              : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Chat Page ───────────────────────────────────────────────────────────
export default function ChatPage() {
  const router = useRouter()
  const { user, isLoading: authLoading, signOut } = useAuth()

  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [inChat, setInChat] = useState(false)
  const [showMorePills, setShowMorePills] = useState(false)
  const [toolData, setToolData] = useState<ToolListResponse>({ total: 0, tools: [], by_category: {} })
  const [lastWorkflow, setLastWorkflow] = useState<string[]>([])
  const [lastParams, setLastParams] = useState<Record<string, unknown>>({})
  const [sessionId] = useState(() => crypto.randomUUID())
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  
  // Dev-mode Profile Overrides
  const [mockEmotion, setMockEmotion] = useState("neutral")
  const [mockStyle, setMockStyle] = useState("direct")
  const [mockMastery, setMockMastery] = useState<number>(5)
  
  const threadRef = useRef<HTMLDivElement>(null)

  // ── Load tools + check backend ─────────────────────────────────────────────
  useEffect(() => {
    if (authLoading || !user) return
    listTools()
      .then(data => { setToolData(data); setBackendOnline(true) })
      .catch(() => {
        setBackendOnline(false)
        // Mock tool categories for UI even when backend is down
        setToolData({
          total: 20,
          tools: [],
          by_category: {
            learning: ['anchor_chart_maker', 'concept_explainer', 'concept_visualizer', 'mind_map'],
            assessment: ['flashcards', 'mock_test', 'quiz_me', 'step_by_step_solver'],
            memory: ['mnemonic_generator', 'summary_generator', 'quick_compare'],
            communication: ['debate_speech_generator', 'pronunciation_coach', 'rhyme_rap_composer'],
            creative: ['quick_prompts', 'visual_story_builder', 'podcast_maker'],
            structured: ['simulation_generator', 'slide_deck_generator', 'timeline_designer'],
          },
        })
      })
  }, [authLoading, user])

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight
  }, [messages])

  // ── Sign out ───────────────────────────────────────────────────────────────
  const handleSignOut = useCallback(async () => {
    await signOut()
    router.push('/signin')
  }, [signOut, router])

  // ── Send message ───────────────────────────────────────────────────────────
  const doSend = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    if (!inChat) setInChat(true)

    const typingId = uid()
    setMessages(prev => [
      ...prev,
      { id: uid(), role: 'user', content: text, timestamp: new Date() },
      { id: typingId, role: 'assistant', content: '', isTyping: true, timestamp: new Date() },
    ])
    setLoading(true)

    if (!backendOnline) {
      // Offline demo response
      await new Promise(r => setTimeout(r, 1200))
      setMessages(prev => prev.map(m => m.id === typingId ? {
        ...m, isTyping: false,
        content: `⚠️ Backend is offline.\n\nStart it with:\n\ncd backend\nuvicorn app.main:app --reload --port 8000\n\nThen refresh this page.`,
      } : m))
      setLoading(false)
      return
    }

    try {
      // JWT is automatically attached by the api client
      const res: ChatResponse = await sendChat({
        message: text,
        session_id: sessionId,
        student_id: user?.id,
        student_profile: { 
          email: user?.email, 
          name: user?.user_metadata?.full_name,
          emotional_state: mockEmotion,
          teaching_style: mockStyle,
          mastery_level: mockMastery
        },
      })

      setLastWorkflow(res.workflow_steps || [])
      setLastParams(res.extracted_params || {})

      setMessages(prev => prev.map(m => m.id === typingId ? {
        id: typingId, role: 'assistant', content: res.response,
        toolUsed: res.tool_used, confidence: res.confidence,
        workflowSteps: res.workflow_steps, timestamp: new Date(),
      } : m))
    } catch {
      setMessages(prev => prev.map(m => m.id === typingId ? {
        ...m, isTyping: false,
        content: 'Something went wrong. Make sure the backend is running at localhost:8000.',
      } : m))
    } finally {
      setLoading(false)
    }
  }, [loading, inChat, backendOnline, sessionId, user])

  // ── Loading / auth guard ───────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div style={{ height: '100vh', background: '#080808', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 42, height: 42, borderRadius: 12, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)', padding: 2, margin: '0 auto 16px' }}>
            <div style={{ width: '100%', height: '100%', borderRadius: 10, background: '#080808', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 900, color: '#fff' }}>YO</div>
          </div>
          <div style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid #1e1e1e', borderTopColor: '#00c9a7', animation: 'spin 0.8s linear infinite', margin: '0 auto' }} />
        </div>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  const displayName = user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Student'
  const pillsToShow = showMorePills ? QUICK_PILLS : QUICK_PILLS.slice(0, 3)

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#080808', overflow: 'hidden' }}>

      {/* ── Left sidebar ─────────────────────────────────────────────────── */}
      <Sidebar onSignOut={handleSignOut} userName={displayName} />

      {/* ── Center ───────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>

        {/* Header */}
        <header style={{ height: 54, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', borderBottom: '1px solid #1a1a1a', flexShrink: 0, background: '#080808' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)', padding: 2 }}>
              <div style={{ width: '100%', height: '100%', borderRadius: 6, background: '#080808', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 900, color: '#fff' }}>YO</div>
            </div>
            <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.3px', color: '#fff' }}>
              Edu<span style={{ color: '#00c9a7' }}>Orchestrator</span>
              <span style={{ color: '#333', fontWeight: 400, fontSize: 11, marginLeft: 4 }}>.ai</span>
            </span>
            <span style={{ fontSize: 11, color: '#2a2a2a', marginLeft: 4 }}>AI powered learning, beyond Limits.</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Backend status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: backendOnline ? '#00c9a7' : '#555' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: backendOnline ? '#00c9a7' : '#333' }} />
              {backendOnline ? 'Backend online' : 'Backend offline'}
            </div>

            {/* Streak */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#111', border: '1px solid #1e1e1e', borderRadius: 20, padding: '4px 12px', fontSize: 12, fontWeight: 600, color: '#f59e0b' }}>
              🔥 2
            </div>

            {/* Tokens */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#111', border: '1px solid #1e1e1e', borderRadius: 20, padding: '4px 12px', fontSize: 12, color: '#aaa' }}>
              💰 100 tokens
            </div>

            {/* User */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, background: '#111', border: '1px solid #1e1e1e', borderRadius: 20, padding: '4px 10px', fontSize: 12, color: '#888', cursor: 'pointer' }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: '#1a2e2b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 700, color: '#00c9a7' }}>
                {displayName.slice(0, 2).toUpperCase()}
              </div>
              <span>{displayName}</span>
            </div>

            {/* Notifications */}
            <div style={{ position: 'relative', width: 32, height: 32, background: '#111', border: '1px solid #1e1e1e', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#555" strokeWidth="2" strokeLinecap="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>
              <div style={{ position: 'absolute', top: -3, right: -3, width: 16, height: 16, background: '#00c9a7', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 700, color: '#000', border: '2px solid #080808' }}>9+</div>
            </div>
          </div>
        </header>

        {/* ── Context Adaptation Developer Toolbar ─────────────────────── */}
        <div style={{ padding: '8px 24px', background: '#0a0a0a', borderBottom: '1px solid #1a1a1a', display: 'flex', alignItems: 'center', gap: 20, fontSize: 12, flexShrink: 0 }}>
          <span style={{ color: '#00c9a7', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: 10, background: 'rgba(0, 201, 167, 0.1)', padding: '3px 8px', borderRadius: 4 }}>Dev Toolbar</span>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#888' }}>Emotion:</span>
            <select value={mockEmotion} onChange={e => setMockEmotion(e.target.value)} style={{ background: '#111', border: '1px solid #222', color: '#e8e8e8', borderRadius: 6, padding: '3px 8px', outline: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
              <option value="neutral">Neutral</option>
              <option value="focused">Focused</option>
              <option value="anxious">Anxious</option>
              <option value="confused">Confused</option>
              <option value="tired">Tired</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#888' }}>Target Style:</span>
            <select value={mockStyle} onChange={e => setMockStyle(e.target.value)} style={{ background: '#111', border: '1px solid #222', color: '#e8e8e8', borderRadius: 6, padding: '3px 8px', outline: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
              <option value="direct">Direct</option>
              <option value="socratic">Socratic</option>
              <option value="visual">Visual</option>
              <option value="flipped_classroom">Flipped Class</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#888' }}>Mastery Level:</span>
            <input type="range" min="1" max="10" value={mockMastery} onChange={e => setMockMastery(parseInt(e.target.value))} style={{ width: 80, cursor: 'pointer', accentColor: '#00c9a7' }} />
            <span style={{ color: '#fff', background: '#1a2e2b', border: '1px solid #2d6b5e', borderRadius: 4, width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700 }}>{mockMastery}</span>
          </div>
        </div>

        {/* ── Welcome screen ─────────────────────────────────────────────── */}
        {!inChat && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '20px 24px 32px', overflowY: 'auto' }}>

            {/* Avatar */}
            <div className="animate-fade-up" style={{ width: 78, height: 78, borderRadius: '50%', padding: 3, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#f59e0b,#00c9a7)', marginBottom: 22, flexShrink: 0 }}>
              <div style={{ width: '100%', height: '100%', borderRadius: '50%', background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 900, color: '#fff', letterSpacing: '-1px' }}>
                YO
              </div>
            </div>

            <h1 className="animate-fade-up" style={{ fontSize: 22, fontWeight: 700, color: '#fff', textAlign: 'center', marginBottom: 10, lineHeight: 1.3, animationDelay: '0.05s', opacity: 0 }}>
              &ldquo;Hi there 👋 I&apos;m Yo, Your personal learning companion&rdquo;
            </h1>
            <p className="animate-fade-up" style={{ fontSize: 14, color: '#555', textAlign: 'center', maxWidth: 460, lineHeight: 1.65, marginBottom: 28, animationDelay: '0.1s', opacity: 0 }}>
              Tell me your goal, challenge, or question — I&apos;ll automatically pick the right tool and get to work.
            </p>

            {/* Quick pills */}
            <div className="animate-fade-up" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, marginBottom: 28, animationDelay: '0.15s', opacity: 0 }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8 }}>
                {pillsToShow.map(p => (
                  <button key={p.label} onClick={() => doSend(p.msg)} className="pill-btn">
                    <span style={{ fontSize: 15 }}>{p.icon}</span>
                    {p.label}
                  </button>
                ))}
              </div>
              {showMorePills && (
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8 }}>
                  {QUICK_PILLS.slice(3).map(p => (
                    <button key={p.label} onClick={() => doSend(p.msg)} className="pill-btn">
                      <span style={{ fontSize: 15 }}>{p.icon}</span>
                      {p.label}
                    </button>
                  ))}
                </div>
              )}
              <button onClick={() => setShowMorePills(p => !p)} className="pill-btn" style={{ color: '#555', borderColor: '#1a1a1a' }}>
                — {showMorePills ? 'Less' : 'More'}
              </button>
            </div>

            {/* Input */}
            <div className="animate-fade-up" style={{ width: '100%', maxWidth: 660, animationDelay: '0.2s', opacity: 0 }}>
              <ChatInput onSend={doSend} disabled={loading} />
            </div>

            <button style={{ marginTop: 16, fontSize: 12, color: '#2a2a2a', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'inherit' }}>
              Explore more ↓
            </button>
          </div>
        )}

        {/* ── Chat thread ────────────────────────────────────────────────── */}
        {inChat && (
          <>
            <div ref={threadRef} style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
              {messages.map(msg => (
                <div key={msg.id} className="animate-msg" style={{ display: 'flex', gap: 10, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
                  {msg.role === 'assistant' ? <AvatarYo /> : <UserAvatar name={displayName} />}

                  <div style={{ maxWidth: '72%' }}>
                    {msg.isTyping ? <TypingBubble /> : (
                      <div style={{
                        padding: '10px 14px', fontSize: 13.5, lineHeight: 1.65, wordBreak: 'break-word',
                        ...(msg.role === 'user'
                          ? { background: '#00c9a7', color: '#000', fontWeight: 500, borderRadius: '14px 4px 14px 14px', whiteSpace: 'pre-wrap' }
                          : { background: '#111', border: '1px solid #1e1e1e', color: '#ddd', borderRadius: '4px 14px 14px 14px', whiteSpace: 'pre-wrap' })
                      }}>
                        {msg.content}

                        {/* Tool badge */}
                        {msg.toolUsed && (
                          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#00c9a7', background: 'rgba(0,201,167,0.08)', border: '1px solid rgba(0,201,167,0.15)', padding: '3px 9px', borderRadius: 20 }}>
                              {TOOL_ICONS[msg.toolUsed] || '🔧'} {formatToolName(msg.toolUsed)}
                              {msg.confidence !== undefined && (
                                <span style={{ color: getConfidenceColor(msg.confidence), marginLeft: 2 }}>
                                  · {Math.round(msg.confidence * 100)}%
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Workflow trace */}
                        {msg.workflowSteps && msg.workflowSteps.length > 0 && (
                          <WorkflowBadge steps={msg.workflowSteps} />
                        )}
                      </div>
                    )}
                    <p style={{ fontSize: 10, color: '#2a2a2a', marginTop: 4, paddingLeft: 2 }}>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Bottom bar */}
            <div style={{ padding: '10px 24px 16px', borderTop: '1px solid #151515', flexShrink: 0 }}>
              {/* Quick starters */}
              <div style={{ display: 'flex', gap: 6, overflowX: 'auto', marginBottom: 10, scrollbarWidth: 'none' }}>
                {EXAMPLE_CHAT_STARTERS.slice(0, 5).map((s, i) => (
                  <button key={i} onClick={() => doSend(s)}
                    style={{ flexShrink: 0, fontSize: 12, padding: '5px 11px', borderRadius: 20, background: '#111', border: '1px solid #1e1e1e', color: '#555', cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.15s', fontFamily: 'inherit' }}
                    onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.borderColor = '#2d6b5e'; el.style.color = '#00c9a7' }}
                    onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.borderColor = '#1e1e1e'; el.style.color = '#555' }}>
                    {s.slice(0, 38)}…
                  </button>
                ))}
              </div>
              <ChatInput onSend={doSend} disabled={loading} />
            </div>
          </>
        )}
      </div>

      {/* ── Right tool panel ─────────────────────────────────────────────── */}
      <ToolPanel tools={toolData.tools} byCategory={toolData.by_category} lastWorkflow={lastWorkflow} lastParams={lastParams} />

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        @keyframes bounce { 0%,80%,100% { transform:scale(0.7); opacity:0.5; } 40% { transform:scale(1.1); opacity:1; } }
        .animate-fade-up { animation: fadeUp 0.4s ease forwards; }
        .animate-msg { animation: fadeUp 0.22s ease; }
        .typing-dot { width:5px; height:5px; background:#444; border-radius:50%; display:inline-block; animation:bounce 0.9s infinite; }
        .typing-dot:nth-child(2) { animation-delay:0.15s; }
        .typing-dot:nth-child(3) { animation-delay:0.30s; }
        .pill-btn { display:flex; align-items:center; gap:7px; background:#111; border:1px solid #1e1e1e; border-radius:50px; padding:8px 16px; font-size:13px; color:#aaa; cursor:pointer; white-space:nowrap; transition:all 0.15s; font-family:inherit; }
        .pill-btn:hover { background:#1a2e2b; border-color:#00c9a7; color:#00c9a7; }
        .chat-box { background:#111; border:1px solid #1e1e1e; border-radius:16px; transition:border-color 0.2s; }
        .chat-box:focus-within { border-color:#2d6b5e; }
        .btn-teal { background:#00c9a7; color:#000; font-weight:600; border:none; cursor:pointer; transition:background 0.15s, transform 0.1s; }
        .btn-teal:hover { background:#009e85; }
        .btn-teal:active { transform:scale(0.97); }
        .btn-teal:disabled { background:#1a2e2b; color:#2d5a4e; cursor:not-allowed; }
        textarea::placeholder { color:#333; }
        textarea:disabled { opacity:0.5; }
        ::-webkit-scrollbar { width:4px; height:4px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:#2a2a2a; border-radius:4px; }
      `}</style>
    </div>
  )
}

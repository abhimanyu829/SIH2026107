import React, { useEffect, useRef, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Send, RotateCcw, Bot, ShieldCheck, ExternalLink, MessageSquareText } from 'lucide-react'
import { chatApi } from '../api'
import { useLang, useToast } from '../contexts/AppContext'
import { PageHeader, StatusBadge, SourceCard, LoadingState, ErrorState } from '../components/common'
import type { ChatResponse } from '../types/api'
import type { TKey } from '../i18n'

interface Msg { role: 'user' | 'assistant'; text?: string; data?: ChatResponse; error?: string }

const EXAMPLES: { q: string; key: TKey }[] = [
  { q: 'What is IS 17631:2022?', key: 'ex1' },
  { q: 'Does my office chair require BIS certification?', key: 'ex2' },
  { q: 'What QCO applies to office work chairs?', key: 'ex3' },
  { q: 'Which laboratory can test it?', key: 'ex4' },
]

const Ask: React.FC = () => {
  const { t, lang } = useLang()
  const { push } = useToast()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [convId] = useState(() => `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`)
  const bottomRef = useRef<HTMLDivElement>(null)

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }, { role: 'assistant' }])
    setBusy(true)
    try {
      const res = await chatApi.send(q, convId, lang)
      setMessages((m) => { const copy = [...m]; copy[copy.length - 1] = { role: 'assistant', data: res }; return copy })
    } catch (e: any) {
      setMessages((m) => { const copy = [...m]; copy[copy.length - 1] = { role: 'assistant', error: e.message } ; return copy })
    } finally { setBusy(false) }
  }

  /* prefill from home omnibar */
  useEffect(() => {
    const q = params.get('q')
    if (q) send(q)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const lastAssistant = [...messages].reverse().find((m: Msg) => m.data)
  const isNumber = (lastAssistant?.data?.entities?.is_number) as string | undefined

  return (
    <div className="fade-in">
      <PageHeader crumb="ASK BIS" title={t('askTitle')} sub={t('askSub')} actions={
        <button className="btn btn-secondary btn-sm" onClick={() => { setMessages([]) }}>
          <RotateCcw size={14} /> {t('newChat')}
        </button>
      } />

      {messages.length === 0 && (
        <div className="bis-card" style={{ padding: 20 }}>
          <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 10 }}>
            {t('examples')}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {EXAMPLES.map((ex) => (
              <button key={ex.q} className="btn btn-secondary" style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                onClick={() => send(ex.q)}>
                <MessageSquareText size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
                <span className="small">{t(ex.key)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
        {messages.map((m, i) => {
          if (m.role === 'user') {
            return (
              <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <div style={{
                  background: 'var(--primary-navy)', color: '#fff', padding: '10px 14px',
                  borderRadius: 'var(--radius-md)', maxWidth: '78%', fontSize: '0.875rem',
                }}>{m.text}</div>
              </div>
            )
          }
          /* assistant */
          return (
            <div key={i} className="bis-card" style={{ padding: 0, maxWidth: '92%', borderLeft: '4px solid var(--accent-cyan)' }}>
              <div className="card-header" style={{ padding: '10px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusBadge kind="ai" />
                  {m.data?.agent?.used && <span className="muted small">· agent steps: {m.data.agent.steps}</span>}
                </div>
                {m.data && <span className="muted" style={{ fontSize: '0.75rem' }}>{t('confidenceLabel')}: {Math.round((m.data.confidence || 0) * 100)}%</span>}
              </div>
              <div className="card-body">
                {m.error && <ErrorState message={m.error} onRetry={() => send(messages[i - 1].text || '')} />}
                {!m.data && !m.error && <LoadingState label={t('searching')} />}
                {m.data && (
                  <>
                    <p style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', lineHeight: 1.6 }}>{m.data.answer}</p>

                    {(m.data.related?.products?.length > 0 || m.data.entities?.is_number) && (
                      <div style={{ marginTop: 14 }}>
                        {isNumber && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                            <span className="muted small">{t('applicableStandard')}:</span>
                            <span className="mono" style={{ fontWeight: 600, color: 'var(--primary-navy)' }}>IS {isNumber}</span>
                          </div>
                        )}
                        {m.data.related?.qcos?.length > 0 && (
                          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                            <strong>QCO:</strong> {m.data.related.qcos.map((q: any) => `${q.qco_number || ''} ${q.qco_name || ''}`).filter(Boolean).join('; ')}
                          </div>
                        )}
                        {m.data.related?.schemes?.length > 0 && (
                          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            <strong>Scheme:</strong> {m.data.related.schemes.map((s: any) => `${s.scheme_code || ''} ${s.scheme_name || ''}`).filter(Boolean).join('; ')}
                          </div>
                        )}
                      </div>
                    )}

                    {m.data.sources?.length > 0 && (
                      <div style={{ marginTop: 14 }}>
                        <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 8 }}>{t('sources')}</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {m.data.sources.map((s, j) => (
                            <SourceCard key={j} title={s.title || s.document_id} clause={s.clause} page={s.page} url={s.source_url} />
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="link-row" style={{ marginTop: 16 }}>
                      {isNumber && (
                        <>
                          <button className="btn btn-secondary btn-sm" onClick={() => nav(`/standards/${isNumber}`)}>
                            <ShieldCheck size={13} /> {t('viewStandard')}
                          </button>
                          <button className="btn btn-secondary btn-sm" onClick={() => nav(`/compliance?product=${encodeURIComponent(messages[i - 1]?.text || '')}`)}>
                            {t('useInCompliance')}
                          </button>
                        </>
                      )}
                      <button className="btn btn-accent btn-sm" onClick={() => nav(`/agent?q=${encodeURIComponent(messages[i - 1]?.text || '')}`)}>
                        <Bot size={13} /> {t('askAgentBtn')}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      <form className="omnibar" style={{ marginTop: 18 }} onSubmit={(e) => { e.preventDefault(); send(input) }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={t('askPlaceholder')} aria-label={t('askPlaceholder')} disabled={busy} />
        <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
          <Send size={15} /> {t('send')}
        </button>
      </form>
    </div>
  )
}

export default Ask

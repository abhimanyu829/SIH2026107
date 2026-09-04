import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Bot, Play, CheckCircle2, Loader2, ShieldCheck, Package, Award, FlaskConical, ListChecks, FileText, GitCompareArrows, BookMarked } from 'lucide-react'
import { agentApi } from '../api'
import { useLang, useToast } from '../contexts/AppContext'
import { PageHeader, StatusBadge, SourceCard, ErrorState } from '../components/common'
import type { AgentRunResponse } from '../types/api'
import type { TKey } from '../i18n'

/* friendly progress labels — no internal terminology shown to users */
const PHASES = ['Understanding request', 'Resolving product', 'Finding standard', 'Checking QCO', 'Checking scheme', 'Finding requirements', 'Preparing answer']

const TEMPLATES: { key: TKey; icon: React.ElementType; prompt: string }[] = [
  { key: 'tplResearch', icon: BookMarked, prompt: 'Research the standard IS 17631: title, scope, status, applicable products and QCO.' },
  { key: 'tplProduct', icon: Package, prompt: 'Check the BIS requirements for my office work chairs: applicable standard, QCO and scheme.' },
  { key: 'tplCertPath', icon: Award, prompt: 'Find the certification path for office work chairs: standard, QCO, scheme and what is mandatory.' },
  { key: 'tplFindLabs', icon: FlaskConical, prompt: 'Find BIS-recognized laboratories that can test office work chairs as per IS 17631.' },
  { key: 'tplChecklist', icon: ListChecks, prompt: 'Prepare a compliance checklist for office work chairs under IS 17631 with tests and documents needed.' },
  { key: 'tplDocs', icon: FileText, prompt: 'Analyze which documents I need for BIS certification of office work chairs.' },
  { key: 'tplCompare', icon: GitCompareArrows, prompt: 'Compare IS 17631 and IS 2347: scope, products and requirements.' },
]

const Agent: React.FC = () => {
  const { t, lang } = useLang()
  const { push } = useToast()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [task, setTask] = useState('')
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState(0)
  const [result, setResult] = useState<AgentRunResponse | null>(null)
  const [error, setError] = useState('')
  const [convId] = useState(() => `agent-${Date.now().toString(36)}`)

  const run = async (text: string) => {
    const q = text.trim()
    if (!q || busy) return
    setBusy(true); setError(''); setResult(null); setPhase(0)
    const timer = setInterval(() => setPhase((p) => Math.min(p + 1, PHASES.length - 1)), 2600)
    try {
      const res = await agentApi.run(q, convId, lang)
      setResult(res)
      if (res.status && res.status !== 'COMPLETED' && res.status !== 'UNKNOWN') {
        push('warning', `Task finished with status: ${res.status}`)
      }
    } catch (e: any) {
      setError(e.message || t('tryAgain'))
    } finally { clearInterval(timer); setBusy(false) }
  }

  useEffect(() => { const q = params.get('q'); if (q) run(q) /* eslint-disable-next-line */ }, [])

  const isNumber = (result?.entities?.is_number || (result?.entities as any)?.resolved_is?.match(/\d+/)?.[0]) as string | undefined

  return (
    <div className="fade-in">
      <PageHeader crumb="AI AGENT" title={t('agentTitle')} sub={t('agentSub')} />

      <div className="bis-card card-accent-agent" style={{ padding: 20 }}>
        <label htmlFor="agent-task" className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          {t('agentPlaceholder')}
        </label>
        <div className="omnibar" style={{ marginTop: 10, boxShadow: 'var(--shadow-sm)' }}>
          <Bot size={19} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
          <input id="agent-task" value={task} onChange={(e) => setTask(e.target.value)}
            placeholder={t('agentPlaceholder')} disabled={busy}
            onKeyDown={(e) => { if (e.key === 'Enter') run(task) }} />
          <button className="btn btn-accent" onClick={() => run(task)} disabled={busy || !task.trim()}>
            {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />} {t('runAgentBtn')}
          </button>
        </div>
        <style>{`.spin { animation: spin 0.8s linear infinite; }`}</style>
      </div>

      {/* templates */}
      <div className="bis-card" style={{ padding: 20, marginTop: 14 }}>
        <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 10 }}>
          {t('agentTemplates')}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {TEMPLATES.map((tpl) => (
            <button key={tpl.key} className="btn btn-secondary" style={{ justifyContent: 'flex-start', textAlign: 'left' }}
              disabled={busy} onClick={() => { setTask(tpl.prompt); run(tpl.prompt) }}>
              <tpl.icon size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
              <span className="small">{t(tpl.key)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* progress */}
      {busy && (
        <div className="bis-card card-accent-agent" style={{ padding: 20, marginTop: 14 }} aria-live="polite">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--accent-cyan)' }} />
            <strong className="small" style={{ color: 'var(--aiagent-text)' }}>{t('agentWorking')}</strong>
          </div>
          {PHASES.map((p, i) => (
            <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', opacity: i <= phase ? 1 : 0.4 }}>
              {i < phase
                ? <CheckCircle2 size={14} style={{ color: 'var(--status-pass)' }} />
                : i === phase
                  ? <Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--accent-cyan)' }} />
                  : <span style={{ width: 14, height: 14, borderRadius: 9999, border: '1.5px solid var(--border-muted)', display: 'inline-block' }} />}
              <span className="small">{p} {i < phase ? '✓' : ''}</span>
            </div>
          ))}
        </div>
      )}

      {/* error */}
      {error && <div style={{ marginTop: 14 }}><ErrorState message={error} onRetry={() => run(task)} retryLabel={t('retry')} /></div>}

      {/* result */}
      {result && (
        <div className="fade-in" style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="bis-card card-accent-pass" style={{ padding: 0 }}>
            <div className="card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CheckCircle2 size={17} style={{ color: 'var(--status-pass)' }} />
                <h3 style={{ fontSize: '1rem' }}>{t('taskCompleted')}</h3>
                <StatusBadge kind="ai" label="AI-ASSISTED" />
              </div>
              <span className="muted" style={{ fontSize: '0.75rem' }}>
                {result.tools_used?.length || 0} steps · {Math.round((result.confidence || 0) * 100)}% {t('confidenceLabel').toLowerCase()}
              </span>
            </div>
            <div className="card-body">
              <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 6 }}>{t('summary')}</div>
              <p style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', lineHeight: 1.6 }}>{result.answer}</p>

              <div className="link-row" style={{ marginTop: 16 }}>
                {isNumber && (
                  <>
                    <button className="btn btn-secondary btn-sm" onClick={() => nav(`/standards/${isNumber}`)}>
                      <ShieldCheck size={13} /> {t('viewStandard')}
                    </button>
                    <button className="btn btn-secondary btn-sm" onClick={() => nav(`/compliance?product=office%20work%20chairs`)}>
                      {t('startCompliance')}
                    </button>
                  </>
                )}
                <button className="btn btn-secondary btn-sm" onClick={() => nav('/ask')}>
                  {t('askFollowUp')}
                </button>
              </div>
            </div>
          </div>

          {result.citations?.length > 0 && (
            <div className="bis-card" style={{ padding: 20 }}>
              <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 10 }}>{t('sources')}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
                {result.citations.slice(0, 6).map((c, i) => (
                  <SourceCard key={i} title={c.title || c.document_id} clause={c.clause} page={c.page} url={c.source_url} />
                ))}
              </div>
            </div>
          )}

          {result.unresolved_items?.length > 0 && (
            <div className="bis-card" style={{ padding: '14px 18px', borderLeft: '4px solid #D97706' }}>
              <strong className="small" style={{ color: 'var(--status-gap)' }}>{t('nextSteps')}</strong>
              <ul className="small" style={{ marginTop: 6, paddingLeft: 18, color: 'var(--text-secondary)' }}>
                {result.unresolved_items.slice(0, 4).map((u: any, i: number) => <li key={i}>{String(u).slice(0, 160)}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Agent

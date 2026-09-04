import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ShieldCheck, Bot, ExternalLink } from 'lucide-react'
import { standardsApi } from '../api'
import { useLang } from '../contexts/AppContext'
import { PageHeader, SectionCard, StatusBadge, LoadingState, ErrorState, KeyValueList, NoResultsState } from '../components/common'

const StandardDetail: React.FC = () => {
  const { isNumber = '' } = useParams()
  const { t } = useLang()
  const nav = useNavigate()
  const [std, setStd] = useState<any>(null)
  const [qco, setQco] = useState<any[] | null>(null)
  const [scheme, setScheme] = useState<any[] | null>(null)
  const [tests, setTests] = useState<any[] | null>(null)
  const [labs, setLabs] = useState<any[] | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setBusy(true); setError(''); setStd(null)
    Promise.all([
      standardsApi.detail(isNumber).catch((e) => { throw e }),
    ]).then(([s]) => {
      setStd(s.data)
      setBusy(false)
      /* secondary sections load independently */
      standardsApi.qco(isNumber).then((r) => setQco(r.data || [])).catch(() => setQco([]))
      standardsApi.scheme(isNumber).then((r) => setScheme(r.data || [])).catch(() => setScheme([]))
      standardsApi.tests(isNumber).then((r) => setTests(r.data || [])).catch(() => setTests([]))
      standardsApi.labs(isNumber).then((r) => setLabs(r.data || [])).catch(() => setLabs([]))
    }).catch((e: any) => { setError(e.message || 'not found'); setBusy(false) })
  }, [isNumber])

  if (busy) return <LoadingState label={t('findingStandard')} />
  if (error) return <ErrorState message={error} onRetry={() => nav(0)} retryLabel={t('retry')} />
  if (!std) return <NoResultsState />

  const num = std.canonical_is_number || std.display_is_number || isNumber

  return (
    <div className="fade-in">
      <PageHeader crumb={t('standardsTitle')} title={`${num}${std.is_year ? ':' + std.is_year : ''} — ${std.title || 'Standard'}`}
        sub={std.standard_status ? `Status: ${std.standard_status}` : undefined}
        actions={
          <>
            <button className="btn btn-primary" onClick={() => nav(`/ask?q=${encodeURIComponent('What is ' + num + '?')}`)}>
              <Bot size={14} /> {t('askAi')}
            </button>
            <button className="btn btn-accent" onClick={() => nav(`/compliance?product=${encodeURIComponent(std.title || '')}`)}>
              <ShieldCheck size={14} /> {t('useForCompliance')}
            </button>
            {std.source_url && (
              <a className="btn btn-secondary" href={std.source_url} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> {t('officialSource')}
              </a>
            )}
          </>
        } />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        <SectionCard title={t('overview')}>
          <KeyValueList items={[
            ['IS Number', <span className="mono">{num}</span>],
            ['Title', std.title],
            ['Status', std.standard_status],
            ['Type', std.mandatory_voluntary],
            ['ICS', std.ics_code && <span className="mono">{std.ics_code}</span>],
            ['Committee', std.technical_committee],
            ['Version', std.version_date || std.is_year],
          ]} />
        </SectionCard>

        <SectionCard title="QCO" badge={qco === null ? undefined : (qco.length ? <StatusBadge kind="official" label="QCO" /> : <StatusBadge kind="unknown" label="NO QCO" />)}>
          {qco === null ? <LoadingState /> : qco.length === 0
            ? <p className="muted small">No QCO linkage is established for this standard in the available data.</p>
            : qco.map((q, i) => (
              <div key={i} className="small" style={{ padding: '8px 0', borderBottom: i < qco.length - 1 ? '1px solid var(--border-default)' : 'none' }}>
                <strong>{q.qco_number}</strong> — {q.qco_name}
                {q.effective_date && <span className="muted"> · effective {q.effective_date}</span>}
              </div>
            ))}
        </SectionCard>

        <SectionCard title="Scheme">
          {scheme === null ? <LoadingState /> : scheme.length === 0
            ? <p className="muted small">No certification scheme linkage established in the available data.</p>
            : scheme.map((s, i) => (
              <div key={i} className="small" style={{ padding: '8px 0', borderBottom: i < scheme.length - 1 ? '1px solid var(--border-default)' : 'none' }}>
                <strong>{s.scheme_code}</strong> — {s.scheme_name}
              </div>
            ))}
        </SectionCard>

        <SectionCard title={t('testing')}>
          {tests === null ? <LoadingState /> : tests.length === 0
            ? <p className="muted small">No test requirements established for this standard in the available data.</p>
            : (
              <table className="bis-table table-wrap">
                <thead><tr><th>Test</th><th>Method</th></tr></thead>
                <tbody>
                  {tests.map((x, i) => (
                    <tr key={i}><td>{x.test_name}</td><td className="mono small">{x.test_method_standard || x.method || '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
        </SectionCard>

        <SectionCard title={t('labsOffices')}>
          {labs === null ? <LoadingState /> : labs.length === 0
            ? <p className="muted small">No recognized laboratories established for this standard in the available data.</p>
            : (
              <table className="bis-table">
                <thead><tr><th>Laboratory</th><th>City</th><th>State</th></tr></thead>
                <tbody>
                  {labs.slice(0, 8).map((l: any, i) => (
                    <tr key={i}>
                      <td>{l.lab_name}{l.lab_code ? <span className="muted small"> ({l.lab_code})</span> : ''}</td>
                      <td>{l.city || '—'}</td>
                      <td>{l.state || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </SectionCard>
      </div>
    </div>
  )
}

export default StandardDetail

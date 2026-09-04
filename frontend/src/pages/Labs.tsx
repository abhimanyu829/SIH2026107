import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Search, FlaskConical, Phone, Mail, MapPin, ExternalLink } from 'lucide-react'
import { labsApi } from '../api'
import { useLang } from '../contexts/AppContext'
import { PageHeader, LoadingState, NoResultsState, ErrorState, SectionCard, StatusBadge, KeyValueList } from '../components/common'
import type { LabRow } from '../types/api'

const PER_PAGE = 20

export const Labs: React.FC = () => {
  const { t } = useLang()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [states, setStates] = useState<string[]>([])
  const [rows, setRows] = useState<LabRow[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [page, setPage] = useState(0)

  const load = async (resetPage = true) => {
    setBusy(true); setError('')
    const p = resetPage ? 0 : page
    if (resetPage) setPage(0)
    try {
      const r = await labsApi.browse({ state, q, limit: 200 })
      setStates(r.data?.states || [])
      setRows(r.data?.labs || [])
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  useEffect(() => { load(true) /* eslint-disable-next-line */ }, [])

  const filtered = (rows || [])
  const slice = filtered.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE)

  return (
    <div className="fade-in">
      <PageHeader crumb="BIS INFORMATION" title={t('labsTitle')} sub={t('labsSub')} />
      <div className="bis-card" style={{ padding: 14, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: 220, display: 'flex', gap: 8, alignItems: 'center' }}>
          <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder={t('searchLab')} onKeyDown={(e) => { if (e.key === 'Enter') load(true) }} />
        </div>
        <select className="input" style={{ width: 200 }} value={state} onChange={(e) => setState(e.target.value)}
          aria-label={t('filterState')}>
          <option value="">{t('filterState')}</option>
          {states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="btn btn-primary" onClick={() => load(true)} disabled={busy}>{t('searchAll')}</button>
      </div>

      <div style={{ marginTop: 16 }}>
        {busy && <LoadingState label={t('searching')} />}
        {error && <ErrorState message={error} onRetry={() => load(true)} />}
        {rows && slice.length === 0 && <NoResultsState message={t('noResults')} />}
        {slice.length > 0 && (
          <>
            <div className="bis-card" style={{ overflow: 'hidden' }}>
              <div className="table-wrap">
                <table className="bis-table">
                  <thead><tr><th>Laboratory</th><th>Code</th><th>City</th><th>State</th><th>Status</th></tr></thead>
                  <tbody>
                    {slice.map((l) => (
                      <tr key={l.lab_id} style={{ cursor: 'pointer' }} onClick={() => nav(`/labs/${encodeURIComponent(l.lab_id)}`)}>
                        <td style={{ fontWeight: 600 }}>{l.lab_name}</td>
                        <td className="mono small">{l.lab_code || '—'}</td>
                        <td>{l.city || '—'}</td>
                        <td>{l.state || '—'}</td>
                        <td>{l.recognition_status ? <StatusBadge kind={l.recognition_status === 'ACTIVE' ? 'pass' : 'unknown'} label={l.recognition_status} /> : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 14, alignItems: 'center' }}>
              <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <span className="muted small">Page {page + 1} / {Math.max(1, Math.ceil(filtered.length / PER_PAGE))} · {filtered.length} labs</span>
              <button className="btn btn-secondary btn-sm" disabled={(page + 1) * PER_PAGE >= filtered.length} onClick={() => setPage((p) => p + 1)}>Next</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export const LabDetail: React.FC = () => {
  const { labId = '' } = useParams()
  const { t } = useLang()
  const nav = useNavigate()
  const [data, setData] = useState<any>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    labsApi.detail(labId).then((r) => setData(r.data)).catch((e) => setError(e.message)).finally(() => setBusy(false))
  }, [labId])

  if (busy) return <LoadingState label={t('loading')} />
  if (error) return <ErrorState message={error} onRetry={() => nav(0)} />
  if (!data) return <NoResultsState />
  const lab = data.lab || {}
  const scope: any[] = data.scope || []

  return (
    <div className="fade-in">
      <PageHeader crumb={t('labsTitle')} title={lab.lab_name || labId}
        sub={[lab.lab_type, lab.city, lab.state].filter(Boolean).join(' · ')}
        actions={lab.scope_url ? <a className="btn btn-secondary" href={lab.scope_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> {t('officialSource')}</a> : undefined} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        <SectionCard title={t('contact')}>
          <KeyValueList items={[
            ['Laboratory ID', <span className="mono">{lab.lab_id}</span>],
            ['Code', <span className="mono">{lab.lab_code}</span>],
            ['Address', lab.address],
            ['City', lab.city],
            ['State', lab.state],
            ['Phone', lab.contact_number && <span className="mono"><Phone size={11} style={{ display: 'inline', marginRight: 4 }} />{lab.contact_number}</span>],
            ['Email', lab.email && <span className="mono"><Mail size={11} style={{ display: 'inline', marginRight: 4 }} />{lab.email}</span>],
            ['Recognition', lab.recognition_status && <StatusBadge kind={lab.recognition_status === 'ACTIVE' ? 'pass' : 'unknown'} label={lab.recognition_status} />],
            ['Validity', lab.validity],
          ]} />
        </SectionCard>
        <SectionCard title={t('scope')}>
          {scope.length === 0 ? <p className="muted small">No scope items established for this laboratory in the available data.</p> : (
            <div className="table-wrap">
              <table className="bis-table">
                <thead><tr><th>Test</th><th>IS</th><th>Product</th><th>Status</th></tr></thead>
                <tbody>
                  {scope.map((s, i) => (
                    <tr key={i}>
                      <td>{s.test_name || '—'}</td>
                      <td className="mono small">{s.canonical_is_number || '—'}</td>
                      <td className="small">{s.product_name || '—'}</td>
                      <td className="small">{s.scope_status || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}

export default Labs

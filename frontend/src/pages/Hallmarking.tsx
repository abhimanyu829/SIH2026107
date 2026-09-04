import React, { useEffect, useState } from 'react'
import { Search, Stamp, ShieldCheck, Bot, ExternalLink } from 'lucide-react'
import { hallmarkApi } from '../api'
import { useLang } from '../contexts/AppContext'
import { PageHeader, SectionCard, LoadingState, NoResultsState, ErrorState, StatusBadge, KeyValueList } from '../components/common'
import type { HallmarkCentre } from '../types/api'

const PER_PAGE = 20

const Hallmarking: React.FC = () => {
  const { t } = useLang()
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [states, setStates] = useState<string[]>([])
  const [rows, setRows] = useState<HallmarkCentre[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [page, setPage] = useState(0)

  const load = async () => {
    setBusy(true); setError(''); setPage(0)
    try {
      const r = await hallmarkApi.centres({ state, q, limit: 200 })
      setStates(r.data?.states || [])
      setRows(r.data?.centres || [])
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  useEffect(() => { load() /* eslint-disable-next-line */ }, [])

  const slice = (rows || []).slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE)

  return (
    <div className="fade-in">
      <PageHeader crumb="BIS INFORMATION" title={t('hmTitle')} sub={t('hmSub')} />

      {/* overview cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14, marginBottom: 16 }}>
        <SectionCard title={t('hmHuid')} accent="official">
          <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            HUID (Hallmarking Unique ID) is a six-digit alphanumeric code stamped on hallmarked gold jewellery alongside the BIS mark,
            purity in carat and fineness, and the assaying &amp; hallmarking centre's identification mark. It makes each hallmarked
            article traceable to its certification.
          </p>
          <a className="btn btn-secondary btn-sm" style={{ marginTop: 12 }} href="https://www.bis.gov.in/hallmarking/" target="_blank" rel="noreferrer">
            <ExternalLink size={13} /> {t('hmGuidance')}
          </a>
        </SectionCard>
        <SectionCard title={t('hmMandatory')}>
          <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Gold jewellery sales in India require BIS hallmarking under the mandatory hallmarking order for the notified
            categories and caratages (14K, 18K, 20K, 22K, 23K, 24K). Verify current coverage on the official BIS portal.
          </p>
          <a className="btn btn-secondary btn-sm" style={{ marginTop: 12 }} href="https://www.bis.gov.in/gold-hallmarking/" target="_blank" rel="noreferrer">
            <ExternalLink size={13} /> Official Hallmarking Order
          </a>
        </SectionCard>
        <SectionCard title="Verify HUID" accent="agent">
          <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{t('hmDisclaimer')}</p>
          <div className="link-row" style={{ marginTop: 12 }}>
            <a className="btn btn-primary btn-sm" href="https://huid.bis.gov.in/" target="_blank" rel="noreferrer">
              <ShieldCheck size={13} /> {t('verifyHuid')}
            </a>
            <a className="btn btn-secondary btn-sm" href="https://www.bcare.bis.gov.in/" target="_blank" rel="noreferrer">
              Verify BIS Licence ↗
            </a>
          </div>
        </SectionCard>
      </div>

      {/* centres search */}
      <SectionCard title={t('hmCentres')} badge={<StatusBadge kind="official" label="OFFICIAL BIS" />}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={t('findCentre')} onKeyDown={(e) => { if (e.key === 'Enter') load() }} />
          </div>
          <select className="input" style={{ width: 200 }} value={state} onChange={(e) => setState(e.target.value)} aria-label={t('filterState')}>
            <option value="">{t('filterState')}</option>
            {states.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button className="btn btn-primary" onClick={load} disabled={busy}>{t('searchAll')}</button>
        </div>

        {busy && <LoadingState label={t('searching')} />}
        {error && <ErrorState message={error} onRetry={load} />}
        {rows && slice.length === 0 && <NoResultsState message={t('noResults')} />}
        {slice.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="bis-table">
                <thead><tr><th>Centre</th><th>Code</th><th>City</th><th>State</th><th>Status</th><th>Validity</th></tr></thead>
                <tbody>
                  {slice.map((c) => (
                    <tr key={c.hm_id}>
                      <td style={{ fontWeight: 600 }}>{c.centre_name}</td>
                      <td className="mono small">{c.centre_code || '—'}</td>
                      <td>{c.city || '—'}</td>
                      <td>{c.state || '—'}</td>
                      <td>{c.recognition_status ? <StatusBadge kind={c.recognition_status === 'ACTIVE' ? 'pass' : c.recognition_status === 'CANCELLED' || c.recognition_status === 'SUSPENDED' ? 'error' : 'unknown'} label={c.recognition_status} /> : '—'}</td>
                      <td className="small">{c.validity || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 14, alignItems: 'center' }}>
              <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <span className="muted small">Page {page + 1} / {Math.max(1, Math.ceil((rows || []).length / PER_PAGE))} · {(rows || []).length} centres</span>
              <button className="btn btn-secondary btn-sm" disabled={(page + 1) * PER_PAGE >= (rows || []).length} onClick={() => setPage((p) => p + 1)}>Next</button>
            </div>
          </>
        )}
        <p className="muted" style={{ fontSize: '0.75rem', marginTop: 12 }}>
          Source: BIS Assaying &amp; Hallmarking centre list (manakonline.in). Verify current status on the official portal before acting.
        </p>
      </SectionCard>
    </div>
  )
}

export default Hallmarking

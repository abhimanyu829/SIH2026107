import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ShieldCheck, BookMarked } from 'lucide-react'
import { standardsApi } from '../api'
import { useLang, useToast } from '../contexts/AppContext'
import { PageHeader, LoadingState, NoResultsState, ErrorState, StatusBadge, EmptyState } from '../components/common'
import type { StandardRow } from '../types/api'

const Standards: React.FC = () => {
  const { t } = useLang()
  const { push } = useToast()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<StandardRow[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const search = async (term?: string) => {
    const query = (term ?? q).trim()
    if (!query) return
    setBusy(true); setError(''); setRows(null)
    try {
      const r = await standardsApi.search(query, 24)
      setRows(r.data || [])
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="fade-in">
      <PageHeader crumb="BIS INFORMATION" title={t('standardsTitle')} sub={t('standardsSub')} />
      <form className="omnibar" style={{ boxShadow: 'var(--shadow-sm)' }} onSubmit={(e) => { e.preventDefault(); search() }}>
        <Search size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('searchPlaceholder')} aria-label={t('searchPlaceholder')} />
        <button className="btn btn-primary" type="submit" disabled={busy || !q.trim()}>{t('searchAll')}</button>
      </form>

      <div style={{ marginTop: 18 }}>
        {busy && <LoadingState label={t('searching')} />}
        {error && <ErrorState message={error} onRetry={() => search()} />}
        {rows && rows.length === 0 && <NoResultsState message={t('noResults')} />}
        {rows && rows.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
            {rows.map((s) => {
              const num = s.canonical_is_number || s.display_is_number || ''
              const digits = String(num).replace(/\D/g, '') || String(s.is_id || '')
              return (
                <div key={s.is_id || num} className="bis-card hoverable" style={{ padding: 18, cursor: 'pointer' }}
                  onClick={() => nav(`/standards/${encodeURIComponent(digits)}`)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span className="mono" style={{ fontWeight: 600, color: 'var(--primary-navy)', fontSize: '0.9375rem' }}>{num || s.is_id}</span>
                    {s.standard_status && (
                      <StatusBadge kind={String(s.standard_status).toUpperCase() === 'ACTIVE' ? 'pass' : 'unknown'} label={String(s.standard_status).toUpperCase()} />
                    )}
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', lineHeight: 1.4, minHeight: 38 }}>{s.title || 'Title not established in source data'}</div>
                  {s.mandatory_voluntary && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 8 }}>{s.mandatory_voluntary}</div>}
                </div>
              )
            })}
          </div>
        )}
        {!busy && !error && !rows && (
          <EmptyState title={t('standardsTitle')} message="Search by IS number (e.g. 17631), title or product keyword — the backend looks up authoritative BIS records." />
        )}
      </div>
    </div>
  )
}

export default Standards

import React, { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { Search, ShieldCheck, Package } from 'lucide-react'
import { productsApi } from '../api'
import { useLang } from '../contexts/AppContext'
import { PageHeader, LoadingState, NoResultsState, ErrorState, EmptyState, SectionCard, KeyValueList, StatusBadge } from '../components/common'
import type { ProductRow } from '../types/api'

const Products: React.FC = () => {
  const { t } = useLang()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<ProductRow[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const search = async () => {
    if (!q.trim()) return
    setBusy(true); setError(''); setRows(null)
    try { const r = await productsApi.search(q, 24); setRows(r.data || []) }
    catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="fade-in">
      <PageHeader crumb="BIS INFORMATION" title={t('productsTitle')} sub={t('productsSub')} />
      <form className="omnibar" style={{ boxShadow: 'var(--shadow-sm)' }} onSubmit={(e) => { e.preventDefault(); search() }}>
        <Search size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('searchPlaceholder')} aria-label={t('searchPlaceholder')} />
        <button className="btn btn-primary" type="submit" disabled={busy || !q.trim()}>{t('searchAll')}</button>
      </form>

      <div style={{ marginTop: 18 }}>
        {busy && <LoadingState label={t('searching')} />}
        {error && <ErrorState message={error} onRetry={search} />}
        {rows && rows.length === 0 && <NoResultsState message={t('noResults')} />}
        {rows && rows.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
            {rows.map((p) => (
              <div key={p.product_id} className="bis-card hoverable" style={{ padding: 18, cursor: 'pointer' }}
                onClick={() => nav(`/products/${encodeURIComponent(p.product_id)}`)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ width: 34, height: 34, borderRadius: 'var(--radius-sm)', background: 'var(--primary-navy-subtle)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <Package size={16} style={{ color: 'var(--primary-navy)' }} />
                  </span>
                  <span className="mono muted" style={{ fontSize: '0.75rem' }}>{p.product_id}</span>
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', lineHeight: 1.4 }}>{p.product_name || 'Unnamed product'}</div>
                {p.product_category && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 6 }}>{p.product_category}</div>}
              </div>
            ))}
          </div>
        )}
        {!busy && !error && !rows && (
          <EmptyState title={t('productsTitle')} message="Search product records — e.g. 'office work chairs', 'pressure cookers', 'cement'." />
        )}
      </div>
    </div>
  )
}

export const ProductDetail: React.FC = () => {
  const { productId = '' } = useParams()
  const { t } = useLang()
  const nav = useNavigate()
  const [data, setData] = useState<any>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setBusy(true)
    productsApi.detail(productId).then((r) => setData(r.data)).catch((e) => setError(e.message)).finally(() => setBusy(false))
  }, [productId])

  if (busy) return <LoadingState label={t('loading')} />
  if (error) return <ErrorState message={error} onRetry={() => nav(0)} />
  if (!data) return <NoResultsState />

  const p = data.product || {}
  const stds: any[] = data.standards || []

  return (
    <div className="fade-in">
      <PageHeader crumb={t('productsTitle')} title={p.product_name || productId}
        sub={p.product_category || undefined}
        actions={
          <button className="btn btn-accent" onClick={() => nav(`/compliance?product=${encodeURIComponent(p.product_name || '')}`)}>
            <ShieldCheck size={14} /> {t('startCompliance')}
          </button>
        } />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        <SectionCard title={t('overview')}>
          <KeyValueList items={[
            ['Product ID', <span className="mono">{p.product_id}</span>],
            ['Name', p.product_name],
            ['Category', p.product_category],
          ]} />
        </SectionCard>
        <SectionCard title={t('applicableStandard')}>
          {stds.length === 0 ? <p className="muted small">No standard linkage established for this product in the available data.</p> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {stds.map((s, i) => {
                const num = s.canonical_is_number || s.display_is_number || ''
                const digits = String(num).replace(/\D/g, '')
                return (
                  <div key={i} className="bis-card hoverable" style={{ padding: '12px 14px', cursor: 'pointer', borderLeft: '4px solid var(--primary-navy)' }}
                    onClick={() => digits && nav(`/standards/${digits}`)}>
                    <div className="mono" style={{ fontWeight: 600, color: 'var(--primary-navy)' }}>{num || '—'}</div>
                    <div className="small">{s.title || ''}</div>
                  </div>
                )
              })}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}

export default Products

/* Evidence drawer — the signature evidence view. Separates BIS SOURCE from
   USER EVIDENCE, never mixes. */
import React from 'react'
import { X, FileText, BookOpen } from 'lucide-react'
import { StatusBadge } from '../common'

export interface DrawerData {
  requirement?: string
  decision?: 'PASS' | 'GAP' | 'UNKNOWN'
  reason?: string
  evidenceRefs?: any[]
  bisSource?: string
  clause?: string
  /* user evidence */
  document?: string
  page?: string | number
  extractedText?: string
  conflictNote?: string
}

export const EvidenceDrawer: React.FC<{ open: boolean; data: DrawerData | null; onClose: () => void; labels: Record<string, string> }> = ({ open, data, onClose, labels }) => {
  if (!open || !data) return null
  const d = data
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Evidence detail">
        <div className="card-header" style={{ position: 'sticky', top: 0, background: 'var(--bg-surface)', zIndex: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <BookOpen size={17} style={{ color: 'var(--primary-navy)' }} />
            <h3 style={{ fontSize: '1rem' }}>{labels.evidence ?? 'Evidence'}</h3>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X size={15} /></button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {d.requirement && (
            <section>
              <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 4 }}>{labels.requirement}</div>
              <p style={{ fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.4 }}>{d.requirement}</p>
              {d.decision && (
                <div style={{ marginTop: 8 }}>
                  <StatusBadge kind={d.decision === 'PASS' ? 'pass' : d.decision === 'GAP' ? 'gap' : 'unknown'} label={d.decision} />
                </div>
              )}
            </section>
          )}
          {d.reason && (
            <section>
              <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 4 }}>{labels.reason}</div>
              <p className="small" style={{ color: 'var(--text-secondary)' }}>{d.reason}</p>
            </section>
          )}
          {d.conflictNote && (
            <div className="bis-card" style={{ padding: '12px 14px', background: 'var(--status-gap-bg)', borderColor: 'var(--status-gap-border)', borderLeft: '4px solid #D97706' }}>
              <StatusBadge kind="gap" label="CONFLICT" />
              <p className="small" style={{ marginTop: 8, color: 'var(--status-gap)' }}>{d.conflictNote}</p>
            </div>
          )}

          {/* USER EVIDENCE — visually separated */}
          {(d.document || d.extractedText || d.page !== undefined) && (
            <section style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: 14, background: 'var(--bg-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <StatusBadge kind="user" />
                <span className="muted small">your uploaded documents</span>
              </div>
              {d.document && (
                <div className="small" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <FileText size={13} style={{ color: 'var(--text-muted)' }} />
                  <strong>{d.document}</strong>
                  {d.page !== undefined && d.page !== '' && <span className="muted">· {labels.page ?? 'Page'} {d.page}</span>}
                </div>
              )}
              {d.extractedText && (
                <div style={{ marginTop: 8 }}>
                  <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 4 }}>{labels.extractedText ?? 'Extracted text'}</div>
                  <div className="mono" style={{ fontSize: '0.75rem', background: 'var(--primary-navy-subtle)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: 10, color: 'var(--primary-navy-dark)', whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>
                    {d.extractedText}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* OFFICIAL BIS SOURCE — visually separated */}
          {(d.bisSource || d.clause) && (
            <section style={{ border: '1px solid var(--official-border)', borderRadius: 'var(--radius-sm)', padding: 14, background: 'var(--official-bg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <StatusBadge kind="official" />
                <span className="small" style={{ color: 'var(--official-text)' }}>authoritative BIS record</span>
              </div>
              <dl className="kv" style={{ gridTemplateColumns: '90px 1fr' }}>
                {d.bisSource && <><dt className="small">{labels.bisSource ?? 'BIS Source'}</dt><dd className="small">{d.bisSource}</dd></>}
                {d.clause && <><dt className="small">{labels.clause ?? 'Clause'}</dt><dd className="small mono">{d.clause}</dd></>}
              </dl>
            </section>
          )}

          {d.evidenceRefs && d.evidenceRefs.length > 0 && (
            <section>
              <div className="muted" style={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 6 }}>Evidence references</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {d.evidenceRefs.map((e: any, i: number) => (
                  <div key={i} className="bis-card" style={{ padding: '10px 12px', borderLeft: '3px solid var(--accent-cyan)' }}>
                    <div className="small" style={{ fontWeight: 600 }}>{e.field || e.evidence_id || `EV-${i + 1}`}</div>
                    {e.value && <div className="small mono" style={{ color: 'var(--text-secondary)', marginTop: 2 }}>{String(e.value).slice(0, 120)}</div>}
                    {e.document && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 2 }}>{e.document} · page {e.page ?? '—'}</div>}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </aside>
    </>
  )
}

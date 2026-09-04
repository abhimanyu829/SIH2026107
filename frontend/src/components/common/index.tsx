/* Reusable common components. */
import React from 'react'
import { Loader2, Inbox, AlertTriangle, SearchX } from 'lucide-react'

/* ---------- StatusBadge: PASS / GAP / UNKNOWN / OFFICIAL / AI / USER ---------- */
export type BadgeKind = 'pass' | 'gap' | 'unknown' | 'error' | 'official' | 'ai' | 'user'
export const StatusBadge: React.FC<{ kind: BadgeKind; label?: string; style?: React.CSSProperties }> = ({ kind, label, style }) => {
  const map: Record<BadgeKind, string> = {
    pass: 'badge badge-pass', gap: 'badge badge-gap', unknown: 'badge badge-unknown',
    error: 'badge badge-error', official: 'badge badge-official', ai: 'badge badge-ai',
    user: 'badge badge-user',
  }
  const defaults: Record<BadgeKind, string> = {
    pass: 'PASS', gap: 'GAP', unknown: 'UNKNOWN', error: 'ERROR',
    official: 'OFFICIAL BIS', ai: 'AI-ASSISTED', user: 'USER EVIDENCE',
  }
  return <span className={map[kind]} style={style}>{label ?? defaults[kind]}</span>
}

/* ---------- LoadingState ---------- */
export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div className="state-box" role="status" aria-live="polite">
    <div className="spinner" />
    <p>{label}</p>
  </div>
)

/* ---------- EmptyState ---------- */
export const EmptyState: React.FC<{ title?: string; message?: string }> = ({ title = 'Nothing here yet', message }) => (
  <div className="state-box">
    <Inbox size={30} strokeWidth={1.6} style={{ color: 'var(--text-light)', margin: '0 auto 10px' }} />
    <h3>{title}</h3>
    {message && <p>{message}</p>}
  </div>
)

/* ---------- NoResultsState ---------- */
export const NoResultsState: React.FC<{ message?: string }> = ({ message = 'No matching BIS information was found in the current knowledge base.' }) => (
  <div className="state-box">
    <SearchX size={30} strokeWidth={1.6} style={{ color: 'var(--text-light)', margin: '0 auto 10px' }} />
    <p>{message}</p>
  </div>
)

/* ---------- ErrorState ---------- */
export const ErrorState: React.FC<{ message?: string; onRetry?: () => void; retryLabel?: string }> = ({
  message = 'BIS Assistant service is temporarily unavailable.', onRetry, retryLabel = 'Retry',
}) => (
  <div className="state-box" role="alert">
    <AlertTriangle size={28} strokeWidth={1.6} style={{ color: '#D97706', margin: '0 auto 10px' }} />
    <p>{message}</p>
    {onRetry && (
      <button className="btn btn-secondary btn-sm" style={{ marginTop: 14 }} onClick={onRetry}>
        <Loader2 size={13} /> {retryLabel}
      </button>
    )}
  </div>
)

/* ---------- PageHeader ---------- */
export const PageHeader: React.FC<{ crumb?: string; title: string; sub?: string; actions?: React.ReactNode }> = ({ crumb, title, sub, actions }) => (
  <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
    <div>
      {crumb && <div className="crumb">{crumb}</div>}
      <h1>{title}</h1>
      {sub && <p className="sub">{sub}</p>}
    </div>
    {actions && <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>{actions}</div>}
  </div>
)

/* ---------- SourceCard ---------- */
export const SourceCard: React.FC<{
  title: string; isNumber?: string; clause?: string; page?: string | number
  documentType?: string; url?: string; onOpen?: () => void
}> = ({ title, isNumber, clause, page, documentType, url, onOpen }) => (
  <div className="bis-card hoverable" style={{ padding: '12px 16px', cursor: onOpen ? 'pointer' : 'default' }} onClick={onOpen}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <StatusBadge kind="official" label="OFFICIAL BIS SOURCE" />
      {documentType && <span className="muted" style={{ fontSize: '0.75rem' }}>{documentType}</span>}
    </div>
    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>{title}</div>
    <div className="small muted" style={{ display: 'flex', gap: 14, marginTop: 4, flexWrap: 'wrap' }}>
      {isNumber && <span className="mono">IS {isNumber}</span>}
      {clause && <span>Clause {clause}</span>}
      {page !== undefined && page !== '' && <span>Page {page}</span>}
    </div>
    {url && <a href={url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ fontSize: '0.75rem', marginTop: 6, display: 'inline-block' }}>Official document ↗</a>}
  </div>
)

/* ---------- FileDropzone ---------- */
export const FileDropzone: React.FC<{
  onFiles: (files: FileList | File[]) => void
  title?: string; hint?: string; browseLabel?: string; disabled?: boolean; onDragLabel?: string
}> = ({ onFiles, title = 'Drag & Drop documents here', hint, browseLabel = 'Browse Files', disabled }) => {
  const [drag, setDrag] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)
  return (
    <div
      className={`dropzone${drag ? ' drag' : ''}`}
      role="button"
      tabIndex={0}
      aria-label={title}
      style={disabled ? { opacity: 0.6, pointerEvents: 'none' } : undefined}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); if (!disabled && e.dataTransfer.files?.length) onFiles(e.dataTransfer.files) }}
    >
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--primary-navy)" strokeWidth="1.6"
        style={{ margin: '0 auto 10px', display: 'block' }} aria-hidden="true">
        <path d="M12 16V4m0 0l-4 4m4-4l4 4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
      </svg>
      <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--primary-navy)' }}>{title}</div>
      <div className="muted" style={{ fontSize: '0.75rem', marginTop: 2 }}>or</div>
      <button type="button" className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}
        onClick={(e) => { e.stopPropagation(); inputRef.current?.click() }}>{browseLabel}</button>
      {hint && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 10 }}>{hint}</div>}
      <input ref={inputRef} type="file" multiple hidden accept=".pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg"
        onChange={(e) => { if (e.target.files?.length) onFiles(e.target.files); e.target.value = '' }} />
    </div>
  )
}

/* ---------- KeyValueList ---------- */
export const KeyValueList: React.FC<{ items: [string, React.ReactNode][] }> = ({ items }) => (
  <dl className="kv">
    {items.filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => (
      <React.Fragment key={k}><dt>{k}</dt><dd>{v}</dd></React.Fragment>
    ))}
  </dl>
)

/* ---------- SectionCard ---------- */
export const SectionCard: React.FC<{
  title?: string; badge?: React.ReactNode; children: React.ReactNode
  accent?: 'agent' | 'pass' | 'gap' | 'official'; style?: React.CSSProperties; noPad?: boolean
}> = ({ title, badge, children, accent, style, noPad }) => (
  <div className={`bis-card${accent ? ` card-accent-${accent}` : ''}`} style={style}>
    {(title || badge) && (
      <div className="card-header">
        <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>{title}</h3>
        {badge}
      </div>
    )}
    <div className={noPad ? '' : 'card-body'}>{children}</div>
  </div>
)

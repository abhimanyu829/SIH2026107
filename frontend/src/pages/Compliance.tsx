import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import {
  ShieldCheck, Upload, Cog, ScanSearch, FileBarChart, RotateCw, Plus,
  CheckCircle2, XCircle, HelpCircle, ExternalLink, Trash2, FileText, Loader2,
} from 'lucide-react'
import { complianceApi, productsApi } from '../api'
import { useLang, useToast } from '../contexts/AppContext'
import { PageHeader, SectionCard, StatusBadge, LoadingState, ErrorState, FileDropzone, KeyValueList } from '../components/common'
import { EvidenceDrawer, type DrawerData } from '../components/evidence/EvidenceDrawer'
import type { TKey } from '../i18n'

type Phase = 'select' | 'confirm' | 'upload' | 'process' | 'analyze' | 'results'

const STEPS: { key: TKey; icon: React.ElementType }[] = [
  { key: 'stepSelect', icon: ShieldCheck },
  { key: 'stepConfirm', icon: CheckCircle2 },
  { key: 'stepUpload', icon: Upload },
  { key: 'stepProcess', icon: Cog },
  { key: 'stepAnalyzeStep', icon: ScanSearch },
  { key: 'stepResults', icon: FileBarChart },
]

const DISPOSABLE_DOC_HINT = 'PDF, DOCX, XLSX, TXT (images via OCR where available)'

/* ---------- main entry: create or resume ---------- */
const Compliance: React.FC = () => {
  const { auditId } = useParams()
  return auditId ? <AuditWorkbench auditId={auditId} /> : <AuditStart />
}

/* ---------- start page ---------- */
const AuditStart: React.FC = () => {
  const { t } = useLang()
  const { push } = useToast()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [product, setProduct] = useState('')
  const [busy, setBusy] = useState(false)
  const [suggestions, setSuggestions] = useState<any[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const p = params.get('product')
    if (p) setProduct(p)
  }, [params])

  const create = async () => {
    if (!product.trim()) return
    setBusy(true); setError('')
    try {
      const r = await complianceApi.createAudit(product.trim())
      push('success', t('auditCreated'))
      nav(`/compliance/${r.audit_id}`)
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  const browse = async () => {
    if (!product.trim()) return
    setSuggestions(null)
    try {
      const r = await productsApi.search(product.trim(), 6)
      setSuggestions(r.data || [])
    } catch { setSuggestions([]) }
  }

  return (
    <div className="fade-in" style={{ maxWidth: 760, margin: '0 auto' }}>
      <div style={{
        background: 'var(--hero-gradient)', borderRadius: 'var(--radius-lg)',
        padding: '44px 36px', textAlign: 'center', color: '#fff', marginBottom: 20,
        boxShadow: 'var(--shadow-lg)',
      }}>
        <ShieldCheck size={36} strokeWidth={1.5} style={{ margin: '0 auto 12px', opacity: 0.9 }} />
        <h1 style={{ color: '#fff', fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.01em' }}>{t('compTitle')}</h1>
        <p style={{ marginTop: 8, fontSize: '0.9375rem', opacity: 0.85, maxWidth: 480, margin: '8px auto 0', lineHeight: 1.55 }}>
          {t('compSub')}
        </p>
      </div>

      <SectionCard title={t('stepSelect')}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input className="input" value={product} onChange={(e) => setProduct(e.target.value)}
            placeholder={t('productPlaceholder')} aria-label="Product"
            onKeyDown={(e) => { if (e.key === 'Enter') create() }} />
          <button className="btn btn-secondary" onClick={browse} disabled={!product.trim()}>{t('browse')}</button>
          <button className="btn btn-primary" onClick={create} disabled={busy || !product.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} {t('createAudit')}
          </button>
        </div>
        <style>{`.spin { animation: spin 0.8s linear infinite; }`}</style>
        {error && <p className="small" style={{ color: 'var(--status-error)', marginTop: 10 }}>{error}</p>}
        {suggestions && suggestions.length === 0 && (
          <p className="small muted" style={{ marginTop: 10 }}>{t('noResults')}</p>
        )}
        {suggestions && suggestions.length > 0 && (
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {suggestions.map((p) => (
              <button key={p.product_id} className="bis-card hoverable" style={{ padding: '10px 14px', textAlign: 'left', cursor: 'pointer' }}
                onClick={() => setProduct(p.product_name)}>
                <strong className="small">{p.product_name}</strong>
                {p.product_category && <span className="muted small"> · {p.product_category}</span>}
              </button>
            ))}
          </div>
        )}
        <p className="muted" style={{ fontSize: '0.75rem', marginTop: 12 }}>
          This is an AI-assisted BIS compliance readiness assessment and does not constitute official BIS certification or replace BIS assessment.
        </p>
      </SectionCard>
    </div>
  )
}

/* ---------- workbench: the full audit workflow ---------- */
const AuditWorkbench: React.FC<{ auditId: string }> = ({ auditId }) => {
  const { t } = useLang()
  const { push } = useToast()
  const nav = useNavigate()
  const [audit, setAudit] = useState<any>(null)
  const [busy, setBusy] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [rechecking, setRechecking] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [report, setReport] = useState<string | null>(null)
  const [reportOpen, setReportOpen] = useState(false)
  const [drawer, setDrawer] = useState<DrawerData | null>(null)
  const [prevScore, setPrevScore] = useState<number | null>(null)

  const stepIdx = (status: string, hasResult: boolean): number => {
    if (hasResult) return 5
    switch (status) {
      case 'created': return 0
      case 'product_resolved': return 1
      case 'documents_pending': return 2
      case 'documents_processed': return 3
      case 'analyzed': return 4
      default: return 1
    }
  }

  const load = async () => {
    try {
      const a = await complianceApi.audit(auditId)
      setAudit(a)
      /* fetch existing results if analyzed */
      try {
        const r = await complianceApi.result(auditId)
        if (r?.results) setResult(r)
      } catch { /* not analyzed yet */ }
    } catch (e: any) { setLoadError(e.message) } finally { setBusy(false) }
  }

  useEffect(() => { load() /* eslint-disable-next-line */ }, [auditId])

  const uploadFiles = async (files: FileList | File[]) => {
    setUploading(true)
    let ok = 0
    for (const f of Array.from(files)) {
      try { await complianceApi.upload(auditId, f); ok++ }
      catch (e: any) { push('error', `${f.name}: ${e.message}`) }
    }
    setUploading(false)
    if (ok) { push('success', `${ok} file(s) uploaded`); load() }
  }

  const process = async () => {
    setProcessing(true)
    try {
      const r = await complianceApi.process(auditId)
      push('success', `${r?.evidence_added ?? 0} evidence extracted`)
      await load()
    } catch (e: any) { push('error', e.message) } finally { setProcessing(false) }
  }

  const analyze = async () => {
    setAnalyzing(true)
    try {
      await complianceApi.analyze(auditId)
      const r = await complianceApi.result(auditId)
      setResult(r)
      push('success', 'Analysis complete')
    } catch (e: any) { push('error', e.message) } finally { setAnalyzing(false) }
  }

  const recheck = async () => {
    setPrevScore(result?.score?.score ?? null)
    setRechecking(true); setReport(null); setReportOpen(false)
    try {
      await complianceApi.recheck(auditId)
      const r = await complianceApi.result(auditId)
      setResult(r)
      push('success', 'Recheck complete')
    } catch (e: any) { push('error', e.message) } finally { setRechecking(false) }
  }

  const openReport = async () => {
    try {
      const md = await complianceApi.reportMarkdown(auditId)
      setReport(md); setReportOpen(true)
    } catch (e: any) { push('error', e.message) }
  }

  const removeDoc = async (docId: string) => {
    /* backend has no delete endpoint — honest limitation */
    push('info', 'Documents cannot be removed once uploaded in this version. Upload corrected evidence and recheck.')
  }

  if (busy) return <LoadingState label={t('loading')} />
  if (loadError) return <ErrorState message={loadError} onRetry={load} />
  if (!audit) return <ErrorState />

  const cur = stepIdx(result?.status || audit.status, !!result?.results?.length && (result?.score !== undefined))
  const hasDocs = (audit.documents || []).length > 0
  const analyzed = !!result?.score || result?.status === 'analyzed' || audit.status === 'analyzed'
  const score = result?.score
  const results: any[] = result?.results || []
  const remediation: any[] = result?.remediation || []

  return (
    <div className="fade-in">
      {/* header + stepper */}
      <PageHeader crumb={t('compliance')} title={t('compTitle')}
        sub={`${audit.product_text}`}
        actions={
          <Link className="btn btn-secondary btn-sm" to="/compliance"><Plus size={13} /> {t('createAudit')}</Link>
        } />

      <div className="bis-card" style={{ padding: '14px 18px', marginBottom: 18, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {STEPS.map((s, i) => (
          <React.Fragment key={s.key}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px', borderRadius: 'var(--radius-sm)',
              background: i < cur ? 'var(--status-pass-bg)' : i === cur ? 'var(--primary-navy-subtle)' : 'transparent',
              color: i <= cur ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: '0.8125rem', fontWeight: i === cur ? 700 : 500 }}>
              {i < cur
                ? <CheckCircle2 size={15} style={{ color: 'var(--status-pass)' }} />
                : <s.icon size={15} style={{ color: i === cur ? 'var(--primary-navy)' : 'var(--text-light)' }} />}
              {t(s.key)}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, minWidth: 14, height: 2, background: i < cur ? 'var(--status-pass-border)' : 'var(--border-default)', marginTop: 16 }} />
            )}
          </React.Fragment>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        {/* resolved product / standard */}
        <SectionCard title={t('stepConfirm')} accent="official"
          badge={audit.is_number ? <StatusBadge kind="official" label={`IS ${audit.is_number}`} /> : <StatusBadge kind="unknown" label="UNRESOLVED" />}>
          {audit.status === 'created' && <LoadingState label={t('resolveNote')} />}
          {audit.product && (
            <KeyValueList items={[
              ['Product', audit.product?.product_name],
              ['Category', audit.product?.product_category],
              ['Standard', audit.is_number && <span className="mono">IS {audit.is_number}</span>],
              ['QCO', audit.product?.qco_number || (audit.product?.qco_name ? `${audit.product.qco_name}` : '—')],
            ]} />
          )}
          {audit.is_number && (
            <button className="btn btn-secondary btn-sm" style={{ marginTop: 12 }}
              onClick={() => nav(`/standards/${String(audit.is_number).replace(/\D/g, '')}`)}>
              <FileText size={13} /> {t('viewStandard')}
            </button>
          )}
        </SectionCard>

        {/* documents */}
        <SectionCard title={t('stepUpload')} accent="agent"
          badge={<StatusBadge kind="user" label={`${(audit.documents || []).length} DOC(S)`} />}>
          <FileDropzone onFiles={uploadFiles} disabled={uploading || processing}
            title={uploading ? 'Uploading…' : t('dropTitle')} hint={t('uploadFormats')} browseLabel={t('browseFiles')} />
          {hasDocs && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {audit.documents.map((d: any) => (
                <div key={d.document_id} className="bis-card" style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <FileText size={15} style={{ color: 'var(--aiagent-text)', flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="small" style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.filename || d.document_id}</div>
                    <div className="muted" style={{ fontSize: '0.6875rem' }}>
                      {d.category || 'unclassified'}{d.pages ? ` · ${d.pages} pages` : ''}{d.evidence_count !== undefined ? ` · ${d.evidence_count} evidence` : ''}
                    </div>
                  </div>
                  <StatusBadge kind={d.status === 'processed' ? 'pass' : 'unknown'} label={(d.status || '').toUpperCase() || 'UPLOADED'} />
                  <button className="btn btn-ghost btn-sm" onClick={() => removeDoc(d.document_id)} aria-label="Remove">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="link-row" style={{ marginTop: 12 }}>
            <button className="btn btn-secondary" onClick={process} disabled={!hasDocs || processing || uploading}>
              {processing ? <Loader2 size={14} className="spin" /> : <Cog size={14} />} {processing ? t('processing') : t('processBtn')}
            </button>
            <button className="btn btn-accent" onClick={analyze} disabled={analyzing || rechecking}
              title={hasDocs ? '' : 'Upload and process documents first'}>
              {analyzing ? <Loader2 size={14} className="spin" /> : <ScanSearch size={14} />} {analyzing ? t('analyzing') : t('analyzeBtn')}
            </button>
          </div>
        </SectionCard>
      </div>

      {/* analyzing overlay */}
      {(analyzing || rechecking) && (
        <div className="bis-card card-accent-agent" style={{ marginTop: 14, padding: 20 }} aria-live="polite">
          <LoadingState label={rechecking ? t('rechecking') : t('analyzing')} />
          <p className="muted small" style={{ maxWidth: 460, margin: '0 auto' }}>
            The agent reads your evidence against BIS requirements. This can take up to a minute.
          </p>
        </div>
      )}

      {/* results */}
      {analyzed && score && (
        <div className="fade-in" style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* score card */}
          <div className="bis-card" style={{ padding: 20, display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ textAlign: 'center', minWidth: 150 }}>
              <div className="muted" style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.05em' }}>{t('readinessScore')}</div>
              <div style={{
                fontFamily: 'var(--font-heading)', fontSize: '3rem', fontWeight: 900, lineHeight: 1.1,
                color: score.score >= 80 ? 'var(--status-pass)' : score.score >= 50 ? 'var(--status-gap)' : 'var(--status-error)',
              }}>
                {score.score}<span style={{ fontSize: '1.2rem', color: 'var(--text-light)' }}>/100</span>
              </div>
              <StatusBadge kind={score.score >= 80 ? 'pass' : score.score >= 50 ? 'gap' : 'error'} label={score.label || String(score.score)} />
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ height: 10, borderRadius: 9999, background: 'var(--bg-muted)', overflow: 'hidden', display: 'flex' }}>
                <span style={{ width: `${score.total ? (score.passed / score.total) * 100 : 0}%`, background: 'var(--status-pass)' }} />
                <span style={{ width: `${score.total ? (score.gaps / score.total) * 100 : 0}%`, background: '#D97706' }} />
                <span style={{ width: `${score.total ? (score.unknown / score.total) * 100 : 0}%`, background: 'var(--border-muted)' }} />
              </div>
              <div style={{ display: 'flex', gap: 18, marginTop: 10, flexWrap: 'wrap' }}>
                <span className="small"><StatusBadge kind="pass" label="PASS" /> <strong>{score.passed}</strong></span>
                <span className="small"><StatusBadge kind="gap" label="GAP" /> <strong>{score.gaps}</strong></span>
                <span className="small"><StatusBadge kind="unknown" label="UNKNOWN" /> <strong>{score.unknown}</strong></span>
                <span className="muted small">· {score.total} {t('requirements')}</span>
              </div>
              {prevScore !== null && prevScore !== score.score && (
                <p className="small" style={{ marginTop: 10, color: score.score > prevScore ? 'var(--status-pass)' : 'var(--status-gap)' }}>
                  {t('previousScore')}: <strong>{prevScore}</strong> → {t('currentScore')}: <strong>{score.score}</strong>
                  {score.score > prevScore ? ' ↑ improved' : score.score < prevScore ? ' ↓ decreased' : ''}
                </p>
              )}
            </div>
            <div className="link-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
              <button className="btn btn-secondary" onClick={recheck} disabled={rechecking || analyzing}>
                {rechecking ? <Loader2 size={14} className="spin" /> : <RotateCw size={14} />} {t('recheckBtn')}
              </button>
              <button className="btn btn-primary" onClick={openReport}>
                <FileBarChart size={14} /> {t('reportBtn')}
              </button>
            </div>
          </div>

          {/* results table */}
          {results.length === 0 ? (
            <SectionCard><p className="muted small">{t('noRequirements')}</p></SectionCard>
          ) : (
            <div className="bis-card" style={{ overflow: 'hidden' }}>
              <div className="card-header">
                <h3 style={{ fontSize: '1rem' }}>{t('requirements')}</h3>
                <span className="muted small">{t('viewEvidence')}: click a row</span>
              </div>
              <div className="table-wrap">
                <table className="bis-table">
                  <thead><tr><th style={{ width: 90 }}>Decision</th><th>Requirement</th><th>Reason</th><th style={{ width: 130 }}>Evidence</th></tr></thead>
                  <tbody>
                    {results.map((r) => (
                      <tr key={r.requirement_id} style={{ cursor: 'pointer' }} onClick={() => setDrawer({
                        requirement: r.requirement,
                        decision: r.decision,
                        reason: r.reason,
                        evidenceRefs: r.evidence_refs,
                        bisSource: r.bis_source,
                        clause: r.clause,
                        conflictNote: (r.conflicts || []).length > 0 ? 'Conflicting evidence detected — verify with the official BIS document.' : undefined,
                      })}>
                        <td>
                          {r.decision === 'PASS' ? <StatusBadge kind="pass" />
                            : r.decision === 'GAP' ? <StatusBadge kind="gap" />
                            : <StatusBadge kind="unknown" />}
                        </td>
                        <td style={{ fontWeight: 600, maxWidth: 280 }}>{r.requirement}</td>
                        <td className="small muted" style={{ maxWidth: 360 }}>{r.reason}</td>
                        <td>
                          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); setDrawer({
                            requirement: r.requirement, decision: r.decision, reason: r.reason,
                            evidenceRefs: r.evidence_refs, bisSource: r.bis_source, clause: r.clause,
                          }) }}>
                            <FileText size={13} /> {t('viewEvidence')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* remediation */}
          {remediation.length > 0 && (
            <SectionCard title={t('remediation')} accent="gap">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {remediation.map((rm, i) => (
                  <div key={i} className="bis-card" style={{ padding: '12px 14px', borderLeft: '4px solid #D97706' }}>
                    <div className="small" style={{ fontWeight: 700, color: 'var(--status-gap)' }}>{rm.gap || rm.missing_evidence || 'Gap'}</div>
                    <div className="small" style={{ marginTop: 4, color: 'var(--text-secondary)' }}>
                      <strong>Fix:</strong> {rm.recommendation}
                    </div>
                    {rm.bis_source && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 4 }}>Source: {rm.bis_source}</div>}
                  </div>
                ))}
              </div>
              <div className="link-row" style={{ marginTop: 14 }}>
                <span className="small muted">{t('uploadCorrected')}:</span>
                <FileDropzone onFiles={uploadFiles} title={t('dropTitle')} hint={DISPOSABLE_DOC_HINT} browseLabel={t('browseFiles')} />
              </div>
            </SectionCard>
          )}

          <p className="muted" style={{ fontSize: '0.75rem', textAlign: 'center' }}>
            This is an AI-assisted BIS compliance readiness assessment and does not constitute official BIS certification or replace BIS assessment.
          </p>
        </div>
      )}

      {/* evidence drawer */}
      <EvidenceDrawer
        open={!!drawer}
        data={drawer}
        onClose={() => setDrawer(null)}
        labels={{ requirement: t('requirement'), reason: t('reason'), evidence: t('evidence'), page: t('page'), extractedText: t('extractedText'), bisSource: t('bisSource'), clause: t('clause') }}
      />

      {/* report modal */}
      {reportOpen && report !== null && (
        <>
          <div className="drawer-overlay" onClick={() => setReportOpen(false)} />
          <aside className="drawer" role="dialog" aria-modal="true" aria-label={t('reportTitle')}
            style={{ maxWidth: 580 }}>
            <div className="card-header" style={{ position: 'sticky', top: 0, background: 'var(--bg-surface)', zIndex: 2 }}>
              <h3 style={{ fontSize: '1rem' }}>{t('reportTitle')}</h3>
              <div className="link-row">
                <button className="btn btn-ghost btn-sm" onClick={() => setReportOpen(false)}>{t('backToAudit')}</button>
              </div>
            </div>
            <div style={{ padding: 20 }}>
              <pre className="mono" style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {report}
              </pre>
              <p className="muted" style={{ fontSize: '0.6875rem', marginTop: 12 }}>
                This is an AI-assisted BIS compliance readiness assessment and does not constitute official BIS certification or replace BIS assessment.
              </p>
            </div>
          </aside>
        </>
      )}
    </div>
  )
}

export default Compliance

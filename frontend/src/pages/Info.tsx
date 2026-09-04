import React from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, BookMarked, FlaskConical, Stamp, Bot, LifeBuoy, Info, ShieldCheck } from 'lucide-react'
import { useLang } from '../contexts/AppContext'
import { PageHeader, SectionCard, StatusBadge } from '../components/common'

/* ---------- Resources ---------- */
export const Resources: React.FC = () => {
  const { t } = useLang()
  const links: { title: string; desc: string; url: string }[] = [
    { title: 'BIS Official Website', desc: 'Bureau of Indian Standards — official portal', url: 'https://www.bis.gov.in' },
    { title: 'BIS Standards Store', desc: 'Purchase full standard texts', url: 'https://www.standardsbis.in' },
    { title: 'e-BIS / MANAK Online', desc: 'Certification and hallmarking applications', url: 'https://www.manakonline.in' },
    { title: 'BIS Care (Consumer Portal)', desc: 'Licence verification and consumer complaints', url: 'https://www.bcare.bis.gov.in' },
    { title: 'HUID Verification', desc: 'Verify hallmarked gold jewellery', url: 'https://huid.bis.gov.in' },
    { title: 'BIS Conformity Assessment Programmes', desc: 'Schemes and certification overview', url: 'https://www.bis.gov.in/conformity-assessment/' },
  ]
  return (
    <div className="fade-in">
      <PageHeader crumb="PREFERENCES" title={t('resources')} sub="Official BIS resources and portals. Transactions happen on the official portals." />
      <SectionCard>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
          {links.map((l) => (
            <a key={l.url} className="bis-card hoverable" href={l.url} target="_blank" rel="noreferrer"
              style={{ padding: 16, textDecoration: 'none', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <ExternalLink size={16} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: 2 }} />
              <span>
                <strong style={{ display: 'block', fontSize: '0.9375rem', fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)' }}>{l.title}</strong>
                <span className="muted" style={{ display: 'block', fontSize: '0.8125rem', marginTop: 3 }}>{l.desc}</span>
              </span>
            </a>
          ))}
        </div>
      </SectionCard>
      <SectionCard title="Inside this assistant" style={{ marginTop: 14 }}>
        <div className="link-row">
          <Link className="btn btn-secondary btn-sm" to="/standards"><BookMarked size={13} /> {t('standards')}</Link>
          <Link className="btn btn-secondary btn-sm" to="/labs"><FlaskConical size={13} /> {t('labsTitle')}</Link>
          <Link className="btn btn-secondary btn-sm" to="/hallmarking"><Stamp size={13} /> {t('hallmarking')}</Link>
          <Link className="btn btn-secondary btn-sm" to="/agent"><Bot size={13} /> {t('aiAgent')}</Link>
          <Link className="btn btn-secondary btn-sm" to="/compliance"><ShieldCheck size={13} /> {t('compliance')}</Link>
        </div>
      </SectionCard>
    </div>
  )
}

/* ---------- Help ---------- */
export const Help: React.FC = () => {
  const { t } = useLang()
  const faqs: [string, string][] = [
    ['What can this assistant do?', 'It answers questions about Indian Standards, products, QCOs, schemes, tests and laboratories; runs AI Agent research tasks; and performs compliance readiness audits against your uploaded documents.'],
    ['Where does the information come from?', 'All factual answers come from the BIS knowledge base built from official BIS publications, with citations shown for every claim.'],
    ['Is this the official BIS website?', 'No. This is an independent AI assistant built around authoritative BIS information. For regulatory decisions and transactions, use the official BIS portal.'],
    ['What is a compliance readiness score?', 'An AI-assisted assessment of how your documents compare to BIS requirements. It is not official BIS certification.'],
    ['How do I verify a BIS licence or HUID?', 'Verification happens on the official portals — use the links on the Hallmarking page or BIS Services page.'],
    ['Which languages are supported?', 'English and Hindi. Use the switcher in the header.'],
  ]
  return (
    <div className="fade-in">
      <PageHeader crumb="PREFERENCES" title={t('help')} sub="How the BIS Intelligent Assistant works." />
      {faqs.map(([q, a], i) => (
        <details key={i} className="bis-card" style={{ padding: '14px 18px', marginBottom: 10 }}>
          <summary style={{ fontWeight: 600, cursor: 'pointer', fontSize: '0.9375rem', color: 'var(--primary-navy-dark)' }}>{q}</summary>
          <p className="small" style={{ color: 'var(--text-secondary)', marginTop: 10, lineHeight: 1.6 }}>{a}</p>
        </details>
      ))}
      <SectionCard style={{ marginTop: 6 }} title={t('askBis')} badge={<StatusBadge kind="ai" />}>
        <p className="small muted">Still stuck? Ask the assistant directly.</p>
        <Link className="btn btn-accent btn-sm" to="/ask"><Bot size={13} /> {t('askBisBtn')}</Link>
      </SectionCard>
    </div>
  )
}

/* ---------- About ---------- */
export const About: React.FC = () => {
  const { t } = useLang()
  return (
    <div className="fade-in">
      <PageHeader crumb="PREFERENCES" title={t('about')} sub="SIH26107 — AI-powered Intelligent Assistant for Indian Standards and BIS Services for Industries and Consumers." />
      <SectionCard title="What this is">
        <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          The BIS Intelligent Assistant is an evidence-grounded AI service built around authoritative BIS publications —
          Indian Standards, QCOs, certification schemes, product manuals, testing parameters, recognized laboratories,
          FMCS licences and hallmarking centres. It answers questions with citations, runs multi-step research tasks
          with the AI Agent, and performs AI-assisted compliance readiness audits on your uploaded documents.
        </p>
        <div className="divider" />
        <p className="small muted">
          This is an independent assistant, not the official Bureau of Indian Standards. For official regulatory
          decisions and transactions, refer to <a href="https://www.bis.gov.in" target="_blank" rel="noreferrer">bis.gov.in</a>.
        </p>
      </SectionCard>
      <SectionCard title="Privacy" style={{ marginTop: 14 }}>
        <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          Uploaded compliance documents are stored locally on the server for your audit only, are never added to the
          BIS knowledge base, and are never used as AI training data. Conversations are held in memory for the session.
        </p>
      </SectionCard>
      <SectionCard title="Data sources" style={{ marginTop: 14 }} badge={<StatusBadge kind="official" />}>
        <ul className="small" style={{ paddingLeft: 18, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <li>Indian Standards master records &amp; QCOs (official BIS publications)</li>
          <li>Product manuals, testing parameters &amp; laboratory scopes</li>
          <li>Recognized laboratories directory (440+ labs)</li>
          <li>FMCS foreign manufacturer licences</li>
          <li>Assaying &amp; Hallmarking centres (2,200+ centres)</li>
        </ul>
      </SectionCard>
    </div>
  )
}

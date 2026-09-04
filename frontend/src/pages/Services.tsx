import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Award, Package, Stamp, ShieldCheck, Bot, BookMarked, FlaskConical, FileText,
  ExternalLink, Building2, LifeBuoy, GraduationCap, BadgeCheck, Search } from 'lucide-react'
import { useLang } from '../contexts/AppContext'
import { PageHeader, SectionCard, StatusBadge } from '../components/common'

interface Svc { title: string; desc: string; helps: string; to?: string; external?: string }

const Services: React.FC = () => {
  const { t } = useLang()
  const nav = useNavigate()

  const groups: { label: string; items: Svc[] }[] = [
    {
      label: t('industryServices'),
      items: [
        { title: 'Know Your Standard', desc: 'Find the Indian Standard that applies to your product.', helps: 'Standard discovery, QCO and scheme linkage', to: '/standards' },
        { title: 'Product Certification', desc: 'Understand the certification route for your product under BIS schemes.', helps: 'Scheme II Product Certification', to: '/standards' },
        { title: 'Compulsory Certification (QCO)', desc: 'Check whether your product falls under a Quality Control Order.', helps: 'Mandatory certification decisions', to: '/standards' },
        { title: 'CRS', desc: 'Compulsory Registration Scheme for electronics & IT goods.', helps: 'Registration route information', external: 'https://www.bis.gov.in/crs/' },
        { title: 'FMCS', desc: 'Foreign Manufacturer Certification Scheme for overseas manufacturers.', helps: 'Foreign certification guidance', external: 'https://www.bis.gov.in/fmcs/' },
        { title: 'Product Manuals', desc: 'Browse product manual records linked to standards.', helps: 'Manufacturing & inspection requirements', to: '/standards' },
        { title: 'Testing & Laboratories', desc: 'Find BIS-recognized laboratories and their scopes.', helps: 'Choosing a test lab', to: '/labs' },
        { title: 'AI Compliance Readiness', desc: 'Upload your documents and get a PASS/GAP/UNKNOWN readiness assessment.', helps: 'Pre-audit preparation', to: '/compliance' },
      ],
    },
    {
      label: t('consumerServices'),
      items: [
        { title: 'Verify BIS Licence / Mark', desc: 'Verify a licence number or marked product on the official portal.', helps: 'Buying with confidence', external: 'https://www.bcare.bis.gov.in/' },
        { title: 'Verify HUID (Gold)', desc: 'Verify hallmarked gold jewellery HUID on the official verification portal.', helps: 'Gold purchase verification', external: 'https://huid.bis.gov.in/' },
        { title: 'Hallmarking Information', desc: 'Understand hallmarking, mandatory categories and find A&H centres.', helps: 'Consumer awareness', to: '/hallmarking' },
        { title: 'Product / Standard Information', desc: 'Ask the AI about standards and product requirements in plain language.', helps: 'Everyday BIS questions', to: '/ask' },
        { title: 'Consumer Complaint Guidance', desc: 'How to raise a complaint about a BIS-certified product.', helps: 'Redressal path', external: 'https://www.bis.gov.in/consumer-affairs/' },
      ],
    },
    {
      label: t('professionalServices'),
      items: [
        { title: 'Find Standards', desc: 'Search the standards knowledge base by number, title or product.', helps: 'Research', to: '/standards' },
        { title: 'Standard Details', desc: 'Standard overview, QCO, scheme, tests and labs in one page.', helps: 'Technical review', to: '/standards' },
        { title: 'Testing Information', desc: 'Tests required per standard, with methods.', helps: 'Test planning', to: '/standards' },
        { title: 'Laboratories', desc: 'Recognized laboratory directory with state filters.', helps: 'Lab selection', to: '/labs' },
        { title: 'BIS Training / NITS', desc: 'Training programmes by the National Institute for Training in Standardisation.', helps: 'Professional development', external: 'https://www.bis.gov.in/nits/' },
        { title: 'BIS Store / Standards', desc: 'Purchase official standards from the BIS standards store.', helps: 'Obtaining full standard text', external: 'https://www.standardsbis.in/' },
      ],
    },
  ]

  const iconFor = (s: Svc): React.ElementType => {
    if (s.title.includes('HUID') || s.title.includes('Hallmark')) return Stamp
    if (s.title.includes('Compliance')) return ShieldCheck
    if (s.title.includes('Verify')) return BadgeCheck
    if (s.title.includes('Lab') || s.title.includes('Testing')) return FlaskConical
    if (s.title.includes('Manual') || s.title.includes('Store') || s.title.includes('Standard')) return BookMarked
    if (s.title.includes('Product')) return Package
    if (s.title.includes('Training')) return GraduationCap
    if (s.title.includes('Complaint') || s.title.includes('Consumer')) return LifeBuoy
    if (s.title.includes('FMCS') || s.title.includes('CRS')) return Award
    return FileText
  }

  return (
    <div className="fade-in">
      <PageHeader crumb="CORE WORKSPACES" title={t('servicesTitle')} sub={t('servicesSub')} />
      {groups.map((g) => (
        <SectionCard key={g.label} title={g.label} style={{ marginBottom: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
            {g.items.map((s) => {
              const Icon = iconFor(s)
              return (
                <div key={s.title} className="bis-card hoverable" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ width: 34, height: 34, borderRadius: 'var(--radius-sm)', background: 'var(--primary-navy-subtle)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Icon size={16} style={{ color: 'var(--primary-navy)' }} />
                    </span>
                    <strong style={{ fontSize: '0.9375rem', fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)' }}>{s.title}</strong>
                  </div>
                  <p className="small" style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s.desc}</p>
                  <div className="muted" style={{ fontSize: '0.75rem' }}>{t('helpsWith')}: {s.helps}</div>
                  <div className="link-row" style={{ marginTop: 'auto' }}>
                    {s.to && <button className="btn btn-primary btn-sm" onClick={() => nav(s.to!)}><Search size={13} /> {t('open')}</button>}
                    {s.to && <button className="btn btn-secondary btn-sm" onClick={() => nav(`/ask?q=${encodeURIComponent('Tell me about ' + s.title)}`)}><Bot size={13} /> {t('askAi')}</button>}
                    {s.external && <a className="btn btn-ghost btn-sm" href={s.external} target="_blank" rel="noreferrer"><ExternalLink size={13} /> {t('openOfficial')}</a>}
                  </div>
                </div>
              )
            })}
          </div>
        </SectionCard>
      ))}
      <p className="muted" style={{ fontSize: '0.75rem', marginTop: 8 }}>
        {t('footerDisclaimer')}
      </p>
    </div>
  )
}

export default Services

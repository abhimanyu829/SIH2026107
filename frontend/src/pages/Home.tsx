import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Bot, MessageSquareText, BookMarked, Package, Award,
  FlaskConical, ShieldCheck, LayoutGrid, ArrowRight, FileText } from 'lucide-react'
import { useLang } from '../contexts/AppContext'
import { StatusBadge } from '../components/common'

const Home: React.FC = () => {
  const { t } = useLang()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<'ask' | 'agent'>('ask')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!q.trim()) return
    if (mode === 'ask') nav(`/ask?q=${encodeURIComponent(q)}`)
    else nav(`/agent?q=${encodeURIComponent(q)}`)
  }

  const quick: { icon: React.ElementType; title: string; sub: string; to: string }[] = [
    { icon: BookMarked, title: t('qaFindStandard'), sub: t('qaFindStandardSub'), to: '/standards' },
    { icon: Package, title: t('qaCheckProduct'), sub: t('qaCheckProductSub'), to: '/products' },
    { icon: Award, title: t('qaCertification'), sub: t('qaCertificationSub'), to: '/standards' },
    { icon: FlaskConical, title: t('qaLabs'), sub: t('qaLabsSub'), to: '/labs' },
    { icon: ShieldCheck, title: t('qaCompliance'), sub: t('qaComplianceSub'), to: '/compliance' },
    { icon: LayoutGrid, title: t('qaServices'), sub: t('qaServicesSub'), to: '/services' },
  ]

  const provides: [string, React.ElementType][] = [
    [t('provStd'), BookMarked], [t('provProd'), Package], [t('provCert'), Award],
    [t('provQco'), FileText], [t('provTest'), FlaskConical], [t('provAi'), MessageSquareText],
    [t('provReady'), ShieldCheck], [t('provDoc'), FileText], [t('provOffice'), FlaskConical],
    [t('provRes'), LayoutGrid],
  ]

  const audience = [t('whoInd'), t('whoMfg'), t('whoSme'), t('whoConsumer'), t('whoTest'), t('whoJewel'), t('whoStudent')]

  return (
    <div className="fade-in" style={{ maxWidth: 880, margin: '0 auto', width: '100%' }}>
      {/* Hero */}
      <section style={{ textAlign: 'center', padding: '44px 0 8px' }}>
        <div style={{
          fontSize: 'clamp(1.2rem, 2.2vw, 1.45rem)', fontWeight: 800, letterSpacing: '0.24em',
          textTransform: 'uppercase', color: 'var(--accent-cyan)', lineHeight: 1.2, marginBottom: 14,
        }}>
          {t('heroEyebrow')}
        </div>
        <h1 style={{
          fontSize: 'clamp(2.85rem, 5.8vw, 4.1rem)', fontWeight: 900, lineHeight: 1.12,
          letterSpacing: '-0.03em', background: 'var(--hero-gradient)',
          WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
          marginBottom: 14,
        }}>
          {t('heroTitle')}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: 620, margin: '0 auto' }}>
          {t('heroSub')}
        </p>

        {/* Omnibar */}
        <form className="omnibar" style={{ marginTop: 28, textAlign: 'left' }} onSubmit={submit}>
          <Search size={19} style={{ color: 'var(--text-muted)', flexShrink: 0 }} aria-hidden="true" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('omnibarPlaceholder')}
            aria-label={t('omnibarPlaceholder')}
          />
          <div className="omnibar-mode" role="group" aria-label="Mode">
            <button type="button" className={mode === 'ask' ? 'active' : ''} onClick={() => setMode('ask')}>{t('ask')}</button>
            <button type="button" className={mode === 'agent' ? 'active' : ''} onClick={() => setMode('agent')}>{t('agentMode')}</button>
          </div>
          <button className="btn btn-primary" type="submit">
            {mode === 'ask' ? <MessageSquareText size={15} /> : <Bot size={15} />}
            {mode === 'ask' ? t('askBisBtn') : t('runAgent')}
          </button>
        </form>

        {/* Primary actions */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 18, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary btn-lg" onClick={() => nav('/ask')}>
            <MessageSquareText size={17} /> {t('askBisBtn')}
          </button>
          <button className="btn btn-accent btn-lg" onClick={() => nav('/agent')}>
            <Bot size={17} /> {t('runAgent')}
          </button>
        </div>
      </section>

      {/* Quick actions */}
      <section style={{ marginTop: 44 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 14 }}>{t('quickActions')}</h2>
        <div className="qa-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {quick.map((qa) => (
            <button key={qa.title} className="bis-card hoverable" style={{
              textAlign: 'left', padding: 18, cursor: 'pointer', display: 'flex', gap: 14, alignItems: 'flex-start',
            }} onClick={() => nav(qa.to)}>
              <span style={{
                width: 38, height: 38, borderRadius: 'var(--radius-sm)', background: 'var(--primary-navy-subtle)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <qa.icon size={19} strokeWidth={1.8} style={{ color: 'var(--primary-navy)' }} />
              </span>
              <span>
                <span style={{ display: 'block', fontWeight: 700, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>{qa.title}</span>
                <span className="muted" style={{ display: 'block', fontSize: '0.8125rem', marginTop: 3, lineHeight: 1.4 }}>{qa.sub}</span>
              </span>
            </button>
          ))}
        </div>
        <style>{`@media (max-width: 1024px) { .qa-grid { grid-template-columns: repeat(2, 1fr) !important; } }
        @media (max-width: 640px) { .qa-grid { grid-template-columns: 1fr !important; } }`}</style>
      </section>

      {/* What we provide */}
      <section style={{ marginTop: 40 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 14 }}>{t('whatWeProvide')}</h2>
        <div className="bis-card" style={{ padding: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 28px' }}>
            {provides.map(([label, Icon]) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                <Icon size={15} strokeWidth={1.9} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
                {label}
              </div>
            ))}
          </div>
          <style>{`@media (max-width: 640px) { .prov-grid { grid-template-columns: 1fr !important; } }`}</style>
        </div>
      </section>

      {/* Who is this for */}
      <section style={{ marginTop: 40, marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 14 }}>{t('whoFor')}</h2>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {audience.map((a) => (
            <span key={a} className="badge badge-unknown" style={{ fontSize: '0.75rem' }}>{a}</span>
          ))}
        </div>
      </section>
    </div>
  )
}

export default Home

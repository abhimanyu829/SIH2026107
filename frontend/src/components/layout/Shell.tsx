/* App shell: header (sticky, tricolor), sidebar, footer, mobile nav. */
import React, { useState } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import {
  Home, MessageSquareText, Bot, ShieldCheck, BookMarked, Package,
  LayoutGrid, FlaskConical, Building2, LifeBuoy, Info, Languages,
  ChevronLeft, Menu, X, Stamp, FileText, Award, Globe
} from 'lucide-react'
import { useLang, useHealth } from '../../contexts/AppContext'
import type { TKey } from '../../i18n'

const BIS_LOGO = (
  <svg width="38" height="42" viewBox="0 0 44 48" aria-label="BIS" role="img" style={{ display: 'block' }}>
    <circle cx="22" cy="24" r="20" fill="none" stroke="var(--primary-navy)" strokeWidth="2.6" />
    <text x="22" y="21.5" textAnchor="middle" fontFamily="var(--font-heading)" fontWeight="800" fontSize="12.5" fill="var(--primary-navy)">BIS</text>
    <text x="22" y="33" textAnchor="middle" fontFamily="var(--font-sans)" fontWeight="600" fontSize="6.2" fill="var(--primary-navy)">मानक</text>
    <path d="M8 38 L36 38" stroke="var(--primary-navy)" strokeWidth="1.4" />
    <path d="M14 41.5 L30 41.5" stroke="var(--primary-navy)" strokeWidth="1" />
  </svg>
)

/* ---------- Navbar ---------- */
export const Navbar: React.FC<{ onMenu: () => void }> = ({ onMenu }) => {
  const { lang, setLang, t } = useLang()
  const { health } = useHealth()
  const up = health?.status === 'ok'
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 50 }}>
      <div style={{ height: 3, background: 'var(--tricolor)' }} aria-hidden="true" />
      <div style={{
        height: 'var(--header-h)', padding: '0 24px', background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(6px)', borderBottom: '1px solid var(--border-default)',
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <button className="btn btn-ghost btn-sm mobile-menu-btn" style={{ display: 'none' }} aria-label="Open menu"
          onClick={onMenu}>
          <Menu size={18} />
        </button>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none' }}>
          <span style={{ filter: 'drop-shadow(0 1px 2px rgba(11,59,96,0.08))' }}>{BIS_LOGO}</span>
          <span>
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 800, fontSize: '0.9375rem', color: 'var(--primary-navy-dark)', display: 'block', lineHeight: 1.2 }}>
              {t('appName')}
            </span>
            <span className="muted" style={{ fontSize: '0.6875rem', letterSpacing: '0.02em' }}>
              SIH26107 · {t('appTagline')}
            </span>
          </span>
        </Link>
        <div style={{ flex: 1 }} />
        <span title={up ? 'All services connected' : 'Service degraded'}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: up ? 'var(--status-pass)' : 'var(--status-gap)' }}>
          <span style={{ width: 8, height: 8, borderRadius: 9999, background: 'currentColor', boxShadow: '0 0 0 3px rgba(21,128,61,0.12)' }} />
        </span>
        <div className="omnibar-mode" role="group" aria-label="Language">
          <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
          <button className={lang === 'hi' ? 'active' : ''} onClick={() => setLang('hi')}>हिन्दी</button>
        </div>
      </div>
    </header>
  )
}

/* ---------- Sidebar ---------- */
const GROUPS: { label: TKey; items: { to: string; label: TKey; icon: React.ElementType }[] }[] = [
  {
    label: 'coreWorkspaces',
    items: [
      { to: '/', label: 'home', icon: Home },
      { to: '/ask', label: 'askBis', icon: MessageSquareText },
      { to: '/agent', label: 'aiAgent', icon: Bot },
      { to: '/compliance', label: 'compliance', icon: ShieldCheck },
    ],
  },
  {
    label: 'bisInfo',
    items: [
      { to: '/standards', label: 'standards', icon: BookMarked },
      { to: '/products', label: 'products', icon: Package },
      { to: '/services', label: 'services', icon: LayoutGrid },
      { to: '/labs', label: 'labsOffices', icon: FlaskConical },
      { to: '/hallmarking', label: 'hallmarking', icon: Stamp },
      { to: '/offices', label: 'offices', icon: Building2 },
      { to: '/resources', label: 'resources', icon: FileText },
    ],
  },
  {
    label: 'preferences',
    items: [
      { to: '/about', label: 'about', icon: Info },
      { to: '/help', label: 'help', icon: LifeBuoy },
    ],
  },
]

export const Sidebar: React.FC<{ collapsed: boolean; onToggle: () => void; mobileOpen: boolean; onMobileClose: () => void }> = ({ collapsed, onToggle, mobileOpen, onMobileClose }) => {
  const { t } = useLang()
  const loc = useLocation()
  const [hidden, setHidden] = useState(true)

  const Inner = (
    <nav aria-label="Main" style={{
      width: 'var(--sidebar-w)', background: 'var(--bg-surface)',
      borderRight: '1px solid var(--border-default)', padding: '16px 12px',
      display: 'flex', flexDirection: 'column', gap: 18,
      position: 'sticky', top: 'var(--header-h)', alignSelf: 'flex-start',
      maxHeight: 'calc(100vh - var(--header-h))', overflowY: 'auto',
    }}>
      {GROUPS.map((g) => (
        <div key={g.label}>
          <div className="muted" style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.05em', padding: '0 10px 8px' }}>
            {t(g.label)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {g.items.map((it) => (
              <NavLink key={it.to} to={it.to} end={it.to === '/'}
                onClick={onMobileClose}
                style={({ isActive }) => ({
                  display: 'flex', alignItems: 'center', gap: 11,
                  padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                  fontSize: '0.875rem', fontWeight: 500, textDecoration: 'none',
                  color: isActive ? 'var(--primary-navy)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--primary-navy-subtle)' : 'transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                <it.icon size={17} strokeWidth={1.9} />
                {t(it.label)}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
      <div style={{ flex: 1 }} />
      <div className="muted" style={{ fontSize: '0.6875rem', padding: '0 10px', display: 'flex', alignItems: 'center', gap: 8, borderTop: '1px solid var(--border-default)', paddingTop: 12 }}>
        <Award size={15} strokeWidth={1.8} style={{ color: 'var(--primary-navy)', flexShrink: 0 }} />
        <span>{t('officialBisWebsite') !== 'Official BIS Website' ? '' : 'Standards under the BIS Act, 2016'}</span>
      </div>
    </nav>
  )

  return (
    <>
      {/* desktop */}
      <aside className="sidebar-desktop" style={{ display: 'block' }}>{Inner}</aside>
      {/* mobile off-canvas */}
      {mobileOpen && (
        <>
          <div className="drawer-overlay" style={{ zIndex: 94 }} onClick={onMobileClose} />
          <aside style={{
            position: 'fixed', left: 0, top: 0, width: 280, height: '100%', zIndex: 95,
            background: 'var(--bg-surface)', boxShadow: 'var(--shadow-drawer)',
            overflowY: 'auto', animation: 'slideInM 0.25s ease',
          }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end', padding: 12 }}>
              <button className="btn btn-ghost btn-sm" onClick={onMobileClose} aria-label="Close menu"><X size={16} /></button>
            </div>
            {Inner}
          </aside>
          <style>{`@keyframes slideInM { from { transform: translateX(-60px); opacity: 0.4; } }`}</style>
        </>
      )}
      <button hidden={hidden} />
    </>
  )
}

/* ---------- Footer ---------- */
export const Footer: React.FC = () => {
  const { t } = useLang()
  const col: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, minWidth: 130 }
  const link = (to: string, label: string) => <Link to={to} style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', textDecoration: 'none' }}>{label}</Link>
  const ext = (href: string, label: string) => <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', textDecoration: 'none' }}>{label} ↗</a>
  return (
    <footer style={{ background: 'var(--footer-grad)', borderTop: '1px solid var(--border-default)', marginTop: 'auto' }}>
      <div style={{ height: 3, background: 'var(--footer-accent)' }} aria-hidden="true" />
      <div style={{ maxWidth: 1240, margin: '0 auto', padding: '44px 28px 24px' }}>
        <div className="footer-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 28 }}>
          <div style={{ gridColumn: 'span 5', display: 'grid', gridTemplateColumns: 'inherit', gap: 28 }}>
            <div style={{ display: 'contents' }} />
          </div>
          <div style={col}>
            <strong style={{ fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)', fontSize: '0.875rem' }}>{t('appName')}</strong>
            {link('/about', t('footerAbout'))}
            {ext('https://www.bis.gov.in', t('officialBisWebsite'))}
          </div>
          <div style={col}>
            <strong style={{ fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)', fontSize: '0.875rem' }}>{t('footerServices')}</strong>
            {link('/services', t('services'))}
            {link('/hallmarking', t('hallmarking'))}
          </div>
          <div style={col}>
            <strong style={{ fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)', fontSize: '0.875rem' }}>{t('footerStandards')}</strong>
            {link('/standards', t('standards'))}
            {link('/products', t('products'))}
          </div>
          <div style={col}>
            <strong style={{ fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)', fontSize: '0.875rem' }}>{t('footerCompliance')}</strong>
            {link('/compliance', t('compliance'))}
            {link('/labs', t('footerLabs'))}
          </div>
          <div style={col}>
            <strong style={{ fontFamily: 'var(--font-heading)', color: 'var(--primary-navy-dark)', fontSize: '0.875rem' }}>{t('footerHelp')}</strong>
            {link('/help', t('help'))}
            {link('/resources', t('footerResources'))}
          </div>
        </div>
        <div className="divider" />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', justifyContent: 'space-between' }}>
          <p className="muted" style={{ fontSize: '0.75rem', maxWidth: 640 }}>{t('footerDisclaimer')}</p>
          <div style={{ display: 'flex', gap: 14, fontSize: '0.75rem' }}>
            <a href="https://www.bis.gov.in" target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)' }}>{t('privacy')}</a>
            <a href="https://www.bis.gov.in" target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)' }}>{t('terms')}</a>
          </div>
        </div>
      </div>
      <style>{`@media (max-width: 1024px) { .footer-grid { grid-template-columns: repeat(2, 1fr) !important; } }
      @media (max-width: 640px) { .footer-grid { grid-template-columns: 1fr !important; } }`}</style>
    </footer>
  )
}

/* ---------- Mobile bottom nav ---------- */
export const MobileNav: React.FC = () => {
  const { t } = useLang()
  const items = [
    { to: '/', label: t('home'), icon: Home },
    { to: '/ask', label: t('askBis'), icon: MessageSquareText },
    { to: '/agent', label: t('aiAgent'), icon: Bot },
    { to: '/compliance', label: t('compliance'), icon: ShieldCheck },
    { to: '/services', label: t('services'), icon: LayoutGrid },
  ]
  return (
    <nav className="mobile-bottom-nav" style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 80,
      background: 'var(--bg-surface)', borderTop: '1px solid var(--border-default)',
      display: 'none', justifyContent: 'space-around', padding: '6px 4px 8px',
    }}>
      {items.map((it) => (
        <NavLink key={it.to} to={it.to} end={it.to === '/'}
          style={({ isActive }) => ({
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
            fontSize: '0.65rem', fontWeight: 600, textDecoration: 'none',
            color: isActive ? 'var(--primary-navy)' : 'var(--text-muted)', padding: '4px 10px',
          })}>
          <it.icon size={18} strokeWidth={1.9} />
          {it.label}
        </NavLink>
      ))}
    </nav>
  )
}

/* ---------- Shell ---------- */
export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const loc = useLocation()
  React.useEffect(() => { setMobileOpen(false) }, [loc.pathname])
  return (
    <div className="app-shell">
      <div className="app-bg" aria-hidden="true" />
      <Navbar onMenu={() => setMobileOpen(true)} />
      <div className="app-body">
        <Sidebar collapsed={false} onToggle={() => {}} mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
        <div className="main-col">
          <main className="main-content">{children}</main>
          <Footer />
        </div>
      </div>
      <MobileNav />
      <style>{`
        @media (max-width: 768px) {
          .sidebar-desktop { display: none !important; }
          .mobile-bottom-nav { display: flex !important; }
          .mobile-menu-btn { display: inline-flex !important; }
        }
      `}</style>
    </div>
  )
}

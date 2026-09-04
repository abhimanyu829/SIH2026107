import React from 'react'
import { Link } from 'react-router-dom'
import { Building2, ExternalLink, FlaskConical } from 'lucide-react'
import { useLang } from '../contexts/AppContext'
import { PageHeader, SectionCard, StatusBadge } from '../components/common'

const Offices: React.FC = () => {
  const { t } = useLang()
  return (
    <div className="fade-in">
      <PageHeader crumb="BIS INFORMATION" title={t('officesTitle')} sub={t('officesSub')} />
      <div className="bis-card" style={{ padding: 20, display: 'flex', gap: 16, alignItems: 'flex-start', borderLeft: '4px solid var(--primary-navy)' }}>
        <Building2 size={22} style={{ color: 'var(--primary-navy)', flexShrink: 0, marginTop: 2 }} />
        <div>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}>{t('officesNote')}</p>
          <div className="link-row" style={{ marginTop: 14 }}>
            <a className="btn btn-primary" href="https://www.bis.gov.in/offices/" target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> {t('openOfficial')}
            </a>
            <Link className="btn btn-secondary" to="/labs">
              <FlaskConical size={14} /> {t('browseLabs')}
            </Link>
          </div>
        </div>
      </div>

      <SectionCard title={t('labsOffices')} style={{ marginTop: 14 }}
        badge={<StatusBadge kind="official" label="OFFICIAL BIS" />}>
        <p className="muted small" style={{ marginBottom: 10 }}>
          Recognized laboratories ARE part of the current knowledge base — browse them with state/city filters.
        </p>
        <Link className="btn btn-accent" to="/labs"><FlaskConical size={14} /> {t('labsTitle')}</Link>
      </SectionCard>
    </div>
  )
}

export default Offices

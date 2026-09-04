import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LanguageProvider, ToastProvider, HealthProvider, useToast } from './contexts/AppContext'
import { Shell } from './components/layout/Shell'
import Home from './pages/Home'
import Ask from './pages/Ask'
import Agent from './pages/Agent'
import Services from './pages/Services'
import Standards from './pages/Standards'
import StandardDetail from './pages/StandardDetail'
import Products, { ProductDetail } from './pages/Products'
import Compliance from './pages/Compliance'
import Labs, { LabDetail } from './pages/Labs'
import Offices from './pages/Offices'
import Hallmarking from './pages/Hallmarking'
import { Resources, Help, About } from './pages/Info'
import { ErrorState } from './components/common'
import './styles/components.css'

/* Toast viewport rendered once at root */
const Toasts: React.FC = () => {
  const { toasts, dismiss } = useToast()
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`} role="alert" onClick={() => dismiss(t.id)}
          style={{ cursor: 'pointer' }}>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  )
}

const NotFound: React.FC = () => (
  <ErrorState message="Page not found." />
)

const App: React.FC = () => (
  <LanguageProvider>
    <ToastProvider>
      <HealthProvider>
        <Shell>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/services" element={<Services />} />
            <Route path="/standards" element={<Standards />} />
            <Route path="/standards/:isNumber" element={<StandardDetail />} />
            <Route path="/products" element={<Products />} />
            <Route path="/products/:productId" element={<ProductDetail />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/compliance/:auditId" element={<Compliance />} />
            <Route path="/labs" element={<Labs />} />
            <Route path="/labs/:labId" element={<LabDetail />} />
            <Route path="/offices" element={<Offices />} />
            <Route path="/hallmarking" element={<Hallmarking />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/help" element={<Help />} />
            <Route path="/about" element={<About />} />
            <Route path="/index.html" element={<Navigate to="/" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Shell>
        <Toasts />
      </HealthProvider>
    </ToastProvider>
  </LanguageProvider>
)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)

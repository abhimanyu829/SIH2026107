/* App-wide contexts: language + toasts + health. */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { translate, type Lang, type TKey } from '../i18n'
import { healthApi } from '../api'
import type { HealthResponse } from '../types/api'

/* ---------- language ---------- */
interface LangCtx { lang: Lang; setLang: (l: Lang) => void; t: (k: TKey) => string }
const LanguageContext = createContext<LangCtx>({ lang: 'en', setLang: () => {}, t: (k) => String(k) })

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem('bis-lang') as Lang) || 'en')
  useEffect(() => { localStorage.setItem('bis-lang', lang); document.documentElement.lang = lang }, [lang])
  const t = useCallback((k: TKey) => translate(lang, k), [lang])
  return <LanguageContext.Provider value={{ lang, setLang, t }}>{children}</LanguageContext.Provider>
}
export const useLang = () => useContext(LanguageContext)

/* ---------- toasts ---------- */
export interface Toast { id: number; type: 'success' | 'warning' | 'error' | 'info'; message: string }
interface ToastCtx { toasts: Toast[]; push: (type: Toast['type'], message: string) => void; dismiss: (id: number) => void }
const ToastContext = createContext<ToastCtx>({ toasts: [], push: () => {}, dismiss: () => {} })

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((type: Toast['type'], message: string) => {
    const id = Date.now() + Math.random()
    setToasts((ts) => [...ts, { id, type, message }])
    setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 5200)
  }, [])
  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((x) => x.id !== id)), [])
  return <ToastContext.Provider value={{ toasts, push, dismiss }}>{children}</ToastContext.Provider>
}
export const useToast = () => useContext(ToastContext)

/* ---------- backend health ---------- */
interface HealthCtx { health: HealthResponse | null; down: boolean; recheck: () => void }
const HealthContext = createContext<HealthCtx>({ health: null, down: false, recheck: () => {} })

export const HealthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [down, setDown] = useState(false)
  const recheck = useCallback(() => {
    healthApi.check()
      .then((h) => { setHealth(h); setDown(h.status !== 'ok') })
      .catch(() => { setDown(true); setHealth(null) })
  }, [])
  useEffect(() => { recheck() }, [recheck])
  return <HealthContext.Provider value={{ health, down, recheck }}>{children}</HealthContext.Provider>
}
export const useHealth = () => useContext(HealthContext)

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken, makeResourceApi, ResourceApi } from './api'

export type Role = 'direccion' | 'coordinacion' | 'equipo' | 'consulta'
export type AppKey = 'admin' | 'ops'
export interface User { id: number; name: string; login: string; email: string; role: Role; member_id: number | null; member_name: string | null; must_change_password: boolean; notify_alerts: boolean; apps: AppKey[]; ops_role: string | null; organization_id: number | null; organization_name: string | null; department: string | null; is_external: boolean; can_export: boolean; mfa_enabled: boolean; mfa_required: boolean; project_ids: number[] }
export interface FieldDef { name: string; string: string; type: string; required: boolean; readonly: boolean; help?: string; selection?: [string, string][]; relation?: string; relation_resource?: string | null; direction_only?: boolean }
export interface Tab { field: string; resource: string; parent_field: string; label: string; defaults?: Record<string, any> }
export interface Resource { key: string; model: string; label: string; singular: string; section: string | null; icon?: string; order: number; list: string[]; filters: string[]; groups: { title: string; fields: string[] }[]; tabs: Tab[]; attachments: boolean; chatter: boolean; sensitive: boolean; actions: { name: string; label: string }[]; can: Record<string, boolean>; fields: Record<string, FieldDef> }
export interface Schema { sections: { key: string; label: string }[]; resources: Record<string, Resource>; role: string; is_external?: boolean; ai_available?: boolean; organization?: string; breakglass?: boolean }

interface Ctx { user: User | null; schema: Schema | null; adminSchema: Schema | null; opsSchema: Schema | null; app: AppKey; setApp: (a: AppKey) => void; rapi: ResourceApi; base: string; loading: boolean; login: (l: string, p: string) => Promise<void>; logout: () => Promise<void>; refresh: () => Promise<void>; toast: (msg: string, kind?: 'ok' | 'err' | 'info') => void; toasts: { id: number; msg: string; kind: string }[] }

const AppCtx = createContext<Ctx>(null as any)
export const useApp = () => useContext(AppCtx)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [adminSchema, setAdminSchema] = useState<Schema | null>(null)
  const [opsSchema, setOpsSchema] = useState<Schema | null>(null)
  const [app, setAppState] = useState<AppKey>((localStorage.getItem('aq_app') as AppKey) || 'admin')
  const [loading, setLoading] = useState(true)
  const setApp = useCallback((a: AppKey) => { localStorage.setItem('aq_app', a); setAppState(a) }, [])
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([])

  const toast = useCallback((msg: string, kind: 'ok' | 'err' | 'info' = 'info') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, msg, kind }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === 'err' ? 7000 : 3500)
  }, [])

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setAdminSchema(null); setOpsSchema(null); setLoading(false); return }
    try {
      const me = await api.me()
      const u: User = me.user
      setUser(u)
      const apps: AppKey[] = u.apps || []
      const [a, o] = await Promise.all([apps.includes('admin') ? makeResourceApi('').schema().catch(() => null) : null, apps.includes('ops') ? makeResourceApi('/ops').schema().catch(() => null) : null])
      setAdminSchema(a); setOpsSchema(o)
      const stored = (localStorage.getItem('aq_app') as AppKey) || 'admin'
      const chosen: AppKey = apps.includes(stored) ? stored : (apps[0] || 'admin')
      localStorage.setItem('aq_app', chosen); setAppState(chosen)
    } catch { setUser(null); setAdminSchema(null); setOpsSchema(null); setToken(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const h = () => { setUser(null); setAdminSchema(null); setOpsSchema(null) }
    window.addEventListener('aq:unauthorized', h)
    return () => window.removeEventListener('aq:unauthorized', h)
  }, [])

  const login = async (l: string, p: string) => {
    const r = await api.login(l, p)
    if (r.mfa_required) { throw Object.assign(new Error('MFA'), { mfa: true, token: r.token }) }
    setToken(r.token)
    if (r.mfa_setup_required) localStorage.setItem('aq_mfa_setup', '1')
    setLoading(true)
    await refresh()
  }
  const logout = async () => { try { await api.logout() } catch {} setToken(null); setUser(null); setAdminSchema(null); setOpsSchema(null) }
  const schema = app === 'ops' ? opsSchema : adminSchema
  const rapi = useMemo(() => makeResourceApi(app === 'ops' ? '/ops' : ''), [app])
  const base = app === 'ops' ? '/ops' : ''

  return <AppCtx.Provider value={{ user, schema, adminSchema, opsSchema, app, setApp, rapi, base, loading, login, logout, refresh, toast, toasts }}>{children}</AppCtx.Provider>
}

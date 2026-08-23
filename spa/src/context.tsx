import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'

export type Role = 'direccion' | 'coordinacion' | 'equipo' | 'consulta'
export interface User { id: number; name: string; login: string; email: string; role: Role; member_id: number | null; member_name: string | null; must_change_password: boolean; notify_alerts: boolean }
export interface FieldDef { name: string; string: string; type: string; required: boolean; readonly: boolean; help?: string; selection?: [string, string][]; relation?: string; relation_resource?: string | null; direction_only?: boolean }
export interface Tab { field: string; resource: string; parent_field: string; label: string; defaults?: Record<string, any> }
export interface Resource { key: string; model: string; label: string; singular: string; section: string | null; icon?: string; order: number; list: string[]; filters: string[]; groups: { title: string; fields: string[] }[]; tabs: Tab[]; attachments: boolean; chatter: boolean; sensitive: boolean; actions: { name: string; label: string }[]; can: Record<string, boolean>; fields: Record<string, FieldDef> }
export interface Schema { sections: { key: string; label: string }[]; resources: Record<string, Resource>; role: Role }

interface Ctx { user: User | null; schema: Schema | null; loading: boolean; login: (l: string, p: string) => Promise<void>; logout: () => Promise<void>; refresh: () => Promise<void>; toast: (msg: string, kind?: 'ok' | 'err' | 'info') => void; toasts: { id: number; msg: string; kind: string }[] }

const AppCtx = createContext<Ctx>(null as any)
export const useApp = () => useContext(AppCtx)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [schema, setSchema] = useState<Schema | null>(null)
  const [loading, setLoading] = useState(true)
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([])

  const toast = useCallback((msg: string, kind: 'ok' | 'err' | 'info' = 'info') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, msg, kind }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === 'err' ? 7000 : 3500)
  }, [])

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setSchema(null); setLoading(false); return }
    try {
      const me = await api.me()
      setUser(me.user)
      const sc = await api.schema()
      setSchema(sc)
    } catch { setUser(null); setSchema(null); setToken(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const h = () => { setUser(null); setSchema(null) }
    window.addEventListener('aq:unauthorized', h)
    return () => window.removeEventListener('aq:unauthorized', h)
  }, [])

  const login = async (l: string, p: string) => {
    const r = await api.login(l, p)
    setToken(r.token)
    setLoading(true)
    await refresh()
  }
  const logout = async () => { try { await api.logout() } catch {} setToken(null); setUser(null); setSchema(null) }

  return <AppCtx.Provider value={{ user, schema, loading, login, logout, refresh, toast, toasts }}>{children}</AppCtx.Provider>
}

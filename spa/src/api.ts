const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const API = BASE + '/aq_portal/api'
const TOKEN_KEY = 'aq_portal_token'

let memToken: string | null = null  // respaldo en memoria si el navegador bloquea localStorage (Safari privado, datos bloqueados)
export const store = {
  get: (k: string): string | null => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* sin almacenamiento */ } },
  del: (k: string) => { try { localStorage.removeItem(k) } catch { /* sin almacenamiento */ } },
}
export function getToken() { return store.get(TOKEN_KEY) ?? memToken }
export function setToken(t: string | null) { memToken = t; t ? store.set(TOKEN_KEY, t) : store.del(TOKEN_KEY) }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

async function call(method: string, path: string, body?: any, raw?: boolean) {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = 'Bearer ' + token
  let payload: any = undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(API + path, { method, headers, body: payload })
  if (raw) return res
  let data: any = null
  try { data = await res.json() } catch { data = null }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login')) {
      setToken(null)
      window.dispatchEvent(new CustomEvent('aq:unauthorized'))
    }
    throw new ApiError((data && data.error) || res.statusText, res.status)
  }
  return data
}

const qs = (params: Record<string, any>) => {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, typeof v === 'object' ? JSON.stringify(v) : String(v)) })
  const s = p.toString()
  return s ? '?' + s : ''
}

export function makeResourceApi(prefix: string) {
  const P = prefix
  return {
    prefix: P,
    list: (resource: string, params: Record<string, any> = {}) => call('GET', `${P}/r/${resource}` + qs(params)),
    read: (resource: string, id: number) => call('GET', `${P}/r/${resource}/${id}`),
    create: (resource: string, vals: any) => call('POST', `${P}/r/${resource}`, vals),
    defaults: (resource: string) => call('GET', `${P}/r/${resource}/defaults`),
    write: (resource: string, id: number, vals: any) => call('PUT', `${P}/r/${resource}/${id}`, vals),
    remove: (resource: string, id: number) => call('DELETE', `${P}/r/${resource}/${id}`),
    action: (resource: string, id: number, action: string) => call('POST', `${P}/r/${resource}/${id}/action/${action}`),
    messages: (resource: string, id: number) => call('GET', `${P}/r/${resource}/${id}/messages`),
    note: (resource: string, id: number, body: string, clientVisible?: boolean) => call('POST', `${P}/r/${resource}/${id}/note`, { body, client_visible: clientVisible }),
    attachments: (resource: string, id: number) => call('GET', `${P}/r/${resource}/${id}/attachments`),
    upload: (resource: string, id: number, files: FileList | File[]) => { const fd = new FormData(); Array.from(files).forEach(f => fd.append('file', f)); return call('POST', `${P}/r/${resource}/${id}/attachments`, fd) },
    nameSearch: (model: string, q: string, limit?: number, domain?: any[]) => call('GET', `${P}/name_search` + qs({ model, q, limit, domain: domain && domain.length ? domain : undefined })),
    schema: () => call('GET', `${P}/schema`),
    exportUrl: (resource: string, params: Record<string, any> = {}) => `${API}${P}/export/${resource}` + qs({ ...params, token: getToken() }),
  }
}
export type ResourceApi = ReturnType<typeof makeResourceApi>

export const ops = {
  mywork: () => call('GET', '/ops/mywork'),
  portfolio: () => call('GET', '/ops/portfolio'),
  command: (id: number) => call('GET', `/ops/projects/${id}/command`),
  clientHome: () => call('GET', '/ops/client/home'),
  kpis: (from?: string, to?: string, project_id?: number) => call('GET', '/ops/kpis' + qs({ from, to, project_id })),
  quickAdd: (vals: any) => call('POST', '/ops/r/items', vals),
  move: (id: number, vals: any) => call('POST', `/ops/items/${id}/move`, vals),
  timerStart: (vals: any) => call('POST', '/ops/timer/start', vals),
  timerStop: () => call('POST', '/ops/timer/stop'),
  week: (week?: string) => call('GET', '/ops/timesheets/week' + qs({ week })),
  approveWeek: (week: string, member_id?: number) => call('POST', '/ops/timesheets/approve-week', { week, member_id }),
  decide: (id: number, decision: string, reason?: string) => call('POST', `/ops/acceptances/${id}/decide`, { decision, reason }),
  answer: (id: number, answer: string) => call('POST', `/ops/questions/${id}/answer`, { answer }),
  notifications: (all?: boolean) => call('GET', '/ops/notifications' + qs({ all: all ? 1 : undefined })),
  notifUpdate: (id: number, vals: any) => call('POST', `/ops/notifications/${id}`, vals),
  notifReadAll: () => call('POST', '/ops/notifications/read-all'),
  ai: (path: string) => call('POST', `/ops/ai/${path}`),
  assist: (resource: string, id: number, body: any) => call('POST', `/ops/ai/assist/${resource}/${id}`, body),
  aiStatus: () => call('GET', '/ops/ai/status'),
  aiTest: () => call('POST', '/ops/ai/test'),
  aiModels: (reasoning: boolean) => call('POST', '/ops/ai/models', { reasoning }),
  live: (since?: string) => call('GET', '/ops/live' + qs({ since })),
  capacityForecast: (weeks = 4) => call('GET', '/ops/capacity/forecast' + qs({ weeks })),
  views: (resource?: string) => call('GET', '/ops/views' + qs({ resource })),
  saveView: (vals: any) => call('POST', '/ops/views', vals),
  invitees: (project_id: number, type_id: number) => call('GET', '/ops/sessions/invitees' + qs({ project_id, type_id })),
  deleteView: (id: number) => call('DELETE', `/ops/views/${id}`),
  icsUrl: () => `${API}/ops/calendar.ics?token=${encodeURIComponent(getToken() || '')}`,
}

export const api = {
  mfaVerify: (token: string, code: string) => call('POST', '/auth/mfa/verify', { token, code }),
  mfaSetup: () => call('POST', '/me/mfa/setup'),
  mfaConfirm: (code: string) => call('POST', '/me/mfa/confirm', { code }),
  mfaDisable: () => call('POST', '/me/mfa/disable'),
  emitEvent: (vals: any) => call('POST', '/events/emit', vals),
  get: (path: string, params: Record<string, any> = {}) => call('GET', path + qs(params)),
  post: (path: string, body?: any) => call('POST', path, body),
  put: (path: string, body?: any) => call('PUT', path, body),
  del: (path: string) => call('DELETE', path),
  // auth
  login: (login: string, password: string) => call('POST', '/auth/login', { login, password }),
  logout: () => call('POST', '/auth/logout'),
  me: () => call('GET', '/auth/me'),
  forgot: (login: string) => call('POST', '/auth/forgot', { login }),
  reset: (token: string, password: string) => call('POST', '/auth/reset', { token, password }),
  changePassword: (current: string, password: string) => call('POST', '/auth/change-password', { current, password }),
  schema: () => call('GET', '/schema'),
  // records
  list: (resource: string, params: Record<string, any> = {}) => call('GET', `/r/${resource}` + qs(params)),
  read: (resource: string, id: number) => call('GET', `/r/${resource}/${id}`),
  create: (resource: string, vals: any) => call('POST', `/r/${resource}`, vals),
  write: (resource: string, id: number, vals: any) => call('PUT', `/r/${resource}/${id}`, vals),
  remove: (resource: string, id: number) => call('DELETE', `/r/${resource}/${id}`),
  action: (resource: string, id: number, action: string) => call('POST', `/r/${resource}/${id}/action/${action}`),
  messages: (resource: string, id: number) => call('GET', `/r/${resource}/${id}/messages`),
  note: (resource: string, id: number, body: string) => call('POST', `/r/${resource}/${id}/note`, { body }),
  attachments: (resource: string, id: number) => call('GET', `/r/${resource}/${id}/attachments`),
  upload: (resource: string, id: number, files: FileList | File[]) => {
    const fd = new FormData()
    Array.from(files).forEach(f => fd.append('file', f))
    return call('POST', `/r/${resource}/${id}/attachments`, fd)
  },
  deleteAttachment: (id: number) => call('DELETE', `/attachments/${id}`),
  downloadUrl: (id: number) => `${API}/attachments/${id}/download?token=${encodeURIComponent(getToken() || '')}`,
  nameSearch: (model: string, q: string) => call('GET', '/name_search' + qs({ model, q })),
  dashboard: (from?: string, to?: string) => call('GET', '/dashboard' + qs({ from, to })),
  calendar: (from?: string, to?: string) => call('GET', '/calendar' + qs({ from, to })),
  routines: (date?: string) => call('GET', '/routines/today' + qs({ date })),
  toggleRoutine: (id: number, done?: boolean, notes?: string) => call('POST', `/routines/${id}/toggle`, { done, notes }),
  generateReport: (type: string, from?: string, to?: string) => call('POST', '/reports/generate', { type, from, to }),
  alerts: () => call('GET', '/alerts'),
  dismissAlert: (id: number) => call('POST', `/alerts/${id}/dismiss`),
  recomputeAlerts: () => call('POST', '/alerts/recompute'),
  prefs: (vals: any) => call('PUT', '/me/preferences', vals),
}

export const fmtMoney = (n: any) => (Number(n) || 0).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })
const pad = (n: number) => String(n).padStart(2, '0')
/** 'YYYY-MM-DD' de un Date en hora LOCAL (nunca toISOString, que devuelve la fecha en UTC). */
export const isoLocal = (x: Date) => `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`
/** Datetime de Odoo ('YYYY-MM-DD HH:MM:SS', siempre UTC) → Date local */
export const fromOdoo = (s: string) => new Date(s.replace(' ', 'T') + (s.endsWith('Z') ? '' : 'Z'))
/** Date local → datetime de Odoo en UTC */
export const toOdoo = (x: Date) => x.toISOString().slice(0, 19).replace('T', ' ')
export const fmtDate = (d?: string | null) => d ? (d.length > 10 ? fromOdoo(d) : new Date(d + 'T00:00:00')).toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' }) : ''
/** Hora local (HH:MM) de un datetime de Odoo */
export const fmtTime = (d?: string | null) => { if (!d || d.length <= 10) return ''; const x = fromOdoo(d); return `${pad(x.getHours())}:${pad(x.getMinutes())}` }
export const fmtDateTime = (d?: string | null) => d ? `${fmtDate(d)} ${fmtTime(d)}`.trim() : ''
/** Valor para <input type="datetime-local"> (hora local) desde un datetime de Odoo (UTC) */
export const toLocalInput = (d?: string | null) => { if (!d) return ''; const x = fromOdoo(d); return `${isoLocal(x)}T${pad(x.getHours())}:${pad(x.getMinutes())}` }
/** Valor de <input type="datetime-local"> (hora local) → datetime de Odoo (UTC) */
export const fromLocalInput = (v: string) => v ? toOdoo(new Date(v)) : null
export const today = () => isoLocal(new Date())
export const addDays = (d: string, n: number) => { const x = new Date(d + 'T00:00:00'); x.setDate(x.getDate() + n); return isoLocal(x) }

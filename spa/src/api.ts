const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const API = BASE + '/aq_portal/api'
const TOKEN_KEY = 'aq_portal_token'

export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(t: string | null) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) }

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
    write: (resource: string, id: number, vals: any) => call('PUT', `${P}/r/${resource}/${id}`, vals),
    remove: (resource: string, id: number) => call('DELETE', `${P}/r/${resource}/${id}`),
    action: (resource: string, id: number, action: string) => call('POST', `${P}/r/${resource}/${id}/action/${action}`),
    messages: (resource: string, id: number) => call('GET', `${P}/r/${resource}/${id}/messages`),
    note: (resource: string, id: number, body: string, clientVisible?: boolean) => call('POST', `${P}/r/${resource}/${id}/note`, { body, client_visible: clientVisible }),
    attachments: (resource: string, id: number) => call('GET', `${P}/r/${resource}/${id}/attachments`),
    upload: (resource: string, id: number, files: FileList | File[]) => { const fd = new FormData(); Array.from(files).forEach(f => fd.append('file', f)); return call('POST', `${P}/r/${resource}/${id}/attachments`, fd) },
    nameSearch: (model: string, q: string) => call('GET', `${P}/name_search` + qs({ model, q })),
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
  kpis: (from?: string, to?: string) => call('GET', '/ops/kpis' + qs({ from, to })),
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
  live: (since?: string) => call('GET', '/ops/live' + qs({ since })),
  capacityForecast: (weeks = 4) => call('GET', '/ops/capacity/forecast' + qs({ weeks })),
  views: (resource?: string) => call('GET', '/ops/views' + qs({ resource })),
  saveView: (vals: any) => call('POST', '/ops/views', vals),
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
export const fmtDate = (d?: string | null) => d ? new Date(d.length > 10 ? d.replace(' ', 'T') + 'Z' : d + 'T00:00:00').toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' }) : ''
export const today = () => new Date().toISOString().slice(0, 10)
export const addDays = (d: string, n: number) => { const x = new Date(d + 'T00:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }

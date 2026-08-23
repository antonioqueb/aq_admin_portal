import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'
import { useApp } from '../context'

export default function ChangePassword({ forced }: { forced?: boolean }) {
  const { refresh, toast, logout } = useApp()
  const nav = useNavigate()
  const [c, setC] = useState(''); const [p1, setP1] = useState(''); const [p2, setP2] = useState(''); const [err, setErr] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr('')
    if (p1 !== p2) { setErr('Las contraseñas no coinciden.'); return }
    try { const r = await api.changePassword(c, p1); setToken(r.token); toast('Contraseña actualizada', 'ok'); await refresh(); nav('/') } catch (e: any) { setErr(e.message) }
  }
  const inner = (
    <form onSubmit={submit} className={forced ? 'box' : 'card'} style={{ maxWidth: 440 }}>
      <h1>{forced ? 'Debes cambiar tu contraseña' : 'Cambiar contraseña'}</h1>
      <p className="sub">Por seguridad, establece una contraseña propia antes de continuar.</p>
      {err && <div className="alert err">{err}</div>}
      <div className="field"><label>Contraseña actual</label><input type="password" value={c} onChange={e => setC(e.target.value)} /></div>
      <div className="field"><label>Nueva contraseña</label><input type="password" value={p1} onChange={e => setP1(e.target.value)} /></div>
      <div className="field"><label>Confirmar</label><input type="password" value={p2} onChange={e => setP2(e.target.value)} /></div>
      <div className="toolbar"><button className="btn">Guardar</button>{forced && <button type="button" className="btn secondary" onClick={() => logout().then(() => nav('/login'))}>Salir</button>}</div>
    </form>
  )
  return forced ? <div className="login"><button className="theme-btn" style={{ position: 'fixed', top: 14, right: 14 }} onClick={() => { const t = (localStorage.getItem('aq_theme') || 'dark') === 'dark' ? 'light' : 'dark'; localStorage.setItem('aq_theme', t); document.documentElement.setAttribute('data-theme', t) }} aria-label="Tema">☀/☾</button>{inner}</div> : inner
}

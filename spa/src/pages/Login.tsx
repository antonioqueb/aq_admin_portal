import { FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'
import { useApp } from '../context'

export default function Login() {
  const { login, refresh } = useApp()
  const nav = useNavigate()
  const loc = useLocation() as any
  const [l, setL] = useState(''); const [p, setP] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const [mfaToken, setMfaToken] = useState<string | null>(null); const [code, setCode] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { await login(l, p); nav(loc.state?.from || '/') } catch (e: any) { if (e.mfa) setMfaToken(e.token); else setErr(e.message) } finally { setBusy(false) }
  }
  const verify = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { const r = await api.mfaVerify(mfaToken!, code); setToken(r.token); await refresh(); nav(loc.state?.from || '/') } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="login"><button className="theme-btn" style={{ position: 'fixed', top: 14, right: 14 }} onClick={() => { const t = (localStorage.getItem('aq_theme') || 'dark') === 'dark' ? 'light' : 'dark'; localStorage.setItem('aq_theme', t); document.documentElement.setAttribute('data-theme', t) }} aria-label="Tema">☀/☾</button>
      <form className="box" onSubmit={mfaToken ? verify : submit}>
        <img className="logo" src="/aq_admin_portal/static/description/logo.png" alt="Alphaqueb" />
        <h1>{mfaToken ? 'Verificación en dos pasos' : 'Portal Alphaqueb'}</h1>
        <p className="sub">{mfaToken ? 'Ingrese el código de su aplicación de autenticación.' : 'Administración · Operaciones · Control de entrega'}</p>
        {err && <div className="alert err">{err}</div>}
        {!mfaToken ? (<>
          <div className="field"><label>Usuario o correo</label><input type="text" value={l} onChange={e => setL(e.target.value)} autoFocus autoComplete="username" /></div>
          <div className="field"><label>Contraseña</label><input type="password" value={p} onChange={e => setP(e.target.value)} autoComplete="current-password" /></div>
        </>) : <div className="field"><label>Código de 6 dígitos</label><input type="text" inputMode="numeric" value={code} onChange={e => setCode(e.target.value)} autoFocus maxLength={6} /></div>}
        <button className="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>{busy ? 'Verificando…' : mfaToken ? 'Verificar' : 'Ingresar'}</button>
        <p style={{ textAlign: 'center', marginTop: 14, fontSize: 13 }}>{mfaToken ? <a href="#" onClick={e => { e.preventDefault(); setMfaToken(null) }}>Volver</a> : <Link to="/forgot-password">¿Olvidaste tu contraseña?</Link>}</p>
      </form>
    </div>
  )
}

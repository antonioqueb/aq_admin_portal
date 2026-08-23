import { FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context'

export default function Login() {
  const { login } = useApp()
  const nav = useNavigate()
  const loc = useLocation() as any
  const [l, setL] = useState(''); const [p, setP] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { await login(l, p); nav(loc.state?.from || '/') } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <img className="logo" src="/aq_admin_portal/static/description/logo.png" alt="AlphaQueb" />
        <h1>Portal administrativo</h1>
        <p className="sub">AlphaQueb Consulting · Control administrativo y operativo</p>
        {err && <div className="alert err">{err}</div>}
        <div className="field"><label>Usuario o correo</label><input type="text" value={l} onChange={e => setL(e.target.value)} autoFocus autoComplete="username" /></div>
        <div className="field"><label>Contraseña</label><input type="password" value={p} onChange={e => setP(e.target.value)} autoComplete="current-password" /></div>
        <button className="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
        <p style={{ textAlign: 'center', marginTop: 14, fontSize: 13 }}><Link to="/forgot-password">¿Olvidaste tu contraseña?</Link></p>
      </form>
    </div>
  )
}

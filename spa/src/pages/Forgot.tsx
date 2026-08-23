import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Forgot() {
  const [l, setL] = useState(''); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setMsg('')
    try { const r = await api.forgot(l); setMsg(r.message) } catch (e: any) { setErr(e.message) }
  }
  return (
    <div className="login"><button className="theme-btn" style={{ position: 'fixed', top: 14, right: 14 }} onClick={() => { const t = (localStorage.getItem('aq_theme') || 'dark') === 'dark' ? 'light' : 'dark'; localStorage.setItem('aq_theme', t); document.documentElement.setAttribute('data-theme', t) }} aria-label="Tema">☀/☾</button>
      <form className="box" onSubmit={submit}>
        <img className="logo" src="/aq_admin_portal/static/description/logo.png" alt="AlphaQueb" />
        <h1>Recuperar contraseña</h1>
        <p className="sub">Te enviaremos un enlace para establecer una nueva contraseña.</p>
        {msg && <div className="alert ok">{msg}</div>}
        {err && <div className="alert err">{err}</div>}
        <div className="field"><label>Usuario o correo</label><input type="text" value={l} onChange={e => setL(e.target.value)} autoFocus /></div>
        <button className="btn" style={{ width: '100%', justifyContent: 'center' }}>Enviar enlace</button>
        <p style={{ textAlign: 'center', marginTop: 14, fontSize: 13 }}><Link to="/login">Volver al inicio de sesión</Link></p>
      </form>
    </div>
  )
}

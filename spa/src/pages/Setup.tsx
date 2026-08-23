import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'
import { useApp } from '../context'

export default function Setup() {
  const { refresh } = useApp()
  const nav = useNavigate()
  const [st, setSt] = useState<any>(null)
  const [f, setF] = useState({ name: '', login: '', email: '', password: '', password2: '', setup_key: '' })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { api.get('/auth/status').then(s => { setSt(s); if (!s.needs_setup) nav('/login') }).catch(e => setErr(e.message)) }, [nav])
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr('')
    if (f.password !== f.password2) { setErr('Las contraseñas no coinciden.'); return }
    setBusy(true)
    try { const r = await api.post('/auth/setup', f); setToken(r.token); await refresh(); nav('/') } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <img src="/aq_admin_portal/static/description/icon.png" width={44} alt="" style={{ borderRadius: 8, marginBottom: 10 }} />
        <h1>Configuración inicial</h1>
        <p className="sub">Aún no existe ningún usuario del portal. Crea la primera cuenta de <b>Dirección</b>; desde ella podrás dar de alta al resto del equipo sin usar Odoo.</p>
        {err && <div className="alert err">{err}</div>}
        <div className="field"><label>Nombre</label><input type="text" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} autoFocus /></div>
        <div className="field"><label>Login (usuario o correo)</label><input type="text" value={f.login} onChange={e => setF({ ...f, login: e.target.value })} /></div>
        <div className="field"><label>Correo</label><input type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></div>
        <div className="field"><label>Contraseña (mín. 8, letras y números)</label><input type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></div>
        <div className="field"><label>Confirmar contraseña</label><input type="password" value={f.password2} onChange={e => setF({ ...f, password2: e.target.value })} /></div>
        {st?.setup_key_required && <div className="field"><label>Clave de configuración (parámetro aq_admin_portal.setup_key)</label><input type="password" value={f.setup_key} onChange={e => setF({ ...f, setup_key: e.target.value })} /></div>}
        <button className="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={busy || !st}>{busy ? 'Creando…' : 'Crear cuenta de Dirección'}</button>
      </form>
    </div>
  )
}

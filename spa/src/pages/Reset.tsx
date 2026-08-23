import { FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'

export default function Reset() {
  const [sp] = useSearchParams(); const token = sp.get('token') || ''
  const nav = useNavigate()
  const [p1, setP1] = useState(''); const [p2, setP2] = useState(''); const [err, setErr] = useState(''); const [ok, setOk] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr('')
    if (p1 !== p2) { setErr('Las contraseñas no coinciden.'); return }
    try { await api.reset(token, p1); setOk(true); setTimeout(() => nav('/login'), 1800) } catch (e: any) { setErr(e.message) }
  }
  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <h1>Nueva contraseña</h1>
        <p className="sub">Mínimo 8 caracteres, combinando letras y números.</p>
        {!token && <div className="alert err">Enlace inválido: falta el token.</div>}
        {ok && <div className="alert ok">Contraseña establecida. Redirigiendo…</div>}
        {err && <div className="alert err">{err}</div>}
        <div className="field"><label>Contraseña</label><input type="password" value={p1} onChange={e => setP1(e.target.value)} autoFocus /></div>
        <div className="field"><label>Confirmar contraseña</label><input type="password" value={p2} onChange={e => setP2(e.target.value)} /></div>
        <button className="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={!token}>Guardar contraseña</button>
        <p style={{ textAlign: 'center', marginTop: 14, fontSize: 13 }}><Link to="/login">Ir al inicio de sesión</Link></p>
      </form>
    </div>
  )
}

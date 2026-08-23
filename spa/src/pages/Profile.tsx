import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'

export default function Profile() {
  const { user, refresh, toast } = useApp()
  const [name, setName] = useState(user?.name || '')
  const [notify, setNotify] = useState(!!user?.notify_alerts)
  if (!user) return null
  const save = async () => { try { await api.prefs({ name, notify_alerts: notify }); await refresh(); toast('Preferencias guardadas', 'ok') } catch (e: any) { toast(e.message, 'err') } }
  return (
    <div>
      <h1>Mi perfil</h1>
      <div className="card" style={{ maxWidth: 520 }}>
        <div className="field"><label>Nombre</label><input type="text" value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="field"><label>Login</label><input type="text" value={user.login} disabled /></div>
        <div className="field"><label>Correo</label><input type="text" value={user.email} disabled /></div>
        <label className="check"><input type="checkbox" checked={notify} onChange={e => setNotify(e.target.checked)} /> Recibir resumen diario de alertas por correo</label>
        <div className="toolbar"><button className="btn" onClick={save}>Guardar</button><Link className="btn secondary" to="/change-password">Cambiar contraseña</Link></div>
      </div>
    </div>
  )
}

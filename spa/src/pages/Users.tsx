import { useCallback, useEffect, useState } from 'react'
import { api, fmtDate } from '../api'
import { useApp } from '../context'
import Many2one from '../components/Many2one'

const ROLES: [string, string][] = [['direccion', 'Dirección'], ['coordinacion', 'Coordinación administrativa'], ['equipo', 'Integrante del equipo'], ['consulta', 'Solo consulta']]
const EMPTY = { name: '', login: '', email: '', role: 'coordinacion', member_id: null as any, password: '', send_invitation: true, notify_alerts: true, active: true }

export default function Users() {
  const { toast } = useApp()
  const [users, setUsers] = useState<any[]>([])
  const [edit, setEdit] = useState<any | null>(null)
  const load = useCallback(() => api.users().then(r => setUsers(r.users)).catch(e => toast(e.message, 'err')), [toast])
  useEffect(() => { load() }, [load])
  const save = async () => {
    try {
      const vals = { ...edit, member_id: edit.member_id?.id || null }
      if (edit.id) await api.updateUser(edit.id, vals); else await api.createUser(vals)
      toast(edit.id ? 'Usuario actualizado' : 'Usuario creado; se envió el correo para establecer contraseña', 'ok'); setEdit(null); load()
    } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div>
      <div className="toolbar"><div><h1>Usuarios externos del portal</h1><div style={{ color: '#6b7280', fontSize: 12 }}>Cuentas independientes de Odoo con su propio login, contraseña y recuperación.</div></div><span className="spacer" /><button className="btn" onClick={() => setEdit({ ...EMPTY })}>+ Nuevo usuario</button></div>
      {edit && (
        <div className="card" style={{ borderColor: '#714B67' }}>
          <h2>{edit.id ? 'Editar usuario' : 'Nuevo usuario'}</h2>
          <div className="grid cols-2">
            <div className="field"><label>Nombre</label><input type="text" value={edit.name} onChange={e => setEdit({ ...edit, name: e.target.value })} /></div>
            <div className="field"><label>Login (usuario o correo)</label><input type="text" value={edit.login} onChange={e => setEdit({ ...edit, login: e.target.value })} /></div>
            <div className="field"><label>Correo</label><input type="email" value={edit.email} onChange={e => setEdit({ ...edit, email: e.target.value })} /></div>
            <div className="field"><label>Rol</label><select value={edit.role} onChange={e => setEdit({ ...edit, role: e.target.value })}>{ROLES.map(r => <option key={r[0]} value={r[0]}>{r[1]}</option>)}</select></div>
            <div className="field"><label>Integrante del equipo relacionado</label><Many2one model="aq.portal.member" value={edit.member_id} onChange={v => setEdit({ ...edit, member_id: v })} /></div>
            <div className="field"><label>Contraseña temporal (opcional; deberá cambiarla al ingresar)</label><input type="password" value={edit.password || ''} onChange={e => setEdit({ ...edit, password: e.target.value })} /></div>
            <label className="check"><input type="checkbox" checked={edit.notify_alerts} onChange={e => setEdit({ ...edit, notify_alerts: e.target.checked })} /> Recibir resumen diario de alertas</label>
            {edit.id ? <label className="check"><input type="checkbox" checked={edit.active} onChange={e => setEdit({ ...edit, active: e.target.checked })} /> Activo</label>
              : <label className="check"><input type="checkbox" checked={edit.send_invitation} onChange={e => setEdit({ ...edit, send_invitation: e.target.checked })} /> Enviar correo de bienvenida con enlace para establecer contraseña</label>}
          </div>
          <div className="toolbar"><button className="btn" onClick={save}>Guardar</button><button className="btn secondary" onClick={() => setEdit(null)}>Cancelar</button></div>
        </div>
      )}
      <div className="card">
        <div className="table-wrap"><table className="list"><thead><tr><th>Nombre</th><th>Login</th><th>Correo</th><th>Rol</th><th>Integrante</th><th>Último acceso</th><th>Estado</th><th></th></tr></thead>
          <tbody>{users.map(u => (
            <tr key={u.id}><td>{u.name}</td><td>{u.login}</td><td>{u.email}</td><td>{ROLES.find(r => r[0] === u.role)?.[1]}</td><td>{u.member_name || '—'}</td><td>{u.last_login ? fmtDate(u.last_login) : 'nunca'}</td><td>{u.active ? <span className="badge ok">activo</span> : <span className="badge err">inactivo</span>}{u.must_change_password && <span className="badge warn" style={{ marginLeft: 4 }}>debe cambiar contraseña</span>}</td>
              <td style={{ whiteSpace: 'nowrap' }}>
                <button className="btn link small" onClick={() => setEdit({ ...u, member_id: u.member_id ? { id: u.member_id, name: u.member_name } : null, password: '' })}>editar</button>
                <button className="btn link small" onClick={() => api.sendReset(u.id).then(() => toast('Enlace enviado a ' + u.email, 'ok')).catch(e => toast(e.message, 'err'))}>enviar enlace</button>
                <button className="btn link small" onClick={() => api.killSessions(u.id).then(() => toast('Sesiones cerradas', 'ok'))}>cerrar sesiones</button>
              </td></tr>
          ))}</tbody></table></div>
      </div>
    </div>
  )
}

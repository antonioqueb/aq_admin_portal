import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'

export default function Profile() {
  const { user, refresh, toast } = useApp()
  const [name, setName] = useState(user?.name || '')
  const [notify, setNotify] = useState(!!user?.notify_alerts)
  const [setup, setSetup] = useState<{ secret: string; otpauth: string } | null>(null)
  const [code, setCode] = useState('')
  const forced = localStorage.getItem('aq_mfa_setup') === '1' && user?.mfa_required && !user?.mfa_enabled
  useEffect(() => { if (forced) begin() }, [])  // eslint-disable-line
  if (!user) return null
  const save = async () => { try { await api.prefs({ name, notify_alerts: notify }); await refresh(); toast('Preferencias guardadas', 'ok') } catch (e: any) { toast(e.message, 'err') } }
  const begin = async () => { try { setSetup(await api.mfaSetup()) } catch (e: any) { toast(e.message, 'err') } }
  const confirm = async () => { try { await api.mfaConfirm(code); localStorage.removeItem('aq_mfa_setup'); setSetup(null); await refresh(); toast('MFA activado', 'ok') } catch (e: any) { toast(e.message, 'err') } }
  const disable = async () => { if (!window.confirm('¿Desactivar MFA?')) return; try { await api.mfaDisable(); await refresh(); toast('MFA desactivado', 'ok') } catch (e: any) { toast(e.message, 'err') } }
  return (
    <div>
      <h1>Mi perfil</h1>
      {forced && <div className="alert info">Su perfil exige verificación en dos pasos (MFA). Actívela ahora para continuar con normalidad.</div>}
      <div className="grid cols-2">
        <div className="card">
          <h3>Identidad</h3>
          <div className="field"><label>Nombre</label><input type="text" value={name} onChange={e => setName(e.target.value)} /></div>
          <div className="field"><label>Login</label><input type="text" value={user.login} disabled /></div>
          <div className="field"><label>Correo</label><input type="text" value={user.email} disabled /></div>
          <div className="field"><label>Aplicaciones</label><div>{user.apps.map(a => <span key={a} className="badge primary" style={{ marginRight: 6 }}>{a === 'ops' ? 'Operaciones' : 'Administración'}</span>)}{user.organization_name && <span className="badge">{user.organization_name}</span>}</div></div>
          <label className="check"><input type="checkbox" checked={notify} onChange={e => setNotify(e.target.checked)} /> Recibir resúmenes por correo</label>
          <div className="toolbar"><button className="btn" onClick={save}>Guardar</button><Link className="btn secondary" to="/change-password">Cambiar contraseña</Link></div>
        </div>
        <div className="card">
          <h3>Verificación en dos pasos (MFA)</h3>
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>Obligatoria para perfiles internos, socios y aprobadores. Use Google Authenticator, Microsoft Authenticator, 1Password o similar.</p>
          <div style={{ marginBottom: 10 }}>{user.mfa_enabled ? <span className="badge ok">Activo</span> : <span className={'badge ' + (user.mfa_required ? 'err' : '')}>{user.mfa_required ? 'Requerido · no activado' : 'No activado'}</span>}</div>
          {!setup && !user.mfa_enabled && <button className="btn" onClick={begin}>Activar MFA</button>}
          {setup && (
            <div>
              <div className="field"><label>1. Agregue esta clave en su aplicación (o abra el enlace desde el móvil)</label><div className="mono" style={{ padding: 8, border: '1px solid var(--border2)', borderRadius: 6 }}>{setup.secret}</div><a href={setup.otpauth} style={{ fontSize: 12 }}>Abrir en app de autenticación</a></div>
              <div className="field"><label>2. Escriba el código generado</label><input type="text" inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value)} /></div>
              <div className="toolbar"><button className="btn" onClick={confirm}>Confirmar y activar</button><button className="btn secondary" onClick={() => setSetup(null)}>Cancelar</button></div>
            </div>
          )}
          {user.mfa_enabled && !user.mfa_required && <button className="btn secondary" onClick={disable}>Desactivar MFA</button>}
        </div>
      </div>
    </div>
  )
}

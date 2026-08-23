import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fmtDate } from '../api'
import { useApp } from '../context'

export default function Attachments({ resource, id, canWrite }: { resource: string; id: number; canWrite: boolean }) {
  const { toast, user, rapi, app } = useApp()
  const [items, setItems] = useState<any[]>([])
  const inp = useRef<HTMLInputElement>(null)
  const load = useCallback(() => rapi.attachments(resource, id).then(r => setItems(r.attachments)).catch(() => {}), [resource, id])
  useEffect(() => { load() }, [load])
  const upload = async (files: FileList | null) => {
    if (!files || !files.length) return
    try { await rapi.upload(resource, id, files); toast('Archivo(s) subido(s)', 'ok'); load() } catch (e: any) { toast(e.message, 'err') }
  }
  const del = async (a: any) => {
    if (!confirm(`¿Eliminar "${a.name}"? Los documentos sensibles no deben eliminarse sin validación.`)) return
    try { await api.deleteAttachment(a.id); load() } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div>
      {canWrite && (
        <div className="dropzone" onClick={() => inp.current?.click()} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files) }}>
          Arrastra archivos aquí o haz clic para subir evidencia / documentos
          <input ref={inp} type="file" multiple style={{ display: 'none' }} onChange={e => upload(e.target.files)} />
        </div>
      )}
      {items.length === 0 && <div className="empty">Sin archivos</div>}
      <ul className="timeline">
        {items.map(a => (
          <li key={a.id}>
            <a href={api.downloadUrl(a.id)} target="_blank" rel="noreferrer">{a.name}</a>
            <span className="meta"> · {(a.size / 1024).toFixed(0)} KB · {fmtDate(a.date)}</span>
            {app === 'admin' && (user?.role === 'direccion' || user?.role === 'coordinacion') && <button className="btn link small" onClick={() => del(a)}>eliminar</button>}
          </li>
        ))}
      </ul>
    </div>
  )
}

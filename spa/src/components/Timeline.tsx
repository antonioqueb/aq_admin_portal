import { useCallback, useEffect, useState } from 'react'
import { api, fmtDate } from '../api'
import { useApp } from '../context'

const ACTION: Record<string, string> = { create: 'Creó', write: 'Modificó', unlink: 'Archivó/eliminó', action: 'Ejecutó', upload: 'Subió archivo', denied: 'Acceso denegado' }

export default function Timeline({ resource, id }: { resource: string; id: number }) {
  const { toast } = useApp()
  const [data, setData] = useState<{ messages: any[]; audit: any[] }>({ messages: [], audit: [] })
  const [note, setNote] = useState('')
  const load = useCallback(() => api.messages(resource, id).then(setData).catch(() => {}), [resource, id])
  useEffect(() => { load() }, [load])
  const send = async () => {
    if (!note.trim()) return
    try { await api.note(resource, id, note); setNote(''); toast('Nota registrada', 'ok'); load() } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div>
      <div className="field"><label>Registrar nota / evidencia (queda en la bitácora)</label><textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Ej. Se solicitó actualización por correo al responsable…" /></div>
      <button className="btn small" onClick={send}>Registrar nota</button>
      <h3 style={{ marginTop: 16 }}>Historial</h3>
      <ul className="timeline">
        {data.messages.map(m => (
          <li key={'m' + m.id}>
            <div className="meta">{fmtDate(m.date)} {m.date.slice(11, 16)} · {m.author}</div>
            {m.body && <div dangerouslySetInnerHTML={{ __html: m.body }} />}
            {m.tracking.map((t: any, i: number) => <div className="chg" key={i}>{t.field}: <s>{String(t.old || '—')}</s> → <b>{String(t.new || '—')}</b></div>)}
          </li>
        ))}
        {data.audit.map(a => (
          <li key={'a' + a.id}><div className="meta">{fmtDate(a.date)} {a.date.slice(11, 16)} · {a.user || 'sistema'} · {ACTION[a.action] || a.action}</div><div>{a.summary}</div></li>
        ))}
        {data.messages.length + data.audit.length === 0 && <li className="empty">Sin historial</li>}
      </ul>
    </div>
  )
}

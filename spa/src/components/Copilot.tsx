import { useState } from 'react'
import { api, ops } from '../api'
import { useApp } from '../context'

const TASKS: [string, string][] = [['summarize', 'Resumir'], ['next', 'Siguiente acción'], ['risks', 'Riesgos y dependencias'], ['questions', 'Preguntas abiertas'], ['criteria', 'Criterios de aceptación'], ['email', 'Correo al cliente'], ['draft', 'Redactar campo'], ['improve', 'Mejorar texto'], ['vision', 'Interpretar imágenes adjuntas']]

/** Copiloto disponible en todas las fichas (Administración y Operaciones). Solo propone; tú decides qué insertar. */
export default function Copilot({ resource, record, fields, value, set }: { resource: string; record: any; fields: Record<string, any>; value: (f: string) => any; set: (f: string, v: any) => void }) {
  const { app, toast, schema, user } = useApp()
  const [open, setOpen] = useState(false)
  const [task, setTask] = useState('summarize')
  const [field, setField] = useState('')
  const [instr, setInstr] = useState('')
  const [out, setOut] = useState('')
  const [busy, setBusy] = useState(false)
  const external = !!(schema?.is_external || user?.is_external)
  const textFields = Object.values(fields).filter((f: any) => ['text', 'html', 'char'].includes(f.type) && !f.readonly)
  const run = async () => {
    setBusy(true)
    try {
      const body = { task, field: field || undefined, text: field && task === 'improve' ? String(value(field) || '') : undefined, instructions: instr || undefined }
      const r = app === 'ops' ? await ops.assist(resource, record.id, body) : await api.post(`/ai/assist/${resource}/${record.id}`, body)
      setOut(r.text || ''); if (!r.ai) toast('IA sin conexión: respuesta heurística. Configure DEEPSEEK_API_KEY.', 'info')
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const insert = () => { if (!field || !out) return; const f = fields[field]; set(field, f.type === 'html' ? '<p>' + out.replace(/\n/g, '<br/>') + '</p>' : out); toast('Insertado en ' + f.string + ' (guarda para confirmar)', 'ok') }
  return (
    <div className="copilot-wrap">
      <button className={'btn secondary small copilot-btn' + (open ? ' on' : '')} onClick={() => setOpen(o => !o)}>✦ Copiloto</button>
      {open && (
        <div className="copilot">
          <h4>Copiloto · propone, no decide</h4>
          <div className="chip-row">{TASKS.filter(t => !external || ['summarize', 'questions', 'draft', 'improve'].includes(t[0])).map(t => <button key={t[0]} className={task === t[0] ? 'on' : ''} onClick={() => setTask(t[0])}>{t[1]}</button>)}</div>
          <div className="grid cols-2" style={{ gap: 8 }}>
            {(task === 'draft' || task === 'improve' || task === 'criteria' || task === 'email') && <div className="field"><label>Campo objetivo</label><select value={field} onChange={e => setField(e.target.value)}><option value="">—</option>{textFields.map((f: any) => <option key={f.name} value={f.name}>{f.string}</option>)}</select></div>}
            <div className="field"><label>Instrucciones (opcional)</label><input type="text" value={instr} onChange={e => setInstr(e.target.value)} placeholder="Ej. tono formal, máximo 80 palabras…" /></div>
          </div>
          <div className="toolbar"><button className="btn small" disabled={busy} onClick={run}>{busy ? 'Pensando…' : 'Generar'}</button>{out && field && <button className="btn secondary small" onClick={insert}>Insertar en {fields[field]?.string}</button>}{out && <button className="btn link small" onClick={() => navigator.clipboard?.writeText(out)}>Copiar</button>}</div>
          {out && <div className="html-content" style={{ whiteSpace: 'pre-wrap', maxHeight: 260 }}>{out}</div>}
          <div className="disclaimer">La IA no aprueba cambios, no altera alcance ni fechas, no acepta entregables ni envía comunicaciones vinculantes. Todo lo que insertes queda como borrador hasta que guardes.</div>
        </div>
      )}
    </div>
  )
}

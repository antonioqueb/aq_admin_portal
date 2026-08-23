import { FieldDef } from '../context'
import { fmtDate, fmtMoney } from '../api'
import Many2one, { Many2many } from './Many2one'

export function selLabel(f: FieldDef | undefined, v: any) {
  if (!f || !f.selection) return v
  const m = f.selection.find(s => s[0] === v)
  return m ? m[1] : v
}

/** Celda de lista: representación de solo lectura */
export function Cell({ f, v }: { f: FieldDef | undefined; v: any }) {
  if (!f) return <>{v == null ? '' : String(v)}</>
  if (v == null || v === '') return <span style={{ color: '#9ca3af' }}>—</span>
  switch (f.type) {
    case 'boolean': return v ? <span className="badge ok">Sí</span> : <span className="badge">No</span>
    case 'many2one': return <>{v.name}</>
    case 'many2many': case 'one2many': return <>{Array.isArray(v) ? v.length : 0}</>
    case 'date': return <>{fmtDate(v)}</>
    case 'datetime': return <>{fmtDate(v)} {v.slice(11, 16)}</>
    case 'monetary': return <>{fmtMoney(v)}</>
    case 'float': return <>{Number(v).toLocaleString('es-MX', { maximumFractionDigits: 2 })}</>
    case 'selection': return <Badge f={f} v={v} />
    case 'html': return <span dangerouslySetInnerHTML={{ __html: String(v).replace(/<[^>]+>/g, ' ').slice(0, 80) }} />
    case 'text': return <>{String(v).slice(0, 90)}{String(v).length > 90 ? '…' : ''}</>
    default: return <>{String(v)}</>
  }
}

const BAD = ['vencid', 'detenid', 'bloquead', 'critic', 'incumplid', 'rechaz', 'perdid', 'faltante', 'materializ', 'incobrable', 'escalad', 'obsolet', 'extravi', 'cancel']
const GOOD = ['pagad', 'cerrad', 'cumplid', 'aprobad', 'autorizad', 'aceptad', 'ganad', 'vigente', 'activo', 'cobrad', 'facturad', 'completad', 'implementad', 'validad', 'recibid', 'controlad', 'firmad', 'emitida', 'enviada', 'entregad']
const WARN = ['por_vencer', 'pendiente', 'parcial', 'alto', 'medio', 'en_revision', 'en_validacion', 'pausad', 'mitigando', 'borrador', 'programada', 'analisis']
export function Badge({ f, v }: { f: FieldDef; v: string }) {
  const s = String(v)
  let cls = ''
  if (BAD.some(x => s.includes(x))) cls = 'err'
  else if (GOOD.some(x => s.includes(x))) cls = 'ok'
  else if (WARN.some(x => s.includes(x))) cls = 'warn'
  return <span className={'badge ' + cls}>{selLabel(f, v)}</span>
}

interface InputProps { f: FieldDef; value: any; onChange: (v: any) => void; disabled?: boolean }

/** Editor de campo según el tipo del esquema */
export function Input({ f, value, onChange, disabled }: InputProps) {
  const dis = disabled || f.readonly
  switch (f.type) {
    case 'boolean':
      return <label className="check"><input type="checkbox" checked={!!value} disabled={dis} onChange={e => onChange(e.target.checked)} /> <span>{value ? 'Sí' : 'No'}</span></label>
    case 'selection':
      return (
        <select value={value ?? ''} disabled={dis} onChange={e => onChange(e.target.value || null)}>
          <option value="">—</option>
          {(f.selection || []).map(s => <option key={s[0]} value={s[0]}>{s[1]}</option>)}
        </select>
      )
    case 'many2one':
      return <Many2one model={f.relation!} value={value} onChange={onChange} disabled={dis} resource={f.relation_resource} />
    case 'many2many':
      return <Many2many model={f.relation!} value={value || []} onChange={onChange} disabled={dis} />
    case 'one2many':
      return <span className="badge">{(value || []).length} registros (ver pestaña)</span>
    case 'date':
      return <input type="date" value={value || ''} disabled={dis} onChange={e => onChange(e.target.value || null)} />
    case 'datetime':
      return <input type="datetime-local" value={value ? value.replace(' ', 'T').slice(0, 16) : ''} disabled={dis} onChange={e => onChange(e.target.value ? e.target.value.replace('T', ' ') + ':00' : null)} />
    case 'integer':
      return <input type="number" step="1" value={value ?? ''} disabled={dis} onChange={e => onChange(e.target.value === '' ? null : parseInt(e.target.value))} />
    case 'float': case 'monetary':
      return <input type="number" step="0.01" value={value ?? ''} disabled={dis} onChange={e => onChange(e.target.value === '' ? null : parseFloat(e.target.value))} />
    case 'text':
      return <textarea value={value || ''} disabled={dis} onChange={e => onChange(e.target.value)} />
    case 'html':
      return dis ? <div className="html-content" dangerouslySetInnerHTML={{ __html: value || '' }} /> : <textarea style={{ minHeight: 200 }} value={value || ''} disabled={dis} onChange={e => onChange(e.target.value)} placeholder="Contenido (se permite HTML básico)" />
    default:
      return <input type={f.name.includes('email') ? 'email' : 'text'} value={value || ''} disabled={dis} onChange={e => onChange(e.target.value)} />
  }
}

export function FieldRow({ f, value, onChange, disabled, canDirection }: InputProps & { canDirection: boolean }) {
  const locked = !!f.direction_only && !canDirection
  return (
    <div className={'field' + (f.direction_only ? ' dir' : '')}>
      <label>{f.string}{f.required && <span className="req"> *</span>}</label>
      <Input f={f} value={value} onChange={onChange} disabled={disabled || locked} />
      {f.help && <div className="help">{f.help}</div>}
    </div>
  )
}

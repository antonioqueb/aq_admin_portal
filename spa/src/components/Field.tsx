import { FieldDef } from '../context'
import { fmtDate, fmtMoney, fmtTime, toLocalInput, fromLocalInput } from '../api'
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
    case 'datetime': return <>{fmtDate(v)} {fmtTime(v)}</>
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

interface InputProps { f: FieldDef; value: any; onChange: (v: any) => void; disabled?: boolean; invalid?: boolean }

/** Editor de campo según el tipo del esquema */
export function Input({ f, value, onChange, disabled, invalid }: InputProps) {
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
      return <Many2one model={f.relation!} value={value} onChange={onChange} disabled={dis} resource={f.relation_resource} domain={f.domain} invalid={invalid} />
    case 'many2many':
      return <Many2many model={f.relation!} value={value || []} onChange={onChange} disabled={dis} />
    case 'one2many':
      return <span className="badge">{(value || []).length} registros (ver pestaña)</span>
    case 'date':
      return <input type="date" value={value || ''} disabled={dis} onChange={e => onChange(e.target.value || null)} />
    case 'datetime':
      return <input type="datetime-local" value={toLocalInput(value)} disabled={dis} onChange={e => onChange(fromLocalInput(e.target.value))} />
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

export function FieldRow({ f, value, onChange, disabled, canDirection, invalid }: InputProps & { canDirection: boolean }) {
  const locked = (!!f.direction_only && !canDirection) || !!f.readonly  // los campos calculados/controlados por acciones no se editan
  return (
    <div className={'field' + (f.direction_only ? ' dir' : '') + (invalid ? ' invalid' : '') + (f.readonly ? ' ro' : '')} data-field={f.name}>
      <label>{f.string}{f.required && !f.readonly && <span className="req"> *</span>}</label>
      <Input f={f} value={value} onChange={onChange} disabled={disabled || locked} invalid={invalid} />
      {invalid && <div className="help err">Este campo es obligatorio.</div>}
      {f.help && <div className="help">{f.help}</div>}
    </div>
  )
}

/** ¿El valor cuenta como vacío para efectos de "obligatorio"? (booleanos nunca lo son) */
export function isEmptyValue(f: FieldDef, v: any) {
  if (f.type === 'boolean') return false
  if (v === null || v === undefined || v === '') return true
  if (Array.isArray(v)) return v.length === 0
  return false
}

/** Campos obligatorios y editables que quedarían vacíos. */
export function missingRequired(fields: Record<string, FieldDef>, value: (f: string) => any) {
  return Object.values(fields).filter(f => f.required && !f.readonly && f.type !== 'one2many' && isEmptyValue(f, value(f.name)))
}

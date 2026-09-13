import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'

type Opt = { id: number; name: string }
interface Props { model: string; value: Opt | null; onChange: (v: Opt | null) => void; disabled?: boolean; resource?: string | null; domain?: any[]; invalid?: boolean }

/**
 * Selector de registro relacionado. El valor solo queda establecido al ELEGIR una opción de la lista
 * (clic, Enter o, si hay una sola coincidencia, al salir del campo). Si el usuario escribe y no elige,
 * se muestra un aviso para que no crea que ya quedó guardado.
 */
export default function Many2one({ model, value, onChange, disabled, resource, domain, invalid }: Props) {
  const { rapi, base } = useApp()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [opts, setOpts] = useState<Opt[]>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const optsRef = useRef<Opt[]>([])
  optsRef.current = opts
  const domKey = JSON.stringify(domain || [])
  useEffect(() => {
    if (!open) return
    setLoading(true)
    const t = setTimeout(() => rapi.nameSearch(model, q, undefined, domain).then(r => setOpts(r.results)).catch(() => setOpts([])).finally(() => setLoading(false)), 200)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, open, model, rapi, domKey])
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const pick = (o: Opt) => { onChange(o); setOpen(false); setQ('') }
  if (value && !open) {
    return (
      <div className="sel m2o">
        <input type="text" value={value.name} readOnly disabled={disabled} onClick={() => !disabled && setOpen(true)} style={{ cursor: disabled ? 'default' : 'pointer' }} />
        {resource && <Link to={`${base}/r/${resource}/${value.id}`} title="Abrir">↗</Link>}
        {!disabled && <a href="#" onClick={e => { e.preventDefault(); onChange(null) }} title="Quitar">✕</a>}
      </div>
    )
  }
  const pending = !open && !!q && !value
  return (
    <div className="m2o" ref={ref}>
      <input
        type="text"
        placeholder="Escribe para buscar y elige de la lista…"
        value={q}
        disabled={disabled}
        aria-invalid={invalid || pending || undefined}
        style={pending || invalid ? { borderColor: 'var(--danger)' } : undefined}
        onFocus={() => setOpen(true)}
        onChange={e => { setQ(e.target.value); setOpen(true) }}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); const o = optsRef.current[0]; if (o) pick(o) }
          if (e.key === 'Escape') { setOpen(false) }
        }}
        onBlur={() => {
          // única coincidencia y el usuario ya escribió algo: se toma como elegida (evita "escribí y no se guardó")
          const cur = optsRef.current
          if (q && cur.length === 1) pick(cur[0])
        }}
      />
      {open && (
        <div className="dd">
          {loading && opts.length === 0 && <div style={{ color: '#888' }}>Buscando…</div>}
          {!loading && opts.length === 0 && <div style={{ color: '#888' }}>Sin resultados</div>}
          {opts.map(o => <div key={o.id} onMouseDown={() => pick(o)}>{o.name}</div>)}
        </div>
      )}
      {pending && <div className="help err">Escribiste «{q}» pero no elegiste ninguna opción de la lista: el campo sigue vacío.</div>}
    </div>
  )
}

export function Many2many({ model, value, onChange, disabled, domain }: { model: string; value: Opt[]; onChange: (v: Opt[]) => void; disabled?: boolean; domain?: any[] }) {
  return (
    <div>
      {!disabled && <Many2one model={model} value={null} domain={domain} onChange={v => { if (v && !value.some(x => x.id === v.id)) onChange([...value, v]) }} />}
      <div className="chips">{value.map(v => <span key={v.id}>{v.name}{!disabled && <b onClick={() => onChange(value.filter(x => x.id !== v.id))}>✕</b>}</span>)}</div>
    </div>
  )
}

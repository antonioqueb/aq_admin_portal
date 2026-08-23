import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'

interface Props { model: string; value: { id: number; name: string } | null; onChange: (v: { id: number; name: string } | null) => void; disabled?: boolean; resource?: string | null }

export default function Many2one({ model, value, onChange, disabled, resource }: Props) {
  const { rapi, base } = useApp()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [opts, setOpts] = useState<{ id: number; name: string }[]>([])
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => rapi.nameSearch(model, q).then(r => setOpts(r.results)).catch(() => setOpts([])), 200)
    return () => clearTimeout(t)
  }, [q, open, model, rapi])
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  if (value && !open) {
    return (
      <div className="sel m2o">
        <input type="text" value={value.name} readOnly disabled={disabled} onClick={() => !disabled && setOpen(true)} style={{ cursor: disabled ? 'default' : 'pointer' }} />
        {resource && <Link to={`${base}/r/${resource}/${value.id}`} title="Abrir">↗</Link>}
        {!disabled && <a href="#" onClick={e => { e.preventDefault(); onChange(null) }} title="Quitar">✕</a>}
      </div>
    )
  }
  return (
    <div className="m2o" ref={ref}>
      <input type="text" placeholder="Buscar…" value={q} disabled={disabled} onFocus={() => setOpen(true)} onChange={e => { setQ(e.target.value); setOpen(true) }} />
      {open && (
        <div className="dd">
          {opts.length === 0 && <div style={{ color: '#888' }}>Sin resultados</div>}
          {opts.map(o => <div key={o.id} onMouseDown={() => { onChange(o); setOpen(false); setQ('') }}>{o.name}</div>)}
        </div>
      )}
    </div>
  )
}

export function Many2many({ model, value, onChange, disabled }: { model: string; value: { id: number; name: string }[]; onChange: (v: { id: number; name: string }[]) => void; disabled?: boolean }) {
  return (
    <div>
      {!disabled && <Many2one model={model} value={null} onChange={v => { if (v && !value.some(x => x.id === v.id)) onChange([...value, v]) }} />}
      <div className="chips">{value.map(v => <span key={v.id}>{v.name}{!disabled && <b onClick={() => onChange(value.filter(x => x.id !== v.id))}>✕</b>}</span>)}</div>
    </div>
  )
}

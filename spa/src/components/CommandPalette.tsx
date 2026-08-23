import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'

interface Item { label: string; hint: string; to: string; kind: 'nav' | 'rec' }
const SEARCH_MODELS: [string, string, string][] = [
  ['aq.portal.project', 'projects', 'Proyecto'], ['aq.portal.agreement', 'agreements', 'Pendiente'],
  ['aq.portal.receivable', 'receivables', 'Cuenta por cobrar'], ['aq.portal.prospect', 'prospects', 'Prospecto'],
  ['res.partner', 'clients', 'Cliente'], ['aq.portal.vendor', 'vendors', 'Proveedor'], ['aq.portal.legal.item', 'legal', 'Documento legal'],
]
const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { schema } = useApp()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [recs, setRecs] = useState<Item[]>([])
  const [idx, setIdx] = useState(0)
  const inp = useRef<HTMLInputElement>(null)
  const navItems = useMemo<Item[]>(() => {
    const base: Item[] = [
      { label: 'Tablero de Dirección', hint: 'Inicio', to: '/', kind: 'nav' }, { label: 'Alertas y vencimientos', hint: 'Inicio', to: '/alerts', kind: 'nav' },
      { label: 'Calendario de obligaciones', hint: 'Inicio', to: '/calendar', kind: 'nav' }, { label: 'Rutina diaria / semanal / mensual', hint: 'Inicio', to: '/routines', kind: 'nav' },
      { label: 'Resúmenes ejecutivos', hint: 'Reportes', to: '/reports', kind: 'nav' }, { label: 'Mi perfil', hint: 'Cuenta', to: '/profile', kind: 'nav' },
    ]
    if (schema) Object.values(schema.resources).filter(r => r.section).sort((a, b) => a.order - b.order).forEach(r => {
      const sec = schema.sections.find(s => s.key === r.section)?.label || ''
      base.push({ label: r.label, hint: sec, to: '/r/' + r.key, kind: 'nav' })
      if (r.can.create) base.push({ label: `Nuevo ${r.singular.toLowerCase()}`, hint: r.label, to: `/r/${r.key}/new`, kind: 'nav' })
    })
    return base
  }, [schema])
  useEffect(() => { if (open) { setQ(''); setRecs([]); setIdx(0); setTimeout(() => inp.current?.focus(), 30) } }, [open])
  useEffect(() => {
    if (!open || q.trim().length < 2) { setRecs([]); return }
    const t = setTimeout(async () => {
      const allowed = SEARCH_MODELS.filter(m => schema?.resources[m[1]])
      const results = await Promise.all(allowed.map(m => api.nameSearch(m[0], q).then(r => r.results.slice(0, 4).map((x: any): Item => ({ label: x.name, hint: m[2], to: `/r/${m[1]}/${x.id}`, kind: 'rec' }))).catch(() => [] as Item[])))
      setRecs(results.flat())
    }, 180)
    return () => clearTimeout(t)
  }, [q, open, schema])
  if (!open) return null
  const items = [...navItems.filter(i => !q || norm(i.label + ' ' + i.hint).includes(norm(q))).slice(0, 12), ...recs]
  const go = (it: Item) => { onClose(); nav(it.to) }
  const key = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(i + 1, items.length - 1)) }
    if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)) }
    if (e.key === 'Enter' && items[idx]) go(items[idx])
    if (e.key === 'Escape') onClose()
  }
  return (
    <div className="palette-bg" onMouseDown={onClose}>
      <div className="palette" onMouseDown={e => e.stopPropagation()}>
        <div className="palette-in"><span className="k">⌕</span><input ref={inp} value={q} onChange={e => { setQ(e.target.value); setIdx(0) }} onKeyDown={key} placeholder="Ir a una sección, crear un registro o buscar proyectos, clientes, facturas…" /><kbd>esc</kbd></div>
        <div className="palette-list">
          {items.length === 0 && <div className="empty">Sin resultados</div>}
          {items.map((it, i) => <div key={it.to + i} className={'palette-item' + (i === idx ? ' on' : '')} onMouseEnter={() => setIdx(i)} onClick={() => go(it)}><span className={'dot ' + it.kind} />{it.label}<span className="hint">{it.hint}</span></div>)}
        </div>
        <div className="palette-foot"><span>↑↓ navegar</span><span>↵ abrir</span><span>⌘K / Ctrl+K abrir paleta</span></div>
      </div>
    </div>
  )
}

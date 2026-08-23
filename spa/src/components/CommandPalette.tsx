import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context'
import { setActiveProject } from '../project'

interface Item { label: string; hint: string; to: string; kind: 'nav' | 'rec' | 'proj'; project?: { id: number; name: string } | null }
const SEARCH_MODELS_ADMIN: [string, string, string][] = [
  ['aq.portal.project', 'projects', 'Proyecto'], ['aq.portal.agreement', 'agreements', 'Pendiente'],
  ['aq.portal.receivable', 'receivables', 'Cuenta por cobrar'], ['aq.portal.prospect', 'prospects', 'Prospecto'],
  ['res.partner', 'clients', 'Cliente'], ['aq.portal.vendor', 'vendors', 'Proveedor'], ['aq.portal.legal.item', 'legal', 'Documento legal'],
]
const SEARCH_MODELS_OPS: [string, string, string][] = [
  ['aq.ops.project', 'projects', 'Proyecto'], ['aq.ops.item', 'items', 'Elemento'], ['aq.ops.request', 'requests', 'Solicitud'],
  ['aq.ops.incident', 'incidents', 'Incidente'], ['aq.ops.decision', 'decisions', 'Decisión'], ['aq.ops.document', 'documents', 'Documento'], ['aq.ops.release', 'releases', 'Liberación'],
]
const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { schema, rapi, base, app } = useApp()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [recs, setRecs] = useState<Item[]>([])
  const [projs, setProjs] = useState<Item[]>([])
  useEffect(() => { if (open && app === 'ops') rapi.list('projects', { limit: 200, fields: 'name', order: 'name asc' }).then(r => setProjs([{ label: 'Ver todos los proyectos', hint: 'Proyecto activo', to: '', kind: 'proj', project: null }, ...r.records.map((p: any) => ({ label: `Proyecto activo: ${p.name}`, hint: 'Proyecto activo', to: '', kind: 'proj' as const, project: { id: p.id, name: p.name } }))])).catch(() => {}) }, [open, app, rapi])
  const [idx, setIdx] = useState(0)
  const inp = useRef<HTMLInputElement>(null)
  const basePath = base
  const navItems = useMemo<Item[]>(() => {
    const items0: Item[] = app === 'ops' ? [
      { label: 'Mi trabajo', hint: 'Operaciones', to: '/ops', kind: 'nav' }, { label: 'Torre de control del portafolio', hint: 'Operaciones', to: '/ops/portfolio', kind: 'nav' },
      { label: 'Tablero de trabajo (Kanban, backlog, Gantt…)', hint: 'Operaciones', to: '/ops/board', kind: 'nav' }, { label: 'Bandeja de solicitudes', hint: 'Operaciones', to: '/ops/requests', kind: 'nav' },
      { label: 'Tiempo y capacidad', hint: 'Operaciones', to: '/ops/time', kind: 'nav' }, { label: 'Notificaciones', hint: 'Operaciones', to: '/ops/notifications', kind: 'nav' },
      { label: 'Reportes operativos', hint: 'Operaciones', to: '/ops/reports', kind: 'nav' }, { label: 'Mi perfil', hint: 'Cuenta', to: '/profile', kind: 'nav' },
    ] : [
      { label: 'Tablero de Dirección', hint: 'Inicio', to: '/', kind: 'nav' }, { label: 'Alertas y vencimientos', hint: 'Inicio', to: '/alerts', kind: 'nav' },
      { label: 'Calendario de obligaciones', hint: 'Inicio', to: '/calendar', kind: 'nav' }, { label: 'Rutina diaria / semanal / mensual', hint: 'Inicio', to: '/routines', kind: 'nav' },
      { label: 'Resúmenes ejecutivos', hint: 'Reportes', to: '/reports', kind: 'nav' }, { label: 'Mi perfil', hint: 'Cuenta', to: '/profile', kind: 'nav' },
    ]
    const base: Item[] = items0
    if (schema) Object.values(schema.resources).filter(r => r.section).sort((a, b) => a.order - b.order).forEach(r => {
      const sec = schema.sections.find(s => s.key === r.section)?.label || ''
      base.push({ label: r.label, hint: sec, to: `${basePath}/r/` + r.key, kind: 'nav' })
      if (r.can.create) base.push({ label: `Nuevo ${r.singular.toLowerCase()}`, hint: r.label, to: `${basePath}/r/${r.key}/new`, kind: 'nav' })
    })
    return base
  }, [schema, app, basePath])
  useEffect(() => { if (open) { setQ(''); setRecs([]); setIdx(0); setTimeout(() => inp.current?.focus(), 30) } }, [open])
  useEffect(() => {
    if (!open || q.trim().length < 2) { setRecs([]); return }
    const t = setTimeout(async () => {
      const allowed = (app === 'ops' ? SEARCH_MODELS_OPS : SEARCH_MODELS_ADMIN).filter(m => schema?.resources[m[1]])
      const results = await Promise.all(allowed.map(m => rapi.nameSearch(m[0], q).then(r => r.results.slice(0, 4).map((x: any): Item => ({ label: x.name, hint: m[2], to: `${basePath}/r/${m[1]}/${x.id}`, kind: 'rec' }))).catch(() => [] as Item[])))
      setRecs(results.flat())
    }, 180)
    return () => clearTimeout(t)
  }, [q, open, schema, app, rapi, basePath])
  if (!open) return null
  const items = [...projs.filter(i => q && norm(i.label).includes(norm(q))).slice(0, 6), ...navItems.filter(i => !q || norm(i.label + ' ' + i.hint).includes(norm(q))).slice(0, 12), ...recs]
  const go = (it: Item) => { onClose(); if (it.kind === 'proj') { setActiveProject(it.project || null); return } nav(it.to) }
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

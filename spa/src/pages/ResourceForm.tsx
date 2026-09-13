import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import OpsExtras from '../components/OpsExtras'
import AdminExtras from '../components/AdminExtras'
import Copilot from '../components/Copilot'
import { useApp } from '../context'
import { FieldRow, missingRequired } from '../components/Field'
import SubTable from '../components/SubTable'
import Attachments from '../components/Attachments'
import Timeline from '../components/Timeline'

export default function ResourceForm() {
  const { resource = '', id } = useParams()
  const [sp] = useSearchParams()
  const { schema, user, toast, rapi, base, app } = useApp()
  const nav = useNavigate()
  const loc = useLocation()
  const [ids, setIds] = useState<number[]>((loc.state as any)?.ids || [])
  const res = schema?.resources[resource]
  const isNew = !id
  const [rec, setRec] = useState<any>(null)
  const [dirty, setDirty] = useState<Record<string, any>>({})
  const [tab, setTab] = useState('form')
  const [saving, setSaving] = useState(false)
  const [invalid, setInvalid] = useState<Set<string>>(new Set())
  const loadKeyRef = useRef('')
  const [moreActions, setMoreActions] = useState(false)
  const [moreTabs, setMoreTabs] = useState(false)
  const load = useCallback(() => {
    if (!res) return
    if (isNew) {
      const d: any = {}
      sp.forEach((v, k) => { if (k.startsWith('d.')) { const fn = k.slice(2); const f = res.fields[fn]; if (f?.type === 'many2one') d[fn] = { id: Number(v), name: sp.get('n.' + fn) || '#' + v }; else d[fn] = v } })
      setInvalid(new Set())
      // valores por defecto del servidor (los mismos que aplicaría al crear) + prellenado por URL
      const key = `${resource}/new`
      rapi.defaults(resource).then(r => { if (loadKeyRef.current !== key) return; const merged = { ...(r.defaults || {}), ...d }; setRec(merged); setDirty(merged) }).catch(() => { if (loadKeyRef.current === key) { setRec(d); setDirty(d) } })
      return
    }
    const key = `${resource}/${id}`
    rapi.read(resource, Number(id)).then(r => { if (loadKeyRef.current !== key) return; setRec(r.record); setDirty({}); setTab(t => { if (t !== 'form' || !res.tabs.length) return t; const first = res.tabs.find(tb => (r.record[tb.field] || []).length > 0); return first ? first.field : 'form' }) }).catch(e => { if (loadKeyRef.current !== key) return; toast(e.message, 'err'); nav(`${base}/r/${resource}`) })
  }, [res, resource, id, isNew, sp, toast, nav, rapi, base])
  useEffect(() => { setTab('form'); setRec(null); setDirty({}); setInvalid(new Set()) }, [resource, id])  // ficha limpia al cambiar de registro
  useEffect(() => { loadKeyRef.current = `${resource}/${id || 'new'}`; load() }, [load, resource, id])
  // navegación entre registros: si no venimos de una lista, se toma la lista por defecto del recurso (mismo orden que la vista)
  useEffect(() => {
    const fromState: number[] = (loc.state as any)?.ids || []
    if (fromState.length) { setIds(fromState); return }
    if (!res || isNew) return
    rapi.list(resource, { limit: 200, fields: 'name' }).then(r => setIds(r.records.map((x: any) => x.id))).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource, isNew])
  const pos = ids.indexOf(Number(id))
  const goTo = (i: number) => { if (i < 0 || i >= ids.length) return; if (Object.keys(dirty).length && !confirm('Hay cambios sin guardar. ¿Continuar sin guardar?')) return; nav(`${base}/r/${resource}/${ids[i]}`, { state: { ids } }) }
  useEffect(() => {
    const h = (e: KeyboardEvent) => { const t = e.target as HTMLElement; if (['INPUT', 'TEXTAREA', 'SELECT'].includes(t?.tagName) || t?.isContentEditable) return; if (e.altKey && e.key === 'ArrowLeft') goTo(pos - 1); if (e.altKey && e.key === 'ArrowRight') goTo(pos + 1) }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos, ids, dirty])
  if (!res) return <div className="empty">Recurso no disponible para su rol.</div>
  if (!rec) return <div className="empty">Cargando…</div>
  const canWrite = isNew ? res.can.create : res.can.write
  const canDirection = app === 'ops' ? true : user?.role === 'direccion'
  const value = (f: string) => (f in dirty ? dirty[f] : rec[f])
  const set = (f: string, v: any) => { setDirty(d => ({ ...d, [f]: v })); if (invalid.has(f)) setInvalid(s => { const n = new Set(s); n.delete(f); return n }) }
  const save = async () => {
    // validación de obligatorios antes de llamar al servidor (al crear: todos; al editar: los que se dejaron vacíos)
    const missing = missingRequired(res.fields, value).filter(f => isNew || f.name in dirty)
    if (missing.length) {
      setInvalid(new Set(missing.map(f => f.name)))
      toast('Faltan campos obligatorios: ' + missing.map(f => f.string).join(', '), 'err')
      const el = document.querySelector(`[data-field="${missing[0].name}"]`); el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setInvalid(new Set())
    setSaving(true)
    try {
      if (isNew) { const r = await rapi.create(resource, dirty); toast('Creado', 'ok'); nav(`${base}/r/${resource}/${r.record.id}`, { replace: true }) }
      else { const r = await rapi.write(resource, Number(id), dirty); setRec(r.record); setDirty({}); toast('Guardado', 'ok') }
    } catch (e: any) { toast(e.message, 'err') } finally { setSaving(false) }
  }
  const run = async (a: { name: string; label: string }) => {
    if (Object.keys(dirty).length && !confirm('Hay cambios sin guardar. ¿Ejecutar la acción de todos modos?')) return
    if (!confirm(`¿Ejecutar "${a.label}"?`)) return
    try { const r = await rapi.action(resource, Number(id), a.name); setRec(r.record); toast(`${a.label}: realizado`, 'ok') } catch (e: any) { toast(e.message, 'err') }
  }
  const remove = async () => {
    if (!confirm('¿Archivar/eliminar este registro? Esta acción queda en la bitácora.')) return
    try { await rapi.remove(resource, Number(id)); toast('Registro archivado', 'ok'); nav(`${base}/r/${resource}`) } catch (e: any) { toast(e.message, 'err') }
  }
  // Esenciales: los del registro; si el recurso no los define, los primeros 8 del primer grupo (siempre hay un diseño mínimo)
  const essential = (res.essential && res.essential.length ? res.essential : (res.groups[0]?.fields || []).slice(0, 8)).filter(f => res.fields[f])
  const essSet = new Set(essential)
  // pestañas: las que tienen contenido (o la activa); el resto bajo "más…"
  const tabsWithData = res.tabs.filter(t => (rec?.[t.field] || []).length > 0 || tab === t.field)
  const tabsHidden = res.tabs.filter(t => !tabsWithData.includes(t))
  const primaryActions = res.actions.slice(0, 2), secondaryActions = res.actions.slice(2)
  const groupedFields = new Set(res.groups.flatMap(g => g.fields))
  const tabFields = new Set(res.tabs.map(t => t.field))
  const others = Object.keys(res.fields).filter(f => !groupedFields.has(f) && !tabFields.has(f) && res.fields[f].type !== 'one2many' && !['active', 'last_activity_date', 'notes', 'currency_id', 'create_date', 'write_date', 'display_name'].includes(f))
  return (
    <div>
      <div className="toolbar">
        <div>
          <div style={{ fontSize: 12, color: '#6b7280' }}><a href="#" onClick={e => { e.preventDefault(); nav(`${base}/r/${resource}`) }}>{res.label}</a> / {isNew ? 'Nuevo' : rec.display_name}</div>
          <h1>{isNew ? `Nuevo ${res.singular.toLowerCase()}` : rec.display_name}</h1>
        </div>
        <span className="spacer" />
        {!isNew && pos >= 0 && ids.length > 1 && <div className="recnav">
          <button className="btn secondary small" disabled={pos <= 0} onClick={() => goTo(pos - 1)} title="Anterior (Alt + ←)">‹ Anterior</button>
          <span>{pos + 1} de {ids.length}</span>
          <button className="btn secondary small" disabled={pos >= ids.length - 1} onClick={() => goTo(pos + 1)} title="Siguiente (Alt + →)">Siguiente ›</button>
        </div>}
        {canWrite && <button className="btn" disabled={saving || !Object.keys(dirty).length} onClick={save}>{saving ? 'Guardando…' : 'Guardar'}</button>}
        {Object.keys(dirty).length > 0 && !isNew && <button className="btn secondary" onClick={() => setDirty({})}>Descartar</button>}
        {!isNew && primaryActions.map(a => <button key={a.name} className="btn secondary" onClick={() => run(a)}>{a.label}</button>)}
        {!isNew && (secondaryActions.length > 0 || res.can.delete) && <div className="menu-wrap"><button className="btn secondary" onClick={() => setMoreActions(m => !m)} title="Más acciones">⋯</button>
          {moreActions && <div className="menu" onMouseLeave={() => setMoreActions(false)}>{secondaryActions.map(a => <button key={a.name} onClick={() => { setMoreActions(false); run(a) }}>{a.label}</button>)}{res.can.delete && <button className="danger" onClick={() => { setMoreActions(false); remove() }}>Archivar</button>}</div>}
        </div>}
      </div>
      {!isNew && schema?.ai_available !== false && <details className="more copilot-fold"><summary>✦ Copiloto de IA</summary><Copilot resource={resource} record={rec} fields={res.fields} value={value} set={set} /></details>}
      {resource === 'documents' && canWrite && (
        <div className="alert info" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          Nomenclatura estándar: <code>AAAA-MM-DD_Tipo_Contraparte_Versión</code>
          <button className="btn secondary small" onClick={async () => {
            const cp = value('partner_id')?.name || value('employee_id')?.name || value('vendor_id')?.name || value('project_id')?.name || ''
            const r = await api.get('/documents/suggest-name', { doc_type: value('document_type') || value('folder_type') || 'DOC', counterparty: cp, version: 'v' + (value('version') || '1'), date: value('doc_date') || undefined })
            set('name', r.name)
          }}>Sugerir nombre</button>
        </div>
      )}
      {res.sensitive && <div className="alert info">Información confidencial: no elimine, mueva ni sustituya documentos de este expediente sin validación de Dirección.</div>}
      {!isNew && app === 'ops' && <OpsExtras resource={resource} record={rec} reload={load} />}
      {!isNew && app === 'admin' && <AdminExtras resource={resource} record={rec} />}
      {!isNew && (
        <div className="tabs">
          <button className={tab === 'form' ? 'active' : ''} onClick={() => setTab('form')}>Ficha</button>
          {tabsWithData.map(t => <button key={t.field} className={tab === t.field ? 'active' : ''} onClick={() => setTab(t.field)}>{t.label} ({(rec[t.field] || []).length})</button>)}
          {res.attachments && <button className={tab === '_att' ? 'active' : ''} onClick={() => setTab('_att')}>Archivos</button>}
          <button className={tab === '_hist' ? 'active' : ''} onClick={() => setTab('_hist')}>Historial</button>
          {tabsHidden.length > 0 && (moreTabs
            ? tabsHidden.map(t => <button key={t.field} className={tab === t.field ? 'active' : ''} onClick={() => setTab(t.field)}>{t.label}</button>)
            : <button className="muted" onClick={() => setMoreTabs(true)} title={tabsHidden.map(t => t.label).join(', ')}>+ {tabsHidden.length} más…</button>)}
        </div>
      )}
      {tab === 'form' && (
        <div>
          <div className="card"><h3>{isNew ? 'Lo necesario para empezar' : 'Esenciales'}</h3><div className="grid cols-2">{essential.map(f => <div key={f} style={{ gridColumn: ['description', 'acceptance_criteria', 'name'].includes(f) ? '1 / -1' : undefined }}><FieldRow f={res.fields[f]} value={value(f)} onChange={v => set(f, v)} canDirection={canDirection} disabled={!canWrite} invalid={invalid.has(f)} /></div>)}</div></div>
          <details className="more"><summary>Más detalles (todo lo demás)</summary>
            <div className="grid cols-2" style={{ marginTop: 12 }}>
              {res.groups.map(g => { const fs = g.fields.filter(f => res.fields[f] && res.fields[f].type !== 'one2many' && !essSet.has(f)); return fs.length ? <div className="card" key={g.title}><h3>{g.title}</h3>{fs.map(f => <FieldRow key={f} f={res.fields[f]} value={value(f)} onChange={v => set(f, v)} canDirection={canDirection} disabled={!canWrite} invalid={invalid.has(f)} />)}</div> : null })}
              {others.filter(f => !essSet.has(f)).length > 0 && <div className="card"><h3>Otros</h3>{others.filter(f => !essSet.has(f)).map(f => <FieldRow key={f} f={res.fields[f]} value={value(f)} onChange={v => set(f, v)} canDirection={canDirection} disabled={!canWrite} invalid={invalid.has(f)} />)}</div>}
            </div>
          </details>
        </div>
      )}
      {!isNew && res.tabs.map(t => tab === t.field && <div className="card" key={t.field}><SubTable tab={t} parentId={Number(id)} parentName={rec.display_name} /></div>)}
      {!isNew && tab === '_att' && <div className="card"><Attachments resource={resource} id={Number(id)} canWrite={res.can.write} /></div>}
      {!isNew && tab === '_hist' && <div className="card"><Timeline resource={resource} id={Number(id)} /></div>}
    </div>
  )
}

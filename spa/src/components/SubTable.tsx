import { useCallback, useEffect, useState } from 'react'
import { Resource, Tab, useApp } from '../context'
import RecordTable from './RecordTable'
import { FieldRow } from './Field'

/** Pestaña one2many: lista de registros hijos con alta/edición en línea (modal ligero). */
export default function SubTable({ tab, parentId, parentName }: { tab: Tab; parentId: number; parentName?: string }) {
  const { schema, user, toast, rapi, app } = useApp()
  const res: Resource | undefined = schema?.resources[tab.resource]
  const [records, setRecords] = useState<any[]>([])
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)
  const load = useCallback(() => {
    if (!res) return
    rapi.list(tab.resource, { domain: [[tab.parent_field, '=', parentId]], limit: 200, order: 'id desc' }).then(r => setRecords(r.records)).catch(e => toast(e.message, 'err'))
  }, [res, tab, parentId, toast, rapi])
  useEffect(() => { load() }, [load])
  if (!res) return <div className="empty">Sin acceso a {tab.label}</div>
  const cols = res.list.filter(c => c !== tab.parent_field)
  const formFields = res.groups.flatMap(g => g.fields).filter(f => f !== tab.parent_field && res.fields[f] && res.fields[f].type !== 'one2many')
  const canDirection = app === 'ops' ? true : user?.role === 'direccion'
  const startNew = () => setEditing({ ...(tab.defaults || {}) })
  const openRec = async (r: any) => { const full = await rapi.read(tab.resource, r.id); setEditing(full.record) }
  const save = async () => {
    setSaving(true)
    try {
      const vals: any = {}
      formFields.forEach(f => { if (editing[f] !== undefined) vals[f] = editing[f] })
      vals[tab.parent_field] = parentId
      if (tab.defaults) Object.assign(vals, tab.defaults)
      if (editing.id) await rapi.write(tab.resource, editing.id, vals)
      else await rapi.create(tab.resource, vals)
      toast('Guardado', 'ok'); setEditing(null); load()
    } catch (e: any) { toast(e.message, 'err') } finally { setSaving(false) }
  }
  const remove = async () => {
    if (!editing?.id || !confirm('¿Eliminar este registro?')) return
    try { await rapi.remove(tab.resource, editing.id); toast('Eliminado', 'ok'); setEditing(null); load() } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div>
      <div className="toolbar">
        <span style={{ color: '#6b7280', fontSize: 12 }}>{records.length} registros{parentName ? ` · ${parentName}` : ''}</span>
        <span className="spacer" />
        {res.can.create && <button className="btn small" onClick={startNew}>+ Agregar {res.singular.toLowerCase()}</button>}
      </div>
      <RecordTable res={res} records={records} columns={cols} onOpen={openRec} />
      {editing && (
        <div className="card" style={{ marginTop: 12, borderColor: '#714B67' }}>
          <h2>{editing.id ? 'Editar' : 'Nuevo'} · {res.singular}</h2>
          <div className="grid cols-2">
            {formFields.map(f => <FieldRow key={f} f={res.fields[f]} value={editing[f]} onChange={v => setEditing({ ...editing, [f]: v })} canDirection={canDirection} disabled={!res.can.write && !!editing.id} />)}
          </div>
          <div className="toolbar" style={{ marginTop: 8 }}>
            <button className="btn" disabled={saving || (!!editing.id && !res.can.write)} onClick={save}>Guardar</button>
            <button className="btn secondary" onClick={() => setEditing(null)}>Cancelar</button>
            <span className="spacer" />
            {editing.id && res.can.delete && <button className="btn danger small" onClick={remove}>Eliminar</button>}
          </div>
        </div>
      )}
    </div>
  )
}

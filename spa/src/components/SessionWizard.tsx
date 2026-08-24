import { useEffect, useMemo, useState } from 'react'
import { api, today } from '../api'
import { useApp } from '../context'
import Many2one from './Many2one'

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const DURACIONES = [15, 30, 45, 60, 90, 120]
const SLOTS: string[] = []
for (let h = 7; h <= 20; h++) { SLOTS.push(`${String(h).padStart(2, '0')}:00`); if (h < 20) SLOTS.push(`${String(h).padStart(2, '0')}:30`) }

const addDaysISO = (iso: string, n: number) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10) }
const nextMonday = () => { const d = new Date(); d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7)); return d.toISOString().slice(0, 10) }
const humanDay = (iso: string) => { const d = new Date(iso + 'T12:00:00'); return `${DIAS[d.getDay()]} ${d.getDate()} de ${MESES[d.getMonth()]}` }
const addMin = (hhmm: string, m: number) => { const [h, mi] = hhmm.split(':').map(Number); const t = Math.max(0, Math.min(23 * 60 + 55, h * 60 + mi + m)); return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}` }

export default function SessionWizard({ types, projects, defaultProject, onCreated }: { types: any[]; projects: any[]; defaultProject: { id: number; name: string } | null; onCreated: (m: any) => void }) {
  const { toast } = useApp()
  const [step, setStep] = useState(1)
  const [project, setProject] = useState<any>(defaultProject)
  const [typeId, setTypeId] = useState<number | null>(null)
  const [date, setDate] = useState(today())
  const [time, setTime] = useState('09:30')
  const [duration, setDuration] = useState<number | null>(null)
  const [context, setContext] = useState('')
  const [brief, setBrief] = useState<{ objetivo: string; agenda: string; mensaje: string } | null>(null)
  const [invitees, setInvitees] = useState<any[]>([])
  const [extra, setExtra] = useState('')
  const [send, setSend] = useState(true)
  const [busy, setBusy] = useState<'' | 'ia' | 'gen'>('')
  const type = types.find(t => t.id === typeId)
  const dur = duration || type?.duration || 30
  const end = addMin(time, dur)
  useEffect(() => { if (defaultProject && !project) setProject(defaultProject) }, [defaultProject])  // eslint-disable-line
  useEffect(() => {
    if (project && typeId) api.get('/ops/sessions/invitees', { project_id: project.id, type_id: typeId }).then(r => setInvitees(r.invitees)).catch(() => setInvitees([]))
  }, [project, typeId])
  const folio = useMemo(() => {
    const p = projects.find((x: any) => x.project === project?.name)
    if (!p || !type) return ''
    return p.scheme === 'cliente' && p.po
      ? `${p.po}-${p.prefix || ''}-Sesión #${(p.client_seq || 0) + 1} - ${type.name}`
      : (p.stage > 1
        ? `SESIÓN #${(p.seq || 0) + 1} ETAPA ${p.stage}– ${p.prefix || '…'}– ${type.name.toUpperCase()} | ${date.split('-').reverse().join('/')}`
        : `SESIÓN #${(p.seq || 0) + 1}– ${p.prefix || '…'}– ${type.name.toUpperCase()} | ${date.split('-').reverse().join('/')}`)
  }, [projects, project, type, date])

  const genBrief = async () => {
    if (!project || !typeId) return
    setBusy('ia')
    try {
      const r = await api.post('/ops/sessions/brief', { project_id: project.id, type_id: typeId, context, start: `${date}T${time}:00`, duration: dur })
      setBrief({ objetivo: r.objetivo || '', agenda: r.agenda || '', mensaje: r.mensaje || '' })
      toast('Agenda y mensaje preparados con IA · edítalos a tu gusto', 'ok')
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const create = async () => {
    if (!project || !typeId) { toast('Elige proyecto y tipo de sesión', 'err'); return }
    setBusy('gen')
    try {
      const r = await api.post('/ops/sessions/generate', {
        project_id: project.id, type_id: typeId, start: `${date}T${time}:00`, duration: dur,
        agenda: brief?.agenda || undefined, context: brief?.objetivo || context || undefined, share_note: brief?.mensaje || undefined,
        extra_emails: extra.split(/[,;\s]+/).filter(x => x.includes('@')),
        attendees: invitees.filter(i => i.checked).map(i => i.email), send_invites: send,
      })
      onCreated(r.meeting)
      setStep(1); setContext(''); setBrief(null)
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const Step = ({ n, label }: { n: number; label: string }) => (
    <button className={'wz-step' + (step === n ? ' on' : '') + (step > n ? ' done' : '')} onClick={() => setStep(n)} disabled={n > 1 && (!project || !typeId)}>
      <em>{step > n ? '✓' : n}</em>{label}
    </button>
  )
  return (
    <div className="card wizard">
      <div className="wz-head">
        <div className="wz-steps"><Step n={1} label="Proyecto y tipo" /><Step n={2} label="Cuándo" /><Step n={3} label="Contexto e invitados" /></div>
        {folio && <div className="wz-folio" title="Así se titulará la sesión"><span>{projects.find((x: any) => x.project === project?.name)?.scheme === 'cliente' ? 'Título (consecutivo del cliente)' : 'Folio'}</span><b>{folio}</b></div>}
      </div>

      {step === 1 && (
        <div className="wz-body">
          <div className="field" style={{ maxWidth: 420 }}><label>Proyecto</label><Many2one model="aq.ops.project" value={project} onChange={setProject} resource="projects" /></div>
          <label className="wz-label">Tipo de sesión</label>
          <div className="type-grid">
            {types.map(t => <button key={t.id} className={'type-card' + (typeId === t.id ? ' on' : '')} onClick={() => { setTypeId(t.id); setDuration(null) }}>
              <b>{t.name}</b><span>{t.duration} min</span></button>)}
          </div>
          <div className="wz-nav"><button className="btn" disabled={!project || !typeId} onClick={() => setStep(2)}>Continuar →</button></div>
        </div>
      )}

      {step === 2 && (
        <div className="wz-body">
          <div className="when-display">
            <div><span>Inicia</span><b>{humanDay(date)}</b></div>
            <div className="when-clock"><button onClick={() => setTime(addMin(time, -5))} title="−5 min">−</button><b>{time}</b><button onClick={() => setTime(addMin(time, 5))} title="+5 min">+</button></div>
            <div><span>Termina</span><b>{end} h</b></div>
          </div>
          <label className="wz-label">Día</label>
          <div className="chip-row">
            <button className={date === today() ? 'on' : ''} onClick={() => setDate(today())}>Hoy</button>
            <button className={date === addDaysISO(today(), 1) ? 'on' : ''} onClick={() => setDate(addDaysISO(today(), 1))}>Mañana</button>
            <button className={date === addDaysISO(today(), 2) ? 'on' : ''} onClick={() => setDate(addDaysISO(today(), 2))}>Pasado</button>
            <button className={date === nextMonday() ? 'on' : ''} onClick={() => setDate(nextMonday())}>Próximo lunes</button>
            <input type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)} style={{ width: 'auto' }} />
          </div>
          <label className="wz-label">Hora de inicio</label>
          <div className="slots">{SLOTS.map(s => <button key={s} className={time === s ? 'on' : ''} onClick={() => setTime(s)}>{s}</button>)}</div>
          <label className="wz-label">Duración</label>
          <div className="chip-row">{DURACIONES.map(d => <button key={d} className={dur === d ? 'on' : ''} onClick={() => setDuration(d)}>{d >= 60 ? `${d / 60} h${d % 60 ? ` ${d % 60}m` : ''}` : `${d} min`}</button>)}</div>
          <div className="wz-nav"><button className="btn secondary" onClick={() => setStep(1)}>← Atrás</button><button className="btn" onClick={() => setStep(3)}>Continuar →</button></div>
        </div>
      )}

      {step === 3 && (
        <div className="wz-body">
          <div className="field"><label>¿De qué va a tratar la sesión? <small style={{ color: 'var(--muted)' }}>— unas líneas bastan; la IA arma la agenda y el mensaje</small></label>
            <textarea rows={3} value={context} onChange={e => setContext(e.target.value)} placeholder="Ej. Revisar el flujo de compras, ver los pendientes de placas y cerrar la validación del reporte de inventario." /></div>
          <div className="toolbar"><button className="btn secondary" disabled={busy === 'ia' || !context.trim()} onClick={genBrief}>{busy === 'ia' ? 'Preparando…' : '✦ Preparar agenda y mensaje'}</button>
            {brief && <span className="badge ok">Listo · puedes editar abajo</span>}</div>
          {brief && (<>
            <div className="field"><label>Objetivo</label><input type="text" value={brief.objetivo} onChange={e => setBrief({ ...brief, objetivo: e.target.value })} /></div>
            <div className="grid cols-2">
              <div className="field"><label>Agenda (va en la invitación de Calendar)</label><textarea rows={6} value={brief.agenda} onChange={e => setBrief({ ...brief, agenda: e.target.value })} /></div>
              <div className="field"><label>Mensaje para compartir (WhatsApp / chat)</label><textarea rows={6} value={brief.mensaje} onChange={e => setBrief({ ...brief, mensaje: e.target.value })} /></div>
            </div>
          </>)}
          <label className="wz-label">Invitados <small style={{ color: 'var(--muted)', textTransform: 'none', letterSpacing: 0 }}>({invitees.filter(i => i.checked).length} de {invitees.length}) — desmarca a quien no deba recibir la invitación</small></label>
          <div className="inv-grid">
            {invitees.map(i => <label key={i.email} className={'inv' + (i.checked ? ' on' : '')}><input type="checkbox" checked={i.checked} onChange={() => setInvitees(inv => inv.map(x => x.email === i.email ? { ...x, checked: !x.checked } : x))} /><span><b>{i.name}</b><small>{i.email}</small></span><em className="badge">{i.kind}</em></label>)}
            {!invitees.length && <div style={{ color: 'var(--muted)', fontSize: 13 }}>Este proyecto aún no tiene equipo ni contactos con correo.</div>}
          </div>
          <div className="toolbar">
            <button className="btn link small" onClick={() => setInvitees(inv => inv.map(i => ({ ...i, checked: true })))}>Todos</button>
            <button className="btn link small" onClick={() => setInvitees(inv => inv.map(i => ({ ...i, checked: false })))}>Ninguno</button>
            <button className="btn link small" onClick={() => setInvitees(inv => inv.map(i => ({ ...i, checked: i.kind === 'interno' })))}>Solo equipo</button>
          </div>
          <div className="field"><label>Invitados adicionales (correos separados por coma)</label><input type="text" value={extra} onChange={e => setExtra(e.target.value)} placeholder="grupo@cliente.com, otra@persona.com" /></div>
          <label className="check"><input type="checkbox" checked={send} onChange={e => setSend(e.target.checked)} /> Enviar invitación por correo (si lo desmarcas, solo se crea la sesión y tú compartes la liga)</label>
          <div className="wz-nav">
            <button className="btn secondary" onClick={() => setStep(2)}>← Atrás</button>
            <button className="btn" disabled={busy === 'gen'} onClick={create}>{busy === 'gen' ? 'Creando…' : '⚡ Crear sesión y generar liga'}</button>
          </div>
        </div>
      )}
    </div>
  )
}

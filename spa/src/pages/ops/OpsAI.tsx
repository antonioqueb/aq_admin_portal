import { useEffect, useState } from 'react'
import { ops } from '../../api'
import { useApp } from '../../context'

export default function OpsAI() {
  const { toast, user } = useApp()
  const [st, setSt] = useState<any>(null)
  const [test, setTest] = useState<any>(null)
  const [models, setModels] = useState<any>(null)
  const owner = ['platform_owner', 'ops_director'].includes(user?.ops_role || '')
  const load = () => ops.aiStatus().then(setSt).catch((e: any) => toast(e.message, 'err'))
  useEffect(() => { load() }, [])  // eslint-disable-line
  if (!st) return <div className="empty">Consultando estado…</div>
  return (
    <div>
      <h1>Copiloto de IA (DeepSeek)</h1>
      <div className="grid cols-2">
        <div className="card"><h3>Estado</h3>
          <p><span className={'badge ' + (st.available ? 'ok' : 'err')}>{st.available ? 'Disponible' : 'Sin conexión (modo heurístico)'}</span></p>
          <p style={{ fontSize: 13 }}><b>Fuente de la clave:</b> {st.source === 'env' ? 'variable de entorno DEEPSEEK_API_KEY' : st.source === 'param' ? 'parámetro del sistema' : st.source === 'record' ? 'registro de integración' : 'ninguna'}{st.key_hint && ` (${st.key_hint})`}<br /><b>Modelo:</b> {st.model}<br /><b>Endpoint:</b> {st.base_url}</p>
          {owner && <div className="toolbar"><button className="btn" onClick={() => ops.aiTest().then(r => { setTest(r); toast(r.ok ? 'DeepSeek respondió correctamente' : 'Fallo: ' + (r.error || 'sin respuesta'), r.ok ? 'ok' : 'err') })}>Probar conexión</button>
            <button className="btn secondary" onClick={() => ops.aiModels(false).then(r => { setModels(r); load(); toast(r.error ? r.error : 'Modelo seleccionado: ' + r.model, r.error ? 'err' : 'ok') })}>Usar el modelo más reciente</button>
            <button className="btn secondary" onClick={() => ops.aiModels(true).then(r => { setModels(r); load(); toast(r.error ? r.error : 'Modelo de razonamiento: ' + r.model, r.error ? 'err' : 'ok') })}>Preferir razonamiento</button></div>}
          {test && <div className={'alert ' + (test.ok ? 'ok' : 'err')}>{test.ok ? `Respuesta: ${test.answer}` : test.error}</div>}
          {models?.models && <div style={{ fontSize: 12, color: 'var(--muted)' }}>Modelos disponibles en la cuenta: {models.models.join(', ')}</div>}
        </div>
        <div className="card"><h3>Dónde actúa el copiloto</h3>
          <ul style={{ fontSize: 13, lineHeight: 1.7 }}>
            <li><b>Todas las fichas</b> (Administración y Operaciones): botón ✦ Copiloto — resumir, siguiente acción, riesgos, preguntas abiertas, criterios de aceptación, correo al cliente, redactar o mejorar cualquier campo de texto.</li>
            <li><b>Solicitudes</b>: al crearse, clasificación y determinación sugeridas + posibles duplicados; comparación con el alcance.</li>
            <li><b>Reuniones</b>: resumen, acuerdos/compromisos/preguntas/riesgos propuestos (se crean solo al confirmar).</li>
            <li><b>Proyectos</b>: por qué está en rojo, siguiente acción, duplicados, borrador de reporte semanal.</li>
            <li><b>Elementos</b>: casos de prueba y dependencias sugeridas. <b>Incidentes</b>: resumen del historial.</li>
            <li><b>Correos</b>: resumen ejecutivo con IA en el digest diario de Operaciones y en el resumen de alertas de Administración.</li>
          </ul>
          <div className="disclaimer" style={{ fontSize: 11, color: 'var(--muted)' }}>Límites: nunca aprueba cambios, altera alcance, acepta entregables, autoriza liberaciones, cambia fechas comprometidas, envía comunicaciones vinculantes, cierra incidentes ni toma decisiones comerciales.</div>
        </div>
      </div>
    </div>
  )
}

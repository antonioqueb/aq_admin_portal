# AlphaQueb · Portal de Control Administrativo (`aq_admin_portal`)

Módulo para **Odoo 19** que expone un **portal web externo** (React, bundle independiente de los assets de Odoo)
con **usuarios propios** (no son `res.users`), para la coordinación administrativa y el control operativo
descrito en la carta de incorporación de la coordinadora administrativa.

## Qué incluye

| Sección de la carta | Recurso del portal | Modelo Odoo |
|---|---|---|
| 1.1 Control general de proyectos | Control maestro de proyectos (+ fechas relevantes, pasos del procedimiento, entregables) | `aq.portal.project`, `aq.portal.project.date`, `aq.portal.project.step`, `aq.portal.deliverable` |
| 1.2 Reuniones y minutas; convocar revisiones administrativas (sección 6) | Reuniones/minutas con convocatoria por correo, minuta y acuerdos derivados | `aq.portal.meeting` |
| 1.2 Seguimiento de acuerdos y pendientes | Acuerdos y pendientes (solicitar actualización, escalar, autorizar, formalizar acuerdos verbales/WhatsApp) | `aq.portal.agreement` |
| 1.3 Facturación | Calendario de facturación (datos fiscales, evidencia, envío, recepción, complemento, detener y validar) | `aq.portal.invoice.schedule` |
| 1.4 Cuentas por cobrar y cobranza | CxC con pagos, seguimientos, compromisos de pago, riesgo, escalamiento y convenios autorizados por Dirección | `aq.portal.receivable`, `aq.portal.receivable.payment` |
| 1.5 Cuentas por pagar | CxP por categoría con autorización y ejecución reservadas a Dirección, recurrencias | `aq.portal.payable` |
| 1.6 Horas, alcances y trabajo facturable | Bolsas de horas, registro de horas, hallazgos (sin facturar, sin registro, fuera de alcance, sin autorización) | `aq.portal.hour.bucket`, `aq.portal.hour.entry` |
| 1.7 Control de clientes (separado de prospectos) | Directorio de clientes y contactos | `res.partner` (recurso `clients`) |
| 1.7 Control de prospectos | Prospectos con interacciones, propuesta, vigencia, etapa, resultado, motivo de pérdida, conversión a cliente/proyecto | `aq.portal.prospect` |
| 1.8 Organización documental | Documentos por expediente, nomenclatura, versiones, firmados, confidencialidad, duplicados, faltantes, archivos adjuntos | `aq.portal.document` + `ir.attachment` |
| 1.9 Inventario legal inicial | Matriz de contratos y documentos legales (existe / vigente / falta / riesgo / prioridad) | `aq.portal.legal.item` |
| 2.1 Estandarización de contratos | Biblioteca legal con versión, responsable de revisión y aprobación (solo aprobados pueden usarse) | `aq.portal.template` |
| 2.2 Administración de personal | Expedientes con datos, contrato, equipo, accesos, eventos, documentos y checklists de incorporación/separación | `aq.portal.employee` y satélites |
| 2.3 Procedimiento administrativo de proyectos | 15 pasos plantilla, creados automáticamente en cada proyecto | `aq.portal.procedure.step`, `aq.portal.project.step` |
| 2.4 Control de cambios | Clasificación, estimación, autorización (cliente / excepción de Dirección), ejecutado sin autorización | `aq.portal.change.request` |
| 2.5 Proveedores, licencias y servicios | Padrón con costo, periodicidad, renovación, contrato, riesgo operativo | `aq.portal.vendor` |
| 2.6 Calendario de obligaciones | Obligaciones + calendario consolidado (facturas, cobros, pagos, pendientes, contratos, renovaciones…) | `aq.portal.obligation` + endpoint `/calendar` |
| 2.7 Privacidad y manejo de información | Inventario de datos personales (qué, para qué, dónde, quién, con quién, cuánto tiempo, ARCO, baja) | `aq.portal.data.inventory` |
| 3.1 Tablero de Dirección | Tablero con todos los indicadores | endpoint `/dashboard` |
| 3.2 Indicadores de operación | KPIs (facturas a tiempo, cobradas en fecha, cartera vencida, días de cobranza, ejecutado vs facturado, etc.) | `aq.portal.report.dashboard_data` |
| 3.3 Matriz de riesgos | Riesgos con responsable, acción preventiva, fecha de revisión; alimentada automáticamente por alertas graves | `aq.portal.risk` |
| 3.4 Manuales y procedimientos | Procedimientos y políticas con versión y aprobación | `aq.portal.manual` |
| 3.5 Gobierno corporativo | Libros, actas, poderes, firmas, decisiones relevantes | `aq.portal.corporate` |
| 3.6 Gobierno y sector público | Convocatorias/contratos públicos con matriz de cumplimiento | `aq.portal.tender` |
| 3.7 Mejora continua | Propuestas de mejora y automatización | `aq.portal.improvement` |
| 4 Ritmo de trabajo | Checklists diario / semanal / mensual generados automáticamente | `aq.portal.routine`, `aq.portal.routine.run` |
| 5 Entregables de incorporación | Entregables por fase (semana 1, 15, 30, 60, 90 días) | `aq.portal.onboarding.deliverable` |
| 6 Facultades y límites | Roles y campos "solo Dirección" (autorizaciones, pagos, convenios, aprobaciones) | registro `controllers/registry.py` |
| Transversal | Alertas diarias, resumen por correo, bitácora de auditoría, seguimientos, reportes ejecutivos | `aq.portal.alert`, `aq.portal.audit.log`, `aq.portal.followup`, `aq.portal.report` |

Datos iniciales: integrantes (Dirección y Coordinación), los 4 clientes del portafolio inicial con un proyecto cada uno, 15 pasos del procedimiento, rutinas diarias/semanales/mensuales y entregables de incorporación. Todos los listados se exportan a CSV.

## Usuarios externos y seguridad

* `aq.portal.user`: login, correo, rol, contraseña con `pbkdf2_sha512` (passlib), bloqueo tras 6 intentos,
  sesiones por token (`aq.portal.session`, 12 h deslizantes), recuperación de contraseña por correo con
  token de 2 h, cambio de contraseña obligatorio en el primer acceso.
* Roles: **Dirección** (todo, incluidas autorizaciones y usuarios), **Coordinación administrativa** (crea y
  edita todos los controles, no autoriza), **Integrante del equipo** (actualiza sus pendientes, horas,
  cambios, entregables, seguimientos), **Solo consulta**.
* Toda operación de la API queda en la bitácora (`aq.portal.audit.log`) y los modelos principales tienen
  tracking de cambios (chatter) visible en la pestaña *Historial y notas*.
* Los expedientes sensibles (personal, corporativo) no se eliminan: se archivan; los archivos de
  expedientes sensibles solo los elimina Dirección.

## Instalación

1. Copiar `aq_admin_portal` a la ruta de addons e instalar (`base`, `mail`, `account`; requiere `passlib`).
2. Compilar el portal (una sola vez, o cada vez que cambie el frontend):

   ```bash
   cd aq_admin_portal/spa
   npm install
   npm run build        # genera aq_admin_portal/static/spa
   ```

3. Parámetro opcional `aq_admin_portal.base_url` (Ajustes → Técnico → Parámetros del sistema) con la URL
   pública si difiere de `web.base.url` (se usa para los enlaces de los correos).
4. Los usuarios se crean **únicamente** en Odoo: la app **Usuarios del Portal → Usuarios** (segundo menú raíz del mismo módulo): Nombre, Login, Correo, Rol, Integrante relacionado, y contraseña mediante
   *Nueva contraseña* o el botón *Enviar enlace para establecer contraseña*. En esa misma app están Sesiones activas y
   Configuración (Parámetros del portal y plantilla de correo de acceso). El portal web no permite crear ni
   administrar usuarios. Los usuarios del portal no son `res.users` y no consumen licencias de Odoo.
5. Abrir `https://<servidor>/admin-portal` e iniciar sesión.

Parámetros del sistema: `aq_admin_portal.stale_days` (5), `warn_days` (7), `prospect_days` (7),
`depletion_threshold` (80 %), `session_hours` (12), `portal_path` (/admin-portal), `base_url`.

## Desarrollo del frontend

```bash
cd aq_admin_portal/spa
ODOO_URL=http://localhost:8069 npm run dev   # Vite en http://localhost:5173 con proxy a /aq_portal
```

La SPA vive en `/admin-portal` (React Router con `basename`), sus assets en
`/aq_admin_portal/static/spa/assets`. No usa el framework web de Odoo ni sus assets.

## API REST (`/aq_portal/api`)

Autenticación `Authorization: Bearer <token>`.

* `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/forgot`, `POST /auth/reset`, `POST /auth/change-password`
* `GET /schema` — recursos, campos, grupos, pestañas, acciones y permisos del rol actual
* `GET|POST /r/<recurso>`, `GET|PUT|DELETE /r/<recurso>/<id>`, `POST /r/<recurso>/<id>/action/<accion>`
* `GET /r/<recurso>/<id>/messages`, `POST /r/<recurso>/<id>/note`, `GET|POST /r/<recurso>/<id>/attachments`
* `GET /dashboard`, `GET /calendar`, `GET /routines/today`, `POST /routines/<id>/toggle`, `POST /reports/generate`
* `GET /alerts`, `POST /alerts/<id>/dismiss`, `POST /alerts/recompute`

## Cron

`Portal administrativo: alertas, rutinas y estados (diario)` — genera los checklists de rutina, actualiza
estados de cobranza/pagos/obligaciones/contratos, recalcula alertas, alimenta la matriz de riesgos y envía
el resumen diario de alertas a Dirección y Coordinación.

---

# Operaciones (AlphaOps) — segundo dominio en el mismo módulo

Misma plataforma, dos dominios. **Identidad, organizaciones/clientes, branding, notificaciones, auditoría, usuarios e integraciones son compartidos**;
contratos, cotizaciones, facturación, cobranza, CxP/CxC, bancos, tarifas/márgenes, legal y RH viven solo en Administración;
planeación, requerimientos, backlog, tareas, riesgos, incidencias, minutas, decisiones, pruebas, validaciones, liberaciones,
capacidad, evidencias y comunicación operativa viven solo en Operaciones. La separación existe en modelos (`aq.ops.*`), API
(`/aq_portal/api/ops/...`), búsquedas, exportaciones y permisos por objeto — no solo en menús.

## Selector de aplicación
En **Usuarios del Portal** cada cuenta tiene *Acceso a Administración*, *Acceso a Operaciones* y *Perfil en Operaciones*.
Quien tiene ambos ve el selector **Administración / Operaciones** en la barra superior; quien tiene uno, solo ese portal.
Operaciones se identifica por nombre permanente, ícono propio, acento cian y navegación propia en la ruta `/admin-portal/ops`
(puede publicarse como `ops.alphaqueb.com` apuntando a esa ruta). La barra muestra la organización y el proyecto activos.

## Perfiles (17) y alcance (RBAC + ABAC)
Propietario de plataforma, Director de Operaciones/PMO, PM, Líder funcional, Líder técnico, Consultor, Desarrollador, QA,
Soporte/Guardia, Colaborador interno, Socio/subcontratista, Patrocinador del cliente, Product Owner del cliente, Validador
departamental, Empleado solicitante, Observador/Auditor y Enlace administrativo. El alcance se calcula por organización
(tenant), proyectos donde participa o proyectos asignados expresamente; los usuarios de cliente solo ven registros
`client_visible` de su organización con campos sensibles redactados (`client_hidden`); el solicitante solo ve sus solicitudes;
el enlace administrativo solo ve eventos. Acceso denegado por defecto; autorización comprobada por objeto en cada llamada.
Seguridad adicional: **MFA TOTP** (obligatorio por perfil), invitaciones externas con caducidad, sesiones/dispositivos auditables,
**break glass** con justificación y vigencia, exportaciones controladas (`Puede exportar`), revocación inmediata al cambiar
perfil o desactivar, bitácora completa.

## Estructura funcional
| Sección | Pantalla | Modelos |
|---|---|---|
| 5.1 Mi trabajo | `/ops` (agenda de ejecución: asignado, hoy/semana, bloqueados, aprobaciones, solicitudes, menciones, reuniones, dependen de mí, horas pendientes, sin movimiento, riesgos/incidentes) | motor `aq.ops.engine.my_work` |
| 5.2 Torre de control | `/ops/portfolio` (agrupación por cliente/PM/tipo/etapa/salud/prioridad/riesgo/dependencia, vistas guardadas y las 9 preguntas de Dirección) | `aq.ops.project` |
| 5.3 Centro de mando | `/ops/projects/:id` (resumen en 2 minutos + vistas de trabajo) | `aq.ops.project`, hitos, ambientes, enlaces, reportes de estado |
| 5.4 Solicitudes | `/ops/requests` (embudo único, clasificación en 11 tipos, 6 determinaciones, duplicados, conversión a elemento/cambio/incidente) | `aq.ops.request` |
| 5.5 Alcance y backlog | Jerarquía objetivo→capacidad→épica→proceso→requerimiento→historia→entregable→tarea→prueba→cambio, un solo objeto | `aq.ops.item` |
| 5.6 Planeación | `/ops/board`: backlog, Kanban (drag & drop, WIP), sprints, lista, calendario, cronograma, Gantt (plan original vs vigente), carga, dependencias, roadmap, por entregable, por cliente, personal; reprogramación controlada, recurrentes, plantillas | `aq.ops.item`, `aq.ops.sprint` |
| 5.7 Reuniones y decisiones | agenda, participantes, minuta, transcripción, acuerdos (confirmación humana → tarea/cambio), preguntas abiertas, riesgos, documentos, próxima reunión; decisiones versionadas e inmutables | `aq.ops.meeting`, `aq.ops.meeting.agreement`, `aq.ops.decision` |
| 5.8 RAID e incidentes | riesgos/supuestos/problemas/dependencias; incidentes con flujo de 11 pasos, SLA por severidad y acción preventiva automática | `aq.ops.raid`, `aq.ops.incident` |
| 5.9 Calidad y aceptación | 16 estados de flujo, planes/casos/ejecuciones, defectos automáticos, aceptación electrónica inmutable con huella (aprobado/cambios/rechazado) y autoridad departamental | `aq.ops.test.*`, `aq.ops.acceptance` |
| 5.10 Liberaciones | candidatos, ambientes, compuerta (respaldo, responsable, pruebas, aprobación, reversión), bitácora, verificación posterior, revisión post-liberación automática | `aq.ops.release`, `aq.ops.environment` |
| 5.11 Tiempo y capacidad | temporizador, captura, clasificación, facturable, aprobación semanal (→ evento a Administración), capacidad por especialidad, ausencias, sobreasignación | `aq.ops.timesheet`, `aq.ops.capacity` |
| 5.12 Portal del cliente | experiencia restringida dentro de Operaciones (`/ops` para perfiles de cliente) | motor `client_home` |
| 5.13 Conocimiento | biblioteca con tipos (blueprint, AS-IS, TO-BE, GAP, manuales, runbooks…), Drive por referencia, versión vigente/canónica | `aq.ops.document` |
| 5.14 Notificaciones | 12 categorías con prioridad y acción directa, correo, resúmenes diario/semanal, integraciones preparadas | `aq.ops.notification`, `aq.ops.integration` |
| 5.15 Reportes | `/ops/reports`: los 20 indicadores (cumplimiento de hitos, desviación, predictibilidad, ciclo, bloqueado, antigüedad, no planificado, cambios, espera del cliente, aceptación, capacidad, estimado vs real, retrabajo, defectos, liberaciones, incidentes, SLA, salud, participación del cliente) | motor `ops_kpis` |

## Flujos imprescindibles (implementados como reglas)
* **Inicio**: `action_start` exige PM, alcance, equipo, validadores, primer hito, siguiente acción, fecha y ruta de escalación; emite *Proyecto listo para iniciar*.
* **Cambio**: solicitud → clasificación → análisis → estimación e impacto → `action_send_commercial` (evento a Administración) → autorización en Administración (automática al autorizar el Control de cambios) → `action_incorporate` (backlog + alcance versionado) → aceptación → `action_accepted` (evento facturable).
* **Validación**: listo para validar → aceptación electrónica inmutable → Operaciones actúa → Administración recibe *Entregable aceptado* / *Hito validado*.
* **Incidente**: 11 pasos con verificaciones de documentación y liberación controlada para S1/S2.
* **Cierre**: `action_ready_to_close` exige entregables aceptados y emite *Proyecto listo para cierre* (facturación final).

## Eventos entre dominios (outbox)
`aq.ops.event` registra y procesa proyecciones: Ops→Admin (listo para iniciar, cambio solicitado, estimación aprobada, hito validado,
horas aprobadas, entregable aceptado, listo para cierre, trabajo administrativo remitido) y Admin→Ops (contrato activo/suspendido,
alcance autorizado, horas autorizadas, condición comercial, pago confirmado, restricción, contrato por vencer). Dirección envía
señales desde la ficha del proyecto administrativo; `POST /aq_portal/api/events/emit`.

## Automatizaciones (gobernadas, con propietario e historial)
Las 16 del documento están en **Configuración → Automatizaciones** (`aq.ops.automation`), ejecutadas por el cron diario/semanal
o integradas en el flujo (bloqueo de liberaciones incompletas, revisión post-liberación, tareas desde minutas tras confirmación).

## Copiloto de IA — DeepSeek por API
**Clave**: variable de entorno `DEEPSEEK_API_KEY` en el servidor (recomendado; no se guarda en BD ni en el repositorio). Orden de prioridad: `DEEPSEEK_API_KEY` → parámetro del sistema `aq_ops.deepseek_api_key` → campo del registro en *Integraciones → DeepSeek*. Opcionales: `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` (por defecto `https://api.deepseek.com`, `deepseek-chat`). Todas las funciones de IA pasan por `aq.ops.ai.chat()`; `GET /ops/ai/status` muestra la fuente activa.
Usa el endpoint compatible `/chat/completions`. Capacidades: resumir reuniones y proponer acuerdos/tareas/preguntas/riesgos,
explicar por qué un proyecto está en rojo, recomendar siguiente acción, detectar duplicados, sugerir dependencias, comparar
alcance con una solicitud, preparar casos de prueba, resumir incidentes, borrador de reporte. Sin clave usa heurísticas locales.
Por diseño **no** aprueba, altera alcance, acepta entregables, autoriza liberaciones, cambia fechas, envía comunicaciones
vinculantes, cierra incidentes ni toma decisiones comerciales: toda propuesta requiere confirmación humana.

## Plantillas
Nueve plantillas (`data/ops_templates.xml`) con fases/hitos y elementos iniciales: blueprint, implementación Odoo, desarrollo,
migración, soporte, regulado, capacitación, cierre/handoff y creativo/catálogo. Se aplican al crear el proyecto.

## Fase 3 y operación
* **PWA**: manifest + service worker (`/admin-portal/sw.js`): instalable en móvil/escritorio, cascarón sin conexión y última información conocida en modo lectura.
* **Actualización en vivo**: sondeo ligero `/ops/live` (45 s) con aviso de nuevas notificaciones; indicador de desconexión.
* **Canales**: portal, correo (resumen diario/semanal), **calendario ICS** (`/ops/calendar.ics`) y **webhooks** Teams / Slack / WhatsApp (Integraciones).
* **Pronósticos**: consumo semanal, fecha de agotamiento de la bolsa, velocidad y fin pronosticado; **planeación predictiva de capacidad** a 4 semanas; **detección de anomalías** diaria.
* **Vistas guardadas** en servidor (`aq.ops.saved.view`, personales o compartidas).
* **Bitácora inmutable** (`aq.portal.audit.log` no admite edición ni borrado manual) y **políticas de retención** (`aq_ops.retention_days_*`).
* Proyectos semilla con plantilla aplicada: Stonia, SAI, Hexágonos, One of a Kind y Getting Ready.

## Experiencia de uso (AlphaOps)
* **Proyecto activo global** (sidebar, barra superior, paleta ⌘K, tecla `P`): filtra tablero, listados, solicitudes, Mi trabajo, tiempo y reportes; precarga el proyecto al crear. "Todos los proyectos" para la vista global.
* **Panel lateral (peek)** al tocar un elemento: esenciales editables, acciones de un toque (iniciar/terminar/bloquear/temporizador), subtareas tipo checklist y comentarios, sin salir del Kanban.
* **Edición en línea** de estado, responsable y fecha en Kanban y Lista; **acciones masivas** en Lista; **alta rápida** con plantillas por tipo (tarea, historia, defecto, entregable, requerimiento).
* **Ficha simplificada**: esenciales primero y "Más detalles" colapsado (elementos, solicitudes, incidentes, RAID).
* **Hoy** (`/ops/today`, tecla `H`): agenda móvil con botones táctiles.
* **Filtros guardados** por persona o equipo en cada listado; **notificaciones accionables** (aprobar, desbloquear, aprobar tiempo/decisión/liberación, incorporar cambio).
* Atajos: `N` nuevo, `B` tablero, `M` mi trabajo, `H` hoy, `P` proyecto, `/` buscar.

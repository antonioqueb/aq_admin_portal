# AlphaQueb · Portal de Control Administrativo (`aq_admin_portal`)

Módulo para **Odoo 19** que expone un **portal web externo** (React, bundle independiente de los assets de Odoo)
con **usuarios propios** (no son `res.users`), para la coordinación administrativa y el control operativo
descrito en la carta de incorporación de la coordinadora administrativa.

## Qué incluye

| Sección de la carta | Recurso del portal | Modelo Odoo |
|---|---|---|
| 1.1 Control general de proyectos | Control maestro de proyectos (+ fechas relevantes, pasos del procedimiento, entregables) | `aq.portal.project`, `aq.portal.project.date`, `aq.portal.project.step`, `aq.portal.deliverable` |
| 1.2 Seguimiento de acuerdos y pendientes | Acuerdos y pendientes (solicitar actualización, escalar, autorizar, formalizar acuerdos verbales/WhatsApp) | `aq.portal.agreement` |
| 1.3 Facturación | Calendario de facturación (datos fiscales, evidencia, envío, recepción, complemento, detener y validar) | `aq.portal.invoice.schedule` |
| 1.4 Cuentas por cobrar y cobranza | CxC con pagos, seguimientos, compromisos de pago, riesgo, escalamiento y convenios autorizados por Dirección | `aq.portal.receivable`, `aq.portal.receivable.payment` |
| 1.5 Cuentas por pagar | CxP por categoría con autorización y ejecución reservadas a Dirección, recurrencias | `aq.portal.payable` |
| 1.6 Horas, alcances y trabajo facturable | Bolsas de horas, registro de horas, hallazgos (sin facturar, sin registro, fuera de alcance, sin autorización) | `aq.portal.hour.bucket`, `aq.portal.hour.entry` |
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
4. En Odoo: **Portal Administrativo → Administración → Usuarios externos del portal** → crear el primer
   usuario con rol *Dirección* y pulsar **Enviar enlace para establecer contraseña** (o escribir una
   contraseña en *Nueva contraseña*).
5. Abrir `https://<servidor>/admin-portal`.

Parámetros del sistema: `aq_admin_portal.stale_days` (5), `warn_days` (7), `prospect_days` (7),
`depletion_threshold` (80 %), `session_hours` (12).

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
* `GET|POST /users`, `PUT /users/<id>`, `POST /users/<id>/send-reset` (solo Dirección)

## Cron

`Portal administrativo: alertas, rutinas y estados (diario)` — genera los checklists de rutina, actualiza
estados de cobranza/pagos/obligaciones/contratos, recalcula alertas, alimenta la matriz de riesgos y envía
el resumen diario de alertas a Dirección y Coordinación.

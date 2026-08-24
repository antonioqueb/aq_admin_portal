# -*- coding: utf-8 -*-
"""Alphaops · solicitudes (embudo único), elementos de trabajo (una sola fuente de verdad), cambios, comentarios, vistas."""
import json
import re
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

REQUEST_SOURCES = [("cliente", "Cliente"), ("empleado_cliente", "Empleado del cliente"), ("reunion", "Reunión"), ("correo", "Correo"),
                   ("consultor", "Consultor"), ("soporte", "Soporte"), ("direccion", "Dirección"), ("incidente_produccion", "Incidente en producción"),
                   ("revision_calidad", "Revisión de calidad")]
REQUEST_TYPES = [("pregunta", "Pregunta"), ("solicitud_operativa", "Solicitud operativa"), ("defecto", "Defecto"), ("incidente", "Incidente"),
                 ("requerimiento", "Requerimiento"), ("cambio_alcance", "Cambio de alcance"), ("mejora", "Mejora"), ("deuda_tecnica", "Deuda técnica"),
                 ("capacitacion", "Capacitación"), ("acceso_configuracion", "Acceso o configuración"), ("administrativo", "Trabajo administrativo (remitir a Administración)"),
                 ("sin_clasificar", "Sin clasificar")]
SCOPE_DECISIONS = [("en_alcance", "1. Incluida en el alcance"), ("soporte", "2. Pertenece a soporte"), ("estimacion", "3. Requiere estimación"),
                   ("aprobacion_comercial", "4. Necesita aprobación comercial"), ("urgente", "5. Urgente por afectación productiva"),
                   ("devolver", "6. Rechazar / devolver por falta de información"), ("pendiente", "Pendiente de análisis")]
ITEM_TYPES = [("objetivo", "Objetivo"), ("capacidad", "Capacidad"), ("epica", "Épica"), ("proceso", "Proceso"), ("requerimiento", "Requerimiento"),
              ("historia", "Historia de usuario"), ("entregable", "Entregable"), ("tarea", "Tarea"), ("subtarea", "Subtarea"), ("prueba", "Prueba"),
              ("defecto", "Defecto"), ("cambio", "Cambio"), ("revision_post_liberacion", "Revisión post-liberación")]
ITEM_STATES = [("backlog", "Backlog"), ("por_hacer", "Por hacer"), ("en_progreso", "En progreso"), ("bloqueado", "Bloqueado"),
               ("desarrollo_completado", "Desarrollo completado"), ("revision_tecnica", "Revisión técnica"), ("qa_interno", "QA interno"),
               ("correccion", "Corrección de defectos"), ("regresion", "Pruebas de regresión"), ("listo_validacion", "Listo para validación"),
               ("validacion_cliente", "Validación del cliente"), ("aceptado", "Aceptado"), ("listo_liberar", "Listo para liberar"),
               ("liberado", "Liberado"), ("verificado", "Verificado"), ("cerrado", "Cerrado"), ("cancelado", "Cancelado")]
DONE_STATES = ("aceptado", "liberado", "verificado", "cerrado", "cancelado")


def _tokens(s):
    return set(w for w in re.findall(r"[a-záéíóúñ0-9]{4,}", (s or "").lower()))


class OpsRequest(models.Model):
    """5.4 Entrada y clasificación de solicitudes. El cliente nunca crea tareas: crea solicitudes."""
    _name = "aq.ops.request"
    _description = "Alphaops: solicitud"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "create_date desc"

    name = fields.Char(string="Solicitud", required=True, tracking=True)
    description = fields.Text(string="Descripción")
    source = fields.Selection(REQUEST_SOURCES, required=True, default="cliente", string="Origen")
    request_type = fields.Selection(REQUEST_TYPES, default="sin_clasificar", string="Clasificación", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Organización", required=True)
    project_id = fields.Many2one("aq.ops.project", string="Proyecto")
    requester_partner_id = fields.Many2one("res.partner", string="Solicitante (cliente)")
    requester_user_id = fields.Many2one("aq.portal.user", string="Usuario solicitante", readonly=True)
    requester_department = fields.Char(string="Área del solicitante")
    urgency = fields.Selection([("baja", "Baja"), ("media", "Media"), ("alta", "Alta"), ("critica", "Crítica (afecta producción)")], default="media")
    impact = fields.Text(string="Impacto identificado")
    scope_decision = fields.Selection(SCOPE_DECISIONS, default="pendiente", string="Determinación", tracking=True)
    missing_info = fields.Text(string="Información faltante / motivo de devolución")
    duplicate_of_id = fields.Many2one("aq.ops.request", string="Duplicado de")
    potential_duplicate_ids = fields.Many2many("aq.ops.request", "aq_ops_request_dup_rel", "req_id", "dup_id", compute="_compute_duplicates", string="Posibles duplicados")
    state = fields.Selection([("nueva", "Nueva"), ("clasificada", "Clasificada"), ("analisis", "En análisis"), ("esperando_info", "Esperando información"),
                              ("convertida", "Convertida"), ("respondida", "Respondida"), ("rechazada", "Rechazada"), ("remitida_admin", "Remitida a Administración"),
                              ("cerrada", "Cerrada")], default="nueva", tracking=True)
    assignee_id = fields.Many2one("aq.portal.member", string="Atiende")
    response = fields.Text(string="Respuesta al solicitante")
    response_date = fields.Datetime(readonly=True)
    first_response_hours = fields.Float(compute="_compute_sla", store=True, string="Tiempo de primera respuesta (h)")
    item_id = fields.Many2one("aq.ops.item", string="Elemento generado", readonly=True)
    change_id = fields.Many2one("aq.ops.change", string="Cambio generado", readonly=True)
    incident_id = fields.Many2one("aq.ops.incident", string="Incidente generado", readonly=True)
    client_visible = fields.Boolean(default=True)
    comment_ids = fields.One2many("aq.ops.comment", "request_id", string="Conversación")
    attachments_count = fields.Integer(compute="_compute_att")
    ai_suggestion = fields.Text(string="Sugerencia del copiloto", readonly=True)

    def _compute_att(self):
        Att = self.env["ir.attachment"].sudo()
        for r in self:
            r.attachments_count = Att.search_count([("res_model", "=", self._name), ("res_id", "=", r.id)])

    @api.depends("response_date", "create_date")
    def _compute_sla(self):
        for r in self:
            r.first_response_hours = ((r.response_date - r.create_date).total_seconds() / 3600.0) if (r.response_date and r.create_date) else 0.0

    def _compute_duplicates(self):
        for r in self:
            toks = _tokens(r.name + " " + (r.description or ""))
            cands = self.search([("partner_id", "=", r.partner_id.id), ("id", "!=", r.id), ("state", "not in", ("rechazada", "cerrada"))], limit=200)
            dups = cands.filtered(lambda c: len(toks & _tokens(c.name + " " + (c.description or ""))) >= max(3, int(len(toks) * 0.5)))
            r.potential_duplicate_ids = dups[:5]

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            if r.project_id and self.env["aq.ops.ai"].available() and not self.env.context.get("portal_import"):
                try:
                    self.env["aq.ops.ai"].classify_request(r)
                except Exception:  # noqa
                    pass
            if r.potential_duplicate_ids:
                self.env["aq.ops.notification"].notify_role(r.project_id, ["pm"], "accion_requerida", _("Posible solicitud duplicada: %s") % r.name, "requests", r.id)
            self.env["aq.ops.notification"].notify_role(r.project_id, ["pm", "support"], "accion_requerida", _("Nueva solicitud: %s") % r.name, "requests", r.id)
        return recs

    def action_classify(self):
        for r in self:
            if r.request_type == "sin_clasificar":
                raise UserError(_("Seleccione una clasificación."))
            if r.scope_decision == "pendiente":
                raise UserError(_("Indique la determinación (alcance, soporte, estimación, aprobación comercial, urgente o devolver)."))
            if r.request_type == "administrativo":
                r.write({"state": "remitida_admin"})
                self.env["aq.ops.event"].emit("ops", "admin_work_referred", r, {"request": r.name, "organization": r.partner_id.name})
                continue
            if r.scope_decision == "devolver":
                r.write({"state": "esperando_info"})
                continue
            r.write({"state": "clasificada"})
            if r.scope_decision == "aprobacion_comercial" or r.request_type == "cambio_alcance":
                self.env["aq.ops.notification"].notify_role(r.project_id, ["pm"], "accion_requerida", _("El cliente solicita un cambio fuera de alcance: %s") % r.name, "requests", r.id)
        return True

    def action_convert_item(self):
        for r in self:
            if r.scope_decision not in ("en_alcance", "soporte", "urgente"):
                raise UserError(_("Solo se convierte directamente a elemento de trabajo cuando está en alcance, es soporte o es urgente. Si requiere estimación o autorización, conviértala en cambio."))
            t = {"defecto": "defecto", "requerimiento": "requerimiento", "mejora": "historia", "deuda_tecnica": "tarea", "capacitacion": "tarea", "acceso_configuracion": "tarea"}.get(r.request_type, "tarea")
            item = self.env["aq.ops.item"].create({"name": r.name, "description": r.description, "item_type": t, "project_id": r.project_id.id, "request_id": r.id,
                                                   "priority": "2" if r.urgency == "critica" else "1" if r.urgency == "alta" else "0", "client_visible": r.client_visible})
            r.write({"item_id": item.id, "state": "convertida"})
        return True

    def action_convert_change(self):
        for r in self:
            ch = self.env["aq.ops.change"].create({"name": r.name, "description": r.description, "project_id": r.project_id.id, "request_id": r.id,
                                                   "requested_by": r.requester_partner_id.name or r.source})
            r.write({"change_id": ch.id, "state": "convertida", "request_type": "cambio_alcance"})
        return True

    def action_convert_incident(self):
        for r in self:
            inc = self.env["aq.ops.incident"].create({"name": r.name, "description": r.description, "project_id": r.project_id.id, "partner_id": r.partner_id.id,
                                                      "request_id": r.id, "severity": "S1" if r.urgency == "critica" else "S2" if r.urgency == "alta" else "S3"})
            r.write({"incident_id": inc.id, "state": "convertida", "request_type": "incidente"})
        return True

    def action_respond(self):
        for r in self:
            if not r.response:
                raise UserError(_("Escriba la respuesta."))
            r.write({"state": "respondida", "response_date": fields.Datetime.now()})
            if r.requester_user_id:
                self.env["aq.ops.notification"].push(r.requester_user_id, "cliente_respondio", _("Respuesta a su solicitud: %s") % r.name, "requests", r.id)
        return True

    def action_reject(self):
        self.write({"state": "rechazada"})
        return True


class OpsItem(models.Model):
    """5.5 / 5.6 / 5.9 · Un elemento operativo existe una sola vez; backlog, kanban, calendario, sprint, Gantt y portal del cliente son vistas del mismo objeto."""
    _name = "aq.ops.item"
    _description = "Alphaops: elemento de trabajo"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "rank, priority desc, id"
    _parent_name = "parent_id"

    name = fields.Char(required=True, tracking=True)
    item_type = fields.Selection(ITEM_TYPES, required=True, default="tarea", tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    parent_id = fields.Many2one("aq.ops.item", string="Elemento padre", ondelete="set null", index=True)
    child_ids = fields.One2many("aq.ops.item", "parent_id", string="Hijos")
    description = fields.Html()
    acceptance_criteria = fields.Text(string="Criterios de aceptación")
    state = fields.Selection(ITEM_STATES, default="backlog", tracking=True, index=True)
    state_since = fields.Datetime(default=fields.Datetime.now, readonly=True)
    days_in_state = fields.Integer(compute="_compute_age")
    age_days = fields.Integer(compute="_compute_age", string="Antigüedad (días)")
    priority = fields.Selection([("0", "Normal"), ("1", "Alta"), ("2", "Crítica")], default="0")
    rank = fields.Integer(default=1000, string="Orden en backlog")
    sequence = fields.Integer(default=10)
    assignee_id = fields.Many2one("aq.portal.member", string="Responsable", tracking=True, index=True)
    reviewer_id = fields.Many2one("aq.portal.member", string="Revisor / QA")
    validator_partner_id = fields.Many2one("res.partner", string="Valida (cliente)")
    validator_department = fields.Char(string="Departamento validador")
    milestone_id = fields.Many2one("aq.ops.milestone", string="Hito")
    sprint_id = fields.Many2one("aq.ops.sprint", string="Sprint")
    deliverable_id = fields.Many2one("aq.ops.item", string="Entregable al que contribuye", domain="[('item_type','=','entregable'),('project_id','=',project_id)]")
    request_id = fields.Many2one("aq.ops.request", string="Solicitud origen")
    change_id = fields.Many2one("aq.ops.change", string="Cambio de alcance")
    meeting_id = fields.Many2one("aq.ops.meeting", string="Reunión origen")
    decision_id = fields.Many2one("aq.ops.decision", string="Decisión relacionada")
    release_id = fields.Many2one("aq.ops.release", string="Liberación")
    incident_id = fields.Many2one("aq.ops.incident", string="Incidente")
    # planeación
    date_start = fields.Date(string="Inicio")
    date_due = fields.Date(string="Fecha comprometida", tracking=True)
    date_baseline = fields.Date(string="Fecha · plan original")
    reschedule_count = fields.Integer(readonly=True, string="Reprogramaciones")
    reschedule_reason = fields.Text(string="Motivo de la última reprogramación")
    estimate_hours = fields.Float(string="Estimación (h)")
    remaining_hours = fields.Float(string="Esfuerzo restante (h)")
    spent_hours = fields.Float(compute="_compute_spent", store=True, string="Horas registradas")
    depends_on_ids = fields.Many2many("aq.ops.item", "aq_ops_item_dep_rel", "item_id", "depends_id", string="Depende de")
    dependent_ids = fields.Many2many("aq.ops.item", "aq_ops_item_dep_rel", "depends_id", "item_id", string="Bloquea a")
    blocked_reason = fields.Text(string="Motivo del bloqueo")
    blocked_since = fields.Datetime(readonly=True)
    blocked_hours = fields.Float(compute="_compute_age", string="Tiempo bloqueado (h)")
    waiting_client = fields.Boolean(string="Esperando al cliente")
    waiting_client_since = fields.Date(readonly=True)
    is_recurring = fields.Boolean(string="Trabajo recurrente")
    recurrence_days = fields.Integer(string="Cada N días")
    unplanned = fields.Boolean(string="Trabajo no planificado")
    is_rework = fields.Boolean(string="Retrabajo")
    found_in = fields.Selection([("interno", "Encontrado internamente"), ("produccion", "Encontrado en producción")], string="Defecto encontrado")
    tags = fields.Char(string="Etiquetas")
    # aceptación
    evidence = fields.Text(string="Evidencia")
    accepted = fields.Boolean(readonly=True, string="Aceptado")
    accepted_date = fields.Date(readonly=True)
    acceptance_ids = fields.One2many("aq.ops.acceptance", "item_id", string="Validaciones")
    test_case_ids = fields.One2many("aq.ops.test.case", "item_id", string="Casos de prueba")
    timesheet_ids = fields.One2many("aq.ops.timesheet", "item_id", string="Tiempo")
    comment_ids = fields.One2many("aq.ops.comment", "item_id", string="Comunicación")
    client_visible = fields.Boolean(default=False, string="Visible para el cliente")
    internal_notes = fields.Text(string="Notas internas (nunca visibles al cliente)")
    done_date = fields.Date(readonly=True)
    cycle_days = fields.Integer(compute="_compute_cycle", store=True, string="Tiempo de ciclo (días)")
    lead_days = fields.Integer(compute="_compute_cycle", store=True, string="Lead time (días)")
    started_date = fields.Date(readonly=True)
    active = fields.Boolean(default=True)

    @api.depends("timesheet_ids.hours", "timesheet_ids.state")
    def _compute_spent(self):
        for i in self:
            i.spent_hours = sum(i.timesheet_ids.filtered(lambda t: t.state != "rechazado").mapped("hours"))

    def _compute_age(self):
        now = fields.Datetime.now()
        for i in self:
            i.days_in_state = (now - (i.state_since or i.create_date or now)).days
            i.age_days = (now - (i.create_date or now)).days if i.state not in DONE_STATES else 0
            i.blocked_hours = ((now - i.blocked_since).total_seconds() / 3600.0) if (i.state == "bloqueado" and i.blocked_since) else 0.0

    @api.depends("done_date", "started_date", "create_date")
    def _compute_cycle(self):
        for i in self:
            i.cycle_days = (i.done_date - i.started_date).days if (i.done_date and i.started_date) else 0
            i.lead_days = (i.done_date - i.create_date.date()).days if (i.done_date and i.create_date) else 0

    @api.constrains("state", "acceptance_criteria", "item_type")
    def _check_acceptance(self):
        for i in self:
            if i.item_type == "entregable" and i.state in ("listo_validacion", "validacion_cliente", "aceptado", "cerrado") and not i.acceptance_criteria:
                raise ValidationError(_("Regla Alphaops: ningún entregable avanza a validación ni se cierra sin criterio de aceptación (%s).") % i.name)
            if i.state == "aceptado" and not i.accepted:
                raise ValidationError(_("'Aceptado' solo se alcanza mediante una validación registrada (aceptación electrónica)."))

    @api.constrains("depends_on_ids")
    def _check_cycle(self):
        for i in self:
            seen, stack = set(), list(i.depends_on_ids)
            while stack:
                d = stack.pop()
                if d == i:
                    raise ValidationError(_("Dependencia circular en %s.") % i.name)
                if d.id not in seen:
                    seen.add(d.id); stack.extend(d.depends_on_ids)

    def write(self, vals):
        now = fields.Datetime.now()
        for i in self:
            v = dict(vals)
            if "state" in vals and vals["state"] != i.state:
                v["state_since"] = now
                if vals["state"] == "bloqueado":
                    v["blocked_since"] = now
                    self.env["aq.ops.notification"].notify_role(i.project_id, ["pm"], "bloqueo", _("Bloqueado: %s") % i.name, "items", i.id)
                if vals["state"] == "en_progreso":
                    if not i.started_date:
                        v["started_date"] = fields.Date.today()
                    # límite WIP
                    assignee = vals.get("assignee_id", i.assignee_id.id)
                    if assignee and i.project_id.wip_limit:
                        wip = self.search_count([("assignee_id", "=", assignee), ("state", "=", "en_progreso"), ("id", "!=", i.id)])
                        if wip >= i.project_id.wip_limit and not self.env.context.get("aq_force_wip"):
                            raise UserError(_("Límite WIP alcanzado (%d en progreso). Termine o reprograme antes de iniciar otro elemento.") % wip)
                if vals["state"] in DONE_STATES and vals["state"] != "cancelado":
                    v["done_date"] = fields.Date.today()
                    for dep in i.dependent_ids.filtered(lambda d: d.state == "bloqueado"):
                        self.env["aq.ops.notification"].notify_member(dep.assignee_id, "dependencia_liberada", _("Dependencia liberada: %s → %s") % (i.name, dep.name), "items", dep.id)
                if vals["state"] == "listo_validacion":
                    self.env["aq.ops.notification"].notify_partner(i.validator_partner_id or i.project_id.validator_ids[:1], "aprobacion", _("Listo para su validación: %s") % i.name, "items", i.id)
            if "date_due" in vals and i.date_due and vals["date_due"] and fields.Date.to_date(vals["date_due"]) != i.date_due:
                v["reschedule_count"] = i.reschedule_count + 1
                if not vals.get("reschedule_reason") and not self.env.context.get("aq_auto"):
                    raise UserError(_("Reprogramación controlada: indique el motivo del cambio de fecha de '%s'.") % i.name)
                self.env["aq.ops.notification"].notify_member(i.assignee_id, "cambio_fecha", _("Cambio de fecha: %s → %s") % (i.name, vals["date_due"]), "items", i.id)
            if "waiting_client" in vals:
                v["waiting_client_since"] = fields.Date.today() if vals["waiting_client"] else False
            super(OpsItem, i).write(v)
        if self and self[0].project_id:
            self.mapped("project_id").portal_touch()
        return True

    def action_block(self):
        self.write({"state": "bloqueado"})
        return True

    def action_unblock(self):
        self.write({"state": "en_progreso"})
        return True

    def action_ready_for_validation(self):
        for i in self:
            if i.test_case_ids and any(tc.last_result != "pass" for tc in i.test_case_ids):
                raise UserError(_("Hay casos de prueba sin pasar. 'Terminado por desarrollo' no significa 'entregado'."))
            i.write({"state": "listo_validacion"})
        return True

    def action_create_recurrence(self):
        for i in self.filtered("is_recurring"):
            i.copy({"state": "por_hacer", "date_due": fields.Date.add(i.date_due or fields.Date.today(), days=i.recurrence_days or 7), "accepted": False,
                    "accepted_date": False, "done_date": False, "started_date": False})
        return True


class OpsChange(models.Model):
    """6 · Solicitud → clasificación → análisis → estimación e impacto → autorización comercial (Administración) → backlog → ejecución → prueba → aceptación → evento facturable."""
    _name = "aq.ops.change"
    _description = "Alphaops: cambio de alcance"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "create_date desc"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    request_id = fields.Many2one("aq.ops.request", string="Solicitud origen")
    meeting_id = fields.Many2one("aq.ops.meeting", string="Reunión donde se mencionó")
    requested_by = fields.Char(string="Solicitado por")
    description = fields.Text()
    scope_analysis = fields.Text(string="Análisis de alcance (¿por qué no está incluido?)")
    impact = fields.Text(string="Impacto (tiempo, calidad, dependencias)")
    estimate_hours = fields.Float(string="Estimación operativa (h)")
    estimated_by_id = fields.Many2one("aq.portal.member", string="Estimó")
    estimate_approved = fields.Boolean(string="Estimación operativa aprobada (PM/Dirección de Operaciones)")
    state = fields.Selection([("solicitado", "Solicitado"), ("analisis", "En análisis"), ("estimado", "Estimado"),
                              ("pendiente_comercial", "Pendiente de autorización comercial (Administración)"),
                              ("autorizado", "Autorizado comercialmente"), ("rechazado", "Rechazado"), ("incorporado", "Incorporado al backlog"),
                              ("ejecutado", "Ejecutado"), ("aceptado", "Aceptado"), ("facturable", "Evento facturable emitido")], default="solicitado", tracking=True)
    commercial_ref = fields.Char(string="Referencia comercial autorizada", readonly=True)
    authorized_hours = fields.Float(string="Horas autorizadas", readonly=True)
    item_ids = fields.One2many("aq.ops.item", "change_id", string="Elementos")
    client_visible = fields.Boolean(default=True)

    def action_send_commercial(self):
        for c in self:
            if not (c.impact and c.estimate_hours and c.estimate_approved):
                raise UserError(_("Regla Alphaops: ningún cambio de alcance sin impacto, estimación y aprobación operativa antes de la autorización comercial."))
            c.write({"state": "pendiente_comercial"})
            self.env["aq.ops.event"].emit("ops", "scope_change_requested", c, {"project": c.project_id.name, "change": c.name, "hours": c.estimate_hours, "impact": c.impact})
            self.env["aq.ops.event"].emit("ops", "estimate_approved", c, {"project": c.project_id.name, "change": c.name, "hours": c.estimate_hours})
        return True

    def action_incorporate(self):
        for c in self:
            if c.state != "autorizado":
                raise UserError(_("Solo se incorpora al backlog un cambio autorizado comercialmente."))
            self.env["aq.ops.item"].create({"name": c.name, "item_type": "cambio", "project_id": c.project_id.id, "change_id": c.id,
                                            "estimate_hours": c.estimate_hours, "acceptance_criteria": c.description, "client_visible": c.client_visible})
            c.project_id.write({"scope_current": (c.project_id.scope_current or "") + "\n\n[Cambio autorizado %s] %s" % (c.commercial_ref or "", c.name)})
            c.project_id.action_update_scope()
            c.write({"state": "incorporado"})
        return True

    def action_accepted(self):
        for c in self:
            if any(not i.accepted for i in c.item_ids):
                raise UserError(_("Todos los elementos del cambio deben estar aceptados."))
            c.write({"state": "facturable"})
            self.env["aq.ops.event"].emit("ops", "deliverable_accepted", c, {"project": c.project_id.name, "change": c.name, "hours": c.authorized_hours or c.estimate_hours})
        return True


class OpsComment(models.Model):
    """5.14 comunicación operativa con menciones @; separa interno vs. visible al cliente."""
    _name = "aq.ops.comment"
    _description = "Alphaops: comentario"
    _order = "create_date desc"
    body = fields.Text(required=True)
    author_user_id = fields.Many2one("aq.portal.user", string="Autor", readonly=True)
    item_id = fields.Many2one("aq.ops.item", ondelete="cascade")
    request_id = fields.Many2one("aq.ops.request", ondelete="cascade")
    incident_id = fields.Many2one("aq.ops.incident", ondelete="cascade")
    project_id = fields.Many2one("aq.ops.project", ondelete="cascade")
    internal = fields.Boolean(string="Solo interno", default=True)
    mention_ids = fields.Many2many("aq.portal.member", string="Menciones")

    @api.model_create_multi
    def create(self, vals_list):
        pu = self.env.context.get("portal_user_id")
        for v in vals_list:
            v.setdefault("author_user_id", pu)
        recs = super().create(vals_list)
        Member = self.env["aq.portal.member"]
        for c in recs:
            names = re.findall(r"@([\wÁÉÍÓÚáéíóúñ]+)", c.body or "")
            members = Member
            for n in names:
                members |= Member.search([("name", "ilike", n)], limit=1)
            if members:
                c.write({"mention_ids": [(6, 0, members.ids)]})
                res = ("items", c.item_id.id) if c.item_id else ("requests", c.request_id.id) if c.request_id else ("incidents", c.incident_id.id) if c.incident_id else ("projects", c.project_id.id)
                for m in members:
                    self.env["aq.ops.notification"].notify_member(m, "mencion", _("Te mencionaron: %s") % (c.body or "")[:80], res[0], res[1])
            if not c.internal and c.request_id and c.author_user_id and not c.author_user_id.is_external:
                pass
            if not c.internal and c.request_id and c.author_user_id and c.author_user_id.is_external:
                self.env["aq.ops.notification"].notify_role(c.request_id.project_id, ["pm", "support"], "cliente_respondio", _("El cliente respondió: %s") % c.request_id.name, "requests", c.request_id.id)
        return recs


class OpsSavedView(models.Model):
    _name = "aq.ops.saved.view"
    _description = "Alphaops: vista guardada"
    name = fields.Char(required=True)
    user_id = fields.Many2one("aq.portal.user", required=True)
    resource = fields.Char(required=True)
    view_mode = fields.Char(default="list")
    filters_json = fields.Text()
    shared = fields.Boolean(string="Compartida con el equipo")

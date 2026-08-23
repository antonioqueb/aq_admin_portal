# -*- coding: utf-8 -*-
"""AlphaOps · proyectos, hitos, ambientes, sprints, plantillas, reportes de estado."""
import json
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

SERVICE_TYPES = [
    ("blueprint", "Análisis y blueprint"), ("implementacion", "Implementación Odoo"), ("desarrollo", "Desarrollo personalizado"),
    ("migracion", "Migración de datos"), ("soporte", "Soporte y estabilización"), ("regulado", "Proyecto regulado"),
    ("capacitacion", "Capacitación"), ("cierre", "Cierre y handoff"), ("creativo", "Proyecto creativo o catálogo"),
]
PROJECT_STAGES = [
    ("autorizado", "Autorizado (sobre recibido de Administración)"), ("preparacion", "Preparación"), ("kickoff", "Kickoff"),
    ("linea_base", "Línea base"), ("ejecucion", "Ejecución"), ("estabilizacion", "Estabilización"),
    ("cierre", "Cierre / handoff"), ("soporte", "Soporte"), ("pausado", "Pausado"), ("cerrado", "Cerrado"),
]
HEALTH = [("verde", "Verde"), ("amarillo", "Amarillo"), ("rojo", "Rojo")]
ACTIVE_STAGES = ("preparacion", "kickoff", "linea_base", "ejecucion", "estabilizacion", "cierre", "soporte")


class OpsTemplate(models.Model):
    _name = "aq.ops.template"
    _description = "AlphaOps: plantilla de proyecto"
    _order = "sequence"

    name = fields.Char(required=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(string="Uso principal")
    methodology = fields.Selection([("kanban", "Kanban"), ("scrum", "Scrum"), ("fases", "Por fases"), ("mixto", "Mixto")], default="mixto")
    phase_ids = fields.One2many("aq.ops.template.phase", "template_id", string="Fases / hitos")
    item_ids = fields.One2many("aq.ops.template.item", "template_id", string="Elementos iniciales")
    wip_limit = fields.Integer(string="Límite WIP sugerido", default=3)


class OpsTemplatePhase(models.Model):
    _name = "aq.ops.template.phase"
    _description = "AlphaOps: fase de plantilla"
    _order = "sequence"
    template_id = fields.Many2one("aq.ops.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    offset_days = fields.Integer(string="Días desde el inicio", default=0)
    enables_billing = fields.Boolean(string="Habilita facturación al validarse")


class OpsTemplateItem(models.Model):
    _name = "aq.ops.template.item"
    _description = "AlphaOps: elemento de plantilla"
    _order = "sequence"
    template_id = fields.Many2one("aq.ops.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    item_type = fields.Selection([("objetivo", "Objetivo"), ("capacidad", "Capacidad"), ("epica", "Épica"), ("proceso", "Proceso"),
                                  ("requerimiento", "Requerimiento"), ("historia", "Historia de usuario"), ("entregable", "Entregable"),
                                  ("tarea", "Tarea"), ("prueba", "Prueba")], default="entregable")
    acceptance_criteria = fields.Text()
    estimate_hours = fields.Float()


class OpsProject(models.Model):
    """5.3 Centro de mando del proyecto."""
    _name = "aq.ops.project"
    _description = "AlphaOps: proyecto"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "priority desc, name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Clave")
    partner_id = fields.Many2one("res.partner", string="Organización / cliente", required=True, domain=[("is_company", "=", True)], tracking=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True, default="implementacion", tracking=True)
    template_id = fields.Many2one("aq.ops.template", string="Plantilla aplicada")
    methodology = fields.Selection([("kanban", "Kanban"), ("scrum", "Scrum"), ("fases", "Por fases"), ("mixto", "Mixto")], default="mixto")
    stage = fields.Selection(PROJECT_STAGES, default="autorizado", required=True, tracking=True)
    priority = fields.Selection([("0", "Normal"), ("1", "Alta"), ("2", "Crítica")], default="0")
    objective = fields.Text(string="Objetivo")
    scope_current = fields.Text(string="Alcance vigente")
    scope_version = fields.Integer(string="Versión del alcance", default=1, readonly=True)
    scope_history = fields.Text(string="Historial de alcance (JSON)", readonly=True)
    # equipo
    pm_id = fields.Many2one("aq.portal.member", string="Project Manager", tracking=True)
    functional_lead_id = fields.Many2one("aq.portal.member", string="Líder funcional")
    tech_lead_id = fields.Many2one("aq.portal.member", string="Líder técnico")
    team_member_ids = fields.Many2many("aq.portal.member", "aq_ops_project_team_rel", "project_id", "member_id", string="Equipo interno")
    client_contact_ids = fields.Many2many("res.partner", "aq_ops_project_client_rel", "project_id", "partner_id", string="Equipo del cliente")
    validator_ids = fields.Many2many("res.partner", "aq_ops_project_validator_rel", "project_id", "partner_id", string="Responsables de validación")
    escalation_path = fields.Text(string="Ruta de escalación")
    # salud
    health_scope = fields.Selection(HEALTH, string="Salud · alcance", default="verde")
    health_time = fields.Selection(HEALTH, string="Salud · tiempo", default="verde")
    health_capacity = fields.Selection(HEALTH, string="Salud · capacidad", default="verde")
    health_quality = fields.Selection(HEALTH, string="Salud · calidad", default="verde")
    health_client = fields.Selection(HEALTH, string="Salud · colaboración del cliente", default="verde")
    health = fields.Selection(HEALTH, compute="_compute_health", store=True, string="Salud global")
    health_reason = fields.Text(compute="_compute_health", store=True, string="Por qué está en este color")
    risk_level = fields.Selection([("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto"), ("critico", "Crítico")], default="bajo", string="Riesgo")
    client_dependent = fields.Boolean(string="Esperando al cliente", compute="_compute_health", store=True)
    # fechas plan original vs vigente
    date_start = fields.Date(string="Inicio")
    date_end_baseline = fields.Date(string="Fin · línea base")
    date_end_current = fields.Date(string="Fin · plan vigente")
    date_end_probable = fields.Date(string="Fecha probable de conclusión", compute="_compute_probable", store=True)
    baseline_set_date = fields.Date(string="Línea base fijada el", readonly=True)
    # horas (solo cantidades; tarifas viven en Administración)
    hours_authorized = fields.Float(string="Horas autorizadas (de Administración)", readonly=True)
    hours_estimated = fields.Float(compute="_compute_hours", store=True, string="Horas estimadas")
    hours_consumed = fields.Float(compute="_compute_hours", store=True, string="Horas consumidas")
    hours_approved = fields.Float(compute="_compute_hours", store=True, string="Horas aprobadas")
    hours_remaining = fields.Float(compute="_compute_hours", store=True, string="Horas restantes")
    hours_pct = fields.Float(compute="_compute_hours", store=True, string="% consumido")
    commercial_restriction = fields.Boolean(string="Restricción comercial (falta de pago)", readonly=True)
    contract_state = fields.Selection([("activo", "Contrato activo"), ("suspendido", "Suspendido"), ("por_vencer", "Próximo a vencer"), ("sin_dato", "Sin dato")],
                                      default="sin_dato", readonly=True, string="Condición contractual")
    admin_project_ref = fields.Char(string="Referencia en Administración", readonly=True)
    admin_project_id = fields.Integer(string="ID proyecto administrativo", readonly=True)
    # siguiente acción (regla no negociable)
    next_action = fields.Char(string="Siguiente acción", tracking=True)
    next_action_owner_id = fields.Many2one("aq.portal.member", string="Responsable de la siguiente acción")
    next_action_date = fields.Date(string="Fecha compromiso", tracking=True)
    next_decision = fields.Char(string="Próxima decisión")
    # relaciones
    milestone_ids = fields.One2many("aq.ops.milestone", "project_id", string="Hitos")
    item_ids = fields.One2many("aq.ops.item", "project_id", string="Elementos de trabajo")
    request_ids = fields.One2many("aq.ops.request", "project_id", string="Solicitudes")
    change_ids = fields.One2many("aq.ops.change", "project_id", string="Cambios de alcance")
    meeting_ids = fields.One2many("aq.ops.meeting", "project_id", string="Reuniones")
    decision_ids = fields.One2many("aq.ops.decision", "project_id", string="Decisiones")
    raid_ids = fields.One2many("aq.ops.raid", "project_id", string="RAID")
    incident_ids = fields.One2many("aq.ops.incident", "project_id", string="Incidentes")
    release_ids = fields.One2many("aq.ops.release", "project_id", string="Liberaciones")
    environment_ids = fields.One2many("aq.ops.environment", "project_id", string="Ambientes")
    sprint_ids = fields.One2many("aq.ops.sprint", "project_id", string="Sprints")
    document_ids = fields.One2many("aq.ops.document", "project_id", string="Documentación")
    acceptance_ids = fields.One2many("aq.ops.acceptance", "project_id", string="Validaciones")
    report_ids = fields.One2many("aq.ops.status.report", "project_id", string="Reportes de estado")
    timesheet_ids = fields.One2many("aq.ops.timesheet", "project_id", string="Tiempo")
    link_ids = fields.One2many("aq.ops.link", "project_id", string="Accesos directos")
    next_milestone_id = fields.Many2one("aq.ops.milestone", compute="_compute_next", string="Próximo hito")
    pending_decisions = fields.Integer(compute="_compute_next", string="Decisiones pendientes")
    in_validation = fields.Integer(compute="_compute_next", string="Entregables en validación")
    open_risks = fields.Integer(compute="_compute_next", string="Riesgos abiertos")
    blocked_items = fields.Integer(compute="_compute_next", string="Elementos bloqueados")
    last_report_id = fields.Many2one("aq.ops.status.report", compute="_compute_next", string="Último reporte")
    days_without_activity = fields.Integer(compute="_compute_next")
    has_next_action = fields.Boolean(compute="_compute_next", search="_search_has_next")
    client_visible = fields.Boolean(default=True, string="Visible para el cliente")
    wip_limit = fields.Integer(string="Límite WIP por persona", default=3)
    active = fields.Boolean(default=True)

    # ---------- cómputos
    @api.depends("health_scope", "health_time", "health_capacity", "health_quality", "health_client", "item_ids.state", "item_ids.waiting_client", "raid_ids.state", "raid_ids.severity")
    def _compute_health(self):
        rank = {"verde": 0, "amarillo": 1, "rojo": 2}
        for p in self:
            dims = {"alcance": p.health_scope, "tiempo": p.health_time, "capacidad": p.health_capacity, "calidad": p.health_quality, "cliente": p.health_client}
            worst = max(dims.values(), key=lambda v: rank[v or "verde"])
            p.health = worst
            reasons = [k for k, v in dims.items() if v == worst and worst != "verde"]
            p.client_dependent = any(i.waiting_client and i.state not in ("cerrado", "cancelado") for i in p.item_ids)
            p.health_reason = (_("Dimensiones en %s: %s") % (worst, ", ".join(reasons))) if reasons else _("Todas las dimensiones en verde")

    @api.depends("item_ids.estimate_hours", "timesheet_ids.hours", "timesheet_ids.state", "hours_authorized")
    def _compute_hours(self):
        for p in self:
            p.hours_estimated = sum(p.item_ids.mapped("estimate_hours"))
            ts = p.timesheet_ids
            p.hours_consumed = sum(ts.filtered(lambda t: t.state != "rechazado").mapped("hours"))
            p.hours_approved = sum(ts.filtered(lambda t: t.state == "aprobado").mapped("hours"))
            p.hours_remaining = p.hours_authorized - p.hours_consumed
            p.hours_pct = (p.hours_consumed / p.hours_authorized * 100.0) if p.hours_authorized else 0.0

    @api.depends("date_end_current", "milestone_ids.date_current", "hours_pct")
    def _compute_probable(self):
        for p in self:
            dates = [m.date_current for m in p.milestone_ids if m.date_current and m.state != "validado"]
            p.date_end_probable = max(dates + [p.date_end_current]) if (dates or p.date_end_current) else False

    def _compute_next(self):
        today = fields.Date.today()
        for p in self:
            nm = p.milestone_ids.filtered(lambda m: m.state not in ("validado", "cancelado")).sorted(lambda m: m.date_current or today)[:1]
            p.next_milestone_id = nm.id if nm else False
            p.pending_decisions = len(p.decision_ids.filtered(lambda d: d.state == "propuesta"))
            p.in_validation = len(p.item_ids.filtered(lambda i: i.state in ("listo_validacion", "validacion_cliente")))
            p.open_risks = len(p.raid_ids.filtered(lambda r: r.raid_type == "risk" and r.state not in ("cerrado", "materializado")))
            p.blocked_items = len(p.item_ids.filtered(lambda i: i.state == "bloqueado"))
            p.last_report_id = p.report_ids.sorted("date", reverse=True)[:1].id if p.report_ids else False
            p.days_without_activity = (today - p.last_activity_date).days if p.last_activity_date else 0
            p.has_next_action = bool(p.next_action and p.next_action_owner_id and p.next_action_date)

    def _search_has_next(self, operator, value):
        dom = [("next_action", "!=", False), ("next_action_owner_id", "!=", False), ("next_action_date", "!=", False)]
        return dom if (operator == "=" and value) or (operator == "!=" and not value) else ["|", "|", ("next_action", "=", False), ("next_action_owner_id", "=", False), ("next_action_date", "=", False)]

    # ---------- reglas no negociables
    @api.constrains("stage", "next_action", "next_action_owner_id", "next_action_date", "pm_id")
    def _check_next_action(self):
        for p in self:
            if p.stage in ACTIVE_STAGES and not (p.next_action and p.next_action_owner_id and p.next_action_date):
                raise ValidationError(_("Regla AlphaOps: ningún proyecto activo puede quedarse sin siguiente acción, responsable y fecha compromiso (%s).") % p.name)

    def action_start(self):
        """Inicio formal: no arranca sin responsable, alcance, equipo, validadores, primer hito, siguiente acción, fecha y escalación."""
        for p in self:
            missing = []
            if not p.pm_id: missing.append(_("Project Manager"))
            if not p.scope_current: missing.append(_("alcance vigente"))
            if not p.team_member_ids: missing.append(_("equipo"))
            if not p.validator_ids: missing.append(_("autoridades de validación"))
            if not p.milestone_ids: missing.append(_("primer hito"))
            if not p.next_action or not p.next_action_owner_id: missing.append(_("siguiente acción y responsable"))
            if not p.next_action_date: missing.append(_("fecha compromiso"))
            if not p.escalation_path: missing.append(_("ruta de escalación"))
            if missing:
                raise UserError(_("No puede iniciar formalmente el proyecto. Falta: %s.") % ", ".join(missing))
            p.write({"stage": "ejecucion"})
            self.env["aq.ops.event"].emit("ops", "project_ready_to_start", p, {"project": p.name, "pm": p.pm_id.name})
        return True

    def action_set_baseline(self):
        for p in self:
            p.write({"date_end_baseline": p.date_end_current, "baseline_set_date": fields.Date.today(), "stage": "linea_base" if p.stage in ("preparacion", "kickoff") else p.stage})
            for m in p.milestone_ids:
                m.write({"date_baseline": m.date_current})
            for i in p.item_ids.filtered(lambda i: i.date_due and not i.date_baseline):
                i.write({"date_baseline": i.date_due})
        return True

    def action_update_scope(self):
        """Versiona el alcance (se usa cuando un cambio autorizado se incorpora)."""
        for p in self:
            hist = json.loads(p.scope_history or "[]")
            hist.append({"version": p.scope_version, "date": str(fields.Date.today()), "scope": p.scope_current})
            p.write({"scope_history": json.dumps(hist, ensure_ascii=False), "scope_version": p.scope_version + 1})
        return True

    def action_ready_to_close(self):
        for p in self:
            pending = p.item_ids.filtered(lambda i: i.item_type == "entregable" and i.state != "cerrado")
            not_accepted = p.item_ids.filtered(lambda i: i.item_type == "entregable" and not i.accepted)
            if not_accepted:
                raise UserError(_("Cierre: %d entregable(s) sin aceptación. Documente pendientes conocidos o complete la aceptación.") % len(not_accepted))
            p.write({"stage": "cierre"})
            self.env["aq.ops.event"].emit("ops", "project_ready_to_close", p, {"project": p.name, "pending_known": len(pending)})
        return True

    def action_generate_status_report(self):
        for p in self:
            self.env["aq.ops.status.report"].generate(p)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for p in projects:
            if p.template_id:
                p._apply_template(p.template_id)
        return projects

    def _apply_template(self, template):
        self.ensure_one()
        start = self.date_start or fields.Date.today()
        for ph in template.phase_ids:
            self.env["aq.ops.milestone"].create({"project_id": self.id, "name": ph.name, "sequence": ph.sequence,
                                                 "date_current": fields.Date.add(start, days=ph.offset_days), "enables_billing": ph.enables_billing})
        for it in template.item_ids:
            self.env["aq.ops.item"].create({"project_id": self.id, "name": it.name, "item_type": it.item_type, "acceptance_criteria": it.acceptance_criteria,
                                            "estimate_hours": it.estimate_hours, "sequence": it.sequence})
        self.write({"methodology": template.methodology, "wip_limit": template.wip_limit})


class OpsMilestone(models.Model):
    _name = "aq.ops.milestone"
    _description = "AlphaOps: hito"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date_current, sequence"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    sequence = fields.Integer(default=10)
    date_baseline = fields.Date(string="Fecha · línea base")
    date_current = fields.Date(string="Fecha · plan vigente")
    date_actual = fields.Date(string="Fecha real")
    deviation_days = fields.Integer(compute="_compute_dev", store=True, string="Desviación (días)")
    state = fields.Selection([("pendiente", "Pendiente"), ("en_progreso", "En progreso"), ("listo_validacion", "Listo para validación"),
                              ("validado", "Validado por el cliente"), ("cancelado", "Cancelado")], default="pendiente", tracking=True)
    owner_id = fields.Many2one("aq.portal.member", string="Responsable")
    validator_id = fields.Many2one("res.partner", string="Valida (cliente)")
    next_action = fields.Char(string="Siguiente acción")
    next_action_date = fields.Date(string="Fecha compromiso")
    enables_billing = fields.Boolean(string="Habilita facturación al validarse")
    validated_date = fields.Date(readonly=True)
    item_ids = fields.One2many("aq.ops.item", "milestone_id", string="Elementos")
    client_visible = fields.Boolean(default=True)
    description = fields.Text()

    @api.depends("date_baseline", "date_current", "date_actual")
    def _compute_dev(self):
        for m in self:
            ref = m.date_actual or m.date_current
            m.deviation_days = (ref - m.date_baseline).days if (ref and m.date_baseline) else 0

    def action_validated(self):
        for m in self:
            m.write({"state": "validado", "validated_date": fields.Date.today(), "date_actual": m.date_actual or fields.Date.today()})
            self.env["aq.ops.event"].emit("ops", "milestone_validated", m, {"project": m.project_id.name, "milestone": m.name,
                                                                             "date": str(fields.Date.today()), "enables_billing": m.enables_billing})
            m.project_id._update_stage_from_milestones()
        return True


class OpsProjectStage(models.Model):
    _inherit = "aq.ops.project"

    def _update_stage_from_milestones(self):
        """Automatización: actualizar estado del proyecto a partir de hitos reales."""
        for p in self:
            ms = p.milestone_ids.filtered(lambda m: m.state != "cancelado")
            if ms and all(m.state == "validado" for m in ms) and p.stage == "ejecucion":
                p.with_context(aq_skip_activity=True).write({"stage": "estabilizacion"})


class OpsEnvironment(models.Model):
    _name = "aq.ops.environment"
    _description = "AlphaOps: ambiente"
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    env_type = fields.Selection([("dev", "Desarrollo"), ("qa", "QA / pruebas"), ("uat", "UAT"), ("prod", "Producción")], required=True, default="qa")
    url = fields.Char(string="URL")
    version = fields.Char(string="Versión desplegada")
    last_deploy = fields.Datetime(string="Último despliegue", readonly=True)
    notes = fields.Text()


class OpsLink(models.Model):
    _name = "aq.ops.link"
    _description = "AlphaOps: acceso directo"
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    url = fields.Char(required=True)
    link_type = fields.Selection([("drive", "Drive"), ("ambiente", "Ambiente"), ("repositorio", "Repositorio"), ("tablero", "Tablero"), ("otro", "Otro")], default="drive")
    client_visible = fields.Boolean(default=False)


class OpsSprint(models.Model):
    _name = "aq.ops.sprint"
    _description = "AlphaOps: sprint"
    _order = "date_start desc"
    name = fields.Char(required=True)
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade")
    goal = fields.Text(string="Objetivo del sprint")
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    capacity_hours = fields.Float(string="Capacidad (h)")
    state = fields.Selection([("planeado", "Planeado"), ("activo", "Activo"), ("cerrado", "Cerrado")], default="planeado")
    item_ids = fields.One2many("aq.ops.item", "sprint_id", string="Elementos")
    committed_hours = fields.Float(compute="_compute_load", store=True)
    done_count = fields.Integer(compute="_compute_load", store=True)
    item_count = fields.Integer(compute="_compute_load", store=True)

    @api.depends("item_ids.estimate_hours", "item_ids.state")
    def _compute_load(self):
        for s in self:
            s.committed_hours = sum(s.item_ids.mapped("estimate_hours"))
            s.item_count = len(s.item_ids)
            s.done_count = len(s.item_ids.filtered(lambda i: i.state in ("aceptado", "liberado", "verificado", "cerrado")))


class OpsStatusReport(models.Model):
    _name = "aq.ops.status.report"
    _description = "AlphaOps: reporte de estado"
    _order = "date desc"
    project_id = fields.Many2one("aq.ops.project", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    date = fields.Date(default=fields.Date.today)
    health = fields.Selection(HEALTH)
    summary = fields.Html(string="Resumen")
    data_json = fields.Text()
    client_visible = fields.Boolean(default=True)
    generated_by_ai = fields.Boolean(string="Borrador generado por IA", readonly=True)
    sent_date = fields.Date(readonly=True)

    @api.model
    def generate(self, project):
        p = project
        today = fields.Date.today()
        items = p.item_ids
        done_week = items.filtered(lambda i: i.state in ("aceptado", "cerrado", "liberado", "verificado") and i.write_date and (today - i.write_date.date()).days <= 7)
        blocked = items.filtered(lambda i: i.state == "bloqueado")
        waiting = items.filtered(lambda i: i.waiting_client and i.state not in ("cerrado", "cancelado"))
        risks = p.raid_ids.filtered(lambda r: r.raid_type == "risk" and r.state not in ("cerrado",))
        html = ["<h3>%s · semana al %s</h3>" % (p.name, today),
                "<p><b>Salud:</b> %s — %s</p>" % (p.health, p.health_reason or ""),
                "<p><b>Etapa:</b> %s · <b>Horas:</b> %.1f / %.1f (%.0f%%)</p>" % (dict(PROJECT_STAGES)[p.stage], p.hours_consumed, p.hours_authorized, p.hours_pct),
                "<p><b>Siguiente acción:</b> %s (%s, %s)</p>" % (p.next_action or "-", p.next_action_owner_id.name or "-", p.next_action_date or "-"),
                "<h4>Completado esta semana</h4><ul>%s</ul>" % "".join("<li>%s</li>" % i.name for i in done_week) or "",
                "<h4>Bloqueos</h4><ul>%s</ul>" % "".join("<li>%s — %s</li>" % (i.name, i.blocked_reason or "") for i in blocked),
                "<h4>Esperando al cliente</h4><ul>%s</ul>" % "".join("<li>%s</li>" % i.name for i in waiting),
                "<h4>Riesgos</h4><ul>%s</ul>" % "".join("<li>%s (%s)</li>" % (r.name, r.severity) for r in risks),
                "<h4>Próximo hito</h4><p>%s · %s</p>" % (p.next_milestone_id.name or "-", p.next_milestone_id.date_current or "-")]
        return self.create({"project_id": p.id, "name": _("Reporte semanal %s · %s") % (p.name, today), "health": p.health, "summary": "".join(html),
                            "data_json": json.dumps({"done": len(done_week), "blocked": len(blocked), "waiting": len(waiting), "risks": len(risks), "hours_pct": p.hours_pct})})


class OpsProjectForecast(models.Model):
    """Fase 3 · pronósticos: agotamiento de bolsa y fin probable por velocidad real."""
    _inherit = "aq.ops.project"

    burn_rate_week = fields.Float(compute="_compute_forecast", store=True, string="Consumo semanal (h, últimas 4 semanas)")
    hours_depletion_forecast = fields.Date(compute="_compute_forecast", store=True, string="Pronóstico de agotamiento de la bolsa")
    velocity_week = fields.Float(compute="_compute_forecast", store=True, string="Velocidad (elementos cerrados / semana)")
    forecast_end_by_velocity = fields.Date(compute="_compute_forecast", store=True, string="Fin pronosticado por velocidad")

    @api.depends("timesheet_ids.hours", "timesheet_ids.date", "hours_authorized", "item_ids.state", "item_ids.done_date")
    def _compute_forecast(self):
        today = fields.Date.today()
        for p in self:
            recent = p.timesheet_ids.filtered(lambda t: t.date and t.date >= today - timedelta(days=28) and t.state != "rechazado")
            p.burn_rate_week = sum(recent.mapped("hours")) / 4.0
            remaining = p.hours_authorized - p.hours_consumed
            p.hours_depletion_forecast = (today + timedelta(days=int(remaining / p.burn_rate_week * 7))) if (p.burn_rate_week > 0 and remaining > 0) else (today if (p.hours_authorized and remaining <= 0) else False)
            done_recent = p.item_ids.filtered(lambda i: i.done_date and i.done_date >= today - timedelta(days=28))
            p.velocity_week = len(done_recent) / 4.0
            open_items = len(p.item_ids.filtered(lambda i: i.state not in ("cerrado", "cancelado", "aceptado", "liberado", "verificado")))
            p.forecast_end_by_velocity = (today + timedelta(days=int(open_items / p.velocity_week * 7))) if (p.velocity_week > 0 and open_items) else False

# -*- coding: utf-8 -*-
"""AlphaOps · tiempo real (temporizador, captura, aprobación semanal) y capacidad futura."""
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

TIME_CATEGORIES = [("analisis", "Análisis"), ("configuracion", "Configuración"), ("desarrollo", "Desarrollo"), ("pruebas", "Pruebas"), ("reunion", "Reunión"),
                   ("soporte", "Soporte"), ("capacitacion", "Capacitación"), ("documentacion", "Documentación"), ("gestion", "Gestión de proyecto"),
                   ("no_planificado", "Trabajo no planificado"), ("interno", "Interno / administrativo")]


class OpsTimesheet(models.Model):
    _name = "aq.ops.timesheet"
    _description = "AlphaOps: registro de tiempo"
    _order = "date desc, id desc"

    member_id = fields.Many2one("aq.portal.member", required=True, string="Integrante", index=True)
    user_id = fields.Many2one("aq.portal.user", string="Usuario", readonly=True)
    project_id = fields.Many2one("aq.ops.project", string="Proyecto", index=True)
    item_id = fields.Many2one("aq.ops.item", string="Elemento")
    date = fields.Date(required=True, default=fields.Date.today)
    hours = fields.Float(required=True)
    category = fields.Selection(TIME_CATEGORIES, default="desarrollo", required=True)
    billable = fields.Boolean(default=True, string="Facturable")
    description = fields.Char(string="Descripción")
    justification = fields.Char(string="Justificación (si no hay proyecto/entregable)")
    timer_start = fields.Datetime(string="Temporizador iniciado")
    running = fields.Boolean(string="Temporizador activo")
    week = fields.Char(compute="_compute_week", store=True, string="Semana")
    state = fields.Selection([("borrador", "Borrador"), ("enviado", "Enviado"), ("aprobado", "Aprobado"), ("rechazado", "Rechazado")], default="borrador", index=True)
    approved_by_id = fields.Many2one("aq.portal.user", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    reject_reason = fields.Char()
    unjustified = fields.Boolean(compute="_compute_unjust", store=True, string="Sin proyecto/entregable/justificación")

    @api.depends("date")
    def _compute_week(self):
        for t in self:
            t.week = t.date.strftime("%G-W%V") if t.date else False

    @api.depends("project_id", "item_id", "justification")
    def _compute_unjust(self):
        for t in self:
            t.unjustified = not t.project_id and not t.item_id and not t.justification

    @api.model_create_multi
    def create(self, vals_list):
        pu = self.env.context.get("portal_user_id")
        for v in vals_list:
            v.setdefault("user_id", pu)
            if v.get("item_id") and not v.get("project_id"):
                v["project_id"] = self.env["aq.ops.item"].browse(v["item_id"]).project_id.id
        recs = super().create(vals_list)
        for t in recs.filtered(lambda x: x.item_id and x.item_id.remaining_hours):
            t.item_id.write({"remaining_hours": max(t.item_id.remaining_hours - t.hours, 0.0)})
        return recs

    @api.model
    def timer_start_for(self, user, item_id=None, project_id=None, description=None):
        member = user.member_id
        if not member:
            raise UserError(_("Su usuario no está vinculado a un integrante del equipo."))
        running = self.search([("member_id", "=", member.id), ("running", "=", True)], limit=1)
        if running:
            running.timer_stop()
        return self.create({"member_id": member.id, "user_id": user.id, "item_id": item_id, "project_id": project_id, "hours": 0.0,
                            "timer_start": fields.Datetime.now(), "running": True, "description": description or _("Temporizador")})

    def timer_stop(self):
        for t in self.filtered("running"):
            elapsed = (fields.Datetime.now() - t.timer_start).total_seconds() / 3600.0
            t.write({"running": False, "hours": round(t.hours + elapsed, 2)})
        return True

    def action_submit(self):
        self.filtered(lambda t: t.state == "borrador").write({"state": "enviado"})
        return True

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"state": "aprobado", "approved_by_id": pu, "approved_at": fields.Datetime.now()})
        for project, group in self._group_by_project():
            if project:
                billable = sum(group.filtered("billable").mapped("hours"))
                if billable:
                    self.env["aq.ops.event"].emit("ops", "hours_approved_for_billing", project, {"project": project.name, "hours": billable, "week": group[0].week})
        return True

    def _group_by_project(self):
        out = {}
        for t in self:
            out.setdefault(t.project_id, self.browse())
            out[t.project_id] |= t
        return out.items()

    def action_reject(self):
        self.write({"state": "rechazado"})
        return True


class OpsCapacity(models.Model):
    """Capacidad futura por persona y semana; carga desde elementos asignados."""
    _name = "aq.ops.capacity"
    _description = "AlphaOps: capacidad semanal"
    _order = "week desc, member_id"

    member_id = fields.Many2one("aq.portal.member", required=True)
    week = fields.Char(required=True, string="Semana (AAAA-Www)")
    specialty = fields.Selection([("funcional", "Funcional"), ("tecnico", "Técnico"), ("qa", "QA"), ("pm", "PM"), ("soporte", "Soporte"), ("diseno", "Diseño")], default="funcional")
    hours_available = fields.Float(default=40.0, string="Horas disponibles")
    unavailable_hours = fields.Float(string="Vacaciones / indisponibilidad (h)")
    unavailability_reason = fields.Char(string="Motivo")
    planned_hours = fields.Float(compute="_compute_load", string="Carga planificada (h)")
    logged_hours = fields.Float(compute="_compute_load", string="Horas registradas")
    load_pct = fields.Float(compute="_compute_load", string="% carga")
    overallocated = fields.Boolean(compute="_compute_load", string="Sobreasignado")

    @api.model
    def _week_bounds(self, week):
        year, wk = week.split("-W")
        monday = fields.Date.to_date("%s-01-04" % year)
        monday = monday - timedelta(days=monday.weekday()) + timedelta(weeks=int(wk) - 1)
        return monday, monday + timedelta(days=6)

    def _compute_load(self):
        Item = self.env["aq.ops.item"]
        TS = self.env["aq.ops.timesheet"]
        for c in self:
            try:
                start, end = self._week_bounds(c.week)
            except Exception:
                c.planned_hours = c.logged_hours = c.load_pct = 0.0; c.overallocated = False; continue
            items = Item.search([("assignee_id", "=", c.member_id.id), ("state", "not in", ("cerrado", "cancelado", "aceptado", "liberado", "verificado")),
                                 "|", ("date_due", "=", False), "&", ("date_due", ">=", start), ("date_due", "<=", end)])
            c.planned_hours = sum((i.remaining_hours or i.estimate_hours) for i in items)
            c.logged_hours = sum(TS.search([("member_id", "=", c.member_id.id), ("date", ">=", start), ("date", "<=", end)]).mapped("hours"))
            avail = max(c.hours_available - c.unavailable_hours, 0.0)
            c.load_pct = (c.planned_hours / avail * 100.0) if avail else 0.0
            c.overallocated = c.planned_hours > avail

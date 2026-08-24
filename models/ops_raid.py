# -*- coding: utf-8 -*-
"""Alphaops · registro RAID e incidentes productivos con flujo de 11 pasos y SLA."""
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

INCIDENT_STEPS = [("reportado", "1. Reporte"), ("clasificado", "2. Clasificación de severidad"), ("contencion", "3. Contención"), ("diagnostico", "4. Diagnóstico"),
                  ("correccion", "5. Corrección"), ("pruebas", "6. Pruebas"), ("liberacion", "7. Liberación controlada"), ("verificacion", "8. Verificación"),
                  ("comunicacion", "9. Comunicación"), ("rca", "10. Análisis de causa raíz"), ("prevencion", "11. Acción preventiva"), ("cerrado", "Cerrado")]
SLA = {"S1": (1, 8), "S2": (4, 24), "S3": (8, 72), "S4": (24, 160)}  # (horas respuesta, horas resolución)


class OpsRaid(models.Model):
    _name = "aq.ops.raid"
    _description = "Alphaops: RAID (riesgo, supuesto, problema, dependencia)"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "severity desc, due_date"

    name = fields.Char(required=True, tracking=True)
    raid_type = fields.Selection([("risk", "Riesgo"), ("assumption", "Supuesto"), ("issue", "Problema"), ("dependency", "Dependencia")], required=True, default="risk")
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    meeting_id = fields.Many2one("aq.ops.meeting", string="Detectado en reunión")
    description = fields.Text()
    probability = fields.Selection([("1", "Baja"), ("2", "Media"), ("3", "Alta")], default="2")
    impact = fields.Selection([("1", "Bajo"), ("2", "Medio"), ("3", "Alto")], default="2")
    severity = fields.Integer(compute="_compute_sev", store=True, string="Severidad")
    owner_id = fields.Many2one("aq.portal.member", string="Responsable")
    requires_client = fields.Boolean(string="Requiere intervención del cliente")
    client_owner_id = fields.Many2one("res.partner", string="Responsable en el cliente")
    mitigation = fields.Text(string="Mitigación / plan")
    next_action = fields.Char(string="Siguiente acción")
    next_action_date = fields.Date(string="Fecha compromiso")
    due_date = fields.Date(string="Fecha límite / revisión")
    depends_on_project_id = fields.Many2one("aq.ops.project", string="Depende del proyecto")
    depends_on_item_id = fields.Many2one("aq.ops.item", string="Depende del elemento")
    affects_item_ids = fields.Many2many("aq.ops.item", string="Elementos afectados")
    state = fields.Selection([("abierto", "Abierto"), ("mitigando", "En mitigación"), ("controlado", "Controlado"), ("materializado", "Materializado"), ("cerrado", "Cerrado")], default="abierto", tracking=True)
    client_visible = fields.Boolean(default=False)
    endangers_date = fields.Boolean(compute="_compute_danger", store=True, string="Pone en riesgo la fecha comprometida")

    @api.depends("probability", "impact")
    def _compute_sev(self):
        for r in self:
            r.severity = int(r.probability or 0) * int(r.impact or 0)

    @api.depends("raid_type", "depends_on_item_id.date_due", "affects_item_ids.date_due", "depends_on_item_id.state")
    def _compute_danger(self):
        for r in self:
            r.endangers_date = False
            if r.raid_type == "dependency" and r.depends_on_item_id and r.depends_on_item_id.state not in ("cerrado", "aceptado", "liberado", "verificado"):
                dd = r.depends_on_item_id.date_due
                r.endangers_date = any(a.date_due and dd and dd >= a.date_due for a in r.affects_item_ids)


class OpsIncident(models.Model):
    _name = "aq.ops.incident"
    _description = "Alphaops: incidente productivo"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "severity, create_date desc"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one("res.partner", string="Organización afectada", required=True)
    request_id = fields.Many2one("aq.ops.request", string="Solicitud origen")
    description = fields.Text(string="Reporte")
    severity = fields.Selection([("S1", "S1 · Crítico (producción detenida)"), ("S2", "S2 · Alto"), ("S3", "S3 · Medio"), ("S4", "S4 · Bajo")], required=True, default="S3", tracking=True)
    step = fields.Selection(INCIDENT_STEPS, default="reportado", string="Paso del flujo", tracking=True)
    owner_id = fields.Many2one("aq.portal.member", string="Responsable (guardia)")
    reported_at = fields.Datetime(default=fields.Datetime.now)
    responded_at = fields.Datetime(string="Primera respuesta", readonly=True)
    contained_at = fields.Datetime(string="Contenido", readonly=True)
    resolved_at = fields.Datetime(string="Resuelto / verificado", readonly=True)
    closed_at = fields.Datetime(readonly=True)
    sla_response_hours = fields.Float(compute="_compute_sla", store=True)
    sla_resolution_hours = fields.Float(compute="_compute_sla", store=True)
    sla_response_met = fields.Boolean(compute="_compute_sla", store=True, string="SLA de respuesta cumplido")
    sla_resolution_met = fields.Boolean(compute="_compute_sla", store=True, string="SLA de resolución cumplido")
    sla_breached = fields.Boolean(compute="_compute_sla", store=True, string="SLA incumplido")
    containment = fields.Text(string="Contención")
    diagnosis = fields.Text(string="Diagnóstico")
    correction = fields.Text(string="Corrección")
    test_evidence = fields.Text(string="Evidencia de pruebas")
    release_id = fields.Many2one("aq.ops.release", string="Liberación controlada")
    verification = fields.Text(string="Verificación")
    communication = fields.Text(string="Comunicación al cliente")
    rca = fields.Text(string="Análisis de causa raíz (postmortem)")
    preventive_action = fields.Text(string="Acción preventiva")
    preventive_item_id = fields.Many2one("aq.ops.item", string="Tarea preventiva", readonly=True)
    affects_other_clients = fields.Boolean(string="Puede afectar a otros clientes", tracking=True)
    item_ids = fields.One2many("aq.ops.item", "incident_id", string="Elementos derivados")
    comment_ids = fields.One2many("aq.ops.comment", "incident_id", string="Bitácora")
    client_visible = fields.Boolean(default=True)
    internal_notes = fields.Text(string="Notas internas")

    @api.depends("severity", "reported_at", "responded_at", "resolved_at", "step")
    def _compute_sla(self):
        now = fields.Datetime.now()
        for i in self:
            resp, res = SLA.get(i.severity, (24, 160))
            i.sla_response_hours, i.sla_resolution_hours = resp, res
            r_at = i.responded_at or (now if i.step == "reportado" else now)
            i.sla_response_met = bool(i.responded_at and (i.responded_at - i.reported_at).total_seconds() / 3600.0 <= resp)
            i.sla_resolution_met = bool(i.resolved_at and (i.resolved_at - i.reported_at).total_seconds() / 3600.0 <= res)
            elapsed = ((i.resolved_at or now) - i.reported_at).total_seconds() / 3600.0 if i.reported_at else 0
            i.sla_breached = (not i.responded_at and i.reported_at and (now - i.reported_at).total_seconds() / 3600.0 > resp) or (not i.resolved_at and elapsed > res)

    def action_advance(self):
        order = [s[0] for s in INCIDENT_STEPS]
        now = fields.Datetime.now()
        for inc in self:
            idx = order.index(inc.step)
            if idx >= len(order) - 1:
                continue
            nxt = order[idx + 1]
            checks = {"contencion": ("containment", _("contención")), "diagnostico": ("containment", _("contención")), "correccion": ("diagnosis", _("diagnóstico")),
                      "pruebas": ("correction", _("corrección")), "liberacion": ("test_evidence", _("evidencia de pruebas")), "comunicacion": ("verification", _("verificación")),
                      "rca": ("communication", _("comunicación")), "prevencion": ("rca", _("análisis de causa raíz")), "cerrado": ("preventive_action", _("acción preventiva"))}
            if nxt in checks and not inc[checks[nxt][0]]:
                raise UserError(_("Para avanzar a '%s' primero documente: %s.") % (dict(INCIDENT_STEPS)[nxt], checks[nxt][1]))
            if nxt == "liberacion" and inc.severity in ("S1", "S2") and not inc.release_id:
                raise UserError(_("Incidentes S1/S2 requieren una liberación controlada registrada."))
            vals = {"step": nxt}
            if nxt == "clasificado" and not inc.responded_at: vals["responded_at"] = now
            if nxt == "contencion": vals["contained_at"] = now
            if nxt == "verificacion": vals["resolved_at"] = now
            if nxt == "cerrado":
                vals["closed_at"] = now
                if not inc.preventive_item_id:
                    vals["preventive_item_id"] = self.env["aq.ops.item"].create({"name": _("Acción preventiva: %s") % inc.name, "item_type": "tarea", "project_id": inc.project_id.id,
                                                                                 "incident_id": inc.id, "description": inc.preventive_action, "state": "por_hacer", "assignee_id": inc.owner_id.id}).id
            inc.write(vals)
            if inc.affects_other_clients:
                self.env["aq.ops.notification"].notify_role(False, ["ops_director", "platform_owner"], "incidente", _("Incidente con posible afectación a otros clientes: %s") % inc.name, "incidents", inc.id)
        return True

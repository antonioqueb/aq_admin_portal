from odoo import api, fields, models, _


class HourBucket(models.Model):
    """1.6 Control de horas, alcances y trabajo facturable (por bolsa / contrato)."""
    _name = "aq.portal.hour.bucket"
    _description = "Portal: bolsa de horas / alcance"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "project_id, id"

    name = fields.Char(string="Bolsa / contrato / alcance", required=True)
    project_id = fields.Many2one("aq.portal.project", string="Proyecto", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    basis_ref = fields.Char(string="Cotización / orden / contrato")
    period_start = fields.Date(string="Vigencia desde")
    period_end = fields.Date(string="Vigencia hasta")
    hourly_rate = fields.Float(string="Tarifa por hora")
    hours_contracted = fields.Float(string="Horas contratadas")
    hours_estimated = fields.Float(string="Horas estimadas")
    hours_executed = fields.Float(string="Horas ejecutadas", compute="_compute_hours", store=True, readonly=False,
                                  help="Se calcula de las entradas registradas; se puede ajustar manualmente.")
    hours_registered = fields.Float(string="Horas registradas (en sistema oficial)", compute="_compute_hours", store=True, readonly=False)
    hours_billed = fields.Float(string="Horas facturadas", compute="_compute_hours", store=True, readonly=False)
    hours_paid = fields.Float(string="Horas pagadas")
    hours_out_of_scope = fields.Float(string="Trabajo adicional fuera del alcance (h)", compute="_compute_hours", store=True, readonly=False)
    hours_unbilled = fields.Float(string="Trabajo realizado sin facturar (h)", compute="_compute_derived", store=True)
    hours_unregistered = fields.Float(string="Trabajo sin registro (h)", compute="_compute_derived", store=True)
    hours_remaining = fields.Float(string="Horas restantes", compute="_compute_derived", store=True)
    pct_consumed = fields.Float(string="% consumido", compute="_compute_derived", store=True)
    variance_quoted_vs_executed = fields.Float(string="Diferencia cotizado vs ejecutado (h)", compute="_compute_derived", store=True)
    near_depletion = fields.Boolean(string="Bolsa próxima a agotarse", compute="_compute_derived", store=True)
    over_budget = fields.Boolean(string="Consume más recursos de lo previsto", compute="_compute_derived", store=True)
    has_unauthorized_work = fields.Boolean(string="Trabajo sin autorización comercial", compute="_compute_derived", store=True)
    deliverables_pending_acceptance = fields.Integer(compute="_compute_derived", store=True, string="Entregables pendientes de aceptación")
    entry_ids = fields.One2many("aq.portal.hour.entry", "bucket_id", string="Registro de horas")
    state = fields.Selection([("activa", "Activa"), ("agotada", "Agotada"), ("cerrada", "Cerrada")], default="activa")

    @api.depends("entry_ids.hours", "entry_ids.registered", "entry_ids.billed", "entry_ids.out_of_scope")
    def _compute_hours(self):
        for b in self:
            e = b.entry_ids
            b.hours_executed = sum(e.mapped("hours"))
            b.hours_registered = sum(e.filtered("registered").mapped("hours"))
            b.hours_billed = sum(e.filtered("billed").mapped("hours"))
            b.hours_out_of_scope = sum(e.filtered("out_of_scope").mapped("hours"))

    @api.depends("hours_contracted", "hours_estimated", "hours_executed", "hours_registered", "hours_billed",
                 "entry_ids.authorized", "entry_ids.out_of_scope", "project_id.deliverable_ids.accepted")
    def _compute_derived(self):
        threshold = float(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.depletion_threshold", "80"))
        for b in self:
            b.hours_unbilled = max(b.hours_executed - b.hours_billed, 0.0)
            b.hours_unregistered = max(b.hours_executed - b.hours_registered, 0.0)
            b.hours_remaining = b.hours_contracted - b.hours_executed
            b.pct_consumed = (b.hours_executed / b.hours_contracted * 100.0) if b.hours_contracted else 0.0
            b.variance_quoted_vs_executed = b.hours_executed - (b.hours_estimated or b.hours_contracted)
            b.near_depletion = bool(b.hours_contracted and b.pct_consumed >= threshold and b.pct_consumed < 100)
            b.over_budget = bool(b.hours_contracted and b.hours_executed > b.hours_contracted) or \
                bool(b.hours_estimated and b.hours_executed > b.hours_estimated)
            b.has_unauthorized_work = any(e.out_of_scope and not e.authorized for e in b.entry_ids)
            b.deliverables_pending_acceptance = len(b.project_id.deliverable_ids.filtered(
                lambda d: d.delivered_date and not d.accepted))


class HourEntry(models.Model):
    _name = "aq.portal.hour.entry"
    _description = "Portal: registro de horas"
    _order = "date desc"

    bucket_id = fields.Many2one("aq.portal.hour.bucket", required=True, ondelete="cascade", string="Bolsa")
    project_id = fields.Many2one(related="bucket_id.project_id", store=True)
    date = fields.Date(required=True, default=fields.Date.today)
    member_id = fields.Many2one("aq.portal.member", string="Integrante", required=True)
    hours = fields.Float(required=True, string="Horas")
    description = fields.Char(string="Actividad", required=True)
    billable = fields.Boolean(default=True, string="Facturable")
    registered = fields.Boolean(string="Registrada en sistema oficial (Odoo/timesheet)")
    billed = fields.Boolean(string="Facturada")
    paid = fields.Boolean(string="Pagada")
    out_of_scope = fields.Boolean(string="Fuera de alcance")
    authorized = fields.Boolean(string="Con autorización comercial")
    change_request_id = fields.Many2one("aq.portal.change.request", string="Solicitud de cambio")


class Deliverable(models.Model):
    _name = "aq.portal.deliverable"
    _description = "Portal: entregable"
    _inherit = ["aq.portal.mixin"]
    _order = "due_date"

    name = fields.Char(required=True, string="Entregable")
    project_id = fields.Many2one("aq.portal.project", required=True, ondelete="cascade")
    due_date = fields.Date(string="Fecha comprometida")
    delivered_date = fields.Date(string="Fecha de entrega")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    validator_partner_id = fields.Many2one("res.partner", string="Valida (cliente)")
    acceptance_criteria = fields.Text(string="Criterios de aceptación")
    accepted = fields.Boolean(string="Aceptado por el cliente")
    acceptance_date = fields.Date(string="Fecha de aceptación")
    acceptance_evidence = fields.Char(string="Evidencia de aceptación (acta, correo)")
    billed = fields.Boolean(string="Facturado")
    state = fields.Selection([("pendiente", "Pendiente"), ("entregado", "Entregado – pendiente de aceptación"),
                              ("aceptado", "Aceptado"), ("rechazado", "Rechazado")], default="pendiente", compute="_compute_state", store=True)

    @api.depends("delivered_date", "accepted")
    def _compute_state(self):
        for d in self:
            if d.accepted:
                d.state = "aceptado"
            elif d.delivered_date:
                d.state = "entregado"
            else:
                d.state = "pendiente"

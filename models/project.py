from odoo import api, fields, models, _

PROJECT_STAGES = [
    ("cotizacion", "1. Cotización y aprobación"),
    ("contrato", "2. Contrato / documento comercial"),
    ("arranque", "3. Anticipo / condición de arranque"),
    ("inicio", "4-8. Expediente, kickoff, responsables, alcance y plan"),
    ("ejecucion", "9-12. Ejecución (acuerdos, cambios, horas, facturación)"),
    ("validacion", "13. Validación del cliente"),
    ("aceptacion", "14. Acta de aceptación"),
    ("cierre", "15. Cierre / transición a soporte"),
    ("soporte", "Soporte"),
    ("pausado", "Pausado"),
    ("cancelado", "Cancelado"),
]


class Project(models.Model):
    """1.1 Control maestro de proyectos."""
    _name = "aq.portal.project"
    _description = "Portal: proyecto"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "priority desc, next_action_date asc, name"

    name = fields.Char(string="Proyecto", required=True, tracking=True)
    code = fields.Char(string="Clave")
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True, tracking=True)
    contact_id = fields.Many2one("res.partner", string="Contacto principal")
    contact_name = fields.Char(string="Nombre del contacto")
    contact_email = fields.Char(string="Correo del contacto")
    contact_phone = fields.Char(string="Teléfono del contacto")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable interno", tracking=True)
    member_ids = fields.Many2many("aq.portal.member", "aq_portal_project_member_rel", "project_id", "member_id",
                                  string="Integrantes del equipo involucrados")
    stage = fields.Selection(PROJECT_STAGES, string="Etapa actual", default="cotizacion", required=True, tracking=True)
    priority = fields.Selection([("0", "Normal"), ("1", "Alta"), ("2", "Crítica")], default="0", string="Prioridad")
    scope = fields.Text(string="Alcance contratado")
    contract_ref = fields.Char(string="Contrato / cotización / orden")
    legal_item_id = fields.Many2one("aq.portal.legal.item", string="Contrato en inventario legal")
    date_start = fields.Date(string="Fecha de inicio", tracking=True)
    date_end_planned = fields.Date(string="Fecha de término planeada")
    date_ids = fields.One2many("aq.portal.project.date", "project_id", string="Fechas relevantes")
    next_deliverable = fields.Char(string="Próximo entregable")
    next_deliverable_date = fields.Date(string="Fecha del próximo entregable")
    next_action = fields.Char(string="Siguiente acción", tracking=True)
    next_action_responsible_id = fields.Many2one("aq.portal.member", string="Responsable de la siguiente acción")
    next_action_date = fields.Date(string="Fecha compromiso", tracking=True)
    blockers = fields.Text(string="Bloqueos")
    pending_client_info = fields.Text(string="Información pendiente del cliente")
    pending_validations = fields.Text(string="Validaciones pendientes")
    billing_status = fields.Selection([
        ("sin_facturar", "Sin facturar"), ("parcial", "Parcialmente facturado"),
        ("facturado", "Facturado"), ("detenido", "Detenido por validación"), ("no_aplica", "No aplica"),
    ], string="Estado de facturación", default="sin_facturar", tracking=True)
    collection_status = fields.Selection([
        ("sin_cobrar", "Sin cobrar"), ("parcial", "Cobro parcial"), ("cobrado", "Cobrado"),
        ("vencido", "Con cartera vencida"), ("no_aplica", "No aplica"),
    ], string="Estado de cobranza", default="sin_cobrar", tracking=True)
    risks = fields.Text(string="Riesgos o decisiones que requieren intervención de Dirección")
    requires_direction = fields.Boolean(string="Requiere decisión de Dirección", tracking=True)
    direction_decision = fields.Text(string="Decisión de Dirección")
    direction_decision_date = fields.Date(string="Fecha de decisión")
    active = fields.Boolean(default=True)

    # relaciones
    agreement_ids = fields.One2many("aq.portal.agreement", "project_id", string="Acuerdos y pendientes")
    invoice_schedule_ids = fields.One2many("aq.portal.invoice.schedule", "project_id", string="Calendario de facturación")
    receivable_ids = fields.One2many("aq.portal.receivable", "project_id", string="Cuentas por cobrar")
    payable_ids = fields.One2many("aq.portal.payable", "project_id", string="Cuentas por pagar")
    hour_bucket_ids = fields.One2many("aq.portal.hour.bucket", "project_id", string="Bolsas de horas")
    deliverable_ids = fields.One2many("aq.portal.deliverable", "project_id", string="Entregables")
    change_request_ids = fields.One2many("aq.portal.change.request", "project_id", string="Control de cambios")
    document_ids = fields.One2many("aq.portal.document", "project_id", string="Documentos")
    step_ids = fields.One2many("aq.portal.project.step", "project_id", string="Procedimiento administrativo")
    risk_ids = fields.One2many("aq.portal.risk", "project_id", string="Riesgos")
    followup_ids = fields.One2many("aq.portal.followup", "project_id", string="Seguimientos")

    # indicadores
    days_without_activity = fields.Integer(compute="_compute_activity", string="Días sin actividad")
    is_stale = fields.Boolean(compute="_compute_activity", string="Sin actividad reciente", search="_search_is_stale")
    has_next_action = fields.Boolean(compute="_compute_activity", string="Tiene siguiente acción definida")
    next_action_overdue = fields.Boolean(compute="_compute_activity", string="Siguiente acción vencida")
    client_dependent = fields.Boolean(compute="_compute_activity", string="Depende del cliente")
    open_agreement_count = fields.Integer(compute="_compute_agreements", string="Pendientes abiertos")
    overdue_agreement_count = fields.Integer(compute="_compute_agreements", string="Pendientes vencidos")
    repeated_agreement_count = fields.Integer(compute="_compute_agreements", string="Pendientes que se repiten")
    hours_contracted = fields.Float(compute="_compute_hours", string="Horas contratadas")
    hours_executed = fields.Float(compute="_compute_hours", string="Horas ejecutadas")
    hours_billed = fields.Float(compute="_compute_hours", string="Horas facturadas")
    hours_unbilled = fields.Float(compute="_compute_hours", string="Horas sin facturar")
    receivable_balance = fields.Float(compute="_compute_money", string="Saldo por cobrar")
    amount_invoiced = fields.Float(compute="_compute_money", string="Importe facturado")
    step_progress = fields.Float(compute="_compute_steps", string="Avance del procedimiento (%)")

    @api.depends("last_activity_date", "next_action", "next_action_date", "next_action_responsible_id",
                 "pending_client_info", "agreement_ids.client_dependent")
    def _compute_activity(self):
        today = fields.Date.today()
        stale_days = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.stale_days", "5"))
        for p in self:
            p.days_without_activity = (today - p.last_activity_date).days if p.last_activity_date else 0
            p.is_stale = p.stage not in ("cierre", "cancelado", "pausado", "soporte") and p.days_without_activity >= stale_days
            p.has_next_action = bool(p.next_action and p.next_action_date and p.next_action_responsible_id)
            p.next_action_overdue = bool(p.next_action_date and p.next_action_date < today and p.stage not in ("cierre", "cancelado"))
            p.client_dependent = bool(p.pending_client_info) or any(a.client_dependent and a.state not in ("cerrado", "cancelado") for a in p.agreement_ids)

    def _search_is_stale(self, operator, value):
        today = fields.Date.today()
        stale_days = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.stale_days", "5"))
        limit = fields.Date.subtract(today, days=stale_days)
        dom = [("last_activity_date", "<=", limit), ("stage", "not in", ("cierre", "cancelado", "pausado", "soporte"))]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom

    @api.depends("agreement_ids.state", "agreement_ids.due_date", "agreement_ids.is_repeated")
    def _compute_agreements(self):
        today = fields.Date.today()
        for p in self:
            open_ = p.agreement_ids.filtered(lambda a: a.state not in ("cerrado", "cancelado"))
            p.open_agreement_count = len(open_)
            p.overdue_agreement_count = len(open_.filtered(lambda a: a.due_date and a.due_date < today))
            p.repeated_agreement_count = len(open_.filtered("is_repeated"))

    @api.depends("hour_bucket_ids.hours_contracted", "hour_bucket_ids.hours_executed", "hour_bucket_ids.hours_billed")
    def _compute_hours(self):
        for p in self:
            b = p.hour_bucket_ids
            p.hours_contracted = sum(b.mapped("hours_contracted"))
            p.hours_executed = sum(b.mapped("hours_executed"))
            p.hours_billed = sum(b.mapped("hours_billed"))
            p.hours_unbilled = max(p.hours_executed - p.hours_billed, 0.0)

    @api.depends("receivable_ids.balance", "receivable_ids.amount_total")
    def _compute_money(self):
        for p in self:
            p.receivable_balance = sum(p.receivable_ids.mapped("balance"))
            p.amount_invoiced = sum(p.receivable_ids.mapped("amount_total"))

    @api.depends("step_ids.state")
    def _compute_steps(self):
        for p in self:
            steps = p.step_ids.filtered(lambda s: s.state != "no_aplica")
            done = steps.filtered(lambda s: s.state == "completado")
            p.step_progress = (len(done) / len(steps) * 100.0) if steps else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._ensure_steps()
        return projects

    def _ensure_steps(self):
        templates = self.env["aq.portal.procedure.step"].search([], order="sequence")
        for p in self:
            existing = p.step_ids.mapped("template_id")
            for t in templates - existing:
                self.env["aq.portal.project.step"].create({
                    "project_id": p.id, "template_id": t.id, "sequence": t.sequence, "name": t.name,
                })

    # acciones
    def action_request_update(self):
        """Solicitar actualización al responsable (facultad 6)."""
        for p in self:
            self.env["aq.portal.followup"].create({
                "project_id": p.id, "channel": "portal", "kind": "solicitud_actualizacion",
                "note": _("Se solicitó actualización de avance al responsable %s.") % (p.responsible_id.name or "-"),
                "member_id": p.responsible_id.id,
            })
            p._notify_member(p.responsible_id, _("Solicitud de actualización: %s") % p.name,
                             _("Se solicita actualización de avance, siguiente acción y fecha compromiso del proyecto %s.") % p.name)
        return True

    def action_escalate(self):
        for p in self:
            p.write({"requires_direction": True})
            p.message_post(body=_("Proyecto escalado a Dirección."))
        return True

    def _notify_member(self, member, subject, body):
        if member and member.email:
            Brand = self.env["aq.portal.branding"]
            self.env["mail.mail"].sudo().create({
                "subject": subject, "email_to": member.email,
                "body_html": Brand.wrap(subject, "<p>%s</p>" % body, _("Abrir proyecto"), Brand.portal_url("projects", self.id)),
            }).send()


class ProjectDate(models.Model):
    _name = "aq.portal.project.date"
    _description = "Portal: fecha relevante de proyecto"
    _order = "date"

    project_id = fields.Many2one("aq.portal.project", required=True, ondelete="cascade")
    name = fields.Char(string="Descripción", required=True)
    date = fields.Date(required=True)
    date_type = fields.Selection([
        ("hito", "Hito"), ("entregable", "Entregable"), ("reunion", "Reunión"), ("facturacion", "Facturación"),
        ("compromiso_cliente", "Compromiso con cliente"), ("vencimiento", "Vencimiento"), ("otro", "Otro"),
    ], default="hito", string="Tipo")
    done = fields.Boolean(string="Cumplida")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")


class ProcedureStep(models.Model):
    """2.3 Plantilla del procedimiento administrativo común (15 pasos)."""
    _name = "aq.portal.procedure.step"
    _description = "Portal: paso del procedimiento de proyectos"
    _order = "sequence"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    description = fields.Text()
    required_evidence = fields.Char(string="Evidencia esperada")


class ProjectStep(models.Model):
    _name = "aq.portal.project.step"
    _description = "Portal: paso del procedimiento en un proyecto"
    _order = "sequence"

    project_id = fields.Many2one("aq.portal.project", required=True, ondelete="cascade")
    template_id = fields.Many2one("aq.portal.procedure.step", string="Paso")
    sequence = fields.Integer()
    name = fields.Char(required=True)
    state = fields.Selection([("pendiente", "Pendiente"), ("en_proceso", "En proceso"),
                              ("completado", "Completado"), ("no_aplica", "No aplica")], default="pendiente")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    date_done = fields.Date(string="Fecha de cumplimiento")
    evidence = fields.Char(string="Evidencia / referencia")
    notes = fields.Text()

    def write(self, vals):
        if vals.get("state") == "completado" and not vals.get("date_done"):
            vals["date_done"] = fields.Date.today()
        return super().write(vals)

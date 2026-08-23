from odoo import api, fields, models, _


class InvoiceSchedule(models.Model):
    """1.3 Calendario de facturación de clientes."""
    _name = "aq.portal.invoice.schedule"
    _description = "Portal: factura programada"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "scheduled_date asc, id desc"

    name = fields.Char(string="Qué debe facturarse", required=True, tracking=True)
    project_id = fields.Many2one("aq.portal.project", string="Proyecto", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    basis_type = fields.Selection([("contrato", "Contrato"), ("cotizacion", "Cotización"), ("orden", "Orden de compra"),
                                   ("periodo", "Periodo")], string="Se factura bajo", default="contrato")
    basis_ref = fields.Char(string="Referencia del contrato / cotización / orden")
    period_start = fields.Date(string="Periodo desde")
    period_end = fields.Date(string="Periodo hasta")
    billing_type = fields.Selection([("anticipo", "Anticipo"), ("mensualidad", "Mensualidad"),
                                     ("horas", "Horas ejecutadas"), ("entregable", "Entregable"), ("otro", "Otro")],
                                    string="Tipo de facturación", default="mensualidad", required=True)
    evidence_required = fields.Text(string="Evidencia necesaria para facturar")
    evidence_received = fields.Boolean(string="Evidencia recibida")
    scheduled_date = fields.Date(string="Fecha programada de emisión", required=True, tracking=True)
    # datos fiscales
    fiscal_name = fields.Char(string="Razón social")
    fiscal_vat = fields.Char(string="RFC")
    fiscal_regime = fields.Char(string="Régimen fiscal")
    fiscal_zip = fields.Char(string="Código postal fiscal")
    cfdi_use = fields.Char(string="Uso de CFDI")
    payment_method = fields.Selection([("PUE", "PUE - Pago en una sola exhibición"), ("PPD", "PPD - Pago en parcialidades o diferido")],
                                      string="Método de pago", default="PUE")
    payment_form = fields.Char(string="Forma de pago (clave SAT)")
    concept = fields.Text(string="Concepto autorizado", required=True)
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    amount_untaxed = fields.Monetary(string="Importe", currency_field="currency_id")
    tax_rate = fields.Float(string="Tasa IVA (%)", default=16.0)
    amount_tax = fields.Monetary(string="Impuestos", compute="_compute_totals", store=True, currency_field="currency_id")
    amount_total = fields.Monetary(string="Total", compute="_compute_totals", store=True, currency_field="currency_id")
    send_to_name = fields.Char(string="Enviar a (persona)")
    send_to_email = fields.Char(string="Enviar a (correo)")
    send_cc_email = fields.Char(string="Copia a")
    issuer_id = fields.Many2one("aq.portal.member", string="Quien emite el CFDI")
    info_sent_to_issuer_date = fields.Date(string="Información enviada a emisor el")
    invoice_id = fields.Many2one("account.move", string="Factura en Odoo", domain=[("move_type", "=", "out_invoice")])
    invoice_number = fields.Char(string="Folio / número de factura")
    issue_date = fields.Date(string="Fecha de emisión real", tracking=True)
    reviewed_vs_agreement = fields.Boolean(string="Revisado administrativamente vs. lo acordado")
    sent_date = fields.Date(string="Fecha en que se envió", tracking=True)
    reception_confirmed = fields.Boolean(string="Confirmación de recepción")
    reception_date = fields.Date(string="Fecha de confirmación")
    due_date = fields.Date(string="Fecha de vencimiento")
    requires_payment_complement = fields.Boolean(string="Requiere complemento de pago")
    complement_state = fields.Selection([("no_aplica", "No aplica"), ("pendiente", "Pendiente"), ("emitido", "Emitido")],
                                        default="no_aplica", string="Complemento de pago")
    state = fields.Selection([
        ("por_programar", "Por programar"), ("programada", "Programada"), ("info_enviada", "Información enviada a emisor"),
        ("emitida", "Emitida"), ("enviada", "Enviada al cliente"), ("recibida", "Recepción confirmada"),
        ("pagada", "Pagada"), ("detenida", "Detenida – requiere validación"), ("cancelada", "Cancelada"),
    ], default="programada", tracking=True, string="Estado final")
    hold_reason = fields.Text(string="Motivo de detención / diferencia detectada")
    validation_requested = fields.Boolean(string="Validación solicitada a Dirección")
    validated_by_direction = fields.Boolean(string="Validado por Dirección", readonly=True)
    validated_by_id = fields.Many2one("aq.portal.user", readonly=True, string="Validado por")
    validation_date = fields.Date(readonly=True)
    receivable_id = fields.Many2one("aq.portal.receivable", string="Cuenta por cobrar generada", readonly=True)
    is_late = fields.Boolean(compute="_compute_late", search="_search_is_late", string="Emisión atrasada")
    issued_on_time = fields.Boolean(compute="_compute_late", string="Emitida a tiempo")

    @api.depends("amount_untaxed", "tax_rate")
    def _compute_totals(self):
        for r in self:
            r.amount_tax = r.amount_untaxed * (r.tax_rate or 0.0) / 100.0
            r.amount_total = r.amount_untaxed + r.amount_tax

    def _compute_late(self):
        today = fields.Date.today()
        for r in self:
            r.is_late = bool(r.scheduled_date and r.scheduled_date < today and r.state in ("por_programar", "programada", "info_enviada", "detenida"))
            r.issued_on_time = bool(r.issue_date and r.scheduled_date and r.issue_date <= r.scheduled_date)

    def _search_is_late(self, operator, value):
        dom = [("scheduled_date", "<", fields.Date.today()), ("state", "in", ("por_programar", "programada", "info_enviada", "detenida"))]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom

    @api.onchange("partner_id")
    def _onchange_partner(self):
        if self.partner_id:
            self.fiscal_name = self.partner_id.name
            self.fiscal_vat = self.partner_id.vat
            self.fiscal_zip = self.partner_id.zip
            self.send_to_email = self.send_to_email or self.partner_id.email

    @api.model_create_multi
    def create(self, vals_list):
        Partner = self.env["res.partner"]
        for vals in vals_list:
            partner = Partner.browse(vals.get("partner_id")) if vals.get("partner_id") else Partner
            if partner:
                vals.setdefault("fiscal_name", partner.name)
                vals.setdefault("fiscal_vat", partner.vat)
                vals.setdefault("fiscal_zip", partner.zip)
                vals.setdefault("send_to_email", partner.email)
        return super().create(vals_list)

    def action_hold(self):
        self.write({"state": "detenida", "validation_requested": True})
        return True

    def action_validate_direction(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"validated_by_direction": True, "validated_by_id": pu, "validation_date": fields.Date.today(),
                    "state": "programada"})
        return True

    def action_mark_issued(self):
        for r in self:
            vals = {"state": "emitida", "issue_date": r.issue_date or fields.Date.today()}
            if not r.receivable_id:
                rec = self.env["aq.portal.receivable"].create({
                    "partner_id": r.partner_id.id, "project_id": r.project_id.id, "invoice_schedule_id": r.id,
                    "invoice_id": r.invoice_id.id, "invoice_number": r.invoice_number,
                    "issue_date": vals["issue_date"], "amount_total": r.amount_total, "currency_id": r.currency_id.id,
                    "due_date": r.due_date or vals["issue_date"], "responsible_id": r.project_id.responsible_id.id,
                })
                vals["receivable_id"] = rec.id
            r.write(vals)
        return True

    def action_mark_sent(self):
        self.write({"state": "enviada", "sent_date": fields.Date.today()})
        return True

    def action_confirm_reception(self):
        self.write({"state": "recibida", "reception_confirmed": True, "reception_date": fields.Date.today()})
        return True

from odoo import api, fields, models, _

PAYABLE_CATEGORIES = [
    ("proveedor", "Proveedores"), ("servicios_profesionales", "Servicios profesionales"),
    ("software", "Software y licencias"), ("infraestructura", "Infraestructura y servidores"),
    ("suscripcion", "Suscripciones"), ("honorarios", "Honorarios"), ("reembolso", "Gastos reembolsables"),
    ("impuesto", "Impuestos u obligaciones informadas por Contabilidad"), ("recurrente", "Pagos recurrentes"),
    ("renovacion", "Renovaciones"), ("otro", "Otro"),
]


class Payable(models.Model):
    """1.5 Cuentas por pagar."""
    _name = "aq.portal.payable"
    _description = "Portal: cuenta por pagar"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "due_date asc"

    name = fields.Char(string="Concepto", required=True, tracking=True)
    category = fields.Selection(PAYABLE_CATEGORIES, required=True, default="proveedor", string="Categoría")
    vendor_id = fields.Many2one("aq.portal.vendor", string="Proveedor / servicio (padrón)")
    partner_id = fields.Many2one("res.partner", string="Proveedor (contacto)")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto relacionado")
    invoice_ref = fields.Char(string="Factura / comprobante")
    has_receipt = fields.Boolean(string="Comprobante adjunto")
    due_date = fields.Date(string="Fecha de vencimiento", required=True, tracking=True)
    proposed_payment_date = fields.Date(string="Fecha propuesta de pago (calendario)")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    amount = fields.Monetary(string="Importe", required=True, currency_field="currency_id")
    account_ref = fields.Char(string="Cuenta / proveedor de pago")
    payment_method = fields.Selection([("transferencia", "Transferencia"), ("tarjeta", "Tarjeta"), ("domiciliado", "Domiciliado"),
                                       ("efectivo", "Efectivo"), ("otro", "Otro")], string="Método de pago")
    authorization_state = fields.Selection([("pendiente", "Pendiente de autorización"), ("autorizado", "Autorizado"),
                                            ("rechazado", "Rechazado")], default="pendiente", tracking=True, string="Autorización")
    authorized_by_id = fields.Many2one("aq.portal.user", readonly=True, string="Autorizado por")
    authorization_date = fields.Date(readonly=True)
    payment_state = fields.Selection([("programado", "Programado"), ("pagado", "Pagado"), ("vencido", "Vencido"),
                                      ("cancelado", "Cancelado")], default="programado", tracking=True, string="Estado de pago")
    payment_date = fields.Date(string="Fecha de pago")
    payment_evidence = fields.Char(string="Evidencia de pago (referencia)")
    paid_by_id = fields.Many2one("aq.portal.member", string="Ejecutó el pago")
    is_recurring = fields.Boolean(string="Recurrente")
    recurrence = fields.Selection([("semanal", "Semanal"), ("mensual", "Mensual"), ("bimestral", "Bimestral"),
                                   ("trimestral", "Trimestral"), ("semestral", "Semestral"), ("anual", "Anual")], string="Periodicidad")
    reported_by_accounting = fields.Boolean(string="Informado por Contabilidad")
    alert_days = fields.Integer(string="Alertar días antes", default=5)
    days_to_due = fields.Integer(compute="_compute_days", string="Días para vencer")
    is_overdue = fields.Boolean(compute="_compute_days", search="_search_is_overdue", string="Vencido")

    def _compute_days(self):
        today = fields.Date.today()
        for p in self:
            p.days_to_due = (p.due_date - today).days if p.due_date else 0
            p.is_overdue = bool(p.due_date and p.due_date < today and p.payment_state == "programado")

    def _search_is_overdue(self, operator, value):
        dom = [("due_date", "<", fields.Date.today()), ("payment_state", "=", "programado")]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom

    def action_authorize(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "autorizado", "authorized_by_id": pu, "authorization_date": fields.Date.today()})
        return True

    def action_reject(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "rechazado", "authorized_by_id": pu, "authorization_date": fields.Date.today()})
        return True

    def action_mark_paid(self):
        for p in self:
            p.write({"payment_state": "pagado", "payment_date": p.payment_date or fields.Date.today()})
            if p.is_recurring and p.recurrence:
                p._create_next_occurrence()
        return True

    def _create_next_occurrence(self):
        self.ensure_one()
        months = {"mensual": 1, "bimestral": 2, "trimestral": 3, "semestral": 6, "anual": 12}
        if self.recurrence == "semanal":
            nxt = fields.Date.add(self.due_date, days=7)
        else:
            nxt = fields.Date.add(self.due_date, months=months[self.recurrence])
        self.copy({"due_date": nxt, "payment_state": "programado", "payment_date": False, "payment_evidence": False,
                   "authorization_state": "pendiente", "authorized_by_id": False, "authorization_date": False,
                   "invoice_ref": False, "has_receipt": False})

from odoo import api, fields, models, _


class Receivable(models.Model):
    """1.4 Cuentas por cobrar y cobranza."""
    _name = "aq.portal.receivable"
    _description = "Portal: cuenta por cobrar"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "due_date asc"
    _rec_name = "invoice_number"

    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    invoice_schedule_id = fields.Many2one("aq.portal.invoice.schedule", string="Factura programada")
    invoice_id = fields.Many2one("account.move", string="Factura en Odoo")
    invoice_number = fields.Char(string="Factura", required=True)
    issue_date = fields.Date(string="Fecha de emisión", required=True)
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    amount_total = fields.Monetary(string="Importe", currency_field="currency_id", required=True)
    due_date = fields.Date(string="Fecha de vencimiento", required=True, tracking=True)
    days_elapsed = fields.Integer(compute="_compute_days", string="Días transcurridos")
    days_overdue = fields.Integer(compute="_compute_days", string="Días vencidos")
    days_to_due = fields.Integer(compute="_compute_days", string="Días para vencer")
    payment_ids = fields.One2many("aq.portal.receivable.payment", "receivable_id", string="Pagos recibidos")
    amount_paid = fields.Monetary(compute="_compute_balance", store=True, string="Pago recibido", currency_field="currency_id")
    balance = fields.Monetary(compute="_compute_balance", store=True, string="Saldo pendiente", currency_field="currency_id")
    last_followup_date = fields.Date(compute="_compute_followup", store=True, string="Último seguimiento")
    last_followup_note = fields.Char(compute="_compute_followup", store=True, string="Nota del último seguimiento")
    followup_ids = fields.One2many("aq.portal.followup", "receivable_id", string="Seguimientos")
    promised_payment_date = fields.Date(string="Compromiso de pago", tracking=True)
    promise_state = fields.Selection([("sin_compromiso", "Sin compromiso"), ("pendiente", "Pendiente de comprobar"),
                                      ("cumplido", "Cumplido"), ("incumplido", "Incumplido")],
                                     default="sin_compromiso", string="Estado del compromiso")
    next_action = fields.Char(string="Próxima acción")
    next_action_date = fields.Date(string="Fecha de próxima acción")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable interno")
    risk = fields.Selection([("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto"), ("critico", "Crítico")],
                            compute="_compute_risk", store=True, readonly=False, string="Riesgo de atraso")
    state = fields.Selection([
        ("vigente", "Vigente"), ("por_vencer", "Por vencer"), ("vencida", "Vencida"), ("parcial", "Pago parcial"),
        ("convenio", "Con convenio autorizado"), ("escalada", "Escalada"), ("pagada", "Pagada"), ("incobrable", "Incobrable"),
    ], default="vigente", tracking=True, string="Estado")
    escalated = fields.Boolean(string="Escalado internamente", tracking=True)
    escalation_date = fields.Date(readonly=True)
    # convenios (requieren autorización de Dirección)
    arrangement_type = fields.Selection([("ninguno", "Ninguno"), ("convenio", "Convenio de pago"), ("prorroga", "Prórroga"),
                                         ("descuento", "Descuento"), ("quita", "Quita"), ("modificacion", "Modificación")],
                                        default="ninguno", string="Convenio / modificación")
    arrangement_description = fields.Text(string="Detalle del convenio")
    arrangement_authorized = fields.Boolean(string="Autorizado por Dirección", readonly=True)
    arrangement_authorized_by_id = fields.Many2one("aq.portal.user", readonly=True, string="Autorizó")
    arrangement_date = fields.Date(readonly=True, string="Fecha de autorización")
    collected_on_time = fields.Boolean(compute="_compute_on_time", store=True, string="Cobrada en fecha")
    collection_days = fields.Integer(compute="_compute_on_time", store=True, string="Días para cobrar")
    paid_date = fields.Date(string="Fecha de pago total", readonly=True)

    @api.depends("partner_id", "invoice_number")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "%s · %s" % (r.invoice_number or "", r.partner_id.name or "")

    def _compute_days(self):
        today = fields.Date.today()
        for r in self:
            r.days_elapsed = (today - r.issue_date).days if r.issue_date else 0
            r.days_overdue = max((today - r.due_date).days, 0) if r.due_date and r.state not in ("pagada",) else 0
            r.days_to_due = (r.due_date - today).days if r.due_date else 0

    @api.depends("payment_ids.amount", "amount_total")
    def _compute_balance(self):
        for r in self:
            r.amount_paid = sum(r.payment_ids.mapped("amount"))
            r.balance = r.amount_total - r.amount_paid

    @api.depends("followup_ids.date", "followup_ids.note")
    def _compute_followup(self):
        for r in self:
            last = r.followup_ids.sorted("date", reverse=True)[:1]
            r.last_followup_date = last.date if last else False
            r.last_followup_note = (last.note or "")[:200] if last else False

    @api.depends("due_date", "promise_state", "balance", "state")
    def _compute_risk(self):
        today = fields.Date.today()
        for r in self:
            if r.state == "pagada" or r.balance <= 0:
                r.risk = "bajo"
                continue
            over = (today - r.due_date).days if r.due_date else 0
            if r.promise_state == "incumplido" or over > 30:
                r.risk = "critico"
            elif over > 0:
                r.risk = "alto"
            elif r.due_date and (r.due_date - today).days <= 7:
                r.risk = "medio"
            else:
                r.risk = "bajo"

    @api.depends("paid_date", "due_date", "issue_date")
    def _compute_on_time(self):
        for r in self:
            r.collected_on_time = bool(r.paid_date and r.due_date and r.paid_date <= r.due_date)
            r.collection_days = (r.paid_date - r.issue_date).days if r.paid_date and r.issue_date else 0

    def _refresh_state(self):
        today = fields.Date.today()
        for r in self:
            if r.state in ("incobrable", "convenio", "escalada") and r.balance > 0:
                continue
            if r.balance <= 0 and r.amount_total > 0:
                vals = {"state": "pagada"}
                if not r.paid_date:
                    last = r.payment_ids.sorted("date", reverse=True)[:1]
                    vals["paid_date"] = last.date if last else today
                r.with_context(aq_skip_activity=True).write(vals)
            elif r.amount_paid > 0:
                r.with_context(aq_skip_activity=True).write({"state": "parcial"})
            elif r.due_date and r.due_date < today:
                r.with_context(aq_skip_activity=True).write({"state": "vencida"})
            elif r.due_date and (r.due_date - today).days <= 7:
                r.with_context(aq_skip_activity=True).write({"state": "por_vencer"})
            else:
                r.with_context(aq_skip_activity=True).write({"state": "vigente"})
        self.mapped("project_id")._update_collection_status()

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("aq_skip_activity") and any(k in vals for k in ("due_date", "amount_total", "promised_payment_date")):
            self._refresh_state()
        return res

    def action_escalate(self):
        self.write({"escalated": True, "escalation_date": fields.Date.today(), "state": "escalada"})
        return True

    def action_authorize_arrangement(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"arrangement_authorized": True, "arrangement_authorized_by_id": pu,
                    "arrangement_date": fields.Date.today(), "state": "convenio"})
        return True

    def action_promise_kept(self):
        self.write({"promise_state": "cumplido"})
        return True

    def action_promise_broken(self):
        self.write({"promise_state": "incumplido", "next_action": _("Nuevo seguimiento y escalamiento interno"),
                    "next_action_date": fields.Date.today()})
        return True


class ReceivablePayment(models.Model):
    _name = "aq.portal.receivable.payment"
    _description = "Portal: pago recibido"
    _order = "date desc"

    receivable_id = fields.Many2one("aq.portal.receivable", required=True, ondelete="cascade")
    date = fields.Date(required=True, default=fields.Date.today)
    amount = fields.Float(required=True, string="Importe")
    reference = fields.Char(string="Referencia")
    verified = fields.Boolean(string="Comprobado en banco")
    complement_issued = fields.Boolean(string="Complemento de pago emitido")

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.mapped("receivable_id")._refresh_state()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.mapped("receivable_id")._refresh_state()
        return res

    def unlink(self):
        recv = self.mapped("receivable_id")
        res = super().unlink()
        recv._refresh_state()
        return res


class ProjectCollection(models.Model):
    _inherit = "aq.portal.project"

    def _update_collection_status(self):
        for p in self:
            recs = p.receivable_ids
            if not recs:
                continue
            if any(r.state == "vencida" for r in recs):
                status = "vencido"
            elif all(r.state == "pagada" for r in recs):
                status = "cobrado"
            elif any(r.amount_paid > 0 for r in recs):
                status = "parcial"
            else:
                status = "sin_cobrar"
            p.with_context(aq_skip_activity=True).write({"collection_status": status})

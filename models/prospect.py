from odoo import api, fields, models, _


class Prospect(models.Model):
    """1.7 Control de prospectos (separado de clientes)."""
    _name = "aq.portal.prospect"
    _description = "Portal: prospecto"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "followup_date asc, id desc"

    name = fields.Char(string="Empresa", required=True, tracking=True)
    contact_name = fields.Char(string="Contacto")
    contact_email = fields.Char(string="Correo")
    contact_phone = fields.Char(string="Teléfono")
    origin = fields.Selection([("referido", "Referido"), ("web", "Sitio web"), ("linkedin", "LinkedIn"),
                               ("evento", "Evento"), ("campana", "Campaña"), ("cliente_actual", "Cliente actual"),
                               ("otro", "Otro")], string="Origen", default="referido")
    need_detected = fields.Text(string="Necesidad detectada")
    service_interest = fields.Selection([("implementacion", "Implementación Odoo"), ("desarrollo", "Desarrollo a medida"),
                                         ("soporte", "Soporte"), ("consultoria", "Consultoría"), ("capacitacion", "Capacitación"),
                                         ("integracion", "Integración"), ("otro", "Otro")], string="Servicio de interés")
    sales_responsible_id = fields.Many2one("aq.portal.member", string="Responsable comercial", tracking=True)
    last_interaction_date = fields.Date(string="Última interacción", compute="_compute_last", store=True, readonly=False)
    next_action = fields.Char(string="Siguiente acción", tracking=True)
    followup_date = fields.Date(string="Fecha de seguimiento", tracking=True)
    proposal_sent = fields.Boolean(string="Cotización / propuesta enviada")
    proposal_ref = fields.Char(string="Referencia de propuesta")
    proposal_date = fields.Date(string="Fecha de propuesta")
    proposal_valid_until = fields.Date(string="Vigencia de la propuesta")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    proposal_amount = fields.Monetary(string="Monto propuesto", currency_field="currency_id")
    pending_info = fields.Text(string="Información pendiente")
    stage = fields.Selection([("nuevo", "Nuevo"), ("contactado", "Contactado"), ("calificado", "Calificado"),
                              ("propuesta", "Propuesta enviada"), ("negociacion", "Negociación"), ("ganado", "Ganado"),
                              ("perdido", "Perdido"), ("pausado", "Pausado")], default="nuevo", string="Etapa", tracking=True)
    probability = fields.Integer(string="Probabilidad (%)", default=10)
    result = fields.Selection([("pendiente", "Pendiente"), ("ganado", "Ganado"), ("perdido", "Perdido"), ("pausado", "Pausado")],
                              default="pendiente", string="Resultado final")
    lost_reason = fields.Selection([("precio", "Precio"), ("tiempo", "Tiempos"), ("competencia", "Competencia"),
                                    ("sin_respuesta", "Sin respuesta"), ("sin_presupuesto", "Sin presupuesto"),
                                    ("alcance", "Alcance"), ("otro", "Otro")], string="Motivo de pérdida")
    lost_reason_detail = fields.Text(string="Detalle del motivo")
    followup_ids = fields.One2many("aq.portal.followup", "prospect_id", string="Interacciones")
    days_without_followup = fields.Integer(compute="_compute_abandon", string="Días sin seguimiento")
    is_abandoned = fields.Boolean(compute="_compute_abandon", search="_search_abandoned", string="Sin seguimiento")
    proposal_expired = fields.Boolean(compute="_compute_abandon", string="Propuesta vencida")
    partner_id = fields.Many2one("res.partner", string="Convertido a cliente")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto generado")

    @api.depends("followup_ids.date")
    def _compute_last(self):
        for p in self:
            last = p.followup_ids.sorted("date", reverse=True)[:1]
            p.last_interaction_date = last.date if last else p.last_interaction_date

    def _compute_abandon(self):
        today = fields.Date.today()
        limit = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.prospect_days", "7"))
        for p in self:
            ref = p.last_interaction_date or p.create_date and p.create_date.date() or today
            p.days_without_followup = (today - ref).days
            open_ = p.stage not in ("ganado", "perdido", "pausado")
            p.is_abandoned = open_ and (not p.next_action or not p.followup_date or p.followup_date < today or p.days_without_followup > limit)
            p.proposal_expired = bool(open_ and p.proposal_valid_until and p.proposal_valid_until < today)

    def _search_abandoned(self, operator, value):
        today = fields.Date.today()
        dom = [("stage", "not in", ("ganado", "perdido", "pausado")),
               "|", "|", ("next_action", "=", False), ("followup_date", "=", False), ("followup_date", "<", today)]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom

    def action_mark_won(self):
        self.write({"stage": "ganado", "result": "ganado", "probability": 100})
        return True

    def action_mark_lost(self):
        self.write({"stage": "perdido", "result": "perdido", "probability": 0})
        return True

    def action_convert(self):
        """Crear cliente (res.partner) y proyecto a partir del prospecto."""
        for p in self:
            partner = p.partner_id or self.env["res.partner"].create({
                "name": p.name, "email": p.contact_email, "phone": p.contact_phone, "is_company": True})
            project = p.project_id or self.env["aq.portal.project"].create({
                "name": "%s · %s" % (p.name, dict(self._fields["service_interest"].selection).get(p.service_interest, "Proyecto")),
                "partner_id": partner.id, "contact_name": p.contact_name, "contact_email": p.contact_email,
                "responsible_id": p.sales_responsible_id.id, "contract_ref": p.proposal_ref,
            })
            p.write({"partner_id": partner.id, "project_id": project.id, "stage": "ganado", "result": "ganado"})
        return True

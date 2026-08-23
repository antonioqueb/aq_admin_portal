from odoo import api, fields, models, _


class Agreement(models.Model):
    """1.2 Seguimiento de acuerdos y pendientes."""
    _name = "aq.portal.agreement"
    _description = "Portal: acuerdo / pendiente"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "due_date asc, id desc"

    name = fields.Char(string="Qué se acordó", required=True, tracking=True)
    description = fields.Text(string="Detalle")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Cliente", related="project_id.partner_id", store=True, readonly=False)
    meeting_date = fields.Date(string="Fecha de la reunión / acuerdo", default=fields.Date.today)
    meeting_ref = fields.Char(string="Minuta / referencia")
    source = fields.Selection([
        ("reunion", "Reunión"), ("whatsapp", "WhatsApp"), ("correo", "Correo"), ("llamada", "Llamada"),
        ("verbal", "Conversación verbal"), ("portal", "Portal"), ("otro", "Otro"),
    ], string="Origen", default="reunion")
    needs_formalization = fields.Boolean(compute="_compute_flags", store=True, string="Requiere trasladarse a registro formal",
                                         help="Acuerdos de WhatsApp, correo o verbales no deben ser la única evidencia.")
    formalized = fields.Boolean(string="Trasladado a minuta/expediente oficial", tracking=True)
    requested_by = fields.Char(string="Quién lo solicitó")
    requested_by_partner_id = fields.Many2one("res.partner", string="Solicitante (contacto)")
    executor_id = fields.Many2one("aq.portal.member", string="Quién debe ejecutarlo", tracking=True)
    due_date = fields.Date(string="Cuándo debe entregarse", tracking=True)
    info_required = fields.Text(string="Qué información se necesita")
    in_scope = fields.Selection([("si", "Sí, forma parte del alcance"), ("no", "No, fuera de alcance"),
                                 ("por_definir", "Por definir")], string="¿Forma parte del alcance?", default="por_definir")
    requires_authorization = fields.Boolean(string="Requiere autorización adicional")
    authorization_state = fields.Selection([("no_aplica", "No aplica"), ("pendiente", "Pendiente"),
                                            ("autorizado", "Autorizado"), ("rechazado", "Rechazado")],
                                           default="no_aplica", string="Estado de autorización", tracking=True)
    authorized_by_id = fields.Many2one("aq.portal.user", string="Autorizado por (Dirección)", readonly=True)
    authorization_date = fields.Date(string="Fecha de autorización", readonly=True)
    completion_evidence = fields.Text(string="Cómo se demostrará que quedó terminado")
    validator_id = fields.Many2one("aq.portal.member", string="Quién debe validarlo (interno)")
    validator_partner_id = fields.Many2one("res.partner", string="Quién debe validarlo (cliente)")
    client_dependent = fields.Boolean(string="Depende del cliente")
    state = fields.Selection([
        ("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("bloqueado", "Bloqueado"),
        ("en_validacion", "En validación"), ("cerrado", "Cerrado"), ("cancelado", "Cancelado"),
    ], default="pendiente", tracking=True, string="Estado")
    closed_date = fields.Date(string="Fecha de cierre", readonly=True)
    closure_evidence = fields.Text(string="Evidencia de cierre")
    closure_validated = fields.Boolean(string="Cierre validado")
    last_update_request_date = fields.Date(string="Última solicitud de actualización", readonly=True)
    update_request_count = fields.Integer(string="Solicitudes de actualización", readonly=True)
    escalated = fields.Boolean(string="Escalado a Dirección", tracking=True)
    escalation_date = fields.Date(readonly=True)
    escalation_reason = fields.Text(string="Motivo de escalamiento")
    risk_type = fields.Selection([("entrega", "Riesgo para una entrega"), ("factura", "Riesgo para una factura"),
                                  ("cliente", "Riesgo con el cliente"), ("contractual", "Riesgo contractual"),
                                  ("ninguno", "Sin riesgo identificado")], default="ninguno", string="Tipo de riesgo")
    is_repeated = fields.Boolean(string="Pendiente que se repite sin cierre")
    repeat_count = fields.Integer(string="Veces reprogramado", readonly=True)
    priority = fields.Selection([("0", "Normal"), ("1", "Alta"), ("2", "Crítica")], default="0")
    is_overdue = fields.Boolean(compute="_compute_overdue", search="_search_is_overdue", string="Vencido")
    days_overdue = fields.Integer(compute="_compute_overdue", string="Días de atraso")
    followup_ids = fields.One2many("aq.portal.followup", "agreement_id", string="Seguimientos")
    change_request_id = fields.Many2one("aq.portal.change.request", string="Solicitud de cambio relacionada")

    @api.depends("source", "formalized")
    def _compute_flags(self):
        for a in self:
            a.needs_formalization = a.source in ("whatsapp", "correo", "verbal", "llamada") and not a.formalized

    def _compute_overdue(self):
        today = fields.Date.today()
        for a in self:
            late = bool(a.due_date and a.due_date < today and a.state not in ("cerrado", "cancelado"))
            a.is_overdue = late
            a.days_overdue = (today - a.due_date).days if late else 0

    def _search_is_overdue(self, operator, value):
        dom = [("due_date", "<", fields.Date.today()), ("state", "not in", ("cerrado", "cancelado"))]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom

    def write(self, vals):
        if "due_date" in vals:
            for a in self:
                if a.due_date and vals["due_date"] and fields.Date.to_date(vals["due_date"]) > a.due_date:
                    vals_r = {"repeat_count": a.repeat_count + 1}
                    if a.repeat_count + 1 >= 2:
                        vals_r["is_repeated"] = True
                    super(Agreement, a).write(vals_r)
        if vals.get("state") == "cerrado":
            vals.setdefault("closed_date", fields.Date.today())
        res = super().write(vals)
        self.mapped("project_id").portal_touch()
        return res

    def action_request_update(self):
        for a in self:
            a.write({"last_update_request_date": fields.Date.today(), "update_request_count": a.update_request_count + 1})
            self.env["aq.portal.followup"].create({
                "agreement_id": a.id, "channel": "portal", "kind": "solicitud_actualizacion",
                "note": _("Se solicitó actualización a %s.") % (a.executor_id.name or "-"), "member_id": a.executor_id.id,
            })
            if a.executor_id.email:
                Brand = self.env["aq.portal.branding"]
                self.env["mail.mail"].sudo().create({
                    "subject": _("Solicitud de actualización: %s") % a.name, "email_to": a.executor_id.email,
                    "body_html": Brand.wrap(_("Solicitud de actualización"),
                                            _("<p>Se solicita actualización del pendiente <b>%s</b> (fecha compromiso: %s).</p>") % (a.name, a.due_date or "-"),
                                            _("Actualizar pendiente"), Brand.portal_url("agreements", a.id)),
                }).send()
        return True

    def action_escalate(self):
        self.write({"escalated": True, "escalation_date": fields.Date.today()})
        return True

    def action_close(self):
        self.write({"state": "cerrado", "closed_date": fields.Date.today()})
        return True

    def action_authorize(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "autorizado", "authorized_by_id": pu, "authorization_date": fields.Date.today()})
        return True

    def action_reject(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "rechazado", "authorized_by_id": pu, "authorization_date": fields.Date.today()})
        return True

from odoo import api, fields, models, _

CLASSIFICATIONS = [
    ("en_alcance", "Incluida en el alcance"), ("correccion", "Corrección o garantía"),
    ("configuracion", "Configuración"), ("soporte", "Soporte"), ("desarrollo_adicional", "Desarrollo adicional"),
    ("cambio_requerimiento", "Cambio de requerimiento"), ("nueva_etapa", "Nueva etapa"),
    ("pendiente_analisis", "Solicitud todavía pendiente de análisis"),
]


class ChangeRequest(models.Model):
    """2.4 Control de cambios y trabajo adicional."""
    _name = "aq.portal.change.request"
    _description = "Portal: solicitud de cambio / trabajo adicional"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "request_date desc"

    name = fields.Char(string="Solicitud", required=True, tracking=True)
    project_id = fields.Many2one("aq.portal.project", required=True, string="Proyecto")
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    requested_by = fields.Char(string="Solicitado por (cliente)")
    request_date = fields.Date(string="Fecha de solicitud", default=fields.Date.today)
    received_by_id = fields.Many2one("aq.portal.member", string="Recibido por")
    description = fields.Text(string="Descripción de la solicitud")
    classification = fields.Selection(CLASSIFICATIONS, default="pendiente_analisis", required=True, string="Clasificación", tracking=True)
    analysis = fields.Text(string="Análisis / justificación de la clasificación")
    estimate_hours = fields.Float(string="Horas estimadas")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    estimate_amount = fields.Monetary(string="Importe estimado", currency_field="currency_id")
    estimated_by_id = fields.Many2one("aq.portal.member", string="Estimó")
    quotation_ref = fields.Char(string="Cotización / orden relacionada")
    authorization_state = fields.Selection([("no_requerida", "No requerida (en alcance/garantía)"), ("pendiente", "Pendiente"),
                                            ("autorizado_cliente", "Autorizado por cliente"), ("autorizado_direccion", "Autorizado por Dirección (excepción)"),
                                            ("rechazado", "Rechazado")], default="pendiente", string="Autorización", tracking=True)
    authorized_by_id = fields.Many2one("aq.portal.user", readonly=True, string="Registró autorización")
    authorization_date = fields.Date(readonly=True)
    authorization_evidence = fields.Char(string="Evidencia de autorización (correo, orden)")
    can_execute = fields.Boolean(compute="_compute_execute", store=True, string="Puede ejecutarse")
    executed = fields.Boolean(string="Ejecutado", tracking=True)
    executed_without_authorization = fields.Boolean(compute="_compute_execute", store=True, string="Ejecutado sin autorización (riesgo)")
    state = fields.Selection([("nuevo", "Nuevo"), ("analisis", "En análisis"), ("estimado", "Estimado"), ("autorizado", "Autorizado"),
                              ("en_ejecucion", "En ejecución"), ("entregado", "Entregado"), ("cerrado", "Cerrado"), ("rechazado", "Rechazado")],
                             default="nuevo", string="Estado", tracking=True)
    agreement_ids = fields.One2many("aq.portal.agreement", "change_request_id", string="Pendientes derivados")
    hour_entry_ids = fields.One2many("aq.portal.hour.entry", "change_request_id", string="Horas ejecutadas")

    @api.depends("classification", "authorization_state", "executed", "quotation_ref")
    def _compute_execute(self):
        for c in self:
            free = c.classification in ("en_alcance", "correccion")
            authorized = c.authorization_state in ("autorizado_cliente", "autorizado_direccion", "no_requerida")
            c.can_execute = free or authorized
            c.executed_without_authorization = c.executed and not c.can_execute

    @api.onchange("classification")
    def _onchange_classification(self):
        if self.classification in ("en_alcance", "correccion"):
            self.authorization_state = "no_requerida"
        elif self.authorization_state == "no_requerida":
            self.authorization_state = "pendiente"

    def action_authorize_client(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "autorizado_cliente", "authorized_by_id": pu,
                    "authorization_date": fields.Date.today(), "state": "autorizado"})
        return True

    def action_authorize_direction(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "autorizado_direccion", "authorized_by_id": pu,
                    "authorization_date": fields.Date.today(), "state": "autorizado"})
        return True

    def action_reject(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"authorization_state": "rechazado", "authorized_by_id": pu, "authorization_date": fields.Date.today(), "state": "rechazado"})
        return True

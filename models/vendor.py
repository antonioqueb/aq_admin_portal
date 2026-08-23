from odoo import api, fields, models, _


class Vendor(models.Model):
    """2.5 Padrón de proveedores, licencias y servicios recurrentes."""
    _name = "aq.portal.vendor"
    _description = "Portal: proveedor / servicio recurrente"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "renewal_date asc, name"

    name = fields.Char(string="Proveedor", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Contacto en Odoo")
    service = fields.Char(string="Servicio", required=True)
    service_type = fields.Selection([("servidor", "Servidores / hosting"), ("dominio", "Dominios"), ("correo", "Correo"),
                                     ("software", "Software"), ("licencia", "Licencias"), ("gestion", "Herramientas de gestión"),
                                     ("profesional", "Servicios profesionales"), ("otro", "Otro")], string="Tipo", default="software")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable interno")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    cost = fields.Monetary(string="Costo", currency_field="currency_id")
    periodicity = fields.Selection([("unico", "Único"), ("mensual", "Mensual"), ("trimestral", "Trimestral"),
                                    ("semestral", "Semestral"), ("anual", "Anual")], string="Periodicidad", default="mensual")
    renewal_date = fields.Date(string="Próxima renovación", tracking=True)
    auto_renew = fields.Boolean(string="Renovación automática")
    contract_ref = fields.Char(string="Contrato / términos")
    legal_item_id = fields.Many2one("aq.portal.legal.item", string="Contrato en inventario legal")
    account_holder = fields.Char(string="Cuenta empresarial / titular (sin contraseñas)")
    credential_location = fields.Char(string="Dónde se resguardan las credenciales (gestor/bóveda)")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto relacionado")
    payment_method = fields.Selection([("tarjeta", "Tarjeta"), ("transferencia", "Transferencia"), ("domiciliado", "Domiciliado"),
                                       ("paypal", "PayPal"), ("otro", "Otro")], string="Método de pago")
    cancellation_notice_days = fields.Integer(string="Aviso previo de cancelación (días)")
    operational_risk = fields.Selection([("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto"), ("critico", "Crítico")],
                                        default="medio", string="Riesgo operativo si se suspende")
    risk_description = fields.Text(string="Impacto si se suspende")
    is_critical = fields.Boolean(string="Proveedor crítico")
    state = fields.Selection([("activo", "Activo"), ("suspendido", "Suspendido"), ("cancelado", "Cancelado")], default="activo", tracking=True)
    payable_ids = fields.One2many("aq.portal.payable", "vendor_id", string="Pagos")
    days_to_renewal = fields.Integer(compute="_compute_days", string="Días para renovación")

    def _compute_days(self):
        today = fields.Date.today()
        for v in self:
            v.days_to_renewal = (v.renewal_date - today).days if v.renewal_date else 0

    def action_generate_payable(self):
        for v in self:
            self.env["aq.portal.payable"].create({
                "name": "%s · %s" % (v.name, v.service), "category": "renovacion" if v.periodicity != "mensual" else "recurrente",
                "vendor_id": v.id, "partner_id": v.partner_id.id, "project_id": v.project_id.id,
                "due_date": v.renewal_date or fields.Date.today(), "amount": v.cost, "currency_id": v.currency_id.id,
                "is_recurring": v.periodicity != "unico", "recurrence": v.periodicity if v.periodicity != "unico" else False,
                "payment_method": "transferencia" if v.payment_method == "transferencia" else "tarjeta" if v.payment_method == "tarjeta" else "otro",
            })
        return True

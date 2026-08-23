from odoo import api, fields, models, _

OBLIGATION_TYPES = [
    ("contrato", "Vencimiento de contrato"), ("renovacion", "Renovación"), ("facturacion", "Facturación"),
    ("cobranza", "Cobranza"), ("pago", "Pago"), ("contabilidad", "Declaración / entregable de Contabilidad"),
    ("aviso_privacidad", "Aviso de privacidad"), ("permiso", "Permiso"), ("licencia", "Licencia"),
    ("dominio", "Dominio"), ("poliza", "Póliza"), ("asamblea", "Asamblea / acuerdo corporativo"),
    ("compromiso_cliente", "Fecha comprometida con cliente"), ("otro", "Otro"),
]


class Obligation(models.Model):
    """2.6 Calendario preventivo de obligaciones."""
    _name = "aq.portal.obligation"
    _description = "Portal: obligación"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date asc"

    name = fields.Char(string="Obligación", required=True, tracking=True)
    obligation_type = fields.Selection(OBLIGATION_TYPES, required=True, string="Tipo", default="otro")
    date = fields.Date(string="Fecha límite", required=True, tracking=True)
    reminder_days = fields.Integer(string="Recordar días antes", default=7)
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    partner_id = fields.Many2one("res.partner", string="Cliente / proveedor")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    vendor_id = fields.Many2one("aq.portal.vendor", string="Proveedor (padrón)")
    legal_item_id = fields.Many2one("aq.portal.legal.item", string="Contrato / documento")
    recurrence = fields.Selection([("ninguna", "Sin recurrencia"), ("mensual", "Mensual"), ("bimestral", "Bimestral"),
                                   ("trimestral", "Trimestral"), ("semestral", "Semestral"), ("anual", "Anual")], default="ninguna")
    state = fields.Selection([("pendiente", "Pendiente"), ("cumplida", "Cumplida"), ("vencida", "Vencida"), ("cancelada", "Cancelada")],
                             default="pendiente", tracking=True)
    done_date = fields.Date(string="Fecha de cumplimiento")
    evidence = fields.Char(string="Evidencia")
    days_to_date = fields.Integer(compute="_compute_days", string="Días restantes")

    def _compute_days(self):
        today = fields.Date.today()
        for o in self:
            o.days_to_date = (o.date - today).days if o.date else 0

    def action_done(self):
        for o in self:
            o.write({"state": "cumplida", "done_date": fields.Date.today()})
            if o.recurrence and o.recurrence != "ninguna":
                months = {"mensual": 1, "bimestral": 2, "trimestral": 3, "semestral": 6, "anual": 12}[o.recurrence]
                o.copy({"date": fields.Date.add(o.date, months=months), "state": "pendiente", "done_date": False, "evidence": False})
        return True

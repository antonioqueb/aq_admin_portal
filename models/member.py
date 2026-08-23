from odoo import api, fields, models


class Member(models.Model):
    """Integrantes del equipo (internos, prestadores, socios). Pueden o no tener usuario del portal."""
    _name = "aq.portal.member"
    _description = "Portal: integrante del equipo"
    _inherit = ["aq.portal.mixin"]
    _order = "name"

    name = fields.Char(required=True)
    email = fields.Char()
    phone = fields.Char()
    member_type = fields.Selection([
        ("socio", "Socio"), ("empleado", "Empleado"), ("prestador", "Prestador de servicios"),
        ("direccion", "Dirección"), ("externo", "Externo"),
    ], default="empleado", required=True, string="Tipo")
    position = fields.Char(string="Puesto")
    is_direction = fields.Boolean(string="Forma parte de Dirección")
    active = fields.Boolean(default=True)
    user_id = fields.Many2one("res.users", string="Usuario Odoo (opcional)")
    portal_user_ids = fields.One2many("aq.portal.user", "member_id", string="Usuarios del portal")
    employee_id = fields.Many2one("aq.portal.employee", string="Expediente")
    color = fields.Integer()

    # KPIs por responsable
    overdue_agreement_count = fields.Integer(compute="_compute_counts", string="Pendientes vencidos")
    open_agreement_count = fields.Integer(compute="_compute_counts", string="Pendientes abiertos")

    def _compute_counts(self):
        today = fields.Date.today()
        Agreement = self.env["aq.portal.agreement"]
        for m in self:
            dom = [("executor_id", "=", m.id), ("state", "not in", ("cerrado", "cancelado"))]
            m.open_agreement_count = Agreement.search_count(dom)
            m.overdue_agreement_count = Agreement.search_count(dom + [("due_date", "<", today)])

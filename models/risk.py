from odoo import api, fields, models

RISK_TYPES = [
    ("trabajo_sin_contrato", "Trabajo sin contrato"), ("alcance_ambiguo", "Alcances ambiguos"),
    ("horas_no_registradas", "Horas no registradas"), ("facturas_no_emitidas", "Facturas no emitidas"),
    ("cartera_vencida", "Cartera vencida"), ("dependencia_persona", "Dependencia de una sola persona"),
    ("sin_evidencia_aceptacion", "Falta de evidencia de aceptación"), ("accesos_exempleados", "Accesos de exempleados"),
    ("contratos_vencidos", "Contratos vencidos"), ("datos_sin_control", "Datos personales sin control"),
    ("proveedor_critico", "Proveedores críticos"), ("sin_respaldo_documental", "Proyectos sin respaldo documental"),
    ("compromiso_no_autorizado", "Compromisos comerciales no autorizados"), ("otro", "Otro"),
]


class Risk(models.Model):
    """3.3 Matriz de riesgos administrativos, contractuales y operativos."""
    _name = "aq.portal.risk"
    _description = "Portal: riesgo"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "severity desc, review_date asc"

    name = fields.Char(string="Riesgo", required=True, tracking=True)
    category = fields.Selection([("administrativo", "Administrativo"), ("contractual", "Contractual"), ("operativo", "Operativo")],
                                required=True, default="administrativo")
    risk_type = fields.Selection(RISK_TYPES, required=True, default="otro", string="Tipo")
    description = fields.Text(string="Descripción / causa")
    probability = fields.Selection([("1", "Baja"), ("2", "Media"), ("3", "Alta")], default="2", string="Probabilidad")
    impact = fields.Selection([("1", "Bajo"), ("2", "Medio"), ("3", "Alto")], default="2", string="Impacto")
    severity = fields.Integer(compute="_compute_severity", store=True, string="Severidad (P×I)")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable", required=True)
    preventive_action = fields.Text(string="Acción preventiva", required=True)
    mitigation_action = fields.Text(string="Plan de mitigación si se materializa")
    review_date = fields.Date(string="Fecha de revisión", required=True)
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    partner_id = fields.Many2one("res.partner", string="Cliente / proveedor")
    vendor_id = fields.Many2one("aq.portal.vendor", string="Proveedor (padrón)")
    employee_id = fields.Many2one("aq.portal.employee", string="Integrante")
    state = fields.Selection([("abierto", "Abierto"), ("mitigando", "En mitigación"), ("controlado", "Controlado"),
                              ("materializado", "Materializado"), ("cerrado", "Cerrado")], default="abierto", tracking=True)
    auto_generated = fields.Boolean(string="Detectado automáticamente")
    source_model = fields.Char()
    source_id = fields.Integer()

    @api.depends("probability", "impact")
    def _compute_severity(self):
        for r in self:
            r.severity = int(r.probability or 0) * int(r.impact or 0)

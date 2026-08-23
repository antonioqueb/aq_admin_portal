from odoo import fields, models


class Improvement(models.Model):
    """3.7 Mejora continua: propuestas."""
    _name = "aq.portal.improvement"
    _description = "Portal: propuesta de mejora"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "priority desc, id desc"

    name = fields.Char(string="Propuesta", required=True, tracking=True)
    improvement_type = fields.Selection([("proceso_manual", "Proceso innecesariamente manual"), ("automatizacion", "Automatización"),
                                         ("duplicidad", "Duplicidad de información"), ("simplificar_formato", "Simplificación de formatos"),
                                         ("organizacion_documental", "Organización documental"), ("ruta_autorizacion", "Responsables y rutas de autorización"),
                                         ("control_preventivo", "Control preventivo"), ("mejora_odoo", "Mejora en Odoo / herramientas internas")],
                                        required=True, string="Tipo", default="proceso_manual")
    description = fields.Text(string="Situación actual y propuesta")
    expected_benefit = fields.Text(string="Beneficio esperado")
    proposed_by_id = fields.Many2one("aq.portal.member", string="Propuesto por")
    date = fields.Date(default=fields.Date.today)
    priority = fields.Selection([("0", "Baja"), ("1", "Media"), ("2", "Alta")], default="1")
    state = fields.Selection([("propuesta", "Propuesta"), ("evaluacion", "En evaluación"), ("aprobada", "Aprobada"),
                              ("implementada", "Implementada"), ("descartada", "Descartada")], default="propuesta", tracking=True)
    decision_notes = fields.Text(string="Decisión de Dirección")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable de implementar")
    target_date = fields.Date(string="Fecha objetivo")

from odoo import api, fields, models


class Tender(models.Model):
    """3.6 Proyectos con gobierno y sector público."""
    _name = "aq.portal.tender"
    _description = "Portal: oportunidad / contrato con sector público"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "deadline asc"

    name = fields.Char(string="Convocatoria / procedimiento", required=True, tracking=True)
    entity = fields.Char(string="Entidad pública", required=True)
    tender_type = fields.Selection([("convocatoria", "Revisión de convocatoria"), ("licitacion", "Procedimiento de contratación"),
                                    ("contrato", "Contrato con entidad pública"), ("registro", "Registro en portal / padrón")],
                                   default="convocatoria", string="Tipo")
    reference = fields.Char(string="Número / referencia")
    portal_url = fields.Char(string="Portal / enlace")
    deadline = fields.Date(string="Fecha límite", tracking=True)
    scope_defined = fields.Boolean(string="Alcance definido por Dirección")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    summary = fields.Text(string="Objeto y alcance")
    requirement_ids = fields.One2many("aq.portal.checklist.item", "tender_id", string="Matriz de cumplimiento / requisitos")
    deliverables = fields.Text(string="Entregables comprometidos")
    guarantees = fields.Text(string="Garantías (cumplimiento, vicios ocultos, anticipo)")
    special_obligations = fields.Text(string="Riesgos y obligaciones especiales")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto generado")
    state = fields.Selection([("analisis", "En análisis"), ("integracion", "Integrando expediente"), ("presentado", "Presentado"),
                              ("adjudicado", "Adjudicado"), ("en_ejecucion", "En ejecución"), ("cerrado", "Cerrado"), ("descartado", "Descartado")],
                             default="analisis", tracking=True)
    compliance_pct = fields.Float(compute="_compute_compliance", string="Cumplimiento (%)")

    @api.depends("requirement_ids.done")
    def _compute_compliance(self):
        for t in self:
            reqs = t.requirement_ids
            t.compliance_pct = (len(reqs.filtered("done")) / len(reqs) * 100.0) if reqs else 0.0

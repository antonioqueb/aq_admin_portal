from odoo import fields, models


class Corporate(models.Model):
    """3.5 Gobierno corporativo."""
    _name = "aq.portal.corporate"
    _description = "Portal: documento de gobierno corporativo"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date desc"

    name = fields.Char(string="Documento / decisión", required=True, tracking=True)
    doc_type = fields.Selection([("libro", "Libros y documentos corporativos"), ("acuerdo_socios", "Acuerdo entre socios"),
                                 ("acta", "Acta"), ("poder", "Poder"), ("responsabilidades", "Responsabilidades"),
                                 ("conflicto_interes", "Conflicto de interés"), ("propiedad_intelectual", "Propiedad intelectual"),
                                 ("firmas", "Firmas autorizadas"), ("decision", "Decisión relevante"), ("otro", "Otro")],
                                required=True, string="Tipo", default="decision")
    date = fields.Date(string="Fecha", default=fields.Date.today)
    parties = fields.Char(string="Partes / socios involucrados")
    signatories = fields.Char(string="Firmantes")
    valid_until = fields.Date(string="Vigencia hasta")
    summary = fields.Text(string="Resumen / acuerdo")
    state = fields.Selection([("vigente", "Vigente"), ("pendiente", "Pendiente de formalizar"), ("vencido", "Vencido"), ("historico", "Histórico")],
                             default="vigente", tracking=True)
    document_id = fields.Many2one("aq.portal.document", string="Documento en expediente")
    legal_item_id = fields.Many2one("aq.portal.legal.item", string="Elemento del inventario legal")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable de actualización")

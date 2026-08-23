from odoo import api, fields, models, _

FOLDER_TYPES = [
    ("cliente", "Clientes"), ("prospecto", "Prospectos"), ("empleado", "Empleados"),
    ("prestador", "Prestadores de servicios"), ("proveedor", "Proveedores"), ("socio", "Socios"),
    ("contrato", "Contratos"), ("facturacion", "Facturación"), ("proyecto", "Proyectos"),
    ("evidencia", "Evidencias de entrega"), ("respaldo", "Respaldos administrativos"), ("corporativo", "Corporativo"),
]


class Document(models.Model):
    """1.8 Organización documental: expedientes claros y localizables."""
    _name = "aq.portal.document"
    _description = "Portal: documento de expediente"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "folder_type, name"

    name = fields.Char(string="Nombre normalizado del archivo", required=True, tracking=True,
                       help="Nomenclatura sugerida: AAAA-MM-DD_Tipo_Contraparte_Versión")
    folder_type = fields.Selection(FOLDER_TYPES, string="Expediente", required=True, default="cliente")
    document_type = fields.Char(string="Tipo de documento", help="Contrato, anexo, acta, identificación, factura, etc.")
    partner_id = fields.Many2one("res.partner", string="Cliente / proveedor / contacto")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    prospect_id = fields.Many2one("aq.portal.prospect", string="Prospecto")
    employee_id = fields.Many2one("aq.portal.employee", string="Integrante (expediente)")
    vendor_id = fields.Many2one("aq.portal.vendor", string="Proveedor (padrón)")
    legal_item_id = fields.Many2one("aq.portal.legal.item", string="Elemento del inventario legal")
    version = fields.Char(string="Versión", default="1.0")
    version_status = fields.Selection([("borrador", "Borrador"), ("final", "Versión final")], default="borrador", string="Borrador / final", tracking=True)
    is_signed = fields.Boolean(string="Documento firmado", tracking=True)
    signed_date = fields.Date(string="Fecha de firma")
    doc_date = fields.Date(string="Fecha del documento")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    confidentiality = fields.Selection([("publico", "Público"), ("interno", "Interno"), ("confidencial", "Confidencial"),
                                        ("restringido", "Restringido")], default="interno", string="Clasificación")
    is_duplicate = fields.Boolean(string="Posible duplicado")
    duplicate_of_id = fields.Many2one("aq.portal.document", string="Duplicado de")
    is_missing = fields.Boolean(string="Documento faltante (no localizado)")
    required = fields.Boolean(string="Documento requerido")
    storage_location = fields.Char(string="Ubicación (Drive / carpeta física)")
    external_url = fields.Char(string="Enlace (Drive)")
    attachment_count = fields.Integer(compute="_compute_attachments", string="Archivos")
    sensitive = fields.Boolean(string="Documento sensible (no eliminar/mover sin validación)")
    change_validated_by_id = fields.Many2one("aq.portal.user", string="Cambio validado por", readonly=True)
    state = fields.Selection([("vigente", "Vigente"), ("obsoleto", "Obsoleto"), ("faltante", "Faltante"), ("en_revision", "En revisión")],
                             default="vigente", string="Estado", tracking=True)

    def _compute_attachments(self):
        Att = self.env["ir.attachment"].sudo()
        for d in self:
            d.attachment_count = Att.search_count([("res_model", "=", self._name), ("res_id", "=", d.id)])

    @api.model
    def suggest_name(self, doc_type, counterparty, version="v1", date=None):
        date = date or fields.Date.today()
        return "%s_%s_%s_%s" % (date.strftime("%Y-%m-%d"), (doc_type or "DOC").replace(" ", "-"),
                                (counterparty or "").replace(" ", "-"), version)

    def action_mark_final(self):
        self.write({"version_status": "final"})
        return True

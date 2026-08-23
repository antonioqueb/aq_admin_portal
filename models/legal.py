from odoo import api, fields, models, _

LEGAL_CATEGORIES = [
    ("laboral", "Contratos laborales"), ("prestador", "Contratos con prestadores de servicios"),
    ("cliente", "Contratos con clientes"), ("proveedor", "Contratos con proveedores"),
    ("socios", "Contratos o acuerdos entre socios"), ("convenio_modificatorio", "Convenios modificatorios"),
    ("anexo_alcance", "Anexos de alcance"), ("orden_cotizacion", "Órdenes o cotizaciones aceptadas"),
    ("nda", "Acuerdos de confidencialidad"), ("aviso_privacidad", "Avisos de privacidad"),
    ("propiedad_intelectual", "Cesión o reconocimiento de propiedad intelectual"),
    ("entrega_equipo", "Entrega de equipo y accesos"), ("acta_aceptacion", "Actas de aceptación"),
    ("terminacion", "Terminaciones o cierres"), ("corporativo", "Documentos corporativos"),
]

TEMPLATE_CATEGORIES = [
    ("personal", "Personal"), ("prestadores", "Prestadores de servicios"), ("socios", "Socios"),
    ("clientes", "Clientes"), ("confidencialidad", "Confidencialidad y privacidad"),
]
TEMPLATE_SUBTYPES = [
    # Personal
    ("p_contrato_individual", "Personal · Contrato individual de trabajo"),
    ("p_contrato_modalidad", "Personal · Contratos por modalidad aplicable"),
    ("p_convenio_modificatorio", "Personal · Convenios modificatorios"),
    ("p_nda", "Personal · Acuerdo de confidencialidad"),
    ("p_politicas", "Personal · Políticas internas"),
    ("p_proteccion_info", "Personal · Protección de información"),
    ("p_pi", "Personal · Propiedad intelectual y entregables"),
    ("p_equipos", "Personal · Entrega y devolución de equipos"),
    ("p_cuentas", "Personal · Uso de cuentas, sistemas y credenciales"),
    ("p_incorporacion", "Personal · Documentos de incorporación"),
    ("p_separacion", "Personal · Documentos de separación y entrega del puesto"),
    # Prestadores
    ("s_contrato", "Prestadores · Contrato de prestación de servicios profesionales"),
    ("s_alcance", "Prestadores · Alcance y entregables"),
    ("s_honorarios", "Prestadores · Honorarios y forma de pago"),
    ("s_confidencialidad", "Prestadores · Confidencialidad"),
    ("s_pi", "Prestadores · Propiedad intelectual"),
    ("s_responsabilidades", "Prestadores · Responsabilidades"),
    ("s_terminacion", "Prestadores · Terminación"),
    ("s_entrega", "Prestadores · Entrega de información y accesos"),
    # Socios
    ("so_convenio", "Socios · Convenio entre socios"),
    ("so_responsabilidades", "Socios · Responsabilidades y funciones"),
    ("so_decisiones", "Socios · Participación en decisiones"),
    ("so_aportaciones", "Socios · Aportaciones"),
    ("so_beneficios", "Socios · Distribución de beneficios"),
    ("so_confidencialidad", "Socios · Confidencialidad"),
    ("so_pi", "Socios · Propiedad intelectual"),
    ("so_entrada_salida", "Socios · Entrada o salida de socios"),
    ("so_conflictos", "Socios · Manejo de conflictos"),
    ("so_post_separacion", "Socios · Restricciones y obligaciones posteriores a la separación"),
    # Clientes
    ("c_marco", "Clientes · Contrato marco de prestación de servicios"),
    ("c_anexo", "Clientes · Anexos de alcance"),
    ("c_cotizacion", "Clientes · Cotizaciones y órdenes aceptadas"),
    ("c_entregables", "Clientes · Entregables"),
    ("c_aceptacion_criterios", "Clientes · Criterios de aceptación"),
    ("c_responsabilidades", "Clientes · Responsabilidades del cliente"),
    ("c_dependencias", "Clientes · Dependencias e información requerida"),
    ("c_control_cambios", "Clientes · Control de cambios"),
    ("c_garantia", "Clientes · Garantía"),
    ("c_soporte", "Clientes · Soporte"),
    ("c_pi", "Clientes · Propiedad intelectual"),
    ("c_confidencialidad", "Clientes · Confidencialidad"),
    ("c_datos", "Clientes · Protección de datos"),
    ("c_suspension", "Clientes · Suspensión por falta de pago"),
    ("c_terminacion", "Clientes · Terminación y entrega"),
    ("c_acta", "Clientes · Actas de aceptación y cierre"),
    # Confidencialidad y privacidad
    ("n_nda_cliente", "NDA para clientes"),
    ("n_nda_empleado", "NDA para empleados"),
    ("n_nda_proveedor", "NDA para prestadores y proveedores"),
    ("n_ap_clientes", "Aviso de privacidad para clientes y contactos"),
    ("n_ap_empleados", "Aviso de privacidad para empleados y candidatos"),
    ("n_ap_proveedores", "Aviso de privacidad para proveedores"),
    ("n_ap_web", "Aviso para sitio web y formularios"),
    ("n_reglas_datos", "Reglas para almacenamiento y acceso a datos personales"),
    ("otro", "Otro"),
]


class LegalItem(models.Model):
    """1.9 Inventario legal inicial / matriz de contratos y documentos legales."""
    _name = "aq.portal.legal.item"
    _description = "Portal: elemento del inventario legal"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "priority desc, date_end asc"

    name = fields.Char(string="Documento / contrato", required=True, tracking=True)
    category = fields.Selection(LEGAL_CATEGORIES, required=True, string="Categoría")
    partner_id = fields.Many2one("res.partner", string="Contraparte (cliente/proveedor)")
    employee_id = fields.Many2one("aq.portal.employee", string="Contraparte (integrante)")
    vendor_id = fields.Many2one("aq.portal.vendor", string="Proveedor (padrón)")
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    exists = fields.Boolean(string="Existe el documento", tracking=True)
    is_current = fields.Boolean(string="Vigente", tracking=True)
    is_missing = fields.Boolean(compute="_compute_missing", store=True, string="Hace falta")
    is_signed = fields.Boolean(string="Firmado")
    date_signed = fields.Date(string="Fecha de firma")
    date_start = fields.Date(string="Inicio de vigencia")
    date_end = fields.Date(string="Fin de vigencia")
    days_to_expiry = fields.Integer(compute="_compute_expiry", string="Días para vencer")
    is_expired = fields.Boolean(compute="_compute_expiry", search="_search_expired", string="Vencido")
    risk_level = fields.Selection([("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto"), ("critico", "Crítico")],
                                  default="medio", string="Nivel de riesgo", tracking=True)
    priority = fields.Selection([("0", "Baja"), ("1", "Media"), ("2", "Alta")], default="1", string="Prioridad")
    status = fields.Selection([("vigente", "Vigente"), ("vencido", "Vencido"), ("faltante", "Faltante"),
                               ("en_elaboracion", "En elaboración"), ("en_revision", "En revisión"),
                               ("pendiente_firma", "Pendiente de firma"), ("terminado", "Terminado / cerrado")],
                              default="faltante", string="Estatus", tracking=True)
    needs_redo = fields.Boolean(string="Debe rehacerse / actualizarse")
    template_id = fields.Many2one("aq.portal.template", string="Formato de la biblioteca a usar")
    document_ids = fields.One2many("aq.portal.document", "legal_item_id", string="Documentos en expediente")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    review_date = fields.Date(string="Fecha de revisión")
    findings = fields.Text(string="Hallazgos / estado real")
    action_plan = fields.Text(string="Acción requerida")

    @api.depends("exists")
    def _compute_missing(self):
        for r in self:
            r.is_missing = not r.exists

    def _compute_expiry(self):
        today = fields.Date.today()
        for r in self:
            r.days_to_expiry = (r.date_end - today).days if r.date_end else 0
            r.is_expired = bool(r.date_end and r.date_end < today)

    def _search_expired(self, operator, value):
        dom = [("date_end", "<", fields.Date.today())]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return dom
        return ["!"] + dom


class Template(models.Model):
    """2.1 Biblioteca controlada de modelos y formatos legales."""
    _name = "aq.portal.template"
    _description = "Portal: formato / modelo legal"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "category, subtype, version desc"

    name = fields.Char(string="Nombre del formato", required=True, tracking=True)
    category = fields.Selection(TEMPLATE_CATEGORIES, required=True, string="Grupo")
    subtype = fields.Selection(TEMPLATE_SUBTYPES, required=True, string="Tipo de formato")
    version = fields.Char(string="Número de versión", required=True, default="1.0", tracking=True)
    version_date = fields.Date(string="Fecha de versión", default=fields.Date.today)
    reviewer_id = fields.Many2one("aq.portal.member", string="Responsable de revisión", required=True)
    approval_state = fields.Selection([("borrador", "Borrador"), ("en_revision", "En revisión"),
                                       ("aprobado", "Aprobado – puede utilizarse"), ("obsoleto", "Obsoleto")],
                                      default="borrador", string="Estado de aprobación", tracking=True)
    approved_by_id = fields.Many2one("aq.portal.user", string="Aprobado por (Dirección)", readonly=True)
    approval_date = fields.Date(readonly=True, string="Fecha de aprobación")
    can_be_used = fields.Boolean(compute="_compute_usable", store=True, string="Autorizado para uso")
    previous_version_id = fields.Many2one("aq.portal.template", string="Versión anterior")
    usage_notes = fields.Text(string="Instrucciones de uso / variables a completar")
    content = fields.Html(string="Contenido del formato")
    external_url = fields.Char(string="Enlace (Drive)")

    @api.depends("approval_state")
    def _compute_usable(self):
        for t in self:
            t.can_be_used = t.approval_state == "aprobado"

    def action_submit_review(self):
        self.write({"approval_state": "en_revision"})
        return True

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"approval_state": "aprobado", "approved_by_id": pu, "approval_date": fields.Date.today()})
        return True

    def action_new_version(self):
        for t in self:
            try:
                major, minor = t.version.split(".")
                new_v = "%s.%d" % (major, int(minor) + 1)
            except Exception:
                new_v = t.version + ".1"
            t.copy({"version": new_v, "version_date": fields.Date.today(), "approval_state": "borrador",
                    "approved_by_id": False, "approval_date": False, "previous_version_id": t.id})
            t.write({"approval_state": "obsoleto"})
        return True

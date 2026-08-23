from odoo import fields, models

PROCESS_TYPES = [
    ("alta_clientes", "Alta de clientes"), ("alta_proveedores", "Alta de proveedores"), ("facturacion", "Facturación"),
    ("cobranza", "Cobranza"), ("registro_gastos", "Registro de gastos"), ("autorizacion_pagos", "Autorización de pagos"),
    ("inicio_proyectos", "Inicio de proyectos"), ("control_cambios", "Control de cambios"), ("cierre_proyectos", "Cierre de proyectos"),
    ("incorporacion_personal", "Incorporación de personal"), ("separacion_personal", "Separación de personal"),
    ("manejo_accesos", "Manejo de accesos"), ("organizacion_drive", "Organización de Drive"),
    ("solicitudes_legales", "Atención de solicitudes legales"), ("incidentes_informacion", "Respuesta ante incidentes de información"),
    ("seguimiento_proyectos", "Seguimiento de proyectos"), ("politica_confidencialidad", "Política de confidencialidad"),
    ("politica_accesos", "Política de accesos"), ("politica_conservacion", "Política de conservación de información"),
    ("politica_eliminacion", "Política de eliminación segura"), ("rutina_semanal", "Rutina semanal administrativa"), ("otro", "Otro"),
]


class Manual(models.Model):
    """3.4 Manuales y procedimientos internos (y políticas de 2.7)."""
    _name = "aq.portal.manual"
    _description = "Portal: manual / procedimiento"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "process_type, version desc"

    name = fields.Char(string="Procedimiento", required=True, tracking=True)
    process_type = fields.Selection(PROCESS_TYPES, required=True, string="Proceso", default="otro")
    purpose = fields.Text(string="Objetivo")
    scope_text = fields.Text(string="Alcance")
    content = fields.Html(string="Contenido (pasos, responsables, rutas de autorización)")
    version = fields.Char(default="1.0", string="Versión")
    owner_id = fields.Many2one("aq.portal.member", string="Responsable del proceso")
    state = fields.Selection([("borrador", "Borrador"), ("en_revision", "En revisión"), ("aprobado", "Aprobado"), ("obsoleto", "Obsoleto")],
                             default="borrador", tracking=True)
    approved_by_id = fields.Many2one("aq.portal.user", readonly=True, string="Aprobado por")
    approval_date = fields.Date(readonly=True)
    external_url = fields.Char(string="Enlace (Drive)")
    review_date = fields.Date(string="Próxima revisión")

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"state": "aprobado", "approved_by_id": pu, "approval_date": fields.Date.today()})
        return True

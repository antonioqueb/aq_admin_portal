from odoo import fields, models


class DataInventory(models.Model):
    """2.7 Privacidad y manejo de información: inventario de datos personales."""
    _name = "aq.portal.data.inventory"
    _description = "Portal: inventario de datos personales"
    _inherit = ["aq.portal.mixin", "mail.thread"]

    name = fields.Char(string="Categoría de datos / tratamiento", required=True, tracking=True)
    data_subjects = fields.Selection([("clientes", "Clientes y contactos"), ("empleados", "Empleados"), ("candidatos", "Candidatos"),
                                      ("proveedores", "Proveedores"), ("web", "Visitantes web / formularios"),
                                      ("clientes_finales", "Datos de clientes de nuestros clientes"), ("otro", "Otro")],
                                     string="Titulares", required=True)
    data_description = fields.Text(string="Qué datos se recopilan")
    purpose = fields.Text(string="Para qué se utilizan")
    storage_location = fields.Char(string="Dónde se almacenan (sistema / carpeta / servidor)")
    access_who = fields.Text(string="Quién tiene acceso")
    access_member_ids = fields.Many2many("aq.portal.member", string="Integrantes con acceso")
    shared_with = fields.Text(string="Con quién se comparten")
    retention_period = fields.Char(string="Cuánto tiempo se conservan")
    arco_procedure = fields.Text(string="Cómo se atienden solicitudes de titulares (ARCO)")
    offboarding_action = fields.Text(string="Qué debe suceder cuando una persona deja la empresa")
    requires_special_controls = fields.Boolean(string="Información de clientes que requiere controles especiales")
    special_controls = fields.Text(string="Controles especiales aplicables")
    privacy_notice_template_id = fields.Many2one("aq.portal.template", string="Aviso de privacidad aplicable")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    review_date = fields.Date(string="Próxima revisión")
    state = fields.Selection([("identificado", "Identificado"), ("documentado", "Documentado"), ("controlado", "Con controles"),
                              ("revision", "Requiere revisión")], default="identificado", tracking=True)

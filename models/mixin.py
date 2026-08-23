from odoo import api, fields, models


class PortalMixin(models.AbstractModel):
    """Campos comunes de trazabilidad para todos los controles del portal."""
    _name = "aq.portal.mixin"
    _description = "Portal: mixin de trazabilidad"

    portal_create_user_id = fields.Many2one(
        "aq.portal.user", string="Creado por (portal)", readonly=True, ondelete="set null")
    portal_write_user_id = fields.Many2one(
        "aq.portal.user", string="Última modificación por (portal)", readonly=True, ondelete="set null")
    last_activity_date = fields.Date(string="Última actividad", readonly=True, default=fields.Date.today)
    notes = fields.Text(string="Notas")

    @api.model_create_multi
    def create(self, vals_list):
        pu = self.env.context.get("portal_user_id")
        today = fields.Date.today()
        for vals in vals_list:
            vals.setdefault("last_activity_date", today)
            if pu:
                vals.setdefault("portal_create_user_id", pu)
                vals.setdefault("portal_write_user_id", pu)
        return super().create(vals_list)

    def write(self, vals):
        pu = self.env.context.get("portal_user_id")
        if not self.env.context.get("aq_skip_activity"):
            vals = dict(vals, last_activity_date=fields.Date.today())
        if pu:
            vals["portal_write_user_id"] = pu
        return super().write(vals)

    def portal_touch(self):
        """Registrar actividad sin cambiar datos."""
        self.with_context(aq_skip_activity=True).write({"last_activity_date": fields.Date.today()})

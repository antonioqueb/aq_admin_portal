import json
from odoo import fields, models


class AuditLog(models.Model):
    _name = "aq.portal.audit.log"
    _description = "Portal: bitácora de auditoría"
    _order = "create_date desc"
    _rec_name = "summary"

    user_id = fields.Many2one("aq.portal.user", string="Usuario del portal", index=True)
    action = fields.Selection([("create", "Creación"), ("write", "Modificación"), ("unlink", "Archivado/eliminación"),
                               ("action", "Acción"), ("login", "Inicio de sesión"), ("logout", "Cierre de sesión"),
                               ("denied", "Acceso denegado"), ("upload", "Archivo subido")], required=True)
    resource = fields.Char(index=True)
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    summary = fields.Char()
    changes = fields.Text(help="JSON con los valores enviados")
    ip = fields.Char()

    def log(self, user, action, resource=None, model=None, res_id=None, summary=None, changes=None, ip=None):
        return self.sudo().create({
            "user_id": user.id if user else False, "action": action, "resource": resource, "res_model": model,
            "res_id": res_id or 0, "summary": summary,
            "changes": json.dumps(changes, default=str, ensure_ascii=False) if changes else False, "ip": ip,
        })

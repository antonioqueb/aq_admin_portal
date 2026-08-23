from odoo import fields, models


class OnboardingDeliverable(models.Model):
    """5. Entregables esperados durante la incorporación (semana 1, 15, 30, 60 y 90 días)."""
    _name = "aq.portal.onboarding.deliverable"
    _description = "Portal: entregable de incorporación"
    _order = "phase, sequence"

    name = fields.Char(required=True, string="Entregable")
    phase = fields.Selection([("semana1", "Primera semana"), ("dias15", "Primeros 15 días"), ("dias30", "Primeros 30 días"),
                              ("dias60", "Entre 30 y 60 días"), ("dias90", "Entre 60 y 90 días")], required=True, string="Fase")
    sequence = fields.Integer(default=10)
    due_date = fields.Date(string="Fecha límite")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    state = fields.Selection([("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("entregado", "Entregado"), ("validado", "Validado por Dirección")],
                             default="pendiente")
    delivered_date = fields.Date(string="Fecha de entrega")
    evidence = fields.Char(string="Evidencia / enlace")
    link_resource = fields.Char(string="Sección del portal relacionada")
    notes = fields.Text()

    def action_deliver(self):
        self.write({"state": "entregado", "delivered_date": fields.Date.today()})
        return True

    def action_validate(self):
        self.write({"state": "validado"})
        return True

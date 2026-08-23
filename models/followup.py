from odoo import api, fields, models


class Followup(models.Model):
    """Seguimiento genérico: cobranza, prospectos, pendientes, pagos y proyectos."""
    _name = "aq.portal.followup"
    _description = "Portal: seguimiento"
    _order = "date desc, id desc"

    date = fields.Date(required=True, default=fields.Date.today)
    kind = fields.Selection([("seguimiento", "Seguimiento"), ("solicitud_actualizacion", "Solicitud de actualización"),
                             ("escalamiento", "Escalamiento"), ("compromiso", "Compromiso registrado"),
                             ("interaccion", "Interacción con cliente/prospecto"), ("nota", "Nota")], default="seguimiento", string="Tipo")
    channel = fields.Selection([("llamada", "Llamada"), ("correo", "Correo"), ("whatsapp", "WhatsApp"), ("reunion", "Reunión"),
                                ("portal", "Portal"), ("otro", "Otro")], default="correo", string="Canal")
    contact = fields.Char(string="Con quién")
    note = fields.Text(string="Detalle", required=True)
    result = fields.Char(string="Resultado")
    next_action = fields.Char(string="Próxima acción")
    next_date = fields.Date(string="Fecha de próxima acción")
    member_id = fields.Many2one("aq.portal.member", string="Realizó")
    receivable_id = fields.Many2one("aq.portal.receivable", ondelete="cascade")
    prospect_id = fields.Many2one("aq.portal.prospect", ondelete="cascade")
    agreement_id = fields.Many2one("aq.portal.agreement", ondelete="cascade")
    payable_id = fields.Many2one("aq.portal.payable", ondelete="cascade")
    project_id = fields.Many2one("aq.portal.project", ondelete="cascade")
    promised_date = fields.Date(string="Fecha de pago prometida (cobranza)")

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for f in recs:
            if f.receivable_id:
                vals = {}
                if f.next_action:
                    vals.update(next_action=f.next_action, next_action_date=f.next_date)
                if f.promised_date:
                    vals.update(promised_payment_date=f.promised_date, promise_state="pendiente")
                if vals:
                    f.receivable_id.write(vals)
                else:
                    f.receivable_id.portal_touch()
            if f.prospect_id:
                vals = {"last_interaction_date": f.date}
                if f.next_action:
                    vals.update(next_action=f.next_action, followup_date=f.next_date)
                f.prospect_id.write(vals)
            if f.agreement_id:
                f.agreement_id.portal_touch()
            if f.project_id:
                f.project_id.portal_touch()
        return recs

from datetime import timedelta
from odoo import api, fields, models


class Routine(models.Model):
    """4. Ritmo de trabajo: rutinas diarias, semanales y mensuales."""
    _name = "aq.portal.routine"
    _description = "Portal: rutina"
    _order = "frequency, sequence"

    name = fields.Char(required=True, string="Actividad")
    frequency = fields.Selection([("diario", "Diario"), ("semanal", "Semanal"), ("mensual", "Mensual")], required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text()
    link_resource = fields.Char(string="Sección del portal relacionada", help="Clave del recurso al que dirige (p. ej. receivables)")
    active = fields.Boolean(default=True)


class RoutineRun(models.Model):
    _name = "aq.portal.routine.run"
    _description = "Portal: ejecución de rutina"
    _order = "period_date desc, routine_id"

    routine_id = fields.Many2one("aq.portal.routine", required=True, ondelete="cascade")
    frequency = fields.Selection(related="routine_id.frequency", store=True)
    period_date = fields.Date(required=True, string="Periodo (fecha de referencia)")
    done = fields.Boolean()
    done_date = fields.Datetime()
    user_id = fields.Many2one("aq.portal.user", string="Realizó")
    notes = fields.Text()

    @api.model
    def ensure_runs(self, date=None):
        """Crea las ejecuciones pendientes para el día, semana (lunes) y mes (día 1) dados."""
        date = date or fields.Date.today()
        week = date - timedelta(days=date.weekday())
        month = date.replace(day=1)
        periods = {"diario": date, "semanal": week, "mensual": month}
        for routine in self.env["aq.portal.routine"].search([]):
            p = periods[routine.frequency]
            if not self.search_count([("routine_id", "=", routine.id), ("period_date", "=", p)]):
                self.create({"routine_id": routine.id, "period_date": p})
        return True

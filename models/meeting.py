from odoo import api, fields, models, _


class Meeting(models.Model):
    """1.2 / 6: reuniones, minutas y revisiones administrativas. Toda reunión con acuerdos relevantes
    se convierte en registro de seguimiento (sus acuerdos son aq.portal.agreement)."""
    _name = "aq.portal.meeting"
    _description = "Portal: reunión / minuta"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date desc"

    name = fields.Char(string="Asunto", required=True, tracking=True)
    meeting_type = fields.Selection([
        ("cliente", "Reunión con cliente"), ("interna", "Reunión interna"),
        ("revision_administrativa", "Revisión administrativa (convocada por Coordinación)"),
        ("direccion", "Reunión con Dirección"), ("kickoff", "Reunión de inicio de proyecto"),
        ("cierre", "Reunión de cierre / aceptación"), ("otra", "Otra"),
    ], default="interna", required=True, string="Tipo", tracking=True)
    date = fields.Datetime(string="Fecha y hora", required=True, default=fields.Datetime.now, tracking=True)
    project_id = fields.Many2one("aq.portal.project", string="Proyecto")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    prospect_id = fields.Many2one("aq.portal.prospect", string="Prospecto")
    convened_by_id = fields.Many2one("aq.portal.member", string="Convocó")
    member_ids = fields.Many2many("aq.portal.member", string="Integrantes convocados")
    external_attendees = fields.Char(string="Asistentes externos")
    location = fields.Char(string="Lugar / enlace de videollamada")
    agenda = fields.Text(string="Orden del día / asuntos a revisar")
    minutes = fields.Html(string="Minuta")
    agreement_ids = fields.One2many("aq.portal.agreement", "meeting_id", string="Acuerdos y pendientes derivados")
    agreement_count = fields.Integer(compute="_compute_counts", string="Acuerdos")
    open_agreement_count = fields.Integer(compute="_compute_counts", string="Acuerdos abiertos")
    state = fields.Selection([("programada", "Programada"), ("realizada", "Realizada"), ("minuta_enviada", "Minuta enviada"),
                              ("cancelada", "Cancelada")], default="programada", tracking=True)
    minutes_sent_date = fields.Date(string="Minuta enviada el", readonly=True)
    next_meeting_date = fields.Date(string="Próxima revisión")
    notified = fields.Boolean(string="Convocatoria enviada", readonly=True)

    @api.depends("agreement_ids.state")
    def _compute_counts(self):
        for m in self:
            m.agreement_count = len(m.agreement_ids)
            m.open_agreement_count = len(m.agreement_ids.filtered(lambda a: a.state not in ("cerrado", "cancelado")))

    def _mail(self, subject, body, members):
        Brand = self.env["aq.portal.branding"]
        html = Brand.wrap(subject, body, _("Ver en el portal"), Brand.portal_url("meetings", self.id))
        for mem in members.filtered("email"):
            self.env["mail.mail"].sudo().create({"subject": subject, "email_to": mem.email, "body_html": html}).send()

    def action_convene(self):
        """Facultad 6: convocar revisiones administrativas (envía convocatoria a los integrantes)."""
        for m in self:
            body = _("<p>Se le convoca a <b>%s</b> (%s).</p><p>Fecha: %s<br/>Lugar: %s</p><p>Asuntos:</p><pre>%s</pre>") % (
                m.name, dict(self._fields["meeting_type"].selection)[m.meeting_type], m.date, m.location or "-", m.agenda or "-")
            m._mail(_("Convocatoria: %s") % m.name, body, m.member_ids)
            m.write({"notified": True})
            m.message_post(body=_("Convocatoria enviada a %s.") % ", ".join(m.member_ids.mapped("name")))
        return True

    def action_mark_done(self):
        self.write({"state": "realizada"})
        return True

    def action_send_minutes(self):
        for m in self:
            rows = "".join("<li><b>%s</b> — %s, fecha %s (%s)</li>" % (a.name, a.executor_id.name or "-", a.due_date or "-",
                                                                       dict(a._fields["state"].selection)[a.state]) for a in m.agreement_ids)
            body = "<h3>%s</h3><p>%s</p>%s<h4>%s</h4><ul>%s</ul>" % (m.name, m.date, m.minutes or "", _("Acuerdos"), rows)
            m._mail(_("Minuta: %s") % m.name, body, m.member_ids)
            m.write({"state": "minuta_enviada", "minutes_sent_date": fields.Date.today()})
        return True


class AgreementMeeting(models.Model):
    _inherit = "aq.portal.agreement"

    meeting_id = fields.Many2one("aq.portal.meeting", string="Reunión / minuta", ondelete="set null")

    @api.onchange("meeting_id")
    def _onchange_meeting(self):
        if self.meeting_id:
            self.meeting_date = self.meeting_id.date.date() if self.meeting_id.date else self.meeting_date
            self.project_id = self.project_id or self.meeting_id.project_id
            self.source = "reunion"
            self.formalized = True

    @api.model_create_multi
    def create(self, vals_list):
        Meeting = self.env["aq.portal.meeting"]
        for vals in vals_list:
            if vals.get("meeting_id"):
                m = Meeting.browse(vals["meeting_id"])
                vals.setdefault("meeting_date", m.date.date() if m.date else False)
                vals.setdefault("project_id", m.project_id.id)
                vals.setdefault("source", "reunion")
                vals.setdefault("formalized", True)
                vals.setdefault("meeting_ref", m.name)
        return super().create(vals_list)

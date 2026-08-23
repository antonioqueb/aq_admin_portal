# -*- coding: utf-8 -*-
"""AlphaOps · reuniones, acuerdos (con confirmación humana) y decisiones versionadas."""
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OpsMeeting(models.Model):
    _name = "aq.ops.meeting"
    _description = "AlphaOps: reunión"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date desc"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    meeting_type = fields.Selection([("kickoff", "Kickoff"), ("seguimiento", "Seguimiento"), ("validacion", "Validación"), ("tecnica", "Técnica"),
                                     ("direccion", "Dirección"), ("cliente", "Con cliente"), ("retro", "Retrospectiva"), ("otra", "Otra")], default="seguimiento")
    location = fields.Char(string="Lugar / enlace de Meet")
    member_ids = fields.Many2many("aq.portal.member", string="Participantes internos")
    client_partner_ids = fields.Many2many("res.partner", string="Participantes del cliente")
    agenda = fields.Text(string="Agenda")
    minutes = fields.Html(string="Minuta")
    transcript = fields.Text(string="Transcripción (evidencia histórica)")
    agreement_ids = fields.One2many("aq.ops.meeting.agreement", "meeting_id", string="Acuerdos y compromisos")
    decision_ids = fields.One2many("aq.ops.decision", "meeting_id", string="Decisiones")
    question_ids = fields.One2many("aq.ops.meeting.question", "meeting_id", string="Preguntas abiertas")
    raid_ids = fields.One2many("aq.ops.raid", "meeting_id", string="Riesgos identificados")
    item_ids = fields.One2many("aq.ops.item", "meeting_id", string="Tareas generadas")
    change_ids = fields.One2many("aq.ops.change", "meeting_id", string="Solicitudes de cambio")
    document_ids = fields.Many2many("aq.ops.document", string="Documentos vinculados")
    next_meeting_date = fields.Datetime(string="Próxima reunión")
    state = fields.Selection([("programada", "Programada"), ("realizada", "Realizada"), ("minuta_enviada", "Minuta enviada")], default="programada", tracking=True)
    client_visible = fields.Boolean(default=True)
    ai_summary = fields.Text(string="Resumen del copiloto (borrador)", readonly=True)
    ai_proposals_json = fields.Text(string="Propuestas del copiloto (JSON)", readonly=True)

    def action_send_minutes(self):
        Brand = self.env["aq.portal.branding"]
        for m in self:
            rows = "".join("<li><b>%s</b> — %s, %s</li>" % (a.name, a.owner_id.name or a.owner_partner_id.name or "-", a.due_date or "-") for a in m.agreement_ids)
            html = Brand.wrap(_("Minuta: %s") % m.name, "<p>%s</p>%s<h4>%s</h4><ul>%s</ul>" % (m.date, m.minutes or "", _("Acuerdos"), rows), _("Ver en Operaciones"), Brand.portal_url() + "/ops/r/meetings/%d" % m.id)
            for mem in m.member_ids.filtered("email"):
                self.env["mail.mail"].sudo().create({"subject": _("Minuta: %s") % m.name, "email_to": mem.email, "body_html": html}).send()
            for c in m.client_partner_ids.filtered("email"):
                self.env["mail.mail"].sudo().create({"subject": _("Minuta: %s") % m.name, "email_to": c.email, "body_html": html}).send()
            m.write({"state": "minuta_enviada"})
        return True

    def action_mark_done(self):
        self.write({"state": "realizada"})
        return True


class OpsMeetingAgreement(models.Model):
    """Acuerdo/compromiso de minuta. Se convierte en tarea SOLO tras confirmación humana (regla 7)."""
    _name = "aq.ops.meeting.agreement"
    _description = "AlphaOps: acuerdo de reunión"
    meeting_id = fields.Many2one("aq.ops.meeting", required=True, ondelete="cascade")
    name = fields.Char(required=True, string="Acuerdo / compromiso")
    owner_id = fields.Many2one("aq.portal.member", string="Responsable interno")
    owner_partner_id = fields.Many2one("res.partner", string="Responsable (cliente)")
    due_date = fields.Date(string="Fecha compromiso")
    kind = fields.Selection([("compromiso", "Compromiso"), ("acuerdo", "Acuerdo"), ("tarea", "Tarea"), ("cambio", "Posible cambio de alcance")], default="compromiso")
    proposed_by_ai = fields.Boolean(string="Propuesto por el copiloto")
    confirmed = fields.Boolean(string="Confirmado por una persona")
    item_id = fields.Many2one("aq.ops.item", string="Tarea creada", readonly=True)
    change_id = fields.Many2one("aq.ops.change", readonly=True)
    is_contractual = fields.Boolean(string="¿Implica compromiso contractual?", help="Una solicitud mencionada en reunión no es compromiso contractual hasta pasar por control de cambios.")

    def action_confirm(self):
        for a in self:
            a.confirmed = True
            if a.kind in ("tarea", "compromiso") and not a.item_id:
                a.item_id = self.env["aq.ops.item"].create({"name": a.name, "item_type": "tarea", "project_id": a.meeting_id.project_id.id, "meeting_id": a.meeting_id.id,
                                                            "assignee_id": a.owner_id.id, "date_due": a.due_date, "state": "por_hacer", "waiting_client": bool(a.owner_partner_id and not a.owner_id)})
            if a.kind == "cambio" and not a.change_id:
                a.change_id = self.env["aq.ops.change"].create({"name": a.name, "project_id": a.meeting_id.project_id.id, "meeting_id": a.meeting_id.id, "requested_by": a.owner_partner_id.name or "Reunión"})
        return True


class OpsMeetingQuestion(models.Model):
    _name = "aq.ops.meeting.question"
    _description = "AlphaOps: pregunta abierta"
    meeting_id = fields.Many2one("aq.ops.meeting", required=True, ondelete="cascade")
    name = fields.Char(required=True, string="Pregunta")
    owner_partner_id = fields.Many2one("res.partner", string="Debe responder (cliente)")
    owner_id = fields.Many2one("aq.portal.member", string="Debe responder (interno)")
    answer = fields.Text(string="Respuesta")
    answered = fields.Boolean()
    client_visible = fields.Boolean(default=True)


class OpsDecision(models.Model):
    """5.7 Una decisión tiene vida propia; aprobada no se edita: se versiona."""
    _name = "aq.ops.decision"
    _description = "AlphaOps: decisión"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "date desc"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    meeting_id = fields.Many2one("aq.ops.meeting", string="Reunión")
    context_text = fields.Text(string="Contexto")
    decision_text = fields.Text(string="Decisión", required=True)
    decided_by_id = fields.Many2one("aq.portal.member", string="Tomada por (interno)")
    decided_by_partner_id = fields.Many2one("res.partner", string="Tomada por (cliente)")
    date = fields.Date(default=fields.Date.today)
    version = fields.Integer(default=1, readonly=True)
    replaces_id = fields.Many2one("aq.ops.decision", string="Reemplaza a", readonly=True)
    superseded_by_id = fields.Many2one("aq.ops.decision", string="Reemplazada por", readonly=True)
    affected_item_ids = fields.Many2many("aq.ops.item", string="Elementos afectados")
    state = fields.Selection([("propuesta", "Propuesta"), ("aprobada", "Aprobada (inmutable)"), ("reemplazada", "Reemplazada"), ("descartada", "Descartada")], default="propuesta", tracking=True)
    approved_date = fields.Date(readonly=True)
    client_visible = fields.Boolean(default=True)
    approver_user_id = fields.Many2one("aq.portal.user", readonly=True, string="Aprobó en el portal")

    IMMUTABLE = ("name", "context_text", "decision_text", "decided_by_id", "decided_by_partner_id", "date", "affected_item_ids", "meeting_id")

    def write(self, vals):
        for d in self:
            if d.state == "aprobada" and any(k in vals for k in self.IMMUTABLE) and not self.env.context.get("aq_version"):
                raise UserError(_("La decisión '%s' está aprobada y no puede editarse silenciosamente. Use 'Nueva versión'.") % d.name)
        return super().write(vals)

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"state": "aprobada", "approved_date": fields.Date.today(), "approver_user_id": pu})
        return True

    def action_new_version(self):
        for d in self:
            new = d.copy({"version": d.version + 1, "replaces_id": d.id, "state": "propuesta", "approved_date": False, "superseded_by_id": False, "approver_user_id": False})
            d.with_context(aq_version=True).write({"state": "reemplazada", "superseded_by_id": new.id})
        return True

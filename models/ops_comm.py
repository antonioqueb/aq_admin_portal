# -*- coding: utf-8 -*-
"""AlphaOps · notificaciones, automatizaciones gobernadas, eventos entre dominios (outbox), integraciones."""
import json
import logging
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

NOTIF_CATEGORIES = [("accion_requerida", "Acción requerida"), ("aprobacion", "Aprobación"), ("bloqueo", "Bloqueo"), ("riesgo", "Riesgo"), ("incidente", "Incidente"),
                    ("mencion", "Mención"), ("cambio_fecha", "Cambio de fecha"), ("dependencia_liberada", "Dependencia liberada"), ("cliente_respondio", "Cliente respondió"),
                    ("entregable_aceptado", "Entregable aceptado"), ("recordatorio", "Recordatorio"), ("resumen", "Resumen informativo")]
PRIORITY_BY_CAT = {"incidente": "4", "bloqueo": "3", "accion_requerida": "3", "aprobacion": "3", "riesgo": "3", "cambio_fecha": "2", "mencion": "2",
                   "dependencia_liberada": "2", "cliente_respondio": "2", "entregable_aceptado": "1", "recordatorio": "1", "resumen": "1"}
EVENT_TYPES = [
    # Operaciones → Administración
    ("project_ready_to_start", "Proyecto listo para iniciar"), ("scope_change_requested", "Cambio de alcance solicitado"), ("estimate_approved", "Estimación operativa aprobada"),
    ("milestone_validated", "Hito validado por el cliente"), ("hours_approved_for_billing", "Horas aprobadas para facturación"), ("deliverable_accepted", "Entregable aceptado"),
    ("project_ready_to_close", "Proyecto listo para cierre"), ("admin_work_referred", "Trabajo administrativo remitido"),
    # Administración → Operaciones
    ("contract_active", "Contrato activo"), ("contract_suspended", "Contrato suspendido"), ("scope_authorized", "Alcance comercial autorizado"),
    ("hours_authorized", "Bolsa de horas autorizada"), ("commercial_condition", "Condición comercial vigente"), ("payment_confirmed", "Pago confirmado"),
    ("payment_restriction", "Restricción por falta de pago"), ("contract_expiring", "Contrato próximo a vencer"),
]


class OpsNotification(models.Model):
    """5.14 Centro de notificaciones con prioridad y acción directa."""
    _name = "aq.ops.notification"
    _description = "AlphaOps: notificación"
    _order = "priority desc, create_date desc"

    user_id = fields.Many2one("aq.portal.user", required=True, index=True, ondelete="cascade")
    category = fields.Selection(NOTIF_CATEGORIES, required=True)
    priority = fields.Selection([("1", "Baja"), ("2", "Normal"), ("3", "Alta"), ("4", "Crítica")], default="2")
    title = fields.Char(required=True)
    body = fields.Text()
    resource = fields.Char()
    res_id = fields.Integer()
    read = fields.Boolean(index=True)
    read_at = fields.Datetime()
    action_required = fields.Boolean()
    done = fields.Boolean(string="Atendida")
    emailed = fields.Boolean()
    app = fields.Selection([("ops", "Operaciones"), ("admin", "Administración")], default="ops")

    @api.model
    def push(self, user, category, title, resource=None, res_id=None, body=None, app="ops"):
        if not user:
            return self.browse()
        if self.search_count([("user_id", "=", user.id), ("category", "=", category), ("resource", "=", resource), ("res_id", "=", res_id or 0), ("read", "=", False), ("title", "=", title)]):
            return self.browse()
        return self.create({"user_id": user.id, "category": category, "priority": PRIORITY_BY_CAT.get(category, "2"), "title": title, "body": body,
                            "resource": resource, "res_id": res_id or 0, "action_required": category in ("accion_requerida", "aprobacion", "bloqueo", "incidente"), "app": app})

    @api.model
    def notify_member(self, member, category, title, resource=None, res_id=None, body=None):
        if not member:
            return
        for u in self.env["aq.portal.user"].search([("member_id", "=", member.id), ("active", "=", True), ("has_ops_access", "=", True)]):
            self.push(u, category, title, resource, res_id, body)

    @api.model
    def notify_partner(self, partner, category, title, resource=None, res_id=None, body=None):
        if not partner:
            return
        for u in self.env["aq.portal.user"].search([("active", "=", True), ("has_ops_access", "=", True), "|", ("organization_id", "=", partner.id), ("organization_id", "=", partner.commercial_partner_id.id)]):
            if u.ops_role in ("client_sponsor", "client_po", "client_validator"):
                self.push(u, category, title, resource, res_id, body)

    @api.model
    def notify_role(self, project, roles, category, title, resource=None, res_id=None, body=None):
        """Notifica a usuarios con esos perfiles; si hay proyecto, prioriza su PM/líderes."""
        users = self.env["aq.portal.user"].search([("active", "=", True), ("has_ops_access", "=", True), ("ops_role", "in", list(roles) + ["ops_director", "platform_owner"])])
        if project:
            members = project.pm_id | project.functional_lead_id | project.tech_lead_id
            users = users.filtered(lambda u: u.ops_role in ("ops_director", "platform_owner") or u.member_id in members or (u.member_id in project.team_member_ids and u.ops_role in roles))
        for u in users:
            self.push(u, category, title, resource, res_id, body)

    @api.model
    def send_digest(self, frequency="daily"):
        Brand = self.env["aq.portal.branding"]
        since = fields.Datetime.now() - timedelta(days=1 if frequency == "daily" else 7)
        for u in self.env["aq.portal.user"].search([("active", "=", True), ("has_ops_access", "=", True), ("notify_alerts", "=", True)]):
            notes = self.search([("user_id", "=", u.id), ("read", "=", False), ("create_date", ">=", since)], limit=60)
            if not notes:
                continue
            rows = "".join("<li><b>[%s]</b> %s</li>" % (dict(NOTIF_CATEGORIES)[n.category], n.title) for n in notes)
            ai = self.env["aq.ops.ai"].digest_summary(["[%s] %s" % (n.category, n.title) for n in notes])
            rows = (("<p style='border-left:3px solid #c89eff;padding-left:10px'><b>Copiloto:</b> %s</p>" % ai.replace("\n", "<br/>")) if ai else "") + rows
            html = Brand.wrap(_("Resumen de Operaciones"), "<ul>%s</ul>" % rows, _("Abrir Operaciones"), Brand.portal_url() + "/ops/notifications", subtitle=_("%d notificaciones pendientes") % len(notes))
            self.env["mail.mail"].sudo().create({"subject": _("AlphaOps · %d pendientes") % len(notes), "email_to": u.email, "body_html": html}).send()
            notes.write({"emailed": True})


class OpsAutomation(models.Model):
    """Disparador → condición → acción, con propietario técnico e historial."""
    _name = "aq.ops.automation"
    _description = "AlphaOps: automatización"
    _order = "sequence"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Clave interna", help="Para automatizaciones integradas (builtin).")
    trigger = fields.Selection([("schedule_daily", "Programada · diaria"), ("schedule_weekly", "Programada · semanal"), ("on_create", "Al crear"), ("on_write", "Al modificar"), ("event", "Al recibir evento")], default="schedule_daily")
    model_name = fields.Char(string="Modelo", default="aq.ops.item")
    condition_domain = fields.Char(string="Condición (dominio)", default="[]")
    action_type = fields.Selection([("builtin", "Integrada"), ("notify", "Notificar a perfil"), ("set_field", "Cambiar campo"), ("escalate", "Escalar a Dirección de Operaciones")], default="builtin")
    action_params = fields.Text(string="Parámetros (JSON)", default="{}")
    owner_id = fields.Many2one("aq.portal.member", string="Propietario técnico")
    active = fields.Boolean(default=True)
    critical = fields.Boolean(string="Crítica (no depende de una sola persona)")
    last_run = fields.Datetime(readonly=True)
    run_count = fields.Integer(readonly=True)
    log_ids = fields.One2many("aq.ops.automation.log", "automation_id", string="Historial")
    description = fields.Text()

    def _log(self, result, count=0, detail=None):
        self.env["aq.ops.automation.log"].create({"automation_id": self.id, "result": result, "affected": count, "detail": detail})
        self.write({"last_run": fields.Datetime.now(), "run_count": self.run_count + 1})

    def run(self):
        Engine = self.env["aq.ops.engine"]
        for a in self:
            try:
                if a.action_type == "builtin" and a.code:
                    n = getattr(Engine, "auto_" + a.code)()
                    a._log("ok", n)
                else:
                    n = Engine.run_generic(a)
                    a._log("ok", n)
            except Exception as e:  # noqa
                _logger.exception("Automatización %s", a.name)
                a._log("error", 0, str(e))
        return True


class OpsAutomationLog(models.Model):
    _name = "aq.ops.automation.log"
    _description = "AlphaOps: ejecución de automatización"
    _order = "create_date desc"
    automation_id = fields.Many2one("aq.ops.automation", required=True, ondelete="cascade")
    result = fields.Selection([("ok", "OK"), ("error", "Error")])
    affected = fields.Integer(string="Registros afectados")
    detail = fields.Text()


class OpsEvent(models.Model):
    """Intercambio de eventos autorizados entre dominios (patrón outbox). Solo resultados; nunca contenido indiscriminado."""
    _name = "aq.ops.event"
    _description = "AlphaOps: evento entre Administración y Operaciones"
    _order = "create_date desc"

    direction = fields.Selection([("ops", "Operaciones → Administración"), ("admin", "Administración → Operaciones")], required=True)
    event_type = fields.Selection(EVENT_TYPES, required=True)
    source_model = fields.Char()
    source_id = fields.Integer()
    payload = fields.Text(string="Proyección (JSON)")
    state = fields.Selection([("pendiente", "Pendiente"), ("procesado", "Procesado"), ("error", "Error")], default="pendiente", index=True)
    processed_at = fields.Datetime()
    error = fields.Text()
    ops_project_id = fields.Many2one("aq.ops.project", string="Proyecto (Operaciones)")
    admin_project_id = fields.Many2one("aq.portal.project", string="Proyecto (Administración)")
    summary = fields.Char(compute="_compute_summary", store=True)

    @api.depends("event_type", "payload")
    def _compute_summary(self):
        for e in self:
            try:
                p = json.loads(e.payload or "{}")
            except Exception:
                p = {}
            e.summary = "%s · %s" % (dict(EVENT_TYPES).get(e.event_type, e.event_type), p.get("project") or p.get("organization") or "")

    @api.model
    def emit(self, direction, event_type, record, payload):
        ops_project = record if record._name == "aq.ops.project" else getattr(record, "project_id", False) if hasattr(record, "project_id") and record._fields.get("project_id") and record.project_id._name == "aq.ops.project" else False
        admin_project = record if record._name == "aq.portal.project" else False
        ev = self.sudo().create({"direction": direction, "event_type": event_type, "source_model": record._name, "source_id": record.id,
                                 "payload": json.dumps(payload, default=str, ensure_ascii=False),
                                 "ops_project_id": ops_project.id if ops_project else False, "admin_project_id": admin_project.id if admin_project else False})
        ev.process()
        return ev

    def process(self):
        for ev in self:
            try:
                p = json.loads(ev.payload or "{}")
                if ev.direction == "admin":
                    ev._project_to_ops(p)
                else:
                    ev._project_to_admin(p)
                ev.write({"state": "procesado", "processed_at": fields.Datetime.now()})
            except Exception as e:  # noqa
                ev.write({"state": "error", "error": str(e)})
                _logger.exception("Evento %s", ev.event_type)

    def _project_to_ops(self, p):
        """Proyecciones que Operaciones puede conocer (sin factura, banco, margen ni negociación)."""
        proj = self.ops_project_id or (self.admin_project_id and self.env["aq.ops.project"].search([("admin_project_id", "=", self.admin_project_id.id)], limit=1))
        if not proj:
            return
        t = self.event_type
        vals = {}
        if t == "contract_active": vals["contract_state"] = "activo"
        if t == "contract_suspended": vals["contract_state"] = "suspendido"
        if t == "contract_expiring": vals["contract_state"] = "por_vencer"
        if t == "hours_authorized": vals["hours_authorized"] = float(p.get("hours", 0))
        if t == "payment_restriction": vals["commercial_restriction"] = True
        if t == "payment_confirmed": vals["commercial_restriction"] = False
        if t == "scope_authorized":
            ch = self.env["aq.ops.change"].browse(int(p.get("change_id", 0))).exists()
            if ch:
                ch.write({"state": "autorizado", "commercial_ref": p.get("ref"), "authorized_hours": float(p.get("hours", ch.estimate_hours))})
                self.env["aq.ops.notification"].notify_role(proj, ["pm"], "aprobacion", _("Cambio autorizado comercialmente: %s") % ch.name, "changes", ch.id)
        if vals:
            proj.with_context(aq_skip_activity=True).write(vals)
        if t in ("payment_restriction", "contract_suspended", "contract_expiring"):
            self.env["aq.ops.notification"].notify_role(proj, ["pm"], "accion_requerida", _("%s: %s") % (dict(EVENT_TYPES)[t], proj.name), "projects", proj.id)

    def _project_to_admin(self, p):
        """Proyecciones hacia Administración: solo resultados (hito aceptado, horas aprobadas…)."""
        Admin = self.env["aq.portal.project"]
        proj = self.admin_project_id or (self.ops_project_id and self.ops_project_id.admin_project_id and Admin.browse(self.ops_project_id.admin_project_id).exists())
        t = self.event_type
        if t == "scope_change_requested" and proj:
            self.env["aq.portal.change.request"].create({"name": p.get("change"), "project_id": proj.id, "requested_by": _("Operaciones"), "description": p.get("impact"),
                                                         "classification": "cambio_requerimiento", "estimate_hours": p.get("hours", 0), "ops_change_id": self.source_id,
                                                         "notes": _("Evento AlphaOps #%d · change_id=%s") % (self.id, self.source_id)})
        if t in ("milestone_validated", "deliverable_accepted") and proj:
            proj.message_post(body=_("AlphaOps: %s — %s (%s)%s") % (dict(EVENT_TYPES)[t], p.get("milestone") or p.get("deliverable") or p.get("change"), p.get("date", ""),
                                                                   _(" · habilita facturación") if p.get("enables_billing") else ""))
            if p.get("enables_billing") or t == "deliverable_accepted":
                self.env["aq.portal.alert"]._upsert("ops_bill_%d" % self.id, {"name": _("Facturable: %s · %s") % (proj.name, p.get("milestone") or p.get("deliverable") or p.get("change")),
                                                                              "alert_type": "factura_por_emitir", "severity": "2", "resource": "invoices", "res_model": proj._name, "res_id": proj.id})
        if t == "hours_approved_for_billing" and proj:
            bucket = proj.hour_bucket_ids[:1]
            if bucket:
                bucket.write({"hours_executed": bucket.hours_executed + float(p.get("hours", 0))})
            proj.message_post(body=_("AlphaOps: %.1f h aprobadas para facturación (semana %s)") % (float(p.get("hours", 0)), p.get("week", "")))
        if t == "project_ready_to_start" and proj:
            proj.with_context(aq_skip_activity=True).write({"stage": "ejecucion"})
        if t == "project_ready_to_close" and proj:
            proj.message_post(body=_("AlphaOps: proyecto listo para cierre (%s pendientes conocidos). Evento de facturación final.") % p.get("pending_known", 0))
            self.env["aq.portal.alert"]._upsert("ops_close_%d" % self.id, {"name": _("Cierre: facturación final de %s") % proj.name, "alert_type": "factura_por_emitir", "severity": "2",
                                                                           "resource": "projects", "res_model": proj._name, "res_id": proj.id})
        if t == "admin_work_referred":
            self.env["aq.portal.agreement"].create({"name": _("Solicitud remitida desde Operaciones: %s") % p.get("request"), "source": "portal", "requested_by": p.get("organization"),
                                                    "project_id": proj.id if proj else False})


class OpsIntegration(models.Model):
    """Integraciones autorizadas (compartidas): DeepSeek, Drive, Teams/Slack/WhatsApp (preparadas)."""
    _name = "aq.ops.integration"
    _description = "AlphaOps: integración"

    name = fields.Char(required=True)
    kind = fields.Selection([("deepseek", "DeepSeek (copiloto IA)"), ("drive", "Google Drive"), ("teams", "Microsoft Teams"), ("slack", "Slack"), ("whatsapp", "WhatsApp"), ("webhook", "Webhook")], required=True)
    enabled = fields.Boolean(default=False)
    base_url = fields.Char(string="URL base", default="https://api.deepseek.com")
    api_key = fields.Char(string="API key", groups="base.group_system")
    model = fields.Char(string="Modelo", default="deepseek-chat")
    webhook_url = fields.Char(string="Webhook (Teams/Slack)")
    owner_id = fields.Many2one("aq.portal.member", string="Propietario")
    notes = fields.Text()
    last_used = fields.Datetime(readonly=True)


class AdminChangeBridge(models.Model):
    """Administración → Operaciones: al autorizar comercialmente un cambio, se proyecta como 'scope_authorized'."""
    _inherit = "aq.portal.change.request"

    ops_change_id = fields.Integer(string="Cambio en Operaciones (id)", readonly=True)

    def _emit_scope_authorized(self):
        import re as _re
        for c in self:
            cid = c.ops_change_id or (int(_re.search(r"change_id=(\d+)", c.notes or "").group(1)) if _re.search(r"change_id=(\d+)", c.notes or "") else 0)
            if cid:
                self.env["aq.ops.event"].emit("admin", "scope_authorized", c.project_id, {"change_id": cid, "ref": c.quotation_ref or c.name, "hours": c.estimate_hours, "project": c.project_id.name})

    def action_authorize_client(self):
        res = super().action_authorize_client()
        self._emit_scope_authorized()
        return res

    def action_authorize_direction(self):
        res = super().action_authorize_direction()
        self._emit_scope_authorized()
        return res


class OpsEventLink(models.Model):
    _inherit = "aq.ops.event"

    def _project_to_ops(self, p):
        if self.ops_project_id and self.admin_project_id and not self.ops_project_id.admin_project_id:
            self.ops_project_id.with_context(aq_skip_activity=True).write({"admin_project_id": self.admin_project_id.id, "admin_project_ref": self.admin_project_id.name})
        return super()._project_to_ops(p)


class OpsNotificationChannels(models.Model):
    """Canales adicionales: webhooks (Teams / Slack / WhatsApp vía proveedor) y calendario (ICS)."""
    _inherit = "aq.ops.notification"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        try:
            recs._deliver_webhooks()
        except Exception:  # noqa
            _logger.exception("Webhook de notificaciones")
        return recs

    def _deliver_webhooks(self):
        import requests as _rq
        integ = self.env["aq.ops.integration"].sudo().search([("kind", "in", ("teams", "slack", "whatsapp", "webhook")), ("enabled", "=", True), ("webhook_url", "!=", False)])
        if not integ:
            return
        base = self.env["aq.portal.user"]._portal_base_url()
        for n in self.filtered(lambda x: x.priority in ("3", "4")):
            text = "[%s] %s — %s%s" % (dict(NOTIF_CATEGORIES)[n.category], n.title, n.user_id.name, (" · %s/ops/r/%s/%d" % (base, n.resource, n.res_id)) if n.resource and n.res_id else "")
            for i in integ:
                payload = {"text": text} if i.kind in ("teams", "slack") else {"message": text, "to": n.user_id.phone if "phone" in n.user_id._fields else ""} if i.kind == "whatsapp" else {"title": n.title, "category": n.category, "priority": n.priority, "user": n.user_id.email, "resource": n.resource, "res_id": n.res_id}
                try:
                    _rq.post(i.webhook_url, json=payload, timeout=8)
                    i.write({"last_used": fields.Datetime.now()})
                except Exception as e:  # noqa
                    _logger.warning("Webhook %s: %s", i.name, e)

    @api.model
    def ics_for_user(self, user, project_domain):
        """Calendario ICS: compromisos, hitos, reuniones, validaciones y liberaciones del usuario."""
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AlphaQueb//AlphaOps//ES", "X-WR-CALNAME:AlphaOps · %s" % user.name]
        def ev(uid, d, summary, desc=""):
            if not d:
                return
            ds = (d if isinstance(d, str) else str(d))[:10].replace("-", "")
            lines.extend(["BEGIN:VEVENT", "UID:%s@alphaops" % uid, "DTSTART;VALUE=DATE:%s" % ds, "SUMMARY:%s" % summary.replace("\n", " "), "DESCRIPTION:%s" % (desc or "").replace("\n", " ")[:200], "END:VEVENT"])
        m = user.member_id
        Item = self.env["aq.ops.item"]
        for i in Item.search([("state", "not in", ("cerrado", "cancelado")), ("date_due", "!=", False)] + project_domain + ([("assignee_id", "=", m.id)] if m and user.ops_role not in ("ops_director", "platform_owner") else [])):
            ev("item-%d" % i.id, i.date_due, "%s · %s" % (i.name, i.project_id.name), i.acceptance_criteria or "")
        for ms in self.env["aq.ops.milestone"].search([("state", "not in", ("validado", "cancelado")), ("date_current", "!=", False)] + project_domain):
            ev("ms-%d" % ms.id, ms.date_current, "Hito: %s · %s" % (ms.name, ms.project_id.name))
        for mt in self.env["aq.ops.meeting"].search([("state", "=", "programada")] + project_domain):
            ev("mt-%d" % mt.id, mt.date, "Reunión: %s · %s" % (mt.name, mt.project_id.name), mt.agenda or "")
        for a in self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente"), ("due_date", "!=", False)] + project_domain):
            ev("acc-%d" % a.id, a.due_date, "Validación: %s" % (a.item_id.name or a.milestone_id.name))
        for r in self.env["aq.ops.release"].search([("state", "in", ("aprobada", "programada")), ("planned_at", "!=", False)] + project_domain):
            ev("rel-%d" % r.id, r.planned_at, "Liberación %s · %s" % (r.name, r.project_id.name))
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)


class ImmutableAudit(models.Model):
    """Bitácora de auditoría no modificable."""
    _inherit = "aq.portal.audit.log"

    def write(self, vals):
        raise UserError(_("La bitácora de auditoría es inmutable."))

    def unlink(self):
        if not self.env.context.get("aq_retention_purge"):
            raise UserError(_("La bitácora de auditoría no se elimina manualmente; solo por política de retención."))
        return super().unlink()

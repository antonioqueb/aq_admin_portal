import logging
from odoo import api, fields, models, _
from .branding import SEVERITY_STYLE

_logger = logging.getLogger(__name__)

ALERT_TYPES = [
    ("proyecto_sin_actividad", "Proyecto sin actividad"), ("proyecto_sin_accion", "Proyecto sin siguiente acción"),
    ("pendiente_vencido", "Pendiente vencido"), ("pendiente_repetido", "Pendiente que se repite"),
    ("acuerdo_sin_formalizar", "Acuerdo sin trasladar a registro formal"),
    ("factura_por_emitir", "Factura por emitir"), ("factura_atrasada", "Factura atrasada"), ("factura_detenida", "Factura detenida"),
    ("cobro_por_vencer", "Cobro por vencer"), ("cobro_vencido", "Cartera vencida"), ("compromiso_pago_incumplido", "Compromiso de pago incumplido"),
    ("pago_por_vencer", "Pago por vencer"), ("pago_vencido", "Pago vencido"), ("pago_sin_autorizar", "Pago sin autorizar"),
    ("bolsa_por_agotar", "Bolsa de horas por agotarse"), ("trabajo_sin_facturar", "Trabajo sin facturar"),
    ("trabajo_sin_autorizar", "Trabajo sin autorización comercial"), ("entregable_sin_aceptar", "Entregable sin aceptación"),
    ("prospecto_sin_seguimiento", "Prospecto sin seguimiento"), ("propuesta_vencida", "Propuesta vencida"),
    ("contrato_por_vencer", "Contrato por vencer"), ("contrato_vencido", "Contrato vencido"), ("documento_faltante", "Documento legal faltante"),
    ("renovacion_proxima", "Renovación próxima"), ("obligacion_proxima", "Obligación próxima"), ("obligacion_vencida", "Obligación vencida"),
    ("acceso_exempleado", "Acceso activo de exintegrante"), ("riesgo_revision", "Riesgo por revisar"),
    ("cambio_sin_autorizacion", "Cambio ejecutado sin autorización"), ("entregable_incorporacion", "Entregable de incorporación vencido"),
]


class Alert(models.Model):
    _name = "aq.portal.alert"
    _description = "Portal: alerta"
    _order = "severity desc, date asc, id desc"

    name = fields.Char(required=True)
    alert_type = fields.Selection(ALERT_TYPES, required=True)
    severity = fields.Selection([("1", "Info"), ("2", "Atención"), ("3", "Urgente"), ("4", "Crítico")], default="2")
    date = fields.Date(default=fields.Date.today)
    resource = fields.Char(string="Recurso del portal")
    res_model = fields.Char()
    res_id = fields.Integer()
    responsible_id = fields.Many2one("aq.portal.member")
    active = fields.Boolean(default=True)
    dismissed = fields.Boolean()
    dismissed_by_id = fields.Many2one("aq.portal.user")
    key = fields.Char(index=True, help="Clave única para no duplicar alertas")

    def _upsert(self, key, vals):
        existing = self.search([("key", "=", key)], limit=1)
        if existing:
            if not existing.dismissed:
                existing.write({"name": vals["name"], "severity": vals["severity"], "date": fields.Date.today()})
            return existing
        return self.create(dict(vals, key=key))

    @api.model
    def cron_daily(self):
        """Cron diario: rutinas, estados, alertas y resumen por correo."""
        env = self.env
        today = fields.Date.today()
        icp = env["ir.config_parameter"].sudo()
        stale_days = int(icp.get_param("aq_admin_portal.stale_days", "5"))
        warn_days = int(icp.get_param("aq_admin_portal.warn_days", "7"))

        env["aq.portal.routine.run"].ensure_runs(today)
        env["aq.portal.session"]._gc_sessions()

        # refrescar estados de cobranza y pagos
        env["aq.portal.receivable"].search([("state", "!=", "pagada")])._refresh_state()
        env["aq.portal.payable"].search([("payment_state", "=", "programado"), ("due_date", "<", today)]).with_context(
            aq_skip_activity=True).write({"payment_state": "vencido"})
        env["aq.portal.obligation"].search([("state", "=", "pendiente"), ("date", "<", today)]).with_context(
            aq_skip_activity=True).write({"state": "vencida"})
        env["aq.portal.legal.item"].search([("status", "=", "vigente"), ("date_end", "<", today)]).with_context(
            aq_skip_activity=True).write({"status": "vencido", "is_current": False})

        active_keys = set()

        def add(key, name, atype, sev, resource, model, res_id, responsible=None):
            active_keys.add(key)
            self._upsert(key, {"name": name, "alert_type": atype, "severity": sev, "resource": resource,
                               "res_model": model, "res_id": res_id, "responsible_id": responsible and responsible.id})

        # Proyectos
        for p in env["aq.portal.project"].search([("stage", "not in", ("cierre", "cancelado", "pausado"))]):
            if p.is_stale:
                add("proj_stale_%s" % p.id, _("%s: %d días sin actividad") % (p.name, p.days_without_activity),
                    "proyecto_sin_actividad", "3" if p.days_without_activity > stale_days * 2 else "2", "projects", p._name, p.id, p.responsible_id)
            if not p.has_next_action:
                add("proj_noaction_%s" % p.id, _("%s: sin siguiente acción, responsable o fecha compromiso") % p.name,
                    "proyecto_sin_accion", "2", "projects", p._name, p.id, p.responsible_id)
        # Pendientes
        for a in env["aq.portal.agreement"].search([("state", "not in", ("cerrado", "cancelado"))]):
            if a.is_overdue:
                sev = "4" if a.risk_type in ("factura", "contractual") or a.days_overdue > 10 else "3"
                add("agr_over_%s" % a.id, _("Pendiente vencido (%d d): %s") % (a.days_overdue, a.name), "pendiente_vencido", sev,
                    "agreements", a._name, a.id, a.executor_id)
            if a.is_repeated:
                add("agr_rep_%s" % a.id, _("Pendiente reprogramado %d veces: %s") % (a.repeat_count, a.name), "pendiente_repetido", "3",
                    "agreements", a._name, a.id, a.executor_id)
            if a.needs_formalization:
                add("agr_form_%s" % a.id, _("Acuerdo por %s sin trasladar a registro formal: %s") % (a.source, a.name),
                    "acuerdo_sin_formalizar", "2", "agreements", a._name, a.id, a.executor_id)
        # Facturación
        for f in env["aq.portal.invoice.schedule"].search([("state", "in", ("por_programar", "programada", "info_enviada", "detenida"))]):
            if f.state == "detenida":
                add("inv_hold_%s" % f.id, _("Factura detenida, requiere validación: %s") % f.name, "factura_detenida", "3", "invoices", f._name, f.id, f.issuer_id)
            elif f.is_late:
                add("inv_late_%s" % f.id, _("Factura atrasada (programada %s): %s") % (f.scheduled_date, f.name), "factura_atrasada", "3", "invoices", f._name, f.id, f.issuer_id)
            elif f.scheduled_date and (f.scheduled_date - today).days <= warn_days:
                add("inv_soon_%s" % f.id, _("Factura por emitir el %s: %s") % (f.scheduled_date, f.name), "factura_por_emitir", "2", "invoices", f._name, f.id, f.issuer_id)
        # Cobranza
        for r in env["aq.portal.receivable"].search([("state", "not in", ("pagada", "incobrable"))]):
            if r.promise_state == "incumplido":
                add("rec_promise_%s" % r.id, _("Compromiso de pago incumplido: %s (%s)") % (r.invoice_number, r.partner_id.name), "compromiso_pago_incumplido", "4", "receivables", r._name, r.id, r.responsible_id)
            elif r.days_overdue > 0:
                add("rec_over_%s" % r.id, _("Factura vencida %d días: %s (%s) saldo %.2f") % (r.days_overdue, r.invoice_number, r.partner_id.name, r.balance),
                    "cobro_vencido", "4" if r.days_overdue > 30 else "3", "receivables", r._name, r.id, r.responsible_id)
            elif 0 <= r.days_to_due <= warn_days:
                add("rec_soon_%s" % r.id, _("Factura por vencer en %d días: %s (%s)") % (r.days_to_due, r.invoice_number, r.partner_id.name), "cobro_por_vencer", "2", "receivables", r._name, r.id, r.responsible_id)
        # Pagos
        for p in env["aq.portal.payable"].search([("payment_state", "in", ("programado", "vencido"))]):
            if p.payment_state == "vencido":
                add("pay_over_%s" % p.id, _("Pago vencido: %s (%.2f)") % (p.name, p.amount), "pago_vencido", "3", "payables", p._name, p.id)
            elif p.days_to_due <= (p.alert_days or warn_days):
                add("pay_soon_%s" % p.id, _("Pago por vencer el %s: %s (%.2f)") % (p.due_date, p.name, p.amount), "pago_por_vencer", "2", "payables", p._name, p.id)
                if p.authorization_state == "pendiente":
                    add("pay_auth_%s" % p.id, _("Pago próximo sin autorización de Dirección: %s") % p.name, "pago_sin_autorizar", "3", "payables", p._name, p.id)
        # Horas
        for b in env["aq.portal.hour.bucket"].search([("state", "=", "activa")]):
            if b.near_depletion or b.over_budget:
                add("hrs_dep_%s" % b.id, _("%s · %s: %.0f%% consumido") % (b.project_id.name, b.name, b.pct_consumed), "bolsa_por_agotar", "3" if b.over_budget else "2", "hours", b._name, b.id, b.project_id.responsible_id)
            if b.hours_unbilled > 0:
                add("hrs_unb_%s" % b.id, _("%s · %s: %.1f h ejecutadas sin facturar") % (b.project_id.name, b.name, b.hours_unbilled), "trabajo_sin_facturar", "2", "hours", b._name, b.id, b.project_id.responsible_id)
            if b.has_unauthorized_work:
                add("hrs_unauth_%s" % b.id, _("%s · %s: trabajo fuera de alcance sin autorización comercial") % (b.project_id.name, b.name), "trabajo_sin_autorizar", "3", "hours", b._name, b.id, b.project_id.responsible_id)
        for d in env["aq.portal.deliverable"].search([("state", "=", "entregado")]):
            if d.delivered_date and (today - d.delivered_date).days > warn_days:
                add("del_acc_%s" % d.id, _("Entregable sin aceptación del cliente: %s (%s)") % (d.name, d.project_id.name), "entregable_sin_aceptar", "2", "deliverables", d._name, d.id, d.responsible_id)
        # Cambios
        for c in env["aq.portal.change.request"].search([("executed_without_authorization", "=", True)]):
            add("chg_unauth_%s" % c.id, _("Cambio ejecutado sin autorización: %s (%s)") % (c.name, c.project_id.name), "cambio_sin_autorizacion", "3", "changes", c._name, c.id)
        # Prospectos
        for pr in env["aq.portal.prospect"].search([("stage", "not in", ("ganado", "perdido", "pausado"))]):
            if pr.is_abandoned:
                add("pros_ab_%s" % pr.id, _("Prospecto sin seguimiento (%d d): %s") % (pr.days_without_followup, pr.name), "prospecto_sin_seguimiento", "2", "prospects", pr._name, pr.id, pr.sales_responsible_id)
            if pr.proposal_expired:
                add("pros_exp_%s" % pr.id, _("Propuesta vencida: %s") % pr.name, "propuesta_vencida", "2", "prospects", pr._name, pr.id, pr.sales_responsible_id)
        # Legal
        for l in env["aq.portal.legal.item"].search([]):
            if l.is_missing and l.priority == "2":
                add("leg_miss_%s" % l.id, _("Documento legal faltante prioritario: %s") % l.name, "documento_faltante", "3", "legal", l._name, l.id, l.responsible_id)
            elif l.date_end and l.is_expired and l.status != "terminado":
                add("leg_exp_%s" % l.id, _("Contrato vencido: %s") % l.name, "contrato_vencido", "3", "legal", l._name, l.id, l.responsible_id)
            elif l.date_end and 0 <= l.days_to_expiry <= 30:
                add("leg_soon_%s" % l.id, _("Contrato por vencer en %d días: %s") % (l.days_to_expiry, l.name), "contrato_por_vencer", "2", "legal", l._name, l.id, l.responsible_id)
        # Proveedores y obligaciones
        for v in env["aq.portal.vendor"].search([("state", "=", "activo"), ("renewal_date", "!=", False)]):
            if v.days_to_renewal <= max(v.cancellation_notice_days, warn_days):
                add("ven_ren_%s" % v.id, _("Renovación próxima (%s): %s · %s") % (v.renewal_date, v.name, v.service), "renovacion_proxima", "3" if v.is_critical else "2", "vendors", v._name, v.id, v.responsible_id)
        for o in env["aq.portal.obligation"].search([("state", "in", ("pendiente", "vencida"))]):
            if o.state == "vencida":
                add("obl_over_%s" % o.id, _("Obligación vencida: %s") % o.name, "obligacion_vencida", "3", "obligations", o._name, o.id, o.responsible_id)
            elif o.days_to_date <= o.reminder_days:
                add("obl_soon_%s" % o.id, _("Obligación el %s: %s") % (o.date, o.name), "obligacion_proxima", "2", "obligations", o._name, o.id, o.responsible_id)
        # Personal y riesgos
        for e in env["aq.portal.employee"].search([("has_active_access_after_exit", "=", True)]):
            add("emp_acc_%s" % e.id, _("Exintegrante con accesos activos: %s") % e.name, "acceso_exempleado", "4", "employees", e._name, e.id)
        for r in env["aq.portal.risk"].search([("state", "not in", ("cerrado",)), ("review_date", "<=", today)]):
            add("risk_rev_%s" % r.id, _("Riesgo por revisar: %s") % r.name, "riesgo_revision", "2", "risks", r._name, r.id, r.responsible_id)
        for d in env["aq.portal.onboarding.deliverable"].search([("state", "in", ("pendiente", "en_proceso")), ("due_date", "<", today)]):
            add("onb_%s" % d.id, _("Entregable de incorporación vencido: %s") % d.name, "entregable_incorporacion", "2", "onboarding", d._name, d.id, d.responsible_id)

        # desactivar alertas que ya no aplican
        self.search([("key", "not in", list(active_keys)), ("active", "=", True)]).write({"active": False})
        self._generate_auto_risks()
        self._send_digest()
        return True

    def _generate_auto_risks(self):
        """Alimenta la matriz de riesgos con hallazgos automáticos (3.3)."""
        Risk = self.env["aq.portal.risk"]
        direction = self.env["aq.portal.member"].search([("is_direction", "=", True)], limit=1)
        mapping = {
            "cobro_vencido": ("cartera_vencida", "administrativo"), "trabajo_sin_facturar": ("horas_no_registradas", "administrativo"),
            "factura_atrasada": ("facturas_no_emitidas", "administrativo"), "acceso_exempleado": ("accesos_exempleados", "operativo"),
            "contrato_vencido": ("contratos_vencidos", "contractual"), "cambio_sin_autorizacion": ("compromiso_no_autorizado", "contractual"),
            "entregable_sin_aceptar": ("sin_evidencia_aceptacion", "contractual"), "trabajo_sin_autorizar": ("compromiso_no_autorizado", "contractual"),
        }
        for alert in self.search([("active", "=", True), ("severity", "in", ("3", "4")), ("alert_type", "in", list(mapping))]):
            rtype, cat = mapping[alert.alert_type]
            if Risk.search_count([("source_model", "=", alert.res_model), ("source_id", "=", alert.res_id), ("risk_type", "=", rtype), ("state", "!=", "cerrado")]):
                continue
            Risk.create({
                "name": alert.name, "category": cat, "risk_type": rtype, "probability": "3", "impact": "2" if alert.severity == "3" else "3",
                "responsible_id": (alert.responsible_id or direction).id or False, "preventive_action": _("Atender la alerta y documentar el cierre."),
                "review_date": fields.Date.add(fields.Date.today(), days=7), "auto_generated": True,
                "source_model": alert.res_model, "source_id": alert.res_id,
                "project_id": alert.res_id if alert.res_model == "aq.portal.project" else False,
            }) if (alert.responsible_id or direction) else None

    def _send_digest(self):
        users = self.env["aq.portal.user"].search([("active", "=", True), ("notify_alerts", "=", True), ("role", "in", ("direccion", "coordinacion"))])
        alerts = self.search([("active", "=", True), ("dismissed", "=", False)], limit=80)
        if not users or not alerts:
            return
        Brand = self.env["aq.portal.branding"]
        counts = {s: len(alerts.filtered(lambda a: a.severity == s)) for s in ("4", "3", "2", "1")}
        summary = ("<table role='presentation' cellpadding='0' cellspacing='0' style='width:100%%;border-collapse:separate;border-spacing:8px 0;margin:4px -8px 0'><tr>"
                   + "".join("<td style='background:#16161a;border:1px solid #2a2a32;border-radius:8px;padding:12px;text-align:center;width:25%%'>"
                             "<div style=\"font-family:'Bebas Neue',Impact,Arial,sans-serif;font-size:28px;color:%s;line-height:1\">%d</div>"
                             "<div style='font-family:Oxanium,Roboto,Arial,sans-serif;font-size:10px;letter-spacing:.12em;color:#9a9aa3;margin-top:4px'>%s</div></td>"
                             % (SEVERITY_STYLE[s][1], counts[s], SEVERITY_STYLE[s][0]) for s in ("4", "3", "2", "1"))
                   + "</tr></table>")
        ai = self.env["aq.ops.ai"].digest_summary([a.name for a in alerts]) if "aq.ops.ai" in self.env else ""
        body = summary + (("<p style='border-left:3px solid #c89eff;padding-left:10px;margin-top:14px'><b>Copiloto:</b> %s</p>" % ai.replace("\n", "<br/>")) if ai else "") + Brand.alert_rows(alerts)
        today = fields.Date.today().strftime("%d/%m/%Y")
        html = Brand.wrap(_("Resumen diario de alertas"), body, cta_label=_("Abrir el portal"), cta_url=Brand.portal_url() + "/alerts",
                          subtitle=_("%s · %d alertas activas que requieren seguimiento") % (today, len(alerts)),
                          preheader=_("%d alertas activas · %d críticas · %d urgentes") % (len(alerts), counts["4"], counts["3"]))
        for u in users:
            self.env["mail.mail"].sudo().create({
                "subject": _("AlphaQueb · %d alertas activas (%d críticas)") % (len(alerts), counts["4"]), "email_to": u.email, "body_html": html,
            }).send()

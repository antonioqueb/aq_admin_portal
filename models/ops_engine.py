# -*- coding: utf-8 -*-
"""AlphaOps · motor de automatizaciones, agregados de pantallas y KPIs operativos."""
import json
from datetime import timedelta
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError
from .ops_core import ACTIVE_STAGES, PROJECT_STAGES
from .ops_work import DONE_STATES

ACTIVE_ITEM_DOM = [("state", "not in", list(DONE_STATES))]


class OpsEngine(models.AbstractModel):
    _name = "aq.ops.engine"
    _description = "AlphaOps: motor"

    # ------------------------------------------------------------ cron
    @api.model
    def cron_daily(self):
        self.env["aq.ops.automation"].search([("active", "=", True), ("trigger", "=", "schedule_daily")]).run()
        self.env["aq.ops.event"].search([("state", "=", "pendiente")]).process()
        self.env["aq.ops.breakglass"].search([("state", "=", "activo"), ("end", "<", fields.Datetime.now())]).write({"state": "vencido"})
        self.env["aq.ops.notification"].send_digest("daily")
        if fields.Date.today().weekday() == 0:
            self.env["aq.ops.automation"].search([("active", "=", True), ("trigger", "=", "schedule_weekly")]).run()
            self.env["aq.ops.notification"].send_digest("weekly")
        return True

    def _N(self):
        return self.env["aq.ops.notification"]

    # ------------------------------------------------------------ importaciones a nombre de OdooBot
    BOT_MODELS = ("aq.ops.", "aq.portal.member", "res.partner", "ir.attachment")

    def _bot_check(self, model):
        if not self.env.user.has_group("aq_admin_portal.group_aq_portal_manager"):
            raise AccessError(_("Solo administradores del portal pueden importar a nombre de OdooBot."))
        if not any(model == m or (m.endswith(".") and model.startswith(m)) for m in self.BOT_MODELS):
            raise AccessError(_("Modelo no permitido para importación: %s") % model)

    @api.model
    def bot_create(self, model, vals_list):
        """Crea registros como OdooBot (superusuario). Pensado para migraciones (p. ej. Taiga)."""
        self._bot_check(model)
        recs = self.env(user=SUPERUSER_ID)[model].with_context(portal_import=True, mail_create_nosubscribe=True).create(vals_list)
        return recs.ids

    @api.model
    def bot_write(self, model, ids, vals):
        self._bot_check(model)
        self.env(user=SUPERUSER_ID)[model].browse(ids).with_context(portal_import=True).write(vals)
        return True

    @api.model
    def bot_post(self, model, res_id, body):
        self._bot_check(model)
        rec = self.env(user=SUPERUSER_ID)[model].browse(res_id)
        if hasattr(rec, "message_post"):
            rec.message_post(body=body, message_type="comment")
        return True

    @api.model
    def safe_partner(self, name):
        """Crea (o recupera) un cliente rellenando campos obligatorios sin valor por defecto (p. ej. personalizaciones como group_rfq)."""
        Partner = self.env["res.partner"].sudo()
        existing = Partner.search([("name", "=", name)], limit=1)
        if existing:
            return existing
        vals = {"name": name, "is_company": True}
        defaults = Partner.default_get(list(Partner._fields))
        for fname, f in Partner._fields.items():
            if f.required and fname not in vals and defaults.get(fname) in (None, False) and not f.compute and f.store:
                if f.type == "selection":
                    sel = f.selection(Partner) if callable(f.selection) else f.selection
                    if sel:
                        vals[fname] = sel[0][0]
                elif f.type == "boolean":
                    vals[fname] = False
                elif f.type in ("char", "text"):
                    vals[fname] = name
                elif f.type in ("integer", "float", "monetary"):
                    vals[fname] = 0
        return Partner.create(vals)

    @api.model
    def bot_partner(self, name, vals=None):
        self._bot_check("res.partner")
        eng = self.env(user=SUPERUSER_ID)["aq.ops.engine"]
        p = eng.safe_partner(name)
        if vals:
            p.write(vals)
        return p.id

    @api.model
    def seed_getting_ready(self):
        P = self.env["aq.ops.project"].sudo()
        if P.search_count([("name", "=", "Getting Ready · Cierre y handoff")]):
            return True
        partner = self.safe_partner("Getting Ready")
        tpl = self.env.ref("aq_admin_portal.ops_template_cierre", raise_if_not_found=False)
        pm = self.env.ref("aq_admin_portal.member_direccion", raise_if_not_found=False)
        P.create({"name": "Getting Ready · Cierre y handoff", "partner_id": partner.id, "service_type": "cierre", "template_id": tpl.id if tpl else False,
                  "pm_id": pm.id if pm else False, "objective": "Cierre, transición, pendientes conocidos y handoff."})
        return True

    # ------------------------------------------------------------ automatizaciones integradas (7)
    @api.model
    def auto_project_without_next_action(self):
        n = 0
        for p in self.env["aq.ops.project"].search([("stage", "in", ACTIVE_STAGES), ("has_next_action", "=", False)]):
            self._N().notify_role(p, ["pm"], "accion_requerida", _("Proyecto sin siguiente acción, responsable o fecha: %s") % p.name, "projects", p.id); n += 1
        for m in self.env["aq.ops.milestone"].search([("state", "in", ("pendiente", "en_progreso")), "|", ("next_action", "=", False), ("next_action_date", "=", False)]):
            self._N().notify_member(m.owner_id or m.project_id.pm_id, "accion_requerida", _("Hito sin siguiente acción/fecha: %s") % m.name, "milestones", m.id); n += 1
        for r in self.env["aq.ops.raid"].search([("state", "in", ("abierto", "mitigando")), "|", ("next_action", "=", False), ("next_action_date", "=", False)]):
            self._N().notify_member(r.owner_id or r.project_id.pm_id, "riesgo", _("Riesgo/problema sin siguiente acción: %s") % r.name, "raid", r.id); n += 1
        return n

    @api.model
    def auto_escalate_blocked(self):
        limit = fields.Datetime.now() - timedelta(hours=int(self.env["ir.config_parameter"].sudo().get_param("aq_ops.blocked_escalation_hours", "48")))
        items = self.env["aq.ops.item"].search([("state", "=", "bloqueado"), ("blocked_since", "<", limit)])
        for i in items:
            self._N().notify_role(i.project_id, ["pm", "ops_director"], "bloqueo", _("Bloqueado demasiado tiempo (%.0f h): %s") % (i.blocked_hours, i.name), "items", i.id)
        return len(items)

    @api.model
    def auto_reassign_overdue_validations(self):
        today = fields.Date.today()
        accs = self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente"), ("due_date", "<", today)])
        for a in accs:
            alt = (a.project_id.validator_ids - a.validator_partner_id)[:1]
            if alt:
                a.write({"validator_partner_id": alt.id, "reassigned_count": a.reassigned_count + 1, "due_date": fields.Date.add(today, days=3)})
                self._N().notify_partner(alt, "aprobacion", _("Validación reasignada a usted: %s") % (a.item_id.name or a.milestone_id.name), "acceptances", a.id)
            self._N().notify_role(a.project_id, ["pm"], "accion_requerida", _("Validación vencida: %s") % (a.item_id.name or a.milestone_id.name), "acceptances", a.id)
        return len(accs)

    @api.model
    def auto_hours_threshold(self):
        n = 0
        for p in self.env["aq.ops.project"].search([("hours_authorized", ">", 0), ("stage", "in", ACTIVE_STAGES)]):
            for th in (70, 85, 100):
                if p.hours_pct >= th:
                    self._N().notify_role(p, ["pm"], "riesgo", _("%s: horas consumidas al %.0f%% (umbral %d%%)") % (p.name, p.hours_pct, th), "projects", p.id); n += 1
        return n

    @api.model
    def auto_weekly_reports(self):
        projects = self.env["aq.ops.project"].search([("stage", "in", ACTIVE_STAGES)])
        for p in projects:
            self.env["aq.ops.status.report"].generate(p)
        return len(projects)

    @api.model
    def auto_remind_waiting_client(self):
        limit = fields.Date.add(fields.Date.today(), days=-3)
        items = self.env["aq.ops.item"].search([("waiting_client", "=", True), ("waiting_client_since", "<=", limit)] + ACTIVE_ITEM_DOM)
        for i in items:
            self._N().notify_partner(i.validator_partner_id or i.project_id.client_contact_ids[:1], "recordatorio", _("Pendiente de su parte: %s") % i.name, "items", i.id)
            self._N().notify_role(i.project_id, ["pm"], "recordatorio", _("Esperando al cliente desde %s: %s") % (i.waiting_client_since, i.name), "items", i.id)
        for a in self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente"), ("requested_at", "<", fields.Datetime.now() - timedelta(days=3))]):
            self._N().notify_partner(a.validator_partner_id, "aprobacion", _("Entregable en espera de su validación: %s") % (a.item_id.name or a.milestone_id.name), "acceptances", a.id)
        return len(items)

    @api.model
    def auto_block_incomplete_releases(self):
        rels = self.env["aq.ops.release"].search([("env_type", "=", "prod"), ("state", "in", ("candidata", "aprobada", "programada")), ("planned_at", "<=", fields.Datetime.now() + timedelta(days=1))])
        n = 0
        for r in rels:
            if r._gate():
                r.write({"state": "bloqueada"}); n += 1
                self._N().notify_member(r.owner_id or r.project_id.tech_lead_id, "bloqueo", _("Liberación bloqueada por requisitos incompletos: %s (%s)") % (r.name, r.gate_missing), "releases", r.id)
        return n

    @api.model
    def auto_update_stage_from_milestones(self):
        projects = self.env["aq.ops.project"].search([("stage", "in", ACTIVE_STAGES)])
        projects._update_stage_from_milestones()
        return len(projects)

    @api.model
    def auto_dependency_risk(self):
        n = 0
        for r in self.env["aq.ops.raid"].search([("raid_type", "=", "dependency"), ("endangers_date", "=", True), ("state", "not in", ("cerrado",))]):
            self._N().notify_role(r.project_id, ["pm"], "riesgo", _("Dependencia pone en riesgo la fecha comprometida: %s") % r.name, "raid", r.id); n += 1
        for i in self.env["aq.ops.item"].search(ACTIVE_ITEM_DOM + [("date_due", "!=", False)]):
            late = i.depends_on_ids.filtered(lambda d: d.state not in DONE_STATES and d.date_due and d.date_due >= i.date_due)
            if late:
                self._N().notify_member(i.assignee_id, "riesgo", _("'%s' depende de elementos que vencen después de su fecha: %s") % (i.name, ", ".join(late.mapped("name"))), "items", i.id); n += 1
        return n

    @api.model
    def auto_overload(self):
        today = fields.Date.today()
        week = today.strftime("%G-W%V")
        Cap = self.env["aq.ops.capacity"]
        n = 0
        for m in self.env["aq.portal.member"].search([("active", "=", True)]):
            cap = Cap.search([("member_id", "=", m.id), ("week", "=", week)], limit=1) or Cap.create({"member_id": m.id, "week": week})
            if cap.overallocated:
                self._N().notify_member(m, "recordatorio", _("Sobreasignación esta semana: %.0f h planificadas vs %.0f disponibles. Sugerencia: reprogramar elementos de menor prioridad.") % (cap.planned_hours, cap.hours_available - cap.unavailable_hours), "capacity", cap.id)
                self._N().notify_role(False, ["ops_director"], "recordatorio", _("%s sobreasignado (%.0f%%)") % (m.name, cap.load_pct), "capacity", cap.id); n += 1
        return n

    @api.model
    def auto_duplicate_requests(self):
        n = 0
        for r in self.env["aq.ops.request"].search([("state", "in", ("nueva", "clasificada"))]):
            if r.potential_duplicate_ids:
                self._N().notify_role(r.project_id, ["pm", "support"], "accion_requerida", _("Solicitud potencialmente duplicada: %s") % r.name, "requests", r.id); n += 1
        return n

    @api.model
    def auto_inactive_projects(self):
        days = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.stale_days", "5"))
        limit = fields.Date.add(fields.Date.today(), days=-days)
        projects = self.env["aq.ops.project"].search([("stage", "in", ACTIVE_STAGES), ("last_activity_date", "<=", limit)])
        for p in projects:
            self._N().notify_role(p, ["pm"], "recordatorio", _("Proyecto sin actividad reciente (%d días): %s") % (p.days_without_activity, p.name), "projects", p.id)
        return len(projects)

    @api.model
    def auto_unjustified_time(self):
        ts = self.env["aq.ops.timesheet"].search([("unjustified", "=", True), ("state", "in", ("borrador", "enviado"))])
        for t in ts:
            self._N().notify_member(t.member_id, "accion_requerida", _("Tiempo registrado sin proyecto, entregable ni justificación (%s, %.1f h)") % (t.date, t.hours), "timesheets", t.id)
        return len(ts)

    @api.model
    def auto_stale_items(self):
        limit = fields.Datetime.now() - timedelta(days=7)
        items = self.env["aq.ops.item"].search(ACTIVE_ITEM_DOM + [("state_since", "<", limit), ("state", "in", ("en_progreso", "revision_tecnica", "qa_interno", "listo_validacion", "validacion_cliente"))])
        for i in items:
            self._N().notify_member(i.assignee_id, "recordatorio", _("Sin movimiento desde hace %d días: %s") % (i.days_in_state, i.name), "items", i.id)
        return len(items)

    @api.model
    def auto_recurring(self):
        today = fields.Date.today()
        items = self.env["aq.ops.item"].search([("is_recurring", "=", True), ("state", "in", list(DONE_STATES)), ("done_date", "<=", fields.Date.add(today, days=-1))])
        for i in items:
            if not self.env["aq.ops.item"].search_count([("is_recurring", "=", True), ("name", "=", i.name), ("project_id", "=", i.project_id.id), ("state", "not in", list(DONE_STATES))]):
                i.action_create_recurrence()
        return len(items)

    @api.model
    def auto_time_pending(self):
        today = fields.Date.today()
        n = 0
        for u in self.env["aq.portal.user"].search([("has_ops_access", "=", True), ("member_id", "!=", False), ("ops_role", "in", ("pm", "functional_lead", "tech_lead", "consultant", "developer", "qa", "support", "collaborator", "partner"))]):
            logged = sum(self.env["aq.ops.timesheet"].search([("member_id", "=", u.member_id.id), ("date", ">=", fields.Date.add(today, days=-1)), ("date", "<=", today)]).mapped("hours"))
            if logged < 4:
                self._N().push(u, "recordatorio", _("Horas pendientes de registrar (ayer/hoy: %.1f h)") % logged, "time", 0); n += 1
        return n

    @api.model
    def run_generic(self, automation):
        Model = self.env[automation.model_name]
        dom = json.loads(automation.condition_domain or "[]")
        recs = Model.search(dom)
        params = json.loads(automation.action_params or "{}")
        for r in recs:
            if automation.action_type == "notify":
                proj = r.project_id if "project_id" in r._fields else False
                self._N().notify_role(proj, params.get("roles", ["pm"]), params.get("category", "recordatorio"), (params.get("title") or automation.name) + ": " + r.display_name, params.get("resource"), r.id)
            elif automation.action_type == "set_field":
                r.with_context(aq_auto=True).write({params["field"]: params["value"]})
            elif automation.action_type == "escalate":
                self._N().notify_role(False, ["ops_director"], "accion_requerida", automation.name + ": " + r.display_name, params.get("resource"), r.id)
        return len(recs)

    # ------------------------------------------------------------ pantallas
    @api.model
    def my_work(self, user, project_domain):
        today = fields.Date.today()
        week_end = today + timedelta(days=6 - today.weekday())
        m = user.member_id
        Item = self.env["aq.ops.item"]
        base = ACTIVE_ITEM_DOM + project_domain

        def ser(i):
            return {"id": i.id, "name": i.name, "type": i.item_type, "state": i.state, "project": i.project_id.name, "project_id": i.project_id.id, "due": str(i.date_due or ""),
                    "priority": i.priority, "assignee": i.assignee_id.name, "blocked_reason": i.blocked_reason, "days_in_state": i.days_in_state, "waiting_client": i.waiting_client}
        mine = Item.search(base + [("assignee_id", "=", m.id)]) if m else Item
        out = {
            "assigned": [ser(i) for i in mine.sorted(lambda i: (i.priority != "2", i.date_due or today))[:40]],
            "today": [ser(i) for i in mine.filtered(lambda i: i.date_due and i.date_due <= today)],
            "week": [ser(i) for i in mine.filtered(lambda i: i.date_due and today < i.date_due <= week_end)],
            "blocked": [ser(i) for i in mine.filtered(lambda i: i.state == "bloqueado")],
            "stale": [ser(i) for i in mine.filtered(lambda i: i.days_in_state >= 7 and i.state not in ("backlog", "por_hacer"))],
            "depends_on_me": [ser(i) for i in Item.search(base + [("depends_on_ids.assignee_id", "=", m.id), ("assignee_id", "!=", m.id)])] if m else [],
        }
        projects = self.env["aq.ops.project"].search(project_domain_to_project(project_domain) + [("stage", "in", ACTIVE_STAGES)])
        out["next_actions"] = [{"id": p.id, "project": p.name, "next_action": p.next_action, "date": str(p.next_action_date or ""), "owner": p.next_action_owner_id.name, "missing": not p.has_next_action}
                               for p in projects if (m and p.next_action_owner_id == m) or not p.has_next_action][:30]
        # aprobaciones
        approvals = []
        if user.ops_role in ("client_sponsor", "client_po", "client_validator"):
            for a in self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente")] + project_domain):
                if not user.department or not a.department or a.department.lower() == user.department.lower():
                    approvals.append({"id": a.id, "kind": "acceptance", "name": a.item_id.name or a.milestone_id.name, "project": a.project_id.name, "due": str(a.due_date or "")})
        if user.ops_role in ("pm", "ops_director", "platform_owner", "tech_lead", "functional_lead"):
            for d in self.env["aq.ops.decision"].search([("state", "=", "propuesta")] + project_domain):
                approvals.append({"id": d.id, "kind": "decision", "name": d.name, "project": d.project_id.name})
            for r in self.env["aq.ops.release"].search([("state", "=", "candidata"), ("env_type", "=", "prod")] + project_domain):
                approvals.append({"id": r.id, "kind": "release", "name": r.name, "project": r.project_id.name})
            for t in self.env["aq.ops.timesheet"].search([("state", "=", "enviado")] + project_domain, limit=50):
                approvals.append({"id": t.id, "kind": "timesheet", "name": "%s · %.1f h · %s" % (t.member_id.name, t.hours, t.date), "project": t.project_id.name})
        out["approvals"] = approvals
        out["requests"] = [{"id": r.id, "name": r.name, "org": r.partner_id.name, "state": r.state, "urgency": r.urgency, "age_days": (today - r.create_date.date()).days}
                           for r in self.env["aq.ops.request"].search([("state", "in", ("nueva", "clasificada", "analisis"))] + project_domain, limit=30)] if user.ops_role not in ("client_requester",) else []
        out["mentions"] = [{"id": n.id, "title": n.title, "resource": n.resource, "res_id": n.res_id, "date": str(n.create_date)} for n in self.env["aq.ops.notification"].search([("user_id", "=", user.id), ("category", "=", "mencion"), ("read", "=", False)], limit=20)]
        out["meetings"] = [{"id": mt.id, "name": mt.name, "date": str(mt.date), "project": mt.project_id.name} for mt in self.env["aq.ops.meeting"].search([("date", ">=", fields.Datetime.now()), ("state", "=", "programada")] + project_domain, order="date", limit=10)]
        logged = sum(self.env["aq.ops.timesheet"].search([("member_id", "=", m.id), ("date", ">=", today - timedelta(days=today.weekday())), ("date", "<=", today)]).mapped("hours")) if m else 0
        out["hours_week"] = logged
        out["hours_pending"] = max((today.weekday() + 1) * 8 - logged, 0) if m else 0
        out["running_timer"] = None
        if m:
            run = self.env["aq.ops.timesheet"].search([("member_id", "=", m.id), ("running", "=", True)], limit=1)
            if run:
                out["running_timer"] = {"id": run.id, "item": run.item_id.name, "project": run.project_id.name, "since": str(run.timer_start)}
        out["risks"] = [{"id": r.id, "name": r.name, "type": r.raid_type, "project": r.project_id.name, "severity": r.severity, "due": str(r.due_date or "")}
                        for r in self.env["aq.ops.raid"].search([("state", "in", ("abierto", "mitigando", "materializado"))] + project_domain + ([("owner_id", "=", m.id)] if m and user.ops_role not in ("ops_director", "platform_owner") else []), limit=20)]
        out["incidents"] = [{"id": i.id, "name": i.name, "severity": i.severity, "step": i.step, "project": i.project_id.name, "sla_breached": i.sla_breached}
                            for i in self.env["aq.ops.incident"].search([("step", "!=", "cerrado")] + project_domain + ([("owner_id", "=", m.id)] if m and user.ops_role not in ("ops_director", "platform_owner", "support") else []), limit=20)]
        out["notifications_unread"] = self.env["aq.ops.notification"].search_count([("user_id", "=", user.id), ("read", "=", False)])
        return out

    @api.model
    def portfolio(self, project_domain):
        today = fields.Date.today()
        P = self.env["aq.ops.project"].search(project_domain_to_project(project_domain) + [("stage", "not in", ("cerrado",))])
        rows = []
        for p in P:
            rows.append({"id": p.id, "name": p.name, "client": p.partner_id.name, "pm": p.pm_id.name, "service_type": p.service_type, "stage": p.stage, "health": p.health, "health_reason": p.health_reason,
                         "priority": p.priority, "risk": p.risk_level, "client_dependent": p.client_dependent, "team": len(p.team_member_ids), "hours_pct": round(p.hours_pct, 1),
                         "hours_consumed": p.hours_consumed, "hours_authorized": p.hours_authorized, "next_milestone": p.next_milestone_id.name, "next_milestone_date": str(p.next_milestone_id.date_current or ""),
                         "next_decision": p.next_decision, "probable_end": str(p.date_end_probable or ""), "baseline_end": str(p.date_end_baseline or ""), "has_next_action": p.has_next_action,
                         "next_action": p.next_action, "blocked": p.blocked_items, "in_validation": p.in_validation, "open_risks": p.open_risks, "days_without_activity": p.days_without_activity,
                         "commercial_restriction": p.commercial_restriction, "contract_state": p.contract_state})
        week = today.strftime("%G-W%V")
        caps = self.env["aq.ops.capacity"].search([("week", "=", week)])
        overloaded = [{"member": c.member_id.name, "load_pct": round(c.load_pct), "planned": c.planned_hours, "available": c.hours_available - c.unavailable_hours} for c in caps if c.overallocated]
        releases = self.env["aq.ops.release"].search([("state", "in", ("aprobada", "programada", "candidata")), ("planned_at", "<=", fields.Datetime.now() + timedelta(days=14))] + project_domain)
        incidents = self.env["aq.ops.incident"].search([("step", "!=", "cerrado"), ("affects_other_clients", "=", True)] + project_domain)
        direction = [r for r in rows if r["health"] == "rojo" or r["commercial_restriction"] or not r["has_next_action"]]
        return {"projects": rows, "answers": {
            "at_risk": [r for r in rows if r["health"] == "rojo" or r["risk"] in ("alto", "critico")],
            "no_next_step": [r for r in rows if not r["has_next_action"]],
            "waiting_client": [r for r in rows if r["client_dependent"]],
            "overloaded": overloaded,
            "upcoming_releases": [{"id": r.id, "name": r.name, "project": r.project_id.name, "env": r.env_type, "planned": str(r.planned_at or ""), "state": r.state, "gate": r.gate_missing} for r in releases],
            "stuck_validation": [{"id": i.id, "name": i.name, "project": i.project_id.name, "days": i.days_in_state} for i in self.env["aq.ops.item"].search([("state", "in", ("listo_validacion", "validacion_cliente"))] + project_domain) if i.days_in_state >= 3],
            "over_hours": [r for r in rows if r["hours_pct"] >= 85],
            "cross_client_incidents": [{"id": i.id, "name": i.name, "severity": i.severity, "project": i.project_id.name} for i in incidents],
            "direction_today": direction,
        }, "groups": {k: sorted(set(r[k] for r in rows if r[k])) for k in ("client", "pm", "service_type", "stage", "health", "priority", "risk")}}

    @api.model
    def command_center(self, project, user):
        p = project
        external = user.is_external
        def vis(recs):
            return recs.filtered("client_visible") if external else recs
        items = vis(p.item_ids)
        return {
            "project": {"id": p.id, "name": p.name, "client": p.partner_id.name, "objective": p.objective, "scope": p.scope_current, "scope_version": p.scope_version, "stage": p.stage, "stage_label": dict(PROJECT_STAGES)[p.stage],
                        "pm": p.pm_id.name, "functional_lead": p.functional_lead_id.name, "tech_lead": p.tech_lead_id.name, "team": p.team_member_ids.mapped("name"), "client_team": p.client_contact_ids.mapped("name"),
                        "validators": p.validator_ids.mapped("name"), "health": p.health, "health_reason": p.health_reason,
                        "health_dims": {"alcance": p.health_scope, "tiempo": p.health_time, "capacidad": p.health_capacity, "calidad": p.health_quality, "cliente": p.health_client},
                        "hours": {"authorized": p.hours_authorized, "consumed": p.hours_consumed, "approved": p.hours_approved, "remaining": p.hours_remaining, "pct": round(p.hours_pct, 1), "estimated": p.hours_estimated},
                        "next_action": p.next_action, "next_action_owner": p.next_action_owner_id.name, "next_action_date": str(p.next_action_date or ""), "next_decision": p.next_decision,
                        "commercial_restriction": p.commercial_restriction, "contract_state": p.contract_state, "methodology": p.methodology, "service_type": p.service_type,
                        "date_start": str(p.date_start or ""), "date_end_baseline": str(p.date_end_baseline or ""), "date_end_current": str(p.date_end_current or ""), "date_end_probable": str(p.date_end_probable or ""),
                        "escalation_path": None if external else p.escalation_path, "client_dependent": p.client_dependent, "wip_limit": p.wip_limit,
                        "forecast": None if external else {"burn_rate_week": p.burn_rate_week, "depletion": str(p.hours_depletion_forecast or ""), "velocity_week": p.velocity_week, "end_by_velocity": str(p.forecast_end_by_velocity or "")}},
            "milestones": [{"id": m.id, "name": m.name, "date": str(m.date_current or ""), "baseline": str(m.date_baseline or ""), "actual": str(m.date_actual or ""), "state": m.state, "deviation": m.deviation_days, "enables_billing": m.enables_billing, "owner": m.owner_id.name}
                           for m in vis(p.milestone_ids).sorted(lambda m: m.date_current or fields.Date.today())],
            "risks": [{"id": r.id, "name": r.name, "type": r.raid_type, "severity": r.severity, "state": r.state, "owner": r.owner_id.name, "requires_client": r.requires_client}
                      for r in vis(p.raid_ids).filtered(lambda r: r.state not in ("cerrado",)).sorted(lambda r: -r.severity)[:8]],
            "decisions": [{"id": d.id, "name": d.name, "state": d.state, "date": str(d.date), "version": d.version} for d in vis(p.decision_ids).filtered(lambda d: d.state in ("propuesta", "aprobada"))[:10]],
            "in_validation": [{"id": i.id, "name": i.name, "state": i.state, "validator": i.validator_partner_id.name, "days": i.days_in_state} for i in items.filtered(lambda i: i.state in ("listo_validacion", "validacion_cliente"))],
            "blocked": [] if external else [{"id": i.id, "name": i.name, "reason": i.blocked_reason, "hours": round(i.blocked_hours)} for i in items.filtered(lambda i: i.state == "bloqueado")],
            "last_report": {"id": p.last_report_id.id, "name": p.last_report_id.name, "date": str(p.last_report_id.date), "health": p.last_report_id.health, "summary": p.last_report_id.summary} if p.last_report_id and (not external or p.last_report_id.client_visible) else None,
            "activity": [] if external else [{"date": str(l.create_date), "user": l.user_id.name, "summary": l.summary, "action": l.action} for l in self.env["aq.portal.audit.log"].search([("res_model", "like", "aq.ops.%"), ("summary", "ilike", p.name)], limit=15)],
            "links": [{"id": l.id, "name": l.name, "url": l.url, "type": l.link_type} for l in (p.link_ids.filtered("client_visible") if external else p.link_ids)],
            "environments": [{"id": e.id, "name": e.name, "type": e.env_type, "url": e.url, "version": e.version} for e in p.environment_ids],
            "documents": [{"id": d.id, "name": d.name, "type": d.doc_type, "url": d.drive_url, "version": d.version, "current": d.is_current} for d in vis(p.document_ids).filtered("is_current")[:12]],
            "counts": {"items": len(items), "open": len(items.filtered(lambda i: i.state not in DONE_STATES)), "requests": len(vis(p.request_ids).filtered(lambda r: r.state in ("nueva", "clasificada", "analisis"))),
                       "incidents": len(vis(p.incident_ids).filtered(lambda i: i.step != "cerrado")), "changes": len(vis(p.change_ids).filtered(lambda c: c.state in ("solicitado", "analisis", "estimado", "pendiente_comercial"))),
                       "releases": len(vis(p.release_ids).filtered(lambda r: r.state in ("candidata", "aprobada", "programada"))), "meetings": len(vis(p.meeting_ids))},
            "board": [{"id": i.id, "name": i.name, "type": i.item_type, "state": i.state, "assignee": i.assignee_id.name, "due": str(i.date_due or ""), "priority": i.priority, "parent": i.parent_id.name, "milestone": i.milestone_id.name,
                       "estimate": i.estimate_hours, "remaining": i.remaining_hours, "spent": i.spent_hours, "waiting_client": i.waiting_client, "sprint": i.sprint_id.name, "deliverable": i.deliverable_id.name, "rank": i.rank,
                       "start": str(i.date_start or ""), "baseline": str(i.date_baseline or ""), "depends_on": i.depends_on_ids.ids, "accepted": i.accepted, "blocked_reason": None if external else i.blocked_reason}
                      for i in items.filtered(lambda i: i.state != "cancelado")],
            "sprints": [{"id": s.id, "name": s.name, "state": s.state, "start": str(s.date_start), "end": str(s.date_end), "goal": s.goal, "items": s.item_count, "done": s.done_count, "committed": s.committed_hours, "capacity": s.capacity_hours} for s in p.sprint_ids],
        }

    @api.model
    def client_home(self, user, project_domain):
        today = fields.Date.today()
        P = self.env["aq.ops.project"].search(project_domain_to_project(project_domain) + [("client_visible", "=", True)])
        dom = project_domain + [("client_visible", "=", True)]
        own = [("requester_user_id", "=", user.id)] if user.ops_role == "client_requester" else []
        return {
            "projects": [{"id": p.id, "name": p.name, "stage": dict(PROJECT_STAGES)[p.stage], "health": p.health, "next_milestone": p.next_milestone_id.name, "next_milestone_date": str(p.next_milestone_id.date_current or ""),
                          "pm": p.pm_id.name, "in_validation": p.in_validation} for p in P],
            "milestones": [{"id": m.id, "name": m.name, "project": m.project_id.name, "date": str(m.date_current or ""), "state": m.state} for m in self.env["aq.ops.milestone"].search(dom, order="date_current")[:30]],
            "roadmap": [{"id": i.id, "name": i.name, "project": i.project_id.name, "due": str(i.date_due or ""), "state": i.state, "type": i.item_type} for i in self.env["aq.ops.item"].search(dom + [("item_type", "in", ("entregable", "epica", "cambio"))], order="date_due")[:40]],
            "approvals": [{"id": a.id, "name": a.item_id.name or a.milestone_id.name, "project": a.project_id.name, "criteria": a.criteria, "evidence": a.evidence, "due": str(a.due_date or ""), "department": a.department}
                          for a in self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente")] + dom) if user.ops_role != "client_requester" and (not a.department or not user.department or a.department.lower() == user.department.lower())],
            "questions": [{"id": q.id, "name": q.name, "meeting": q.meeting_id.name, "project": q.meeting_id.project_id.name} for q in self.env["aq.ops.meeting.question"].search([("answered", "=", False), ("client_visible", "=", True), ("meeting_id.project_id", "in", P.ids)])],
            "commitments": [{"id": i.id, "name": i.name, "project": i.project_id.name, "due": str(i.date_due or "")} for i in self.env["aq.ops.item"].search(dom + [("waiting_client", "=", True)] + ACTIVE_ITEM_DOM)],
            "requests": [{"id": r.id, "name": r.name, "state": r.state, "type": r.request_type, "date": str(r.create_date.date()), "response": r.response} for r in self.env["aq.ops.request"].search([("partner_id", "=", user.organization_id.id)] + own, limit=50)],
            "tests": [{"id": c.id, "name": c.name, "project": c.project_id.name, "result": c.last_result, "department": c.department} for c in self.env["aq.ops.test.case"].search([("client_visible", "=", True), ("project_id", "in", P.ids), ("plan_id.plan_type", "=", "uat")], limit=40)],
            "decisions": [{"id": d.id, "name": d.name, "decision": d.decision_text, "date": str(d.date), "state": d.state} for d in self.env["aq.ops.decision"].search(dom + [("state", "=", "aprobada")], limit=20)],
            "meetings": [{"id": m.id, "name": m.name, "date": str(m.date), "project": m.project_id.name, "state": m.state} for m in self.env["aq.ops.meeting"].search(dom, order="date desc", limit=15)],
            "risks": [{"id": r.id, "name": r.name, "project": r.project_id.name, "severity": r.severity, "owner": r.client_owner_id.name} for r in self.env["aq.ops.raid"].search(dom + [("requires_client", "=", True), ("state", "not in", ("cerrado",))])],
            "incidents": [{"id": i.id, "name": i.name, "severity": i.severity, "step": i.step, "project": i.project_id.name} for i in self.env["aq.ops.incident"].search(dom + [("partner_id", "=", user.organization_id.id)], limit=20)],
            "documents": [{"id": d.id, "name": d.name, "type": d.doc_type, "url": d.drive_url, "version": d.version, "project": d.project_id.name} for d in self.env["aq.ops.document"].search(dom + [("is_current", "=", True)], limit=40)],
            "organization": user.organization_id.name,
        }

    @api.model
    def ops_kpis(self, project_domain, date_from=None, date_to=None):
        today = fields.Date.today()
        date_from = date_from or (today - timedelta(days=30)); date_to = date_to or today
        Item = self.env["aq.ops.item"]
        pd = project_domain
        ms = self.env["aq.ops.milestone"].search([("state", "=", "validado"), ("date_actual", ">=", date_from), ("date_actual", "<=", date_to)] + pd)
        on_time = ms.filtered(lambda m: m.deviation_days <= 0)
        done = Item.search([("done_date", ">=", date_from), ("done_date", "<=", date_to)] + pd)
        with_baseline = done.filtered(lambda i: i.date_baseline)
        predictable = with_baseline.filtered(lambda i: i.done_date <= i.date_baseline)
        open_items = Item.search(ACTIVE_ITEM_DOM + pd)
        blocked_hours = sum(open_items.mapped("blocked_hours"))
        pct = lambda n, d: round(n / d * 100.0, 1) if d else 0.0
        accs = self.env["aq.ops.acceptance"].search([("decided_at", ">=", fields.Datetime.to_datetime(date_from)), ("decided_at", "<=", fields.Datetime.to_datetime(date_to) + timedelta(days=1))] + pd)
        acc_days = [(a.decided_at - a.requested_at).total_seconds() / 86400.0 for a in accs if a.requested_at]
        reqs = self.env["aq.ops.request"].search([("create_date", ">=", fields.Datetime.to_datetime(date_from))] + pd)
        client_resp = [r.first_response_hours for r in reqs if r.response_date]
        waiting = open_items.filtered("waiting_client")
        wait_days = [(today - i.waiting_client_since).days for i in waiting if i.waiting_client_since]
        projects = self.env["aq.ops.project"].search(project_domain_to_project(pd) + [("stage", "in", ACTIVE_STAGES)])
        est_vs_real = [(p.hours_estimated, p.hours_consumed) for p in projects if p.hours_estimated]
        rels = self.env["aq.ops.release"].search([("deployed_at", ">=", fields.Datetime.to_datetime(date_from))] + pd)
        incs = self.env["aq.ops.incident"].search([("reported_at", ">=", fields.Datetime.to_datetime(date_from))] + pd)
        week = today.strftime("%G-W%V")
        caps = self.env["aq.ops.capacity"].search([("week", "=", week)])
        return {
            "period": {"from": str(date_from), "to": str(date_to)},
            "milestone_compliance_pct": pct(len(on_time), len(ms)), "milestones_validated": len(ms),
            "plan_deviation_days": round(sum(m.deviation_days for m in ms) / len(ms), 1) if ms else 0,
            "predictability_pct": pct(len(predictable), len(with_baseline)),
            "cycle_time_days": round(sum(done.mapped("cycle_days")) / len(done), 1) if done else 0,
            "lead_time_days": round(sum(done.mapped("lead_days")) / len(done), 1) if done else 0,
            "blocked_hours": round(blocked_hours), "blocked_items": len(open_items.filtered(lambda i: i.state == "bloqueado")),
            "aging_avg_days": round(sum(open_items.mapped("age_days")) / len(open_items), 1) if open_items else 0, "aging_over_30": len(open_items.filtered(lambda i: i.age_days > 30)),
            "unplanned_pct": pct(len(done.filtered("unplanned")), len(done)),
            "scope_changes": self.env["aq.ops.change"].search_count([("create_date", ">=", fields.Datetime.to_datetime(date_from))] + pd),
            "waiting_client_items": len(waiting), "waiting_client_avg_days": round(sum(wait_days) / len(wait_days), 1) if wait_days else 0,
            "acceptance_avg_days": round(sum(acc_days) / len(acc_days), 1) if acc_days else 0, "acceptances": len(accs), "acceptance_approved_pct": pct(len(accs.filtered(lambda a: a.decision == "aprobado")), len(accs)),
            "capacity_load_pct": round(sum(caps.mapped("load_pct")) / len(caps), 1) if caps else 0, "overloaded_people": len(caps.filtered("overallocated")),
            "estimated_vs_real_pct": pct(sum(r for e, r in est_vs_real), sum(e for e, r in est_vs_real)),
            "rework_pct": pct(len(done.filtered("is_rework")), len(done)),
            "defects_internal": Item.search_count([("item_type", "=", "defecto"), ("found_in", "=", "interno"), ("create_date", ">=", fields.Datetime.to_datetime(date_from))] + pd),
            "defects_production": Item.search_count([("item_type", "=", "defecto"), ("found_in", "=", "produccion"), ("create_date", ">=", fields.Datetime.to_datetime(date_from))] + pd),
            "release_success_pct": pct(len(rels.filtered("success")), len(rels)), "releases": len(rels),
            "incidents_by_severity": {s: len(incs.filtered(lambda i: i.severity == s)) for s in ("S1", "S2", "S3", "S4")},
            "sla_compliance_pct": pct(len(incs.filtered(lambda i: i.sla_response_met and (i.sla_resolution_met or not i.resolved_at))), len(incs)),
            "portfolio_health": {h: len(projects.filtered(lambda p: p.health == h)) for h in ("verde", "amarillo", "rojo")},
            "client_response_hours": round(sum(client_resp) / len(client_resp), 1) if client_resp else 0, "client_requests": len(reqs),
            "client_participation_pct": pct(len(accs), len(accs) + len(self.env["aq.ops.acceptance"].search([("decision", "=", "pendiente")] + pd))),
        }


def project_domain_to_project(domain):
    """Convierte un dominio sobre project_id a dominio sobre aq.ops.project."""
    out = []
    for leaf in domain:
        if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == "project_id":
            out.append(("id", leaf[1], leaf[2]))
        elif isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == "partner_id":
            out.append(("partner_id", leaf[1], leaf[2]))
        else:
            out.append(leaf)
    return out


class OpsRetention(models.AbstractModel):
    _inherit = "aq.ops.engine"

    @api.model
    def cron_daily(self):
        res = super().cron_daily()
        self.apply_retention()
        self.auto_anomalies()
        return res

    @api.model
    def auto_retention(self):
        self.apply_retention(); return 1

    @api.model
    def apply_retention(self):
        """Políticas de retención (parámetros aq_ops.retention_days_*)."""
        icp = self.env["ir.config_parameter"].sudo()
        now = fields.Datetime.now()
        days_n = int(icp.get_param("aq_ops.retention_days_notifications", "365"))
        self.env["aq.ops.notification"].sudo().search([("create_date", "<", now - timedelta(days=days_n)), ("read", "=", True)]).unlink()
        days_a = int(icp.get_param("aq_ops.retention_days_audit", "1825"))
        self.env["aq.portal.audit.log"].sudo().with_context(aq_retention_purge=True).search([("create_date", "<", now - timedelta(days=days_a))]).unlink()
        days_l = int(icp.get_param("aq_ops.retention_days_automation_logs", "180"))
        self.env["aq.ops.automation.log"].sudo().search([("create_date", "<", now - timedelta(days=days_l))]).unlink()
        self.env["aq.portal.session"].sudo().search([("expires", "<", now - timedelta(days=30))]).unlink()
        return True

    @api.model
    def auto_anomalies(self):
        """Detección de anomalías: picos de horas, reprogramaciones repetidas, consumo acelerado, SLA en riesgo."""
        N = self.env["aq.ops.notification"]
        today = fields.Date.today(); n = 0
        TS = self.env["aq.ops.timesheet"]
        for m in self.env["aq.portal.member"].search([("active", "=", True)]):
            last = sum(TS.search([("member_id", "=", m.id), ("date", ">=", today - timedelta(days=7))]).mapped("hours"))
            prev = sum(TS.search([("member_id", "=", m.id), ("date", ">=", today - timedelta(days=35)), ("date", "<", today - timedelta(days=7))]).mapped("hours")) / 4.0
            if prev and last > prev * 1.6 and last > 45:
                N.notify_role(False, ["ops_director"], "riesgo", _("Anomalía: %s registró %.0f h esta semana (promedio %.0f h)") % (m.name, last, prev), "capacity", 0); n += 1
        for i in self.env["aq.ops.item"].search([("reschedule_count", ">=", 3), ("state", "not in", ("cerrado", "cancelado"))]):
            N.notify_role(i.project_id, ["pm"], "riesgo", _("Anomalía: '%s' reprogramado %d veces") % (i.name, i.reschedule_count), "items", i.id); n += 1
        for p in self.env["aq.ops.project"].search([("hours_authorized", ">", 0), ("hours_depletion_forecast", "!=", False)]):
            if p.date_end_current and p.hours_depletion_forecast < p.date_end_current:
                N.notify_role(p, ["pm"], "riesgo", _("Pronóstico: la bolsa de %s se agota el %s, antes del fin planeado (%s)") % (p.name, p.hours_depletion_forecast, p.date_end_current), "projects", p.id); n += 1
        for inc in self.env["aq.ops.incident"].search([("step", "!=", "cerrado"), ("resolved_at", "=", False)]):
            elapsed = (fields.Datetime.now() - inc.reported_at).total_seconds() / 3600.0 if inc.reported_at else 0
            if inc.sla_resolution_hours and elapsed > inc.sla_resolution_hours * 0.8 and not inc.sla_breached:
                N.notify_member(inc.owner_id, "incidente", _("SLA en riesgo (80%%): %s") % inc.name, "incidents", inc.id); n += 1
        return n


class OpsCapacityForecast(models.AbstractModel):
    _inherit = "aq.ops.engine"

    @api.model
    def capacity_forecast(self, member_domain=None, weeks=4):
        """Planeación predictiva de capacidad: carga por persona en las próximas N semanas."""
        today = fields.Date.today()
        out = []
        Cap = self.env["aq.ops.capacity"]
        Item = self.env["aq.ops.item"]
        for m in self.env["aq.portal.member"].search((member_domain or []) + [("active", "=", True)]):
            row = {"member": m.name, "member_id": m.id, "weeks": []}
            for w in range(weeks):
                start = today - timedelta(days=today.weekday()) + timedelta(weeks=w); end = start + timedelta(days=6)
                wk = start.strftime("%G-W%V")
                cap = Cap.search([("member_id", "=", m.id), ("week", "=", wk)], limit=1)
                avail = (cap.hours_available - cap.unavailable_hours) if cap else 40.0
                items = Item.search([("assignee_id", "=", m.id), ("state", "not in", ("cerrado", "cancelado", "aceptado", "liberado", "verificado")), ("date_due", ">=", start), ("date_due", "<=", end)])
                planned = sum((i.remaining_hours or i.estimate_hours) for i in items)
                row["weeks"].append({"week": wk, "available": avail, "planned": planned, "load_pct": round(planned / avail * 100) if avail else 0, "overallocated": planned > avail, "items": len(items)})
            out.append(row)
        return out

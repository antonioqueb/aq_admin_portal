# -*- coding: utf-8 -*-
"""Alphaops · planes/casos/ejecuciones de prueba, aceptación electrónica inmutable, liberaciones con compuerta."""
import hashlib
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OpsTestPlan(models.Model):
    _name = "aq.ops.test.plan"
    _description = "Alphaops: plan de pruebas"
    name = fields.Char(required=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    environment_id = fields.Many2one("aq.ops.environment", string="Ambiente")
    plan_type = fields.Selection([("unitaria", "Unitaria"), ("integracion", "Integración"), ("qa", "QA interno"), ("regresion", "Regresión"), ("uat", "UAT (cliente)")], default="qa")
    case_ids = fields.One2many("aq.ops.test.case", "plan_id", string="Casos")
    state = fields.Selection([("borrador", "Borrador"), ("en_ejecucion", "En ejecución"), ("cerrado", "Cerrado")], default="borrador")
    pass_pct = fields.Float(compute="_compute_pct", string="% aprobado")

    def _compute_pct(self):
        for p in self:
            cases = p.case_ids
            p.pass_pct = (len(cases.filtered(lambda c: c.last_result == "pass")) / len(cases) * 100.0) if cases else 0.0


class OpsTestCase(models.Model):
    _name = "aq.ops.test.case"
    _description = "Alphaops: caso de prueba"
    name = fields.Char(required=True)
    plan_id = fields.Many2one("aq.ops.test.plan", ondelete="cascade")
    project_id = fields.Many2one("aq.ops.project", required=True)
    item_id = fields.Many2one("aq.ops.item", string="Elemento probado")
    steps = fields.Text(string="Pasos")
    expected = fields.Text(string="Resultado esperado")
    department = fields.Char(string="Departamento que valida")
    run_ids = fields.One2many("aq.ops.test.run", "case_id", string="Ejecuciones")
    last_result = fields.Selection([("pass", "Aprobado"), ("fail", "Fallido"), ("blocked", "Bloqueado"), ("pending", "Pendiente")], compute="_compute_last", store=True)
    generated_by_ai = fields.Boolean(readonly=True)
    client_visible = fields.Boolean(default=True)

    @api.depends("run_ids.result")
    def _compute_last(self):
        for c in self:
            last = c.run_ids.sorted("create_date", reverse=True)[:1]
            c.last_result = last.result if last else "pending"


class OpsTestRun(models.Model):
    _name = "aq.ops.test.run"
    _description = "Alphaops: ejecución de prueba"
    _order = "create_date desc"
    case_id = fields.Many2one("aq.ops.test.case", required=True, ondelete="cascade")
    environment_id = fields.Many2one("aq.ops.environment")
    result = fields.Selection([("pass", "Aprobado"), ("fail", "Fallido"), ("blocked", "Bloqueado")], required=True)
    evidence = fields.Text(string="Evidencia")
    executed_by_id = fields.Many2one("aq.portal.member", string="Ejecutó (interno)")
    executed_by_partner_id = fields.Many2one("res.partner", string="Ejecutó (cliente)")
    is_retest = fields.Boolean(string="Reprueba")
    defect_item_id = fields.Many2one("aq.ops.item", string="Defecto registrado", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        runs = super().create(vals_list)
        for r in runs.filtered(lambda x: x.result == "fail" and not x.defect_item_id):
            r.defect_item_id = self.env["aq.ops.item"].create({"name": _("Defecto: %s") % r.case_id.name, "item_type": "defecto", "project_id": r.case_id.project_id.id,
                                                              "parent_id": r.case_id.item_id.id, "found_in": "produccion" if r.environment_id.env_type == "prod" else "interno",
                                                              "state": "por_hacer", "description": r.evidence, "is_rework": True}).id
        return runs


class OpsAcceptance(models.Model):
    """5.9 Aceptación electrónica: aprobado / cambios solicitados / rechazado. Registro inmutable con huella."""
    _name = "aq.ops.acceptance"
    _description = "Alphaops: validación / aceptación"
    _order = "create_date desc"

    project_id = fields.Many2one("aq.ops.project", required=True)
    item_id = fields.Many2one("aq.ops.item", string="Entregable / elemento")
    milestone_id = fields.Many2one("aq.ops.milestone", string="Hito")
    release_id = fields.Many2one("aq.ops.release", string="Liberación")
    validator_partner_id = fields.Many2one("res.partner", string="Validador (cliente)")
    validator_user_id = fields.Many2one("aq.portal.user", string="Usuario que decidió", readonly=True)
    department = fields.Char(string="Departamento / autoridad")
    criteria = fields.Text(string="Criterios de aceptación presentados")
    evidence = fields.Text(string="Evidencia presentada")
    decision = fields.Selection([("pendiente", "Pendiente"), ("aprobado", "Aprobado"), ("cambios", "Cambios solicitados"), ("rechazado", "Rechazado")], default="pendiente")
    reason = fields.Text(string="Motivo / cambios solicitados")
    decided_at = fields.Datetime(readonly=True)
    signature_hash = fields.Char(readonly=True, string="Huella electrónica")
    requested_at = fields.Datetime(default=fields.Datetime.now)
    due_date = fields.Date(string="Responder antes de")
    reassigned_count = fields.Integer(readonly=True)
    client_visible = fields.Boolean(default=True)

    def write(self, vals):
        for a in self:
            if a.decision != "pendiente" and any(k in vals for k in ("decision", "reason", "criteria", "evidence", "validator_partner_id")):
                raise UserError(_("La validación ya fue decidida y es inmutable."))
        return super().write(vals)

    def decide(self, decision, reason, user):
        self.ensure_one()
        if self.decision != "pendiente":
            raise UserError(_("Esta validación ya fue decidida."))
        if decision in ("cambios", "rechazado") and not reason:
            raise UserError(_("Indique el motivo del rechazo o los cambios solicitados."))
        now = fields.Datetime.now()
        payload = json.dumps({"id": self.id, "item": self.item_id.id, "milestone": self.milestone_id.id, "decision": decision, "reason": reason, "user": user.id, "at": str(now)}, sort_keys=True)
        h = hashlib.sha256(payload.encode()).hexdigest()
        super(OpsAcceptance, self).write({"decision": decision, "reason": reason, "decided_at": now, "validator_user_id": user.id, "signature_hash": h})
        if decision == "aprobado":
            if self.item_id:
                self.item_id.write({"accepted": True, "accepted_date": fields.Date.today(), "state": "aceptado"})
                self.env["aq.ops.event"].emit("ops", "deliverable_accepted", self.item_id, {"project": self.project_id.name, "deliverable": self.item_id.name, "date": str(fields.Date.today()), "hash": h})
            if self.milestone_id:
                self.milestone_id.action_validated()
        elif self.item_id:
            self.item_id.write({"state": "correccion", "is_rework": True})
        self.env["aq.ops.notification"].notify_role(self.project_id, ["pm"], "entregable_aceptado" if decision == "aprobado" else "accion_requerida",
                                                     _("Validación %s: %s") % (dict(self._fields["decision"].selection)[decision], self.item_id.name or self.milestone_id.name), "acceptances", self.id)
        return True


class OpsRelease(models.Model):
    """5.10 Liberaciones: ninguna a producción sin respaldo, responsable, pruebas, aprobación, reversión y verificación posterior."""
    _name = "aq.ops.release"
    _description = "Alphaops: liberación"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "planned_at desc"

    name = fields.Char(required=True, string="Versión / paquete", tracking=True)
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    environment_id = fields.Many2one("aq.ops.environment", string="Ambiente destino", required=True)
    env_type = fields.Selection(related="environment_id.env_type", store=True)
    item_ids = fields.One2many("aq.ops.item", "release_id", string="Funcionalidades y correcciones incluidas")
    incident_ids = fields.One2many("aq.ops.incident", "release_id", string="Incidencias derivadas / atendidas")
    owner_id = fields.Many2one("aq.portal.member", string="Responsable del despliegue")
    approvals_required = fields.Text(string="Aprobaciones necesarias")
    approved_by_id = fields.Many2one("aq.portal.user", string="Aprobada por", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    backup_verified = fields.Boolean(string="Respaldo / punto de recuperación verificado", tracking=True)
    backup_ref = fields.Char(string="Referencia del respaldo")
    test_evidence = fields.Text(string="Evidencia de pruebas")
    plan = fields.Text(string="Plan de liberación")
    maintenance_window = fields.Char(string="Ventana de mantenimiento")
    planned_at = fields.Datetime(string="Programada para")
    rollback_plan = fields.Text(string="Plan de reversión")
    deploy_log = fields.Text(string="Bitácora del despliegue")
    deployed_at = fields.Datetime(readonly=True)
    post_verification = fields.Text(string="Validación posterior")
    verified_at = fields.Datetime(readonly=True)
    review_item_id = fields.Many2one("aq.ops.item", string="Revisión post-liberación", readonly=True)
    state = fields.Selection([("candidata", "Candidata"), ("aprobada", "Aprobada"), ("programada", "Programada"), ("desplegada", "Desplegada"),
                              ("verificada", "Verificada"), ("cerrada", "Cerrada"), ("revertida", "Revertida"), ("bloqueada", "Bloqueada (incompleta)")], default="candidata", tracking=True)
    success = fields.Boolean(string="Liberación exitosa", readonly=True)
    client_visible = fields.Boolean(default=True)
    gate_missing = fields.Text(compute="_compute_gate", string="Requisitos faltantes")

    def _gate(self):
        self.ensure_one()
        missing = []
        if self.env_type == "prod":
            if not self.backup_verified: missing.append(_("respaldo o punto de recuperación"))
            if not self.owner_id: missing.append(_("responsable"))
            if not self.test_evidence: missing.append(_("evidencia de pruebas"))
            if not self.approved_by_id: missing.append(_("aprobación"))
            if not self.rollback_plan: missing.append(_("plan de reversión"))
            if any(i.test_case_ids and any(tc.last_result != "pass" for tc in i.test_case_ids) for i in self.item_ids): missing.append(_("casos de prueba fallidos"))
        return missing

    def _compute_gate(self):
        for r in self:
            r.gate_missing = ", ".join(r._gate()) or ""

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"approved_by_id": pu, "approved_at": fields.Datetime.now(), "state": "aprobada"})
        return True

    def action_deploy(self):
        for r in self:
            missing = r._gate()
            if missing:
                r.write({"state": "bloqueada"})
                raise UserError(_("Liberación bloqueada. Falta: %s.") % ", ".join(missing))
            r.write({"state": "desplegada", "deployed_at": fields.Datetime.now()})
            r.environment_id.write({"version": r.name, "last_deploy": fields.Datetime.now()})
            r.item_ids.filtered(lambda i: i.state in ("listo_liberar", "aceptado")).write({"state": "liberado"})
            if not r.review_item_id:
                r.review_item_id = self.env["aq.ops.item"].create({"name": _("Revisión post-liberación %s") % r.name, "item_type": "revision_post_liberacion", "project_id": r.project_id.id,
                                                                  "release_id": r.id, "assignee_id": r.owner_id.id, "date_due": fields.Date.add(fields.Date.today(), days=2), "state": "por_hacer"}).id
        return True

    def action_verify(self):
        for r in self:
            if not r.post_verification:
                raise UserError(_("Documente la validación posterior."))
            r.write({"state": "verificada", "verified_at": fields.Datetime.now(), "success": True})
            r.item_ids.filtered(lambda i: i.state == "liberado").write({"state": "verificado"})
        return True

    def action_rollback(self):
        self.write({"state": "revertida", "success": False})
        return True

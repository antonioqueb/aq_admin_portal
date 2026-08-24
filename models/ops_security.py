# -*- coding: utf-8 -*-
"""Alphaops · identidad compartida, perfiles operativos, MFA, invitaciones, break-glass."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied, UserError

OPS_ROLES = [
    ("platform_owner", "Propietario de plataforma"),
    ("ops_director", "Director de Operaciones / PMO"),
    ("pm", "Project Manager"),
    ("functional_lead", "Líder funcional"),
    ("tech_lead", "Líder técnico"),
    ("consultant", "Consultor funcional"),
    ("developer", "Desarrollador"),
    ("qa", "QA / Tester"),
    ("support", "Soporte / Guardia"),
    ("collaborator", "Colaborador interno"),
    ("partner", "Socio o subcontratista"),
    ("client_sponsor", "Patrocinador del cliente"),
    ("client_po", "Product Owner del cliente"),
    ("client_validator", "Validador departamental"),
    ("client_requester", "Empleado solicitante del cliente"),
    ("observer", "Observador / Auditor"),
    ("admin_liaison", "Enlace administrativo"),
]
FULL_ROLES = {"platform_owner", "ops_director"}
INTERNAL_ROLES = {"pm", "functional_lead", "tech_lead", "consultant", "developer", "qa", "support"}
RESTRICTED_ROLES = {"collaborator", "partner"}
CLIENT_ROLES = {"client_sponsor", "client_po", "client_validator", "client_requester"}
APPROVER_ROLES = FULL_ROLES | {"pm", "functional_lead", "tech_lead", "client_sponsor", "client_po", "client_validator"}
MFA_ROLES = FULL_ROLES | INTERNAL_ROLES | RESTRICTED_ROLES | {"client_sponsor", "client_po", "client_validator"}


def _totp(secret_b32, for_time=None, window=0):
    key = base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))
    counter = int((for_time or time.time()) // 30) + window
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000
    return "%06d" % code


class PortalUserOps(models.Model):
    _inherit = "aq.portal.user"

    # --- selector de aplicación: quién ve qué ---
    has_admin_access = fields.Boolean(string="Acceso a Administración", default=True, tracking=True,
                                      help="El portal administrativo (contratos, facturación, cobranza, legal, RH…).")
    has_ops_access = fields.Boolean(string="Acceso a Operaciones", default=False, tracking=True,
                                    help="Alphaops: proyectos, backlog, calidad, liberaciones, clientes…")
    ops_role = fields.Selection(OPS_ROLES, string="Perfil en Operaciones", tracking=True)
    organization_id = fields.Many2one("res.partner", string="Organización (tenant)", domain=[("is_company", "=", True)],
                                      help="Para usuarios del cliente y socios: limita todo el contenido a esta organización.")
    department = fields.Char(string="Área / departamento (validador)")
    ops_project_ids = fields.Many2many("aq.ops.project", "aq_ops_project_user_rel", "user_id", "project_id",
                                       string="Proyectos asignados expresamente",
                                       help="Colaboradores, socios y usuarios de cliente solo ven estos proyectos (además de su organización).")
    is_external = fields.Boolean(compute="_compute_external", store=True, string="Usuario externo")
    can_export = fields.Boolean(string="Puede exportar datos", default=False, tracking=True)
    invite_expiry = fields.Datetime(string="Caducidad de la invitación externa")
    # --- MFA (TOTP) ---
    mfa_enabled = fields.Boolean(string="MFA activo", tracking=True)
    mfa_secret = fields.Char(groups="base.group_system", copy=False)
    mfa_pending_secret = fields.Char(groups="base.group_system", copy=False)
    mfa_required = fields.Boolean(compute="_compute_external", store=True, string="MFA obligatorio por perfil")
    last_device = fields.Char(string="Último dispositivo", readonly=True)

    @api.depends("ops_role", "role")
    def _compute_external(self):
        for u in self:
            u.is_external = u.ops_role in (CLIENT_ROLES | {"partner"})
            u.mfa_required = bool(u.ops_role in MFA_ROLES)

    def to_public_dict(self):
        d = super().to_public_dict()
        apps = []
        if self.has_admin_access and self.role:
            apps.append("admin")
        if self.has_ops_access and self.ops_role:
            apps.append("ops")
        d.update(apps=apps, ops_role=self.ops_role, organization_id=self.organization_id.id or None,
                 organization_name=self.organization_id.name or None, department=self.department,
                 is_external=self.is_external, can_export=self.can_export, mfa_enabled=self.mfa_enabled,
                 mfa_required=self.mfa_required, project_ids=self.ops_project_ids.ids)
        return d

    # --- revocación inmediata ---
    def write(self, vals):
        res = super().write(vals)
        if vals.get("active") is False or "ops_role" in vals or "role" in vals or "has_ops_access" in vals or "has_admin_access" in vals:
            self.sudo().session_ids.write({"active": False})
        return res

    # --- invitaciones con caducidad ---
    @api.model
    def authenticate(self, login, password, ip=None, user_agent=None):
        user, token = super().authenticate(login, password, ip=ip, user_agent=user_agent)
        if user.is_external and user.invite_expiry and user.invite_expiry < fields.Datetime.now():
            user.sudo().session_ids.write({"active": False})
            raise AccessDenied(_("La invitación externa ha caducado. Solicite una nueva invitación."))
        user.sudo().write({"last_device": (user_agent or "")[:120]})
        return user, token

    # --- MFA ---
    def mfa_begin_setup(self):
        self.ensure_one()
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        self.sudo().write({"mfa_pending_secret": secret})
        issuer = "Alphaqueb"
        return {"secret": secret, "otpauth": "otpauth://totp/%s:%s?secret=%s&issuer=%s&digits=6&period=30" % (issuer, self.login, secret, issuer)}

    def mfa_confirm_setup(self, code):
        self.ensure_one()
        secret = self.sudo().mfa_pending_secret
        if not secret or not self._mfa_check(secret, code):
            raise UserError(_("Código incorrecto. Verifique la hora del dispositivo e intente de nuevo."))
        self.sudo().write({"mfa_secret": secret, "mfa_pending_secret": False, "mfa_enabled": True})
        return True

    def mfa_disable(self):
        self.sudo().write({"mfa_enabled": False, "mfa_secret": False})

    def _mfa_check(self, secret, code):
        code = (code or "").strip().replace(" ", "")
        return any(hmac.compare_digest(_totp(secret, window=w), code) for w in (-1, 0, 1))

    def mfa_verify(self, code):
        self.ensure_one()
        if not self.mfa_enabled:
            return True
        if not self._mfa_check(self.sudo().mfa_secret, code):
            raise AccessDenied(_("Código MFA incorrecto."))
        return True


class BreakGlass(models.Model):
    """Acceso extraordinario con justificación, vigencia y registro."""
    _name = "aq.ops.breakglass"
    _description = "Alphaops: acceso extraordinario (break glass)"
    _order = "create_date desc"

    user_id = fields.Many2one("aq.portal.user", required=True, string="Usuario")
    justification = fields.Text(required=True, string="Justificación")
    granted_role = fields.Selection(OPS_ROLES, required=True, string="Perfil temporal", default="ops_director")
    project_id = fields.Many2one("aq.ops.project", string="Proyecto (opcional)")
    start = fields.Datetime(default=fields.Datetime.now)
    end = fields.Datetime(required=True, string="Vence")
    approved_by_id = fields.Many2one("aq.portal.user", string="Aprobó (propietario de plataforma)")
    state = fields.Selection([("solicitado", "Solicitado"), ("activo", "Activo"), ("vencido", "Vencido"), ("revocado", "Revocado")], default="solicitado")
    actions_log = fields.Text(string="Acciones realizadas", readonly=True)

    @api.model
    def active_for(self, user):
        now = fields.Datetime.now()
        return self.sudo().search([("user_id", "=", user.id), ("state", "=", "activo"), ("start", "<=", now), ("end", ">=", now)], limit=1)

    def action_approve(self):
        pu = self.env.context.get("portal_user_id")
        self.write({"state": "activo", "approved_by_id": pu})
        return True

    def action_revoke(self):
        self.write({"state": "revocado"})
        return True

import hashlib
import logging
import secrets
from datetime import timedelta

from passlib.context import CryptContext

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied, UserError, ValidationError

_logger = logging.getLogger(__name__)
_crypt = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")

ROLES = [
    ("direccion", "Dirección"),
    ("coordinacion", "Coordinación administrativa"),
    ("equipo", "Integrante del equipo"),
    ("consulta", "Solo consulta"),
]
MAX_FAILED = 6
LOCK_MINUTES = 15


def _sha(token):
    return hashlib.sha256(token.encode()).hexdigest()


class PortalUser(models.Model):
    """Usuarios externos del portal. Totalmente independientes de res.users."""
    _name = "aq.portal.user"
    _description = "Portal: usuario externo"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    login = fields.Char(required=True, tracking=True, help="Identificador de acceso (correo o usuario)")
    email = fields.Char(required=True, tracking=True)
    role = fields.Selection(ROLES, required=True, default="consulta", tracking=True, string="Rol")
    active = fields.Boolean(default=True, tracking=True)
    member_id = fields.Many2one("aq.portal.member", string="Integrante del equipo relacionado", ondelete="set null")
    password_hash = fields.Char(copy=False, groups="base.group_system")
    new_password = fields.Char(string="Nueva contraseña", compute="_compute_new_password",
                               inverse="_inverse_new_password", store=False,
                               help="Escriba aquí para establecer/cambiar la contraseña. No se almacena en claro.")
    must_change_password = fields.Boolean(string="Debe cambiar contraseña al ingresar", default=True)
    last_login = fields.Datetime(readonly=True)
    failed_attempts = fields.Integer(readonly=True, default=0)
    locked_until = fields.Datetime(readonly=True)
    reset_token_hash = fields.Char(copy=False, groups="base.group_system")
    reset_token_expiry = fields.Datetime(copy=False, groups="base.group_system")
    session_ids = fields.One2many("aq.portal.session", "user_id", string="Sesiones")
    notify_alerts = fields.Boolean(string="Recibir resumen diario de alertas por correo", default=True)
    timezone = fields.Char(default="America/Mexico_City")

    @api.constrains("login")
    def _check_login_unique(self):
        for rec in self:
            if self.search_count([("login", "=ilike", rec.login), ("id", "!=", rec.id)]):
                raise ValidationError(_("El login '%s' ya está en uso.") % rec.login)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("login"):
                vals["login"] = vals["login"].strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("login"):
            vals["login"] = vals["login"].strip().lower()
        return super().write(vals)

    # ---- contraseñas -------------------------------------------------
    def _compute_new_password(self):
        for rec in self:
            rec.new_password = ""

    def _inverse_new_password(self):
        for rec in self:
            if rec.new_password:
                rec.set_password(rec.new_password)

    @staticmethod
    def _validate_password_strength(password):
        if not password or len(password) < 8:
            raise UserError(_("La contraseña debe tener al menos 8 caracteres."))
        if password.isdigit() or password.isalpha():
            raise UserError(_("La contraseña debe combinar letras y números."))

    def set_password(self, password, must_change=False):
        self._validate_password_strength(password)
        self.sudo().write({
            "password_hash": _crypt.hash(password),
            "must_change_password": must_change,
            "reset_token_hash": False,
            "reset_token_expiry": False,
            "failed_attempts": 0,
            "locked_until": False,
        })
        # cerrar sesiones existentes al cambiar contraseña
        self.sudo().session_ids.write({"active": False})

    def check_password(self, password):
        self.ensure_one()
        h = self.sudo().password_hash
        if not h or not password:
            return False
        try:
            return _crypt.verify(password, h)
        except ValueError:
            return False

    # ---- autenticación -----------------------------------------------
    @api.model
    def authenticate(self, login, password, ip=None, user_agent=None):
        login = (login or "").strip().lower()
        user = self.sudo().search([("login", "=", login), ("active", "=", True)], limit=1)
        if not user:
            raise AccessDenied(_("Usuario o contraseña incorrectos."))
        now = fields.Datetime.now()
        if user.locked_until and user.locked_until > now:
            raise AccessDenied(_("Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde."))
        if not user.check_password(password):
            attempts = user.failed_attempts + 1
            vals = {"failed_attempts": attempts}
            if attempts >= MAX_FAILED:
                vals.update(locked_until=now + timedelta(minutes=LOCK_MINUTES), failed_attempts=0)
            user.write(vals)
            raise AccessDenied(_("Usuario o contraseña incorrectos."))
        user.write({"failed_attempts": 0, "locked_until": False, "last_login": now})
        token = user._create_session(ip=ip, user_agent=user_agent)
        return user, token

    def _create_session(self, ip=None, user_agent=None):
        self.ensure_one()
        token = secrets.token_urlsafe(48)
        ttl_hours = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.session_hours", "12"))
        self.env["aq.portal.session"].sudo().create({
            "user_id": self.id,
            "token_hash": _sha(token),
            "expires": fields.Datetime.now() + timedelta(hours=ttl_hours),
            "ip": ip, "user_agent": (user_agent or "")[:300],
        })
        return token

    @api.model
    def from_token(self, token, allow_pending=False):
        if not token:
            return self.browse()
        Session = self.env["aq.portal.session"].sudo()
        session = Session.search([("token_hash", "=", _sha(token)), ("active", "=", True)], limit=1)
        if not session or session.expires < fields.Datetime.now() or not session.user_id.active:
            return self.browse()
        if session.mfa_pending and not allow_pending:
            return self.browse()
        # extender sesión deslizante cada 10 minutos
        if (fields.Datetime.now() - (session.last_seen or session.create_date)).total_seconds() > 600:
            ttl_hours = int(self.env["ir.config_parameter"].sudo().get_param("aq_admin_portal.session_hours", "12"))
            session.write({"last_seen": fields.Datetime.now(),
                           "expires": fields.Datetime.now() + timedelta(hours=ttl_hours)})
        return session.user_id

    @api.model
    def logout_token(self, token):
        if token:
            self.env["aq.portal.session"].sudo().search(
                [("token_hash", "=", _sha(token))]).write({"active": False})

    # ---- recuperación de contraseña ---------------------------------
    def _portal_base_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("aq_admin_portal.base_url") or icp.get_param("web.base.url")
        path = icp.get_param("aq_admin_portal.portal_path") or "/admin-portal"
        return base.rstrip("/") + path

    def generate_reset_token(self):
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.sudo().write({
            "reset_token_hash": _sha(token),
            "reset_token_expiry": fields.Datetime.now() + timedelta(hours=2),
        })
        return token

    def action_send_reset_email(self):
        for user in self:
            token = user.generate_reset_token()
            link = "%s/reset-password?token=%s" % (user._portal_base_url(), token)
            template = self.env.ref("aq_admin_portal.mail_template_portal_reset", raise_if_not_found=False)
            if template:
                template.sudo().with_context(reset_link=link).send_mail(user.id, force_send=True)
            else:
                Brand = self.env["aq.portal.branding"]
                self.env["mail.mail"].sudo().create({
                    "subject": _("Restablecer contraseña · Portal Alphaqueb"), "email_to": user.email,
                    "body_html": Brand.wrap(_("Acceso al portal"), _("<p>Hola %s,</p><p>Usa el botón para establecer tu contraseña. El enlace vence en 2 horas.</p>") % user.name,
                                            _("Establecer contraseña"), link),
                }).send()
            _logger.info("Enlace de restablecimiento enviado a %s", user.email)
        return True

    @api.model
    def request_reset(self, login_or_email):
        value = (login_or_email or "").strip().lower()
        user = self.sudo().search(["|", ("login", "=", value), ("email", "=ilike", value), ("active", "=", True)], limit=1)
        if user:
            user.action_send_reset_email()
        # siempre responde igual para no revelar existencia de cuentas
        return True

    @api.model
    def reset_with_token(self, token, new_password):
        user = self.sudo().search([("reset_token_hash", "=", _sha(token or "")), ("active", "=", True)], limit=1)
        if not user or not user.reset_token_expiry or user.reset_token_expiry < fields.Datetime.now():
            raise UserError(_("El enlace de restablecimiento no es válido o ya venció."))
        user.set_password(new_password)
        return user

    def action_create_welcome(self):
        """Crea un token de restablecimiento y envía correo de bienvenida para fijar contraseña."""
        return self.action_send_reset_email()

    def action_close_sessions(self):
        self.sudo().session_ids.write({"active": False})
        return True

    def to_public_dict(self):
        self.ensure_one()
        return {
            "id": self.id, "name": self.name, "login": self.login, "email": self.email,
            "role": self.role, "member_id": self.member_id.id or None,
            "member_name": self.member_id.name or None,
            "must_change_password": self.must_change_password,
            "last_login": fields.Datetime.to_string(self.last_login) if self.last_login else None,
            "active": self.active, "notify_alerts": self.notify_alerts,
        }


class PortalSession(models.Model):
    _name = "aq.portal.session"
    _description = "Portal: sesión"
    _order = "create_date desc"

    user_id = fields.Many2one("aq.portal.user", required=True, ondelete="cascade", index=True)
    token_hash = fields.Char(required=True, index=True)
    expires = fields.Datetime(required=True)
    last_seen = fields.Datetime()
    ip = fields.Char()
    user_agent = fields.Char()
    active = fields.Boolean(default=True)
    mfa_pending = fields.Boolean(string="Pendiente de MFA")

    @api.model
    def _gc_sessions(self):
        self.sudo().search([("expires", "<", fields.Datetime.now() - timedelta(days=7))]).unlink()

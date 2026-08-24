# -*- coding: utf-8 -*-
"""OAuth 2.0 con Google y endpoints de la integración (Administración y Operaciones)."""
import json
import secrets

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request

from .api import API, portal_route, _json, _error, _body, _log, _serialize, _prepare_vals
from .ops_api import _effective_role, _cfg as _ops_cfg, _fields as _ops_fields, _get as _ops_get
from .ops_registry import OPS_RESOURCES

STATE_KEY = "aq_google.oauth_state"


class GoogleController(http.Controller):

    @http.route("/aq_portal/google/auth", type="http", auth="public", csrf=False)
    def google_auth(self, token=None, **kw):
        user = request.env["aq.portal.user"].sudo().from_token(token)
        if not user or not (user.role == "direccion" or user.ops_role == "platform_owner"):
            return request.make_response(_("Solo Dirección o el propietario de plataforma pueden conectar Google."), status=403)
        state = secrets.token_urlsafe(24)
        request.env["ir.config_parameter"].sudo().set_param(STATE_KEY, json.dumps({"state": state, "user": user.id}))
        return request.redirect(request.env["aq.google.account"].sudo().auth_url(state), local=False)

    @http.route("/aq_portal/google/callback", type="http", auth="public", csrf=False)
    def google_callback(self, code=None, state=None, error=None, **kw):
        base = request.env["aq.portal.user"].sudo()._portal_base_url()
        if error or not code:
            return request.redirect(base + "/ops/google?error=" + (error or "sin_codigo"))
        try:
            saved = json.loads(request.env["ir.config_parameter"].sudo().get_param(STATE_KEY) or "{}")
        except Exception:
            saved = {}
        if not saved or saved.get("state") != state:
            return request.make_response(_("Estado OAuth inválido; reinicie la conexión."), status=400)
        user = request.env["aq.portal.user"].sudo().browse(saved.get("user"))
        try:
            acc = request.env["aq.google.account"].sudo().exchange_code(code, user)
        except UserError as e:
            return request.redirect(base + "/ops/google?error=" + str(e.args[0])[:120])
        request.env["ir.config_parameter"].sudo().set_param(STATE_KEY, "")
        _log(user, "action", resource="google", model="aq.google.account", res_id=acc.id, summary=_("Google conectado: %s") % acc.email)
        return request.redirect(base + "/ops/google?connected=1")


class GoogleApi(http.Controller):

    def _status(self):
        accs = request.env["aq.google.account"].sudo().search([])
        return {"accounts": [{"id": a.id, "name": a.name, "email": a.email, "state": a.state, "last_error": a.last_error, "last_gmail_sync": str(a.last_gmail_sync or ""), "last_calendar_sync": str(a.last_calendar_sync or ""),
                              "last_meet_sync": str(a.last_meet_sync or ""), "last_drive_sync": str(a.last_drive_sync or ""), "messages": a.messages_count, "sync_gmail": a.sync_gmail, "sync_calendar": a.sync_calendar,
                              "sync_meet": a.sync_meet, "sync_drive": a.sync_drive, "gmail_query": a.gmail_query} for a in accs],
                "client_id_configured": bool(request.env["aq.google.account"].sudo().env["ir.config_parameter"].sudo().get_param("GOOGLE_CLIENT_ID") or __import__("os").environ.get("GOOGLE_CLIENT_ID")),
                "client_secret_configured": bool(request.env["ir.config_parameter"].sudo().get_param("GOOGLE_CLIENT_SECRET") or __import__("os").environ.get("GOOGLE_CLIENT_SECRET")),
                "pending": {"ops": request.env["aq.google.message"].sudo().search_count([("app", "=", "ops"), ("state", "=", "nuevo")]), "admin": request.env["aq.google.message"].sudo().search_count([("app", "=", "admin"), ("state", "=", "nuevo")])}}

    @portal_route(API + "/google/status", methods=["GET"], app=None)
    def status(self, user):
        return _json(self._status())

    @portal_route(API + "/google/auth-url", methods=["GET"], app=None)
    def auth_url(self, user):
        if not (user.role == "direccion" or user.ops_role == "platform_owner"):
            return _error(_("Solo Dirección / propietario de plataforma"), 403)
        from .api import _token
        return _json({"url": "/aq_portal/google/auth?token=%s" % _token()})

    @portal_route(API + "/google/sync", methods=["POST"], app=None)
    def sync(self, user):
        if not (user.role in ("direccion", "coordinacion") or user.ops_role in ("platform_owner", "ops_director", "pm")):
            return _error(_("Sin permiso"), 403)
        try:
            days = int((_body() or {}).get("days") or 0) or None
        except Exception:
            days = None
        if days:
            days = min(days, 90)
        Sync = request.env["aq.google.sync"].sudo().with_context(portal_user_id=user.id, aq_gmail_days=days)
        for a in request.env["aq.google.account"].sudo().search([("state", "in", ("conectada", "error"))]):
            Sync.sync_account(a)
        Sync.cron_autoprocess()
        _log(user, "action", resource="google", summary=_("Sincronización manual de Google") + (_(" (últimos %d días)") % days if days else ""))
        return _json(self._status())

    @portal_route(API + "/google/accounts/<int:aid>", methods=["PUT"], app=None)
    def account_write(self, user, aid):
        if not (user.role == "direccion" or user.ops_role == "platform_owner"):
            return _error(_("Sin permiso"), 403)
        a = request.env["aq.google.account"].sudo().browse(aid).exists()
        b = _body()
        a.write({k: b[k] for k in ("sync_gmail", "sync_calendar", "sync_meet", "sync_drive", "gmail_query", "gmail_label_done", "drive_folder_name", "name") if k in b})
        if b.get("disconnect"):
            a.action_disconnect()
        return _json(self._status())

    @portal_route(API + "/google/export/portfolio", methods=["POST"], app="ops")
    def export_portfolio(self, user):
        if _effective_role(user) not in ("platform_owner", "ops_director", "pm"):
            return _error(_("Sin permiso"), 403)
        url = request.env["aq.google.sync"].sudo().export_portfolio_sheet()
        _log(user, "action", resource="google", summary=_("Portafolio exportado a Sheets"))
        return _json({"url": url})

    @portal_route(API + "/google/meetings/<int:mid>/doc", methods=["POST"], app="ops")
    def meeting_doc(self, user, mid):
        m = _ops_get(OPS_RESOURCES["meetings"], user, mid, "write")
        m.with_context(portal_user_id=user.id).action_create_google_doc()
        return _json({"url": m.google_doc_url})

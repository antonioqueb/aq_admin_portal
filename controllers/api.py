# -*- coding: utf-8 -*-
import base64
import functools
import json
import logging
from datetime import date, datetime, timedelta

from odoo import fields, http, _
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request

from .registry import RESOURCES, SECTIONS, COMMON_HIDDEN, NAME_SEARCH_MODELS, NAME_SEARCH_DOMAINS, resource_for_model

_logger = logging.getLogger(__name__)
API = "/aq_portal/api"


# --------------------------------------------------------------------------- helpers
def _json(data, status=200):
    return request.make_json_response(data, status=status)


def _error(message, status=400, code=None):
    request.env.cr.rollback()
    return _json({"error": message, "code": code or status}, status=status)


def _body():
    raw = request.httprequest.get_data()
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _token():
    auth = request.httprequest.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.params.get("token") or request.httprequest.cookies.get("aq_portal_token")


def _user():
    return request.env["aq.portal.user"].sudo().from_token(_token())


def _ip():
    return request.httprequest.remote_addr


def _log(user, action, **kw):
    request.env["aq.portal.audit.log"].sudo().log(user, action, ip=_ip(), **kw)


def portal_route(path, methods=("GET",), auth_required=True, roles=None):
    """Decorador: ruta HTTP JSON pública con autenticación por token del portal."""
    def decorator(func):
        @http.route(path, type="http", auth="public", csrf=False, methods=list(methods) + ["OPTIONS"], cors="*", save_session=False)
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if request.httprequest.method == "OPTIONS":
                return request.make_response("", headers=[("Access-Control-Allow-Headers", "Authorization, Content-Type")])
            user = request.env["aq.portal.user"].sudo()
            if auth_required:
                user = _user()
                if not user:
                    return _json({"error": _("Sesión no válida o expirada."), "code": 401}, status=401)
                if roles and user.role not in roles:
                    _log(user, "denied", summary="%s %s" % (request.httprequest.method, path))
                    return _json({"error": _("No tiene permisos para esta operación."), "code": 403}, status=403)
            try:
                return func(self, user, *args, **kwargs)
            except AccessDenied as e:
                return _error(str(e.args[0]) if e.args else _("Acceso denegado"), 401)
            except (AccessError,) as e:
                return _error(str(e.args[0]) if e.args else _("Acceso denegado"), 403)
            except (UserError, ValidationError) as e:
                return _error(str(e.args[0]) if e.args else str(e), 400)
            except Exception as e:  # noqa
                _logger.exception("Error en API del portal")
                return _error(_("Error interno: %s") % e, 500)
        return wrapper
    return decorator


def _serialize_value(rec, fname, finfo):
    val = rec[fname]
    ftype = finfo["type"]
    if ftype == "many2one":
        return {"id": val.id, "name": val.display_name} if val else None
    if ftype in ("one2many", "many2many"):
        return [{"id": r.id, "name": r.display_name} for r in val]
    if ftype == "date":
        return fields.Date.to_string(val) if val else None
    if ftype == "datetime":
        return fields.Datetime.to_string(val) if val else None
    if ftype == "binary":
        return None
    if ftype in ("float", "monetary"):
        return float(val or 0.0)
    if ftype == "integer":
        return int(val or 0)
    if ftype == "boolean":
        return bool(val)
    return val if val is not False else None


def _field_list(model, resource):
    Model = request.env[model].sudo()
    cfg = RESOURCES.get(resource) or {}
    only = cfg.get("only_fields")
    info = Model.fields_get(only) if only else Model.fields_get()
    hidden = COMMON_HIDDEN
    return {k: v for k, v in info.items() if k not in hidden and (not only or k in only)}


def _serialize(rec, finfo_map, fnames=None):
    data = {"id": rec.id, "display_name": rec.display_name}
    for fname in (fnames or finfo_map.keys()):
        finfo = finfo_map.get(fname)
        if finfo:
            data[fname] = _serialize_value(rec, fname, finfo)
    return data


def _prepare_vals(model, vals, user, resource_cfg, create=False):
    Model = request.env[model].sudo()
    info = Model.fields_get()
    out = {}
    direction_fields = set(resource_cfg.get("direction_fields", []))
    for k, v in (vals or {}).items():
        if k not in info or k in COMMON_HIDDEN:
            continue
        finfo = info[k]
        if finfo.get("readonly"):
            # campos readonly (computados / controlados por acciones) no se escriben directo
            continue
        if k in direction_fields and user.role != "direccion":
            raise AccessError(_("El campo '%s' solo puede modificarlo Dirección.") % finfo["string"])
        t = finfo["type"]
        if t == "many2one":
            if isinstance(v, dict):
                v = v.get("id")
            out[k] = int(v) if v else False
        elif t in ("many2many", "one2many"):
            if t == "one2many":
                continue
            ids = [x["id"] if isinstance(x, dict) else int(x) for x in (v or [])]
            out[k] = [(6, 0, ids)]
        elif t in ("date", "datetime"):
            out[k] = v or False
        elif t in ("float", "monetary"):
            out[k] = float(v) if v not in (None, "") else 0.0
        elif t == "integer":
            out[k] = int(v) if v not in (None, "") else 0
        elif t == "boolean":
            out[k] = bool(v)
        elif t == "selection":
            out[k] = v or False
        else:
            out[k] = v if v is not None else False
    return out


def _cfg(resource):
    cfg = RESOURCES.get(resource)
    if not cfg:
        raise UserError(_("Recurso desconocido: %s") % resource)
    return cfg


def _check(cfg, op, user):
    allowed = cfg.get("roles", {}).get(op, [])
    if user.role not in allowed:
        raise AccessError(_("Su rol (%s) no permite '%s' en %s.") % (user.role, op, cfg["label"]))


def _build_domain(model, params, resource=None):
    Model = request.env[model].sudo()
    info = Model.fields_get()
    domain = list((RESOURCES.get(resource) or {}).get("domain", []))
    search = params.get("search")
    if search:
        name_field = Model._rec_name or "name"
        text_fields = [f for f in ("name", "invoice_number", "description", "concept", "service", "entity", "contact_name") if f in info and info[f]["type"] in ("char", "text")]
        if name_field in info and name_field not in text_fields:
            text_fields.insert(0, name_field)
        sub = []
        for f in text_fields:
            sub.append((f, "ilike", search))
        if "partner_id" in info:
            sub.append(("partner_id.name", "ilike", search))
        if sub:
            domain += ["|"] * (len(sub) - 1) + sub
    filters = params.get("filters")
    if filters:
        try:
            filters = json.loads(filters) if isinstance(filters, str) else filters
        except Exception:
            filters = {}
        for k, v in filters.items():
            if k not in info or v in (None, "", []):
                continue
            t = info[k]["type"]
            if t == "boolean":
                domain.append((k, "=", v in (True, "true", "1", 1)))
            elif isinstance(v, list):
                domain.append((k, "in", v))
            elif t == "many2one":
                domain.append((k, "=", int(v)))
            else:
                domain.append((k, "=", v))
    extra = params.get("domain")
    if extra:
        try:
            extra = json.loads(extra) if isinstance(extra, str) else extra
            for leaf in extra:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3:
                    fname = leaf[0].split(".")[0]
                    if fname not in info:
                        raise UserError(_("Campo no permitido en dominio: %s") % leaf[0])
            domain += [tuple(l) if isinstance(l, list) else l for l in extra]
        except UserError:
            raise
        except Exception:
            pass
    if "active" in info and not params.get("include_archived"):
        domain.append(("active", "=", True))
    return domain


class PortalApi(http.Controller):

    # ------------------------------------------------------------------ auth
    @portal_route(API + "/auth/login", methods=["POST"], auth_required=False)
    def login(self, _u):
        body = _body()
        User = request.env["aq.portal.user"].sudo()
        try:
            user, token = User.authenticate(body.get("login"), body.get("password"), ip=_ip(),
                                            user_agent=request.httprequest.headers.get("User-Agent"))
        except AccessDenied as e:
            request.env.cr.commit()  # persistir contador de intentos fallidos
            return _json({"error": str(e.args[0]) if e.args else _("Acceso denegado"), "code": 401}, status=401)
        _log(user, "login", summary=_("Inicio de sesión"))
        return _json({"token": token, "user": user.to_public_dict()})

    @portal_route(API + "/auth/logout", methods=["POST"])
    def logout(self, user):
        request.env["aq.portal.user"].sudo().logout_token(_token())
        _log(user, "logout", summary=_("Cierre de sesión"))
        return _json({"ok": True})

    @portal_route(API + "/auth/me", methods=["GET"])
    def me(self, user):
        return _json({"user": user.to_public_dict()})

    @portal_route(API + "/auth/forgot", methods=["POST"], auth_required=False)
    def forgot(self, _u):
        body = _body()
        request.env["aq.portal.user"].sudo().request_reset(body.get("login"))
        return _json({"ok": True, "message": _("Si la cuenta existe, se envió un correo con instrucciones.")})

    @portal_route(API + "/auth/reset", methods=["POST"], auth_required=False)
    def reset(self, _u):
        body = _body()
        user = request.env["aq.portal.user"].sudo().reset_with_token(body.get("token"), body.get("password"))
        _log(user, "write", summary=_("Contraseña restablecida con enlace"))
        return _json({"ok": True})

    @portal_route(API + "/auth/change-password", methods=["POST"])
    def change_password(self, user):
        body = _body()
        if not user.check_password(body.get("current") or ""):
            raise UserError(_("La contraseña actual no es correcta."))
        user.set_password(body.get("password"))
        token = user._create_session(ip=_ip(), user_agent=request.httprequest.headers.get("User-Agent"))
        _log(user, "write", summary=_("Cambio de contraseña"))
        return _json({"ok": True, "token": token})

    # ------------------------------------------------------------------ schema
    @portal_route(API + "/schema", methods=["GET"])
    def schema(self, user):
        out = {"sections": SECTIONS, "resources": {}, "role": user.role}
        for key, cfg in RESOURCES.items():
            if user.role not in cfg["roles"].get("read", []):
                continue
            info = _field_list(cfg["model"], key)
            fields_out = {}
            for fname, f in info.items():
                fo = {"name": fname, "string": f.get("string"), "type": f["type"], "required": bool(f.get("required")),
                      "readonly": bool(f.get("readonly")), "help": f.get("help")}
                if f["type"] == "selection":
                    fo["selection"] = [list(x) for x in (f.get("selection") or [])]
                if f["type"] in ("many2one", "many2many", "one2many"):
                    fo["relation"] = f.get("relation")
                    fo["relation_resource"] = resource_for_model(f.get("relation"))
                if fname in cfg.get("direction_fields", []):
                    fo["direction_only"] = True
                fields_out[fname] = fo
            out["resources"][key] = {
                "key": key, "model": cfg["model"], "label": cfg["label"], "singular": cfg.get("singular"), "section": cfg.get("section"),
                "icon": cfg.get("icon"), "order": cfg.get("order", 100), "list": cfg.get("list", []), "filters": cfg.get("filters", []),
                "groups": cfg.get("groups", []), "tabs": cfg.get("tabs", []), "attachments": cfg.get("attachments", False),
                "chatter": cfg.get("chatter", False), "sensitive": cfg.get("sensitive", False),
                "actions": [a for a in cfg.get("actions", []) if user.role in a.get("roles", [])],
                "can": {op: user.role in r for op, r in cfg["roles"].items()}, "fields": fields_out,
            }
        return _json(out)

    # ------------------------------------------------------------------ CRUD genérico
    @portal_route(API + "/r/<string:resource>", methods=["GET"])
    def list_records(self, user, resource):
        cfg = _cfg(resource)
        _check(cfg, "read", user)
        Model = request.env[cfg["model"]].sudo()
        params = request.params
        domain = _build_domain(cfg["model"], params, resource)
        limit = min(int(params.get("limit", 80)), 500)
        offset = int(params.get("offset", 0))
        order = params.get("order") or None
        if order:
            # solo se permite ordenar por campos almacenados
            parts = []
            for piece in order.split(","):
                fname = piece.strip().split(" ")[0]
                fld = Model._fields.get(fname)
                if fld and fld.store:
                    parts.append(piece.strip())
            order = ", ".join(parts) or None
        info = _field_list(cfg["model"], resource)
        fnames = params.get("fields")
        fnames = fnames.split(",") if fnames else (cfg.get("list", []) + ["id"])
        fnames = [f for f in fnames if f in info]
        recs = Model.search(domain, limit=limit, offset=offset, order=order)
        total = Model.search_count(domain)
        return _json({"records": [_serialize(r, info, fnames) for r in recs], "total": total, "limit": limit, "offset": offset})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>", methods=["GET"])
    def get_record(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "read", user)
        rec = request.env[cfg["model"]].sudo().browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        info = _field_list(cfg["model"], resource)
        return _json({"record": _serialize(rec, info)})

    @portal_route(API + "/r/<string:resource>", methods=["POST"])
    def create_record(self, user, resource):
        cfg = _cfg(resource)
        _check(cfg, "create", user)
        body = _body()
        vals = dict(cfg.get("defaults", {}), **_prepare_vals(cfg["model"], body, user, cfg, create=True))
        rec = request.env[cfg["model"]].sudo().with_context(portal_user_id=user.id).create(vals)
        _log(user, "create", resource=resource, model=cfg["model"], res_id=rec.id, summary=rec.display_name, changes=body)
        info = _field_list(cfg["model"], resource)
        return _json({"record": _serialize(rec, info)}, status=201)

    @portal_route(API + "/r/<string:resource>/<int:rec_id>", methods=["PUT", "PATCH"])
    def write_record(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "write", user)
        rec = request.env[cfg["model"]].sudo().with_context(portal_user_id=user.id).browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        body = _body()
        vals = _prepare_vals(cfg["model"], body, user, cfg)
        if vals:
            rec.write(vals)
            _log(user, "write", resource=resource, model=cfg["model"], res_id=rec.id, summary=rec.display_name, changes=body)
        info = _field_list(cfg["model"], resource)
        return _json({"record": _serialize(rec, info)})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>", methods=["DELETE"])
    def delete_record(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "delete", user)
        rec = request.env[cfg["model"]].sudo().with_context(portal_user_id=user.id).browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        name = rec.display_name
        if cfg.get("sensitive") or "active" in rec._fields:
            # Documentos y expedientes sensibles no se eliminan: se archivan.
            if "active" in rec._fields:
                rec.write({"active": False})
            else:
                raise UserError(_("Este registro es sensible y no puede eliminarse; contacte a Dirección."))
        else:
            rec.unlink()
        _log(user, "unlink", resource=resource, model=cfg["model"], res_id=rec_id, summary=name)
        return _json({"ok": True})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>/action/<string:action>", methods=["POST"])
    def run_action(self, user, resource, rec_id, action):
        cfg = _cfg(resource)
        allowed = [a for a in cfg.get("actions", []) if a["name"] == action]
        if not allowed:
            return _error(_("Acción no permitida"), 403)
        if user.role not in allowed[0].get("roles", []):
            _log(user, "denied", resource=resource, res_id=rec_id, summary=action)
            return _error(_("Su rol no permite ejecutar '%s'.") % allowed[0]["label"], 403)
        rec = request.env[cfg["model"]].sudo().with_context(portal_user_id=user.id).browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        getattr(rec, action)()
        _log(user, "action", resource=resource, model=cfg["model"], res_id=rec.id, summary="%s: %s" % (allowed[0]["label"], rec.display_name))
        info = _field_list(cfg["model"], resource)
        return _json({"record": _serialize(rec, info)})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>/messages", methods=["GET"])
    def messages(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "read", user)
        out = []
        if cfg.get("chatter"):
            msgs = request.env["mail.message"].sudo().search([("model", "=", cfg["model"]), ("res_id", "=", rec_id)], order="date desc", limit=100)
            for m in msgs:
                changes = [{"field": t.field_id.field_description, "old": t.old_value_char or t.old_value_text or (t.old_value_float if t.old_value_float else "") or "",
                            "new": t.new_value_char or t.new_value_text or (t.new_value_float if t.new_value_float else "") or ""} for t in m.tracking_value_ids]
                out.append({"id": m.id, "date": fields.Datetime.to_string(m.date), "body": m.body or "", "author": m.author_id.name or m.email_from or "Sistema",
                            "tracking": changes})
        logs = request.env["aq.portal.audit.log"].sudo().search([("res_model", "=", cfg["model"]), ("res_id", "=", rec_id)], limit=100)
        audit = [{"id": l.id, "date": fields.Datetime.to_string(l.create_date), "user": l.user_id.name, "action": l.action, "summary": l.summary, "changes": l.changes} for l in logs]
        return _json({"messages": out, "audit": audit})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>/note", methods=["POST"])
    def post_note(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "read", user)
        body = _body()
        rec = request.env[cfg["model"]].sudo().browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        text = (body.get("body") or "").strip()
        if not text:
            raise UserError(_("La nota está vacía."))
        if cfg.get("chatter"):
            rec.message_post(body="<b>%s</b> (portal): %s" % (user.name, text), message_type="comment")
        _log(user, "write", resource=resource, model=cfg["model"], res_id=rec.id, summary=_("Nota: %s") % text[:120])
        if hasattr(rec, "portal_touch"):
            rec.with_context(portal_user_id=user.id).portal_touch()
        return _json({"ok": True})

    # ------------------------------------------------------------------ adjuntos
    @portal_route(API + "/r/<string:resource>/<int:rec_id>/attachments", methods=["GET"])
    def list_attachments(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "read", user)
        atts = request.env["ir.attachment"].sudo().search([("res_model", "=", cfg["model"]), ("res_id", "=", rec_id)], order="create_date desc")
        return _json({"attachments": [{"id": a.id, "name": a.name, "mimetype": a.mimetype, "size": a.file_size,
                                       "date": fields.Datetime.to_string(a.create_date), "url": "%s/attachments/%d/download" % (API, a.id)} for a in atts]})

    @portal_route(API + "/r/<string:resource>/<int:rec_id>/attachments", methods=["POST"])
    def upload_attachment(self, user, resource, rec_id):
        cfg = _cfg(resource)
        _check(cfg, "write", user)
        rec = request.env[cfg["model"]].sudo().browse(rec_id).exists()
        if not rec:
            return _error(_("Registro no encontrado"), 404)
        files = request.httprequest.files.getlist("file")
        created = []
        Att = request.env["ir.attachment"].sudo()
        if files:
            for f in files:
                created.append(Att.create({"name": f.filename, "datas": base64.b64encode(f.read()), "res_model": cfg["model"], "res_id": rec_id, "mimetype": f.mimetype}))
        else:
            body = _body()
            if body.get("name") and body.get("data"):
                created.append(Att.create({"name": body["name"], "datas": body["data"], "res_model": cfg["model"], "res_id": rec_id}))
        for a in created:
            _log(user, "upload", resource=resource, model=cfg["model"], res_id=rec_id, summary=a.name)
        return _json({"attachments": [{"id": a.id, "name": a.name, "url": "%s/attachments/%d/download" % (API, a.id)} for a in created]}, status=201)

    @portal_route(API + "/attachments/<int:att_id>/download", methods=["GET"])
    def download_attachment(self, user, att_id):
        att = request.env["ir.attachment"].sudo().browse(att_id).exists()
        if not att:
            return _error(_("Archivo no encontrado"), 404)
        resource = resource_for_model(att.res_model)
        if not resource or user.role not in RESOURCES[resource]["roles"]["read"]:
            return _error(_("Sin permiso para este archivo"), 403)
        data = base64.b64decode(att.datas or b"")
        return request.make_response(data, headers=[("Content-Type", att.mimetype or "application/octet-stream"),
                                                    ("Content-Disposition", http.content_disposition(att.name))])

    @portal_route(API + "/attachments/<int:att_id>", methods=["DELETE"], roles=["direccion", "coordinacion"])
    def delete_attachment(self, user, att_id):
        att = request.env["ir.attachment"].sudo().browse(att_id).exists()
        if att:
            resource = resource_for_model(att.res_model)
            if resource and RESOURCES[resource].get("sensitive") and user.role != "direccion":
                raise AccessError(_("Los archivos de expedientes sensibles solo los elimina Dirección."))
            _log(user, "unlink", resource=resource, model=att.res_model, res_id=att.res_id, summary=_("Archivo eliminado: %s") % att.name)
            att.unlink()
        return _json({"ok": True})

    @portal_route(API + "/documents/suggest-name", methods=["GET"])
    def suggest_name(self, user):
        p = request.params
        d = fields.Date.to_date(p.get("date")) if p.get("date") else None
        name = request.env["aq.portal.document"].sudo().suggest_name(p.get("doc_type"), p.get("counterparty"), p.get("version") or "v1", d)
        return _json({"name": name})

    # ------------------------------------------------------------------ búsquedas
    @portal_route(API + "/name_search", methods=["GET"])
    def name_search(self, user):
        model = request.params.get("model")
        if model not in NAME_SEARCH_MODELS:
            return _error(_("Modelo no permitido"), 403)
        q = request.params.get("q") or ""
        domain = list(NAME_SEARCH_DOMAINS.get(model, []))
        Model = request.env[model].sudo()
        if "active" in Model._fields:
            domain.append(("active", "=", True))
        res = Model.name_search(q, args=domain, limit=int(request.params.get("limit", 20)))
        return _json({"results": [{"id": r[0], "name": r[1]} for r in res]})

    # ------------------------------------------------------------------ tablero / calendario
    @portal_route(API + "/dashboard", methods=["GET"])
    def dashboard(self, user):
        p = request.params
        df = fields.Date.to_date(p.get("from")) if p.get("from") else None
        dt = fields.Date.to_date(p.get("to")) if p.get("to") else None
        return _json(request.env["aq.portal.report"].sudo().dashboard_data(df, dt))

    @portal_route(API + "/calendar", methods=["GET"])
    def calendar(self, user):
        p = request.params
        today = fields.Date.today()
        df = fields.Date.to_date(p.get("from")) if p.get("from") else today - timedelta(days=7)
        dt = fields.Date.to_date(p.get("to")) if p.get("to") else today + timedelta(days=45)
        env = request.env
        ev = []

        def add(d, title, kind, resource, rid, responsible=None, amount=None, state=None):
            ev.append({"date": fields.Date.to_string(d), "title": title, "kind": kind, "resource": resource, "id": rid,
                       "responsible": responsible, "amount": amount, "state": state})

        for o in env["aq.portal.obligation"].sudo().search([("date", ">=", df), ("date", "<=", dt), ("state", "!=", "cancelada")]):
            add(o.date, o.name, "obligacion:" + o.obligation_type, "obligations", o.id, o.responsible_id.name, None, o.state)
        for i in env["aq.portal.invoice.schedule"].sudo().search([("scheduled_date", ">=", df), ("scheduled_date", "<=", dt), ("state", "!=", "cancelada")]):
            add(i.scheduled_date, _("Facturar: %s (%s)") % (i.name, i.partner_id.name), "facturacion", "invoices", i.id, i.issuer_id.name, i.amount_total, i.state)
        for r in env["aq.portal.receivable"].sudo().search([("due_date", ">=", df), ("due_date", "<=", dt), ("state", "!=", "pagada")]):
            add(r.due_date, _("Vence cobro: %s (%s)") % (r.invoice_number, r.partner_id.name), "cobranza", "receivables", r.id, r.responsible_id.name, r.balance, r.state)
            if r.promised_payment_date and df <= r.promised_payment_date <= dt:
                add(r.promised_payment_date, _("Compromiso de pago: %s") % r.partner_id.name, "compromiso_pago", "receivables", r.id, r.responsible_id.name, r.balance, r.promise_state)
        for y in env["aq.portal.payable"].sudo().search([("due_date", ">=", df), ("due_date", "<=", dt), ("payment_state", "in", ("programado", "vencido"))]):
            add(y.due_date, _("Pagar: %s") % y.name, "pago", "payables", y.id, None, y.amount, y.payment_state)
        for a in env["aq.portal.agreement"].sudo().search([("due_date", ">=", df), ("due_date", "<=", dt), ("state", "not in", ("cerrado", "cancelado"))]):
            add(a.due_date, _("Pendiente: %s") % a.name, "pendiente", "agreements", a.id, a.executor_id.name, None, a.state)
        for p_ in env["aq.portal.project"].sudo().search([("next_action_date", ">=", df), ("next_action_date", "<=", dt)]):
            add(p_.next_action_date, _("%s: %s") % (p_.name, p_.next_action or _("siguiente acción")), "proyecto", "projects", p_.id, p_.next_action_responsible_id.name)
        for d in env["aq.portal.project.date"].sudo().search([("date", ">=", df), ("date", "<=", dt)]):
            add(d.date, _("%s: %s") % (d.project_id.name, d.name), "fecha_proyecto:" + (d.date_type or ""), "projects", d.project_id.id, d.responsible_id.name, None, "done" if d.done else "pendiente")
        for d in env["aq.portal.deliverable"].sudo().search([("due_date", ">=", df), ("due_date", "<=", dt), ("accepted", "=", False)]):
            add(d.due_date, _("Entregable: %s (%s)") % (d.name, d.project_id.name), "entregable", "deliverables", d.id, d.responsible_id.name, None, d.state)
        for pr in env["aq.portal.prospect"].sudo().search([("followup_date", ">=", df), ("followup_date", "<=", dt), ("stage", "not in", ("ganado", "perdido"))]):
            add(pr.followup_date, _("Prospecto: %s – %s") % (pr.name, pr.next_action or ""), "prospecto", "prospects", pr.id, pr.sales_responsible_id.name, None, pr.stage)
            if pr.proposal_valid_until and df <= pr.proposal_valid_until <= dt:
                add(pr.proposal_valid_until, _("Vence propuesta: %s") % pr.name, "propuesta", "prospects", pr.id, pr.sales_responsible_id.name)
        for l in env["aq.portal.legal.item"].sudo().search([("date_end", ">=", df), ("date_end", "<=", dt)]):
            add(l.date_end, _("Vence contrato: %s") % l.name, "contrato", "legal", l.id, l.responsible_id.name, None, l.status)
        for v in env["aq.portal.vendor"].sudo().search([("renewal_date", ">=", df), ("renewal_date", "<=", dt), ("state", "=", "activo")]):
            add(v.renewal_date, _("Renovación: %s · %s") % (v.name, v.service), "renovacion", "vendors", v.id, v.responsible_id.name, v.cost)
        for rk in env["aq.portal.risk"].sudo().search([("review_date", ">=", df), ("review_date", "<=", dt), ("state", "!=", "cerrado")]):
            add(rk.review_date, _("Revisar riesgo: %s") % rk.name, "riesgo", "risks", rk.id, rk.responsible_id.name)
        for ob in env["aq.portal.onboarding.deliverable"].sudo().search([("due_date", ">=", df), ("due_date", "<=", dt), ("state", "in", ("pendiente", "en_proceso"))]):
            add(ob.due_date, _("Entregable de incorporación: %s") % ob.name, "incorporacion", "onboarding", ob.id, ob.responsible_id.name)
        ev.sort(key=lambda e: e["date"])
        return _json({"events": ev, "from": fields.Date.to_string(df), "to": fields.Date.to_string(dt)})

    # ------------------------------------------------------------------ rutinas
    @portal_route(API + "/routines/today", methods=["GET"])
    def routines_today(self, user):
        d = fields.Date.to_date(request.params.get("date")) if request.params.get("date") else fields.Date.today()
        Run = request.env["aq.portal.routine.run"].sudo()
        Run.ensure_runs(d)
        week = d - timedelta(days=d.weekday())
        month = d.replace(day=1)
        runs = Run.search(["|", "|", "&", ("frequency", "=", "diario"), ("period_date", "=", d),
                           "&", ("frequency", "=", "semanal"), ("period_date", "=", week),
                           "&", ("frequency", "=", "mensual"), ("period_date", "=", month)], order="frequency, routine_id")
        backlog = Run.search([("done", "=", False), ("period_date", "<", d)], limit=100)
        def ser(r):
            return {"id": r.id, "routine_id": r.routine_id.id, "name": r.routine_id.name, "frequency": r.frequency, "period_date": fields.Date.to_string(r.period_date),
                    "done": r.done, "done_date": fields.Datetime.to_string(r.done_date) if r.done_date else None, "user": r.user_id.name,
                    "notes": r.notes, "link": r.routine_id.link_resource, "description": r.routine_id.description}
        return _json({"date": fields.Date.to_string(d), "runs": [ser(r) for r in runs], "backlog": [ser(r) for r in backlog]})

    @portal_route(API + "/routines/<int:run_id>/toggle", methods=["POST"], roles=["direccion", "coordinacion", "equipo"])
    def routine_toggle(self, user, run_id):
        run = request.env["aq.portal.routine.run"].sudo().browse(run_id).exists()
        if not run:
            return _error(_("No encontrado"), 404)
        body = _body()
        done = not run.done if "done" not in body else bool(body["done"])
        run.write({"done": done, "done_date": fields.Datetime.now() if done else False, "user_id": user.id if done else False, "notes": body.get("notes", run.notes)})
        return _json({"ok": True, "done": run.done})

    # ------------------------------------------------------------------ reportes
    @portal_route(API + "/reports/generate", methods=["POST"], roles=["direccion", "coordinacion"])
    def generate_report(self, user):
        body = _body()
        df = fields.Date.to_date(body["from"]) if body.get("from") else None
        dt = fields.Date.to_date(body["to"]) if body.get("to") else None
        rep = request.env["aq.portal.report"].sudo().generate(body.get("type", "semanal"), df, dt, user.id)
        _log(user, "create", resource="reports", model="aq.portal.report", res_id=rep.id, summary=rep.name)
        info = _field_list("aq.portal.report", "reports")
        return _json({"record": _serialize(rep, info)}, status=201)

    # ------------------------------------------------------------------ alertas
    @portal_route(API + "/alerts", methods=["GET"])
    def alerts(self, user):
        dom = [("active", "=", True), ("dismissed", "=", False)]
        if user.role == "equipo" and user.member_id:
            dom.append(("responsible_id", "=", user.member_id.id))
        alerts = request.env["aq.portal.alert"].sudo().search(dom, limit=200)
        return _json({"alerts": [{"id": a.id, "name": a.name, "type": a.alert_type, "severity": a.severity, "date": fields.Date.to_string(a.date),
                                  "resource": a.resource, "res_id": a.res_id, "responsible": a.responsible_id.name} for a in alerts]})

    @portal_route(API + "/alerts/<int:alert_id>/dismiss", methods=["POST"], roles=["direccion", "coordinacion"])
    def dismiss_alert(self, user, alert_id):
        a = request.env["aq.portal.alert"].sudo().browse(alert_id).exists()
        if a:
            a.write({"dismissed": True, "dismissed_by_id": user.id})
        return _json({"ok": True})

    @portal_route(API + "/alerts/recompute", methods=["POST"], roles=["direccion", "coordinacion"])
    def recompute_alerts(self, user):
        request.env["aq.portal.alert"].sudo().with_context(portal_user_id=user.id).cron_daily()
        return _json({"ok": True})

    # ------------------------------------------------------------------ usuarios del portal (solo Dirección)
    @portal_route(API + "/users", methods=["GET"], roles=["direccion"])
    def users_list(self, user):
        users = request.env["aq.portal.user"].sudo().with_context(active_test=False).search([], order="name")
        return _json({"users": [u.to_public_dict() for u in users]})

    @portal_route(API + "/users", methods=["POST"], roles=["direccion"])
    def users_create(self, user):
        body = _body()
        vals = {k: body.get(k) for k in ("name", "login", "email", "role", "member_id", "notify_alerts") if k in body}
        if isinstance(vals.get("member_id"), dict):
            vals["member_id"] = vals["member_id"].get("id")
        u = request.env["aq.portal.user"].sudo().create(vals)
        if body.get("password"):
            u.set_password(body["password"], must_change=True)
        if body.get("send_invitation", True):
            u.action_send_reset_email()
        _log(user, "create", resource="users", model="aq.portal.user", res_id=u.id, summary=u.login)
        return _json({"user": u.to_public_dict()}, status=201)

    @portal_route(API + "/users/<int:uid>", methods=["PUT"], roles=["direccion"])
    def users_write(self, user, uid):
        u = request.env["aq.portal.user"].sudo().with_context(active_test=False).browse(uid).exists()
        if not u:
            return _error(_("Usuario no encontrado"), 404)
        body = _body()
        vals = {k: body.get(k) for k in ("name", "login", "email", "role", "member_id", "active", "notify_alerts") if k in body}
        if isinstance(vals.get("member_id"), dict):
            vals["member_id"] = vals["member_id"].get("id")
        if u.id == user.id and vals.get("role") and vals["role"] != "direccion":
            raise UserError(_("No puede quitarse a sí mismo el rol de Dirección."))
        u.write(vals)
        if body.get("password"):
            u.set_password(body["password"], must_change=True)
        _log(user, "write", resource="users", model="aq.portal.user", res_id=u.id, summary=u.login, changes={k: v for k, v in body.items() if k != "password"})
        return _json({"user": u.to_public_dict()})

    @portal_route(API + "/users/<int:uid>/send-reset", methods=["POST"], roles=["direccion"])
    def users_send_reset(self, user, uid):
        u = request.env["aq.portal.user"].sudo().browse(uid).exists()
        if not u:
            return _error(_("Usuario no encontrado"), 404)
        u.action_send_reset_email()
        _log(user, "action", resource="users", model="aq.portal.user", res_id=u.id, summary=_("Enlace de restablecimiento enviado"))
        return _json({"ok": True})

    @portal_route(API + "/users/<int:uid>/sessions", methods=["DELETE"], roles=["direccion"])
    def users_kill_sessions(self, user, uid):
        request.env["aq.portal.session"].sudo().search([("user_id", "=", uid)]).write({"active": False})
        return _json({"ok": True})

    @portal_route(API + "/me/preferences", methods=["PUT"])
    def me_prefs(self, user):
        body = _body()
        user.write({k: body[k] for k in ("notify_alerts", "timezone", "name") if k in body})
        return _json({"user": user.to_public_dict()})

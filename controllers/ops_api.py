# -*- coding: utf-8 -*-
"""API de Operaciones (AlphaOps). Autorización explícita por recurso y por objeto; acceso denegado por defecto."""
import base64
import csv
import io
import json
from datetime import timedelta

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from .api import API, portal_route, _json, _error, _body, _log, _serialize, _prepare_vals, _ip, COMMON_HIDDEN
from .ops_registry import OPS_RESOURCES, OPS_SECTIONS, OPS_NAME_SEARCH_MODELS, ops_resource_for_model, CLIENT_APPROVERS
from ..models.ops_security import FULL_ROLES, INTERNAL_ROLES, RESTRICTED_ROLES, CLIENT_ROLES

OPS = API + "/ops"


# ------------------------------------------------------------------ alcance (ABAC)
def _effective_role(user):
    bg = request.env["aq.ops.breakglass"].sudo().active_for(user)
    return bg.granted_role if bg else user.ops_role


def _scope(user):
    """Devuelve (project_ids | None=todos, org_id | None, role). Denegado por defecto: quien no tiene relación no ve nada."""
    role = _effective_role(user)
    bg = request.env["aq.ops.breakglass"].sudo().active_for(user)
    if bg and bg.project_id:
        return [bg.project_id.id], None, role
    if role in FULL_ROLES or role == "observer":
        return None, None, role
    P = request.env["aq.ops.project"].sudo()
    if role == "admin_liaison":
        return [], None, role
    if role in CLIENT_ROLES:
        org = user.organization_id.id
        if not org:
            return [], None, role
        ids = P.search([("partner_id", "=", org), ("client_visible", "=", True)]).ids
        if user.ops_project_ids:
            ids = [i for i in ids if i in user.ops_project_ids.ids]
        return ids, org, role
    if role in RESTRICTED_ROLES:
        return user.ops_project_ids.ids, None, role
    # internos: proyectos donde participan (PM, líder, equipo) + asignados expresamente
    m = user.member_id
    dom = ["|", ("id", "in", user.ops_project_ids.ids), ("team_member_ids", "in", [m.id])] if m else [("id", "in", user.ops_project_ids.ids)]
    if m:
        dom = ["|", "|", "|"] + [("pm_id", "=", m.id), ("functional_lead_id", "=", m.id), ("tech_lead_id", "=", m.id)] + dom
    if role == "support":
        dom = ["|", ("stage", "in", ("soporte", "estabilizacion"))] + dom
    return P.search(dom).ids, None, role


def _scope_domain(cfg, user):
    ids, org, role = _scope(user)
    Model = request.env[cfg["model"]].sudo()
    dom = []
    sc = cfg.get("scope")
    if role == "admin_liaison":
        return [] if cfg["model"] == "aq.ops.event" else [("id", "=", 0)]
    if sc == "id":
        if ids is not None:
            dom.append(("id", "in", ids))
    elif sc:
        if ids is not None:
            dom.append((sc, "in", ids))
    elif role in CLIENT_ROLES and cfg["model"] not in ("aq.ops.comment", "aq.ops.saved.view", "aq.ops.capacity"):
        dom.append(("id", "=", 0))
    if role in CLIENT_ROLES:
        if "client_visible" in Model._fields:
            dom.append(("client_visible", "=", True))
        if "internal" in Model._fields:
            dom.append(("internal", "=", False))
        if cfg.get("org_field") and org:
            dom.append((cfg["org_field"], "=", org))
        if role == "client_requester" and cfg["model"] == "aq.ops.request":
            dom.append(("requester_user_id", "=", user.id))
        if cfg["model"] == "aq.ops.incident" and org:
            dom.append(("partner_id", "=", org))
    if cfg["model"] == "aq.ops.saved.view":
        dom = ["|", ("user_id", "=", user.id), ("shared", "=", True)]
    if cfg["model"] == "aq.ops.timesheet" and role not in (FULL_ROLES | {"pm", "functional_lead", "tech_lead"}) and user.member_id:
        dom.append(("member_id", "=", user.member_id.id))
    return dom


def _cfg(resource):
    cfg = OPS_RESOURCES.get(resource)
    if not cfg:
        raise UserError(_("Recurso desconocido: %s") % resource)
    return cfg


def _check(cfg, op, user):
    role = _effective_role(user)
    if role == "observer" and op != "read":
        raise AccessError(_("Perfil observador: solo consulta."))
    if role not in cfg["roles"].get(op, []):
        raise AccessError(_("Su perfil (%s) no permite '%s' en %s.") % (role, op, cfg["label"]))


def _fields(cfg, user):
    Model = request.env[cfg["model"]].sudo()
    info = Model.fields_get()
    hidden = set(COMMON_HIDDEN)
    if _effective_role(user) in CLIENT_ROLES:
        hidden |= set(cfg.get("client_hidden", []))
    if cfg["model"] == "aq.ops.integration" and _effective_role(user) != "platform_owner":
        hidden.add("api_key")
    return {k: v for k, v in info.items() if k not in hidden}


def _get(cfg, user, rec_id, op="read"):
    """Autorización a nivel de objeto: el registro debe estar dentro del alcance del usuario."""
    Model = request.env[cfg["model"]].sudo()
    rec = Model.search([("id", "=", rec_id)] + _scope_domain(cfg, user), limit=1)
    if not rec:
        _log(user, "denied", resource=None, model=cfg["model"], res_id=rec_id, summary="object-level %s" % op)
        raise AccessError(_("Registro fuera de su alcance o inexistente."))
    return rec


def _build_domain(cfg, user, params):
    Model = request.env[cfg["model"]].sudo()
    info = Model.fields_get()
    dom = _scope_domain(cfg, user)
    q = params.get("search")
    if q:
        subs = [(f, "ilike", q) for f in ("name", "description", "body", "summary", "title") if f in info and info[f]["type"] in ("char", "text", "html")]
        if subs:
            dom += ["|"] * (len(subs) - 1) + subs
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
                dom.append((k, "=", v in (True, "true", "1", 1)))
            elif isinstance(v, list):
                dom.append((k, "in", v))
            elif t == "many2one":
                dom.append((k, "=", int(v)))
            else:
                dom.append((k, "=", v))
    extra = params.get("domain")
    if extra:
        try:
            extra = json.loads(extra) if isinstance(extra, str) else extra
        except Exception:
            extra = []
        for leaf in extra:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0].split(".")[0] not in info:
                raise UserError(_("Campo no permitido: %s") % leaf[0])
        dom += [tuple(l) if isinstance(l, list) else l for l in extra]
    if "active" in info and not params.get("include_archived"):
        dom.append(("active", "=", True))
    return dom


class OpsApi(http.Controller):

    @portal_route(OPS + "/schema", methods=["GET"], app="ops")
    def schema(self, user):
        role = _effective_role(user)
        out = {"sections": OPS_SECTIONS, "resources": {}, "role": role, "is_external": role in CLIENT_ROLES, "ai_available": request.env["aq.ops.ai"].sudo().available(),
               "organization": user.organization_id.name, "breakglass": bool(request.env["aq.ops.breakglass"].sudo().active_for(user))}
        for key, cfg in OPS_RESOURCES.items():
            if role not in cfg["roles"].get("read", []):
                continue
            info = _fields(cfg, user)
            fo = {}
            for fname, f in info.items():
                d = {"name": fname, "string": f.get("string"), "type": f["type"], "required": bool(f.get("required")), "readonly": bool(f.get("readonly")), "help": f.get("help")}
                if f["type"] == "selection":
                    d["selection"] = [list(x) for x in (f.get("selection") or [])]
                if f["type"] in ("many2one", "many2many", "one2many"):
                    d["relation"] = f.get("relation"); d["relation_resource"] = ops_resource_for_model(f.get("relation"))
                if role in CLIENT_ROLES and cfg.get("client_editable") and fname not in cfg["client_editable"]:
                    d["readonly"] = True
                fo[fname] = d
            can = {op: role in r for op, r in cfg["roles"].items()}
            if role == "observer":
                can = {"read": True, "write": False, "create": False, "delete": False}
            out["resources"][key] = {"key": key, "model": cfg["model"], "label": cfg["label"], "singular": cfg.get("singular"), "section": cfg.get("section"), "order": cfg.get("order", 100),
                                     "list": [c for c in cfg.get("list", []) if c in fo], "filters": [c for c in cfg.get("filters", []) if c in fo],
                                     "groups": [{"title": g["title"], "fields": [f for f in g["fields"] if f in fo]} for g in cfg.get("groups", [])],
                                     "tabs": [t for t in cfg.get("tabs", []) if t["resource"] in OPS_RESOURCES and role in OPS_RESOURCES[t["resource"]]["roles"]["read"]],
                                     "attachments": cfg.get("attachments", False), "chatter": cfg.get("chatter", False), "sensitive": False,
                                     "actions": [a for a in cfg.get("actions", []) if role in a.get("roles", [])], "can": can, "fields": fo,
                                     "essential": [f for f in cfg.get("essential", []) if f in fo]}
        return _json(out)

    # ------------------------------------------------------------------ CRUD genérico con alcance
    @portal_route(OPS + "/r/<string:resource>", methods=["GET"], app="ops")
    def list_records(self, user, resource):
        cfg = _cfg(resource); _check(cfg, "read", user)
        Model = request.env[cfg["model"]].sudo()
        params = request.params
        dom = _build_domain(cfg, user, params)
        limit = min(int(params.get("limit", 80)), 500); offset = int(params.get("offset", 0))
        order = params.get("order") or None
        if order:
            order = ", ".join(p.strip() for p in order.split(",") if Model._fields.get(p.strip().split(" ")[0]) and Model._fields[p.strip().split(" ")[0]].store) or None
        info = _fields(cfg, user)
        fnames = params.get("fields")
        fnames = [f for f in (fnames.split(",") if fnames else cfg.get("list", []) + ["id"]) if f in info]
        recs = Model.search(dom, limit=limit, offset=offset, order=order)
        return _json({"records": [_serialize(r, info, fnames) for r in recs], "total": Model.search_count(dom), "limit": limit, "offset": offset})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>", methods=["GET"], app="ops")
    def get_record(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "read", user)
        rec = _get(cfg, user, rec_id)
        return _json({"record": _serialize(rec, _fields(cfg, user))})

    @portal_route(OPS + "/r/<string:resource>", methods=["POST"], app="ops")
    def create_record(self, user, resource):
        cfg = _cfg(resource); _check(cfg, "create", user)
        body = _body()
        role = _effective_role(user)
        if role in CLIENT_ROLES:
            allowed = set(cfg.get("client_editable", [])) | {"project_id", "partner_id", "item_id", "request_id", "meeting_id", "incident_id", "parent_id", "case_id", "result", "evidence", "executed_by_partner_id", "internal"}
            body = {k: v for k, v in body.items() if k in allowed}
            if cfg["model"] == "aq.ops.request":
                body["partner_id"] = user.organization_id.id; body["requester_user_id"] = user.id; body["source"] = "empleado_cliente" if role == "client_requester" else "cliente"
                body["requester_department"] = body.get("requester_department") or user.department
            if cfg["model"] == "aq.ops.comment":
                body["internal"] = False
            if cfg["model"] == "aq.ops.incident":
                body["partner_id"] = user.organization_id.id
        vals = _prepare_vals(cfg["model"], body, user, {"direction_fields": []})
        if role in CLIENT_ROLES and cfg["model"] == "aq.ops.request":
            vals.update(partner_id=user.organization_id.id, requester_user_id=user.id, source=body["source"])
        # el padre debe estar dentro del alcance
        for pf in ("project_id", "item_id", "request_id", "meeting_id", "incident_id", "case_id", "release_id", "milestone_id"):
            if vals.get(pf):
                pres = {"project_id": "projects", "item_id": "items", "request_id": "requests", "meeting_id": "meetings", "incident_id": "incidents", "case_id": "test_cases", "release_id": "releases", "milestone_id": "milestones"}[pf]
                _get(OPS_RESOURCES[pres], user, vals[pf], "link")
        rec = request.env[cfg["model"]].sudo().with_context(portal_user_id=user.id).create(vals)
        _log(user, "create", resource="ops:" + resource, model=cfg["model"], res_id=rec.id, summary=rec.display_name, changes=body)
        return _json({"record": _serialize(rec, _fields(cfg, user))}, status=201)

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>", methods=["PUT", "PATCH"], app="ops")
    def write_record(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "write", user)
        rec = _get(cfg, user, rec_id, "write").with_context(portal_user_id=user.id)
        body = _body()
        if _effective_role(user) in CLIENT_ROLES:
            body = {k: v for k, v in body.items() if k in cfg.get("client_editable", [])}
        if cfg["model"] == "aq.ops.timesheet" and rec.state == "aprobado":
            raise AccessError(_("Un registro de tiempo aprobado no se modifica."))
        vals = _prepare_vals(cfg["model"], body, user, {"direction_fields": []})
        if vals:
            rec.write(vals)
            _log(user, "write", resource="ops:" + resource, model=cfg["model"], res_id=rec.id, summary=rec.display_name, changes=body)
        return _json({"record": _serialize(rec, _fields(cfg, user))})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>", methods=["DELETE"], app="ops")
    def delete_record(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "delete", user)
        rec = _get(cfg, user, rec_id, "delete")
        name = rec.display_name
        if "active" in rec._fields:
            rec.write({"active": False})
        else:
            rec.unlink()
        _log(user, "unlink", resource="ops:" + resource, model=cfg["model"], res_id=rec_id, summary=name)
        return _json({"ok": True})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>/action/<string:action>", methods=["POST"], app="ops")
    def run_action(self, user, resource, rec_id, action):
        cfg = _cfg(resource)
        allowed = [a for a in cfg.get("actions", []) if a["name"] == action]
        role = _effective_role(user)
        if not allowed or role not in allowed[0]["roles"]:
            _log(user, "denied", resource="ops:" + resource, res_id=rec_id, summary=action)
            return _error(_("Acción no permitida para su perfil."), 403)
        rec = _get(cfg, user, rec_id, "action").with_context(portal_user_id=user.id)
        getattr(rec, action)()
        _log(user, "action", resource="ops:" + resource, model=cfg["model"], res_id=rec.id, summary="%s: %s" % (allowed[0]["label"], rec.display_name))
        return _json({"record": _serialize(rec, _fields(cfg, user))})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>/messages", methods=["GET"], app="ops")
    def messages(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "read", user); rec = _get(cfg, user, rec_id)
        out = []
        if cfg.get("chatter") and _effective_role(user) not in CLIENT_ROLES:
            for m in request.env["mail.message"].sudo().search([("model", "=", cfg["model"]), ("res_id", "=", rec.id)], order="date desc", limit=80):
                out.append({"id": m.id, "date": fields.Datetime.to_string(m.date), "body": m.body or "", "author": m.author_id.name or "Sistema",
                            "tracking": [{"field": t.field_id.field_description, "old": t.old_value_char or t.old_value_text or "", "new": t.new_value_char or t.new_value_text or ""} for t in m.tracking_value_ids]})
        audit = [] if _effective_role(user) in CLIENT_ROLES else [{"id": l.id, "date": fields.Datetime.to_string(l.create_date), "user": l.user_id.name, "action": l.action, "summary": l.summary, "changes": l.changes}
                                                                  for l in request.env["aq.portal.audit.log"].sudo().search([("res_model", "=", cfg["model"]), ("res_id", "=", rec.id)], limit=80)]
        return _json({"messages": out, "audit": audit})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>/note", methods=["POST"], app="ops")
    def note(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "read", user); rec = _get(cfg, user, rec_id)
        text = (_body().get("body") or "").strip()
        if not text:
            raise UserError(_("La nota está vacía."))
        fk = {"aq.ops.item": "item_id", "aq.ops.request": "request_id", "aq.ops.incident": "incident_id", "aq.ops.project": "project_id"}.get(cfg["model"])
        if fk:
            request.env["aq.ops.comment"].sudo().with_context(portal_user_id=user.id).create({fk: rec.id, "body": text, "internal": _effective_role(user) not in CLIENT_ROLES and not _body().get("client_visible")})
        elif cfg.get("chatter"):
            rec.message_post(body="<b>%s</b>: %s" % (user.name, text))
        _log(user, "write", resource="ops:" + resource, model=cfg["model"], res_id=rec.id, summary=_("Nota: %s") % text[:100])
        return _json({"ok": True})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>/attachments", methods=["GET"], app="ops")
    def attachments(self, user, resource, rec_id):
        cfg = _cfg(resource); _check(cfg, "read", user); rec = _get(cfg, user, rec_id)
        atts = request.env["ir.attachment"].sudo().search([("res_model", "=", cfg["model"]), ("res_id", "=", rec.id)], order="create_date desc")
        if _effective_role(user) in CLIENT_ROLES:
            atts = atts.filtered(lambda a: not (a.description or "").startswith("internal"))
        return _json({"attachments": [{"id": a.id, "name": a.name, "mimetype": a.mimetype, "size": a.file_size, "date": fields.Datetime.to_string(a.create_date), "url": "%s/attachments/%d/download" % (API, a.id)} for a in atts]})

    @portal_route(OPS + "/r/<string:resource>/<int:rec_id>/attachments", methods=["POST"], app="ops")
    def upload(self, user, resource, rec_id):
        cfg = _cfg(resource)
        if _effective_role(user) in CLIENT_ROLES and cfg["model"] not in ("aq.ops.request", "aq.ops.acceptance", "aq.ops.test.run", "aq.ops.incident", "aq.ops.item"):
            raise AccessError(_("No puede cargar archivos en este recurso."))
        rec = _get(cfg, user, rec_id, "write")
        Att = request.env["ir.attachment"].sudo()
        created = [Att.create({"name": f.filename, "datas": base64.b64encode(f.read()), "res_model": cfg["model"], "res_id": rec.id, "mimetype": f.mimetype}) for f in request.httprequest.files.getlist("file")]
        for a in created:
            _log(user, "upload", resource="ops:" + resource, model=cfg["model"], res_id=rec.id, summary=a.name)
        return _json({"attachments": [{"id": a.id, "name": a.name} for a in created]}, status=201)

    @portal_route(OPS + "/name_search", methods=["GET"], app="ops")
    def name_search(self, user):
        model = request.params.get("model")
        if model not in OPS_NAME_SEARCH_MODELS:
            return _error(_("Modelo no permitido"), 403)
        Model = request.env[model].sudo()
        res_key = ops_resource_for_model(model)
        dom = _scope_domain(OPS_RESOURCES[res_key], user) if res_key else []
        if model == "res.partner" and _effective_role(user) in CLIENT_ROLES:
            dom = ["|", ("id", "=", user.organization_id.id), ("parent_id", "=", user.organization_id.id)]  # nunca cruzar clientes
        if "active" in Model._fields:
            dom.append(("active", "=", True))
        res = Model.name_search(request.params.get("q") or "", args=dom, limit=min(int(request.params.get("limit", 20)), 200))
        return _json({"results": [{"id": r[0], "name": r[1]} for r in res]})

    @portal_route(OPS + "/export/<string:resource>", methods=["GET"], app="ops")
    def export(self, user, resource):
        """Exportación controlada: requiere permiso explícito y queda en bitácora."""
        if not user.can_export:
            _log(user, "denied", resource="ops:" + resource, summary="export")
            return _error(_("Exportación no autorizada para su cuenta."), 403)
        cfg = _cfg(resource); _check(cfg, "read", user)
        Model = request.env[cfg["model"]].sudo()
        info = _fields(cfg, user)
        cols = [c for c in cfg.get("list", []) if c in info]
        recs = Model.search(_build_domain(cfg, user, request.params), limit=2000)
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow([info[c]["string"] for c in cols])
        for r in recs:
            row = []
            for c in cols:
                v = _serialize(r, info, [c])[c]
                row.append(v["name"] if isinstance(v, dict) else "; ".join(x["name"] for x in v) if isinstance(v, list) else v)
            w.writerow(row)
        _log(user, "action", resource="ops:" + resource, summary=_("Exportación CSV (%d registros)") % len(recs))
        return request.make_response("﻿" + buf.getvalue(), headers=[("Content-Type", "text/csv; charset=utf-8"), ("Content-Disposition", http.content_disposition("%s.csv" % resource))])

    # ------------------------------------------------------------------ pantallas
    def _pdom(self, user):
        return _scope_domain(OPS_RESOURCES["items"], user)[:1] if _scope(user)[0] is not None else []

    @portal_route(OPS + "/mywork", methods=["GET"], app="ops")
    def mywork(self, user):
        return _json(request.env["aq.ops.engine"].sudo().my_work(user, self._pdom(user)))

    @portal_route(OPS + "/portfolio", methods=["GET"], app="ops")
    def portfolio(self, user):
        if _effective_role(user) in CLIENT_ROLES:
            return _error(_("Sin acceso"), 403)
        return _json(request.env["aq.ops.engine"].sudo().portfolio(self._pdom(user)))

    @portal_route(OPS + "/projects/<int:pid>/command", methods=["GET"], app="ops")
    def command(self, user, pid):
        p = _get(OPS_RESOURCES["projects"], user, pid)
        return _json(request.env["aq.ops.engine"].sudo().command_center(p, user))

    @portal_route(OPS + "/client/home", methods=["GET"], app="ops")
    def client_home(self, user):
        if _effective_role(user) not in CLIENT_ROLES:
            return _error(_("Solo usuarios del cliente"), 403)
        return _json(request.env["aq.ops.engine"].sudo().client_home(user, self._pdom(user)))

    @portal_route(OPS + "/kpis", methods=["GET"], app="ops")
    def kpis(self, user):
        if _effective_role(user) in CLIENT_ROLES:
            return _error(_("Sin acceso"), 403)
        p = request.params
        df = fields.Date.to_date(p.get("from")) if p.get("from") else None
        dt = fields.Date.to_date(p.get("to")) if p.get("to") else None
        dom = self._pdom(user)
        if p.get("project_id"):
            _get(OPS_RESOURCES["projects"], user, int(p["project_id"]))
            dom = dom + [("project_id", "=", int(p["project_id"]))]
        return _json(request.env["aq.ops.engine"].sudo().ops_kpis(dom, df, dt))

    # ------------------------------------------------------------------ tablero / items
    @portal_route(OPS + "/items/<int:iid>/move", methods=["POST"], app="ops")
    def move_item(self, user, iid):
        cfg = OPS_RESOURCES["items"]; _check(cfg, "write", user)
        rec = _get(cfg, user, iid, "write").with_context(portal_user_id=user.id)
        body = _body(); vals = {}
        if body.get("state"):
            vals["state"] = body["state"]
        if body.get("rank") is not None:
            vals["rank"] = int(body["rank"])
        if body.get("sprint_id") is not None:
            vals["sprint_id"] = body["sprint_id"] or False
        if body.get("assignee_id") is not None:
            vals["assignee_id"] = body["assignee_id"] or False
        if body.get("date_due"):
            vals["date_due"] = body["date_due"]; vals["reschedule_reason"] = body.get("reason")
        if body.get("blocked_reason"):
            vals["blocked_reason"] = body["blocked_reason"]
        rec.with_context(aq_force_wip=bool(body.get("force_wip"))).write(vals)
        _log(user, "write", resource="ops:items", model="aq.ops.item", res_id=rec.id, summary=_("Movido: %s → %s") % (rec.name, vals.get("state", "")), changes=vals)
        return _json({"record": _serialize(rec, _fields(cfg, user))})

    # ------------------------------------------------------------------ tiempo
    @portal_route(OPS + "/timer/start", methods=["POST"], app="ops")
    def timer_start(self, user):
        b = _body()
        if b.get("item_id"):
            _get(OPS_RESOURCES["items"], user, int(b["item_id"]))
        t = request.env["aq.ops.timesheet"].sudo().with_context(portal_user_id=user.id).timer_start_for(user, b.get("item_id"), b.get("project_id"), b.get("description"))
        return _json({"timer": {"id": t.id, "since": fields.Datetime.to_string(t.timer_start)}})

    @portal_route(OPS + "/timer/stop", methods=["POST"], app="ops")
    def timer_stop(self, user):
        m = user.member_id
        run = request.env["aq.ops.timesheet"].sudo().search([("member_id", "=", m.id), ("running", "=", True)], limit=1) if m else None
        if run:
            run.timer_stop()
        return _json({"timesheet": {"id": run.id, "hours": run.hours} if run else None})

    @portal_route(OPS + "/timesheets/week", methods=["GET"], app="ops")
    def week(self, user):
        week = request.params.get("week") or fields.Date.today().strftime("%G-W%V")
        start, end = request.env["aq.ops.capacity"]._week_bounds(week)
        dom = [("date", ">=", start), ("date", "<=", end)] + _scope_domain(OPS_RESOURCES["timesheets"], user)
        ts = request.env["aq.ops.timesheet"].sudo().search(dom, order="date, id")
        info = _fields(OPS_RESOURCES["timesheets"], user)
        fn = ["member_id", "project_id", "item_id", "date", "hours", "category", "billable", "description", "state", "running", "unjustified"]
        caps = request.env["aq.ops.capacity"].sudo().search([("week", "=", week)] + ([("member_id", "=", user.member_id.id)] if user.member_id and _effective_role(user) not in FULL_ROLES | {"pm"} else []))
        return _json({"week": week, "start": str(start), "end": str(end), "entries": [_serialize(t, info, fn) for t in ts],
                      "capacity": [{"id": c.id, "member": c.member_id.name, "available": c.hours_available - c.unavailable_hours, "planned": c.planned_hours, "logged": c.logged_hours, "load_pct": round(c.load_pct), "overallocated": c.overallocated, "specialty": c.specialty} for c in caps],
                      "members": [{"id": m.id, "name": m.name} for m in request.env["aq.portal.member"].sudo().search([("active", "=", True)])]})

    @portal_route(OPS + "/timesheets/approve-week", methods=["POST"], app="ops")
    def approve_week(self, user):
        if _effective_role(user) not in FULL_ROLES | {"pm", "functional_lead", "tech_lead"}:
            return _error(_("Solo PM/líderes aprueban"), 403)
        b = _body()
        dom = [("week", "=", b.get("week")), ("state", "=", "enviado")] + ([("member_id", "=", int(b["member_id"]))] if b.get("member_id") else []) + _scope_domain(OPS_RESOURCES["timesheets"], user)
        ts = request.env["aq.ops.timesheet"].sudo().search(dom).with_context(portal_user_id=user.id)
        ts.action_approve()
        _log(user, "action", resource="ops:timesheets", summary=_("Aprobación semanal %s: %d registros") % (b.get("week"), len(ts)))
        return _json({"approved": len(ts)})

    # ------------------------------------------------------------------ aceptación electrónica
    @portal_route(OPS + "/acceptances/<int:aid>/decide", methods=["POST"], app="ops")
    def decide(self, user, aid):
        role = _effective_role(user)
        a = _get(OPS_RESOURCES["acceptances"], user, aid, "decide")
        if role in CLIENT_ROLES:
            if role not in CLIENT_APPROVERS:
                raise AccessError(_("Su perfil no tiene autoridad de aceptación."))
            if a.department and user.department and a.department.lower() != user.department.lower():
                raise AccessError(_("Esta validación corresponde al departamento %s.") % a.department)
        elif role not in FULL_ROLES | {"pm"}:
            raise AccessError(_("Solo el cliente (o PM por delegación documentada) decide una validación."))
        b = _body()
        a.with_context(portal_user_id=user.id).decide(b.get("decision"), b.get("reason"), user)
        _log(user, "action", resource="ops:acceptances", model="aq.ops.acceptance", res_id=a.id, summary=_("Validación: %s") % b.get("decision"))
        return _json({"record": _serialize(a, _fields(OPS_RESOURCES["acceptances"], user))})

    @portal_route(OPS + "/questions/<int:qid>/answer", methods=["POST"], app="ops")
    def answer(self, user, qid):
        q = _get(OPS_RESOURCES["questions"], user, qid, "write")
        q.write({"answer": _body().get("answer"), "answered": True})
        request.env["aq.ops.notification"].sudo().notify_role(q.meeting_id.project_id, ["pm"], "cliente_respondio", _("Pregunta respondida: %s") % q.name, "meetings", q.meeting_id.id)
        return _json({"ok": True})

    @portal_route(OPS + "/calendar.ics", methods=["GET"], app="ops")
    def calendar_ics(self, user):
        ics = request.env["aq.ops.notification"].sudo().ics_for_user(user, self._pdom(user))
        return request.make_response(ics, headers=[("Content-Type", "text/calendar; charset=utf-8"), ("Content-Disposition", http.content_disposition("alphaops.ics"))])

    @portal_route(OPS + "/live", methods=["GET"], app="ops")
    def live(self, user):
        """Actualización en vivo por sondeo ligero (sustituye SSE/WebSockets, que Odoo no mantiene abiertos por worker)."""
        since = request.params.get("since")
        dom = [("user_id", "=", user.id), ("read", "=", False)]
        if since:
            dom.append(("create_date", ">", since))
        N = request.env["aq.ops.notification"].sudo()
        fresh = N.search(dom, limit=10, order="create_date desc")
        return _json({"now": fields.Datetime.to_string(fields.Datetime.now()), "unread": N.search_count([("user_id", "=", user.id), ("read", "=", False)]),
                      "fresh": [{"id": n.id, "title": n.title, "category": n.category, "priority": n.priority, "resource": n.resource, "res_id": n.res_id} for n in fresh]})

    @portal_route(OPS + "/capacity/forecast", methods=["GET"], app="ops")
    def capacity_forecast(self, user):
        role = _effective_role(user)
        if role in CLIENT_ROLES:
            return _error(_("Sin acceso"), 403)
        dom = [] if role in FULL_ROLES | {"pm", "functional_lead", "tech_lead"} else [("id", "=", user.member_id.id)]
        return _json({"forecast": request.env["aq.ops.engine"].sudo().capacity_forecast(dom, int(request.params.get("weeks", 4)))})

    @portal_route(OPS + "/views", methods=["GET"], app="ops")
    def views_list(self, user):
        res = request.params.get("resource")
        V = request.env["aq.ops.saved.view"].sudo().search(["|", ("user_id", "=", user.id), ("shared", "=", True)] + ([("resource", "=", res)] if res else []))
        return _json({"views": [{"id": v.id, "name": v.name, "resource": v.resource, "view_mode": v.view_mode, "filters": json.loads(v.filters_json or "{}"), "shared": v.shared, "mine": v.user_id.id == user.id} for v in V]})

    @portal_route(OPS + "/views", methods=["POST"], app="ops")
    def views_save(self, user):
        b = _body()
        v = request.env["aq.ops.saved.view"].sudo().create({"name": b.get("name"), "user_id": user.id, "resource": b.get("resource"), "view_mode": b.get("view_mode", "list"),
                                                             "filters_json": json.dumps(b.get("filters") or {}), "shared": bool(b.get("shared"))})
        return _json({"id": v.id}, status=201)

    @portal_route(OPS + "/views/<int:vid>", methods=["DELETE"], app="ops")
    def views_delete(self, user, vid):
        request.env["aq.ops.saved.view"].sudo().search([("id", "=", vid), ("user_id", "=", user.id)]).unlink()
        return _json({"ok": True})

    # ------------------------------------------------------------------ notificaciones
    @portal_route(OPS + "/notifications", methods=["GET"], app="ops")
    def notifications(self, user):
        dom = [("user_id", "=", user.id)]
        if not request.params.get("all"):
            dom.append(("read", "=", False))
        notes = request.env["aq.ops.notification"].sudo().search(dom, limit=200)
        return _json({"notifications": [{"id": n.id, "category": n.category, "priority": n.priority, "title": n.title, "body": n.body, "resource": n.resource, "res_id": n.res_id, "read": n.read,
                                         "action_required": n.action_required, "done": n.done, "date": fields.Datetime.to_string(n.create_date)} for n in notes],
                      "unread": request.env["aq.ops.notification"].sudo().search_count([("user_id", "=", user.id), ("read", "=", False)])})

    @portal_route(OPS + "/notifications/<int:nid>", methods=["POST"], app="ops")
    def notification_update(self, user, nid):
        n = request.env["aq.ops.notification"].sudo().search([("id", "=", nid), ("user_id", "=", user.id)], limit=1)
        if n:
            b = _body(); vals = {}
            if "read" in b: vals.update(read=bool(b["read"]), read_at=fields.Datetime.now())
            if "done" in b: vals.update(done=bool(b["done"]), read=True)
            n.write(vals)
        return _json({"ok": True})

    @portal_route(OPS + "/notifications/read-all", methods=["POST"], app="ops")
    def notifications_read_all(self, user):
        request.env["aq.ops.notification"].sudo().search([("user_id", "=", user.id), ("read", "=", False)]).write({"read": True, "read_at": fields.Datetime.now()})
        return _json({"ok": True})

    # ------------------------------------------------------------------ copiloto IA (DeepSeek) — solo propone
    def _ai(self):
        return request.env["aq.ops.ai"].sudo()

    @portal_route(OPS + "/ai/status", methods=["GET"], app="ops")
    def ai_status(self, user):
        st = self._ai().status()
        if _effective_role(user) != "platform_owner":
            st.pop("key_hint", None)
        return _json(st)

    @portal_route(OPS + "/ai/meetings/<int:mid>/summarize", methods=["POST"], app="ops")
    def ai_meeting(self, user, mid):
        m = _get(OPS_RESOURCES["meetings"], user, mid, "write")
        if _effective_role(user) in CLIENT_ROLES:
            raise AccessError(_("Sin acceso"))
        data = self._ai().with_context(portal_user_id=user.id).summarize_meeting(m)
        _log(user, "action", resource="ops:meetings", model="aq.ops.meeting", res_id=m.id, summary=_("Copiloto: resumen y propuestas (requieren confirmación)"))
        return _json({"proposals": data, "ai": self._ai().available()})

    @portal_route(OPS + "/ai/projects/<int:pid>/explain", methods=["POST"], app="ops")
    def ai_explain(self, user, pid):
        p = _get(OPS_RESOURCES["projects"], user, pid)
        return _json({"text": self._ai().explain_project(p), "ai": self._ai().available()})

    @portal_route(OPS + "/ai/projects/<int:pid>/next-action", methods=["POST"], app="ops")
    def ai_next(self, user, pid):
        p = _get(OPS_RESOURCES["projects"], user, pid)
        return _json({"text": self._ai().next_action(p), "ai": self._ai().available()})

    @portal_route(OPS + "/ai/projects/<int:pid>/duplicates", methods=["POST"], app="ops")
    def ai_dups(self, user, pid):
        p = _get(OPS_RESOURCES["projects"], user, pid)
        return _json({"pairs": self._ai().duplicates(p)})

    @portal_route(OPS + "/ai/projects/<int:pid>/report", methods=["POST"], app="ops")
    def ai_report(self, user, pid):
        p = _get(OPS_RESOURCES["projects"], user, pid, "write")
        if _effective_role(user) in CLIENT_ROLES:
            raise AccessError(_("Sin acceso"))
        rep = self._ai().with_context(portal_user_id=user.id).draft_report(p)
        return _json({"report": {"id": rep.id, "name": rep.name, "summary": rep.summary, "ai": rep.generated_by_ai}})

    @portal_route(OPS + "/ai/requests/<int:rid>/scope", methods=["POST"], app="ops")
    def ai_scope(self, user, rid):
        r = _get(OPS_RESOURCES["requests"], user, rid)
        if _effective_role(user) in CLIENT_ROLES:
            raise AccessError(_("Sin acceso"))
        return _json({"analysis": self._ai().compare_scope(r), "ai": self._ai().available()})

    @portal_route(OPS + "/ai/items/<int:iid>/tests", methods=["POST"], app="ops")
    def ai_tests(self, user, iid):
        i = _get(OPS_RESOURCES["items"], user, iid, "write")
        if _effective_role(user) in CLIENT_ROLES:
            raise AccessError(_("Sin acceso"))
        return _json({"created": self._ai().with_context(portal_user_id=user.id).suggest_tests(i)})

    @portal_route(OPS + "/ai/items/<int:iid>/dependencies", methods=["POST"], app="ops")
    def ai_deps(self, user, iid):
        i = _get(OPS_RESOURCES["items"], user, iid)
        return _json({"suggestions": self._ai().suggest_dependencies(i)})

    @portal_route(OPS + "/ai/incidents/<int:iid>/summary", methods=["POST"], app="ops")
    def ai_incident(self, user, iid):
        i = _get(OPS_RESOURCES["incidents"], user, iid)
        return _json({"text": self._ai().summarize_incident(i), "ai": self._ai().available()})

# -*- coding: utf-8 -*-
"""Importa exportaciones JSON de Taiga al portal de Operaciones (AlphaOps) a nombre de OdooBot.

Uso:  python3 aq_admin_portal/tools/import_taiga.py Datos/*.json [--dry-run]
Requiere el módulo aq_admin_portal actualizado (método aq.ops.engine.bot_create) y credenciales en .env.
Idempotente: cada elemento lleva la etiqueta 'taiga:<slug>#<ref>'; no duplica lo ya importado.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from odoo_client import OdooClient  # noqa

DRY = "--dry-run" in sys.argv
FILES = [a for a in sys.argv[1:] if a.endswith(".json")]

# Mapeos -------------------------------------------------------------------
PROJECT_MAP = {  # slug Taiga -> (nombre de proyecto existente en Ops | None, nombre de cliente, nombre nuevo de proyecto)
    "servicios-ambientales": ("SAI · Proyecto por etapas (regulado)", "Servicios Ambientales Internacionales — SAI", None),
    "som-monterrey": ("Stonia · Implementación y estabilización", "SOM Group / Stonia", None),
    "som-cabos": (None, "SOM Group / Stonia", "SOM Cabos · Digitalización y mejora operativa"),
    "creattivo-ti": (None, "Creattivo TI", "Creattivo TI · Digitalización y mejora operativa"),
}
STATUS_MAP = {"New": "backlog", "Ready": "por_hacer", "In progress": "en_progreso", "Ready for test": "qa_interno", "Done": "cerrado", "Archived": "cerrado"}
EPIC_STATUS = {"New": "backlog", "Ready": "por_hacer", "In progress": "en_progreso", "Done": "cerrado", "Closed": "cerrado"}
INTERNAL_DOMAINS = ("alphaqueb.com",)
GROUP_SUBJECTS = {"taller": "Taller", "portal proveedor": "Portal proveedor"}  # asuntos repetidos que en realidad son agrupadores → épica + hijas


def md_to_html(md):
    if not md:
        return False
    h = md.strip()
    h = re.sub(r"^### (.*)$", r"<h4>\1</h4>", h, flags=re.M)
    h = re.sub(r"^## (.*)$", r"<h3>\1</h3>", h, flags=re.M)
    h = re.sub(r"^# (.*)$", r"<h3>\1</h3>", h, flags=re.M)
    h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
    h = re.sub(r"^\s*[-*] (.*)$", r"<li>\1</li>", h, flags=re.M)
    h = h.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")
    return "<p>%s</p>" % h


def d(s):
    return s[:10] if s else False


class Importer:
    def __init__(self):
        self.c = OdooClient()
        self.c.conectar()
        self.members = {}   # email -> member id
        self.names = {}     # email -> nombre completo (de history)
        self.stats = defaultdict(int)

    # --- helpers RPC como OdooBot
    def bot_create(self, model, vals):
        self.stats["create:" + model] += 1
        if DRY:
            return -self.stats["create:" + model]
        return self.c.execute("aq.ops.engine", "bot_create", [model, [vals]])[0]

    def bot_write(self, model, ids, vals):
        self.stats["write:" + model] += 1
        if not DRY:
            self.c.execute("aq.ops.engine", "bot_write", [model, ids, vals])

    def find(self, model, dom, fields=("id",)):
        r = self.c.search_read(model, dom, list(fields), limit=1)
        return r[0] if r else None

    # --- personas
    def collect_names(self, data):
        for coll in ("user_stories", "epics", "issues"):
            for u in data.get(coll, []):
                for h in u.get("history", []):
                    usr = h.get("user")
                    if isinstance(usr, list) and len(usr) == 2 and usr[0]:
                        self.names[usr[0]] = usr[1]

    def member_for(self, email):
        if not email:
            return False
        if email in self.members:
            return self.members[email]
        dom = email.split("@")[-1]
        name = self.names.get(email) or email.split("@")[0].replace(".", " ").title()
        m = self.find("aq.portal.member", [["email", "=", email]])
        if not m and email == "antonio@alphaqueb.com":
            m = self.find("aq.portal.member", [["name", "ilike", "Antonio"]])
        if not m and email == "marinayarethmay@gmail.com":
            m = self.find("aq.portal.member", [["name", "ilike", "Marina"]])
        if m:
            if not self.find("aq.portal.member", [["id", "=", m["id"]], ["email", "=", email]]):
                self.bot_write("aq.portal.member", [m["id"]], {"email": email})
            self.members[email] = m["id"]
            return m["id"]
        mtype = "empleado" if dom in INTERNAL_DOMAINS else "prestador"
        mid = self.bot_create("aq.portal.member", {"name": name, "email": email, "member_type": mtype, "position": "Consultor / desarrollo" if dom in INTERNAL_DOMAINS else "Colaborador externo"})
        self.members[email] = mid
        return mid

    def client_contact(self, email, partner_id):
        p = self.find("res.partner", [["email", "=", email]])
        if p:
            return p["id"]
        name = self.names.get(email) or email.split("@")[0].title()
        if DRY:
            self.stats["create:res.partner(contact)"] += 1
            return -1
        return self.c.execute("aq.ops.engine", "bot_partner", [name, {"email": email, "parent_id": partner_id, "is_company": False, "type": "contact"}])

    # --- proyecto
    def project_for(self, data):
        slug = data["slug"]
        key = next((k for k in PROJECT_MAP if slug.startswith(k)), None)
        if not key:
            raise SystemExit("Sin mapeo para %s" % slug)
        existing_name, partner_name, new_name = PROJECT_MAP[key]
        partner = self.find("res.partner", [["name", "=", partner_name], ["is_company", "=", True]])
        if not partner:
            if DRY:
                self.stats["create:res.partner(company)"] += 1; partner = {"id": -1}
            else:
                partner = {"id": self.c.execute("aq.ops.engine", "bot_partner", [partner_name, {}])}
        proj = self.find("aq.ops.project", [["name", "=", existing_name or new_name]], ("id", "name", "objective", "stage"))
        desc = (data.get("description") or "").strip()
        if not proj:
            pid = self.bot_create("aq.ops.project", {"name": new_name, "partner_id": partner["id"], "service_type": "implementacion", "methodology": "kanban", "objective": desc,
                                                     "scope_current": desc, "date_start": d(data["created_date"]), "pm_id": self.member_for("antonio@alphaqueb.com"),
                                                     "admin_project_ref": "Origen: Taiga · %s" % data["name"]})
            proj = {"id": pid, "name": new_name, "objective": "", "stage": "autorizado"}
        elif desc and not proj.get("objective"):
            self.bot_write("aq.ops.project", [proj["id"]], {"objective": desc, "scope_current": desc})
        # equipo y contactos del cliente
        team, clients = [], []
        for m in data.get("memberships", []):
            email = m.get("user") or m.get("email")
            if not email:
                continue
            if email.split("@")[-1] in INTERNAL_DOMAINS or email in ("marinayarethmay@gmail.com", "dendira6@gmail.com", "rdavid.1018@gmail.com"):
                team.append(self.member_for(email))
            else:
                clients.append(self.client_contact(email, partner["id"]))
        vals = {"team_member_ids": [[4, i] for i in team if i and i > 0], "client_contact_ids": [[4, i] for i in clients if i and i > 0], "wip_limit": max((s.get("wip_limit") or 0) for s in data.get("us_statuses", [])) or 3}
        if any(v for v in vals.values()):
            self.bot_write("aq.ops.project", [proj["id"]], vals)
        return proj, partner["id"]

    # --- elementos
    def tag(self, data, ref):
        key = next((k for k in PROJECT_MAP if data["slug"].startswith(k)), data["slug"])
        return "taiga:%s#%s" % (key, ref)

    def existing_item(self, project_id, tag):
        return self.find("aq.ops.item", [["project_id", "=", project_id], ["tags", "ilike", tag]])

    def item_vals(self, data, u, project_id, name, parent=False, item_type="historia", desc_override=None):
        state = STATUS_MAP.get(u.get("status"), "backlog")
        if u.get("is_blocked"):
            state = "bloqueado"
        assignee = self.member_for(u.get("assigned_to")) if u.get("assigned_to") else False
        desc = desc_override if desc_override is not None else (u.get("description") or "")
        header = "Origen: Taiga %s · ref #%s · creado %s por %s" % (data["name"], u["ref"], d(u["created_date"]), self.names.get(u.get("owner"), u.get("owner") or "—"))
        vals = {"name": name[:200], "item_type": item_type, "project_id": project_id, "state": state, "assignee_id": assignee or False, "parent_id": parent or False,
                "description": (md_to_html(desc) or "") + "<p style='color:#888;font-size:11px'>%s</p>" % header,
                "date_due": d(u.get("due_date")), "tags": self.tag(data, u["ref"]), "blocked_reason": u.get("blocked_note") or False,
                "priority": "1" if u.get("client_requirement") else "0", "client_visible": bool(u.get("client_requirement")),
                "done_date": d(u.get("finish_date")) if state == "cerrado" else False, "started_date": d(u.get("created_date")) if state != "backlog" else False}
        if state == "cerrado" and not vals["done_date"]:
            vals["done_date"] = d(u.get("modified_date"))
        return vals

    def import_comments(self, data, u, item_id):
        for h in u.get("history", []):
            com = (h.get("comment") or "").strip()
            if not com or com == "?":
                continue
            usr = h.get("user")
            who = usr[1] if isinstance(usr, list) and len(usr) == 2 else str(usr)
            body = "[Taiga · %s · %s] %s" % (who, (h.get("created_at") or "")[:16].replace("T", " "), com)
            if self.find("aq.ops.comment", [["item_id", "=", item_id], ["body", "=", body]]):
                continue
            self.bot_create("aq.ops.comment", {"item_id": item_id, "body": body, "internal": True})

    def import_attachments(self, u, item_id):
        for a in u.get("attachments", []):
            f = a.get("attached_file") or {}
            if not f.get("data"):
                continue
            if self.find("ir.attachment", [["res_model", "=", "aq.ops.item"], ["res_id", "=", item_id], ["name", "=", a["name"]]]):
                continue
            self.bot_create("ir.attachment", {"name": a["name"], "datas": f["data"], "res_model": "aq.ops.item", "res_id": item_id, "description": a.get("description") or ""})

    def import_project(self, path):
        data = json.load(open(path))
        self.collect_names(data)
        print("\n=== %s (%s)" % (data["name"], data["slug"]))
        proj, partner_id = self.project_for(data)
        pid = proj["id"]
        stories = data.get("user_stories", [])
        # 1) épicas de Taiga
        epic_by_ref = {}
        for e in data.get("epics", []):
            tag = self.tag(data, e["ref"])
            ex = self.existing_item(pid, tag)
            if ex:
                epic_by_ref[e["ref"]] = ex["id"]; continue
            vals = self.item_vals(data, e, pid, e["subject"], item_type="epica")
            vals["state"] = EPIC_STATUS.get(e.get("status"), "backlog")
            eid = self.bot_create("aq.ops.item", vals)
            epic_by_ref[e["ref"]] = eid
            for r in e.get("related_user_stories", []):
                epic_by_ref.setdefault("us:%s" % r.get("user_story"), eid)
        # 2) agrupadores por asunto repetido → épica + hijas
        groups = defaultdict(list)
        for u in stories:
            k = u["subject"].strip().lower()
            if k in GROUP_SUBJECTS:
                groups[k].append(u)
        group_parent = {}
        for k, items in groups.items():
            label = GROUP_SUBJECTS[k]
            ex = self.find("aq.ops.item", [["project_id", "=", pid], ["item_type", "=", "epica"], ["name", "=", label]])
            if ex:
                group_parent[k] = ex["id"]
            else:
                all_done = all(STATUS_MAP.get(i["status"]) == "cerrado" for i in items)
                group_parent[k] = self.bot_create("aq.ops.item", {"name": label, "item_type": "epica", "project_id": pid, "state": "cerrado" if all_done else "en_progreso",
                                                                   "description": "<p>Agrupador importado de Taiga: %d historias con el asunto '%s'.</p>" % (len(items), label), "tags": "taiga:grupo"})
        # 3) duplicados exactos (mismo asunto y misma descripción) → uno solo
        seen = {}
        merged = defaultdict(list)
        for u in sorted(stories, key=lambda x: x["created_date"]):
            k = u["subject"].strip().lower()
            if k in GROUP_SUBJECTS:
                continue
            key = (k, (u.get("description") or "").strip().lower())
            if key in seen:
                merged[seen[key]].append(u["ref"]); u["_skip"] = True
            else:
                seen[key] = u["ref"]
        # 4) historias
        for u in stories:
            if u.get("_skip"):
                continue
            k = u["subject"].strip().lower()
            tag = self.tag(data, u["ref"])
            if self.existing_item(pid, tag):
                self.stats["skip:existing"] += 1; continue
            if k in GROUP_SUBJECTS:
                desc = (u.get("description") or "").strip()
                name = (desc.splitlines()[0] if desc else u["subject"])[:120]
                vals = self.item_vals(data, u, pid, name, parent=group_parent[k], item_type="tarea", desc_override=desc)
            else:
                parent = epic_by_ref.get("us:%s" % u["ref"], False)
                vals = self.item_vals(data, u, pid, u["subject"], parent=parent)
            if merged.get(u["ref"]):
                vals["description"] += "<p style='color:#888;font-size:11px'>Consolidado: también refs Taiga #%s (duplicados exactos).</p>" % ", #".join(str(r) for r in merged[u["ref"]])
            iid = self.bot_create("aq.ops.item", vals)
            if iid > 0:
                self.import_comments(data, u, iid)
                self.import_attachments(u, iid)
        # 5) issues → solicitudes
        for i in data.get("issues", []):
            name = i["subject"].strip()
            if self.find("aq.ops.request", [["project_id", "=", pid], ["name", "=", name]]):
                continue
            t = {"Question": "pregunta", "Bug": "defecto", "Enhancement": "mejora"}.get(i.get("type"), "sin_clasificar")
            urg = {"Wishlist": "baja", "Minor": "baja", "Normal": "media", "Important": "alta", "Critical": "critica"}.get(i.get("severity"), "media")
            rid = self.bot_create("aq.ops.request", {"name": name, "description": (i.get("description") or "") + "\n\nOrigen: Taiga %s · issue #%s" % (data["name"], i["ref"]), "source": "cliente",
                                                     "request_type": t, "partner_id": partner_id, "project_id": pid, "urgency": urg,
                                                     "state": "cerrada" if i.get("status") in ("Closed", "Rejected") else "nueva", "client_visible": True})
            if rid > 0:
                for h in i.get("history", []):
                    com = (h.get("comment") or "").strip()
                    if com and com != "?":
                        self.bot_create("aq.ops.comment", {"request_id": rid, "body": "[Taiga] " + com, "internal": True})
        # 6) wiki → documentación (solo con contenido)
        for w in data.get("wiki_pages", []):
            if not (w.get("content") or "").strip():
                continue
            if self.find("aq.ops.document", [["project_id", "=", pid], ["name", "=", w["slug"]]]):
                continue
            self.bot_create("aq.ops.document", {"name": w["slug"].replace("-", " ").title(), "doc_type": "procedimiento", "project_id": pid, "summary": w["content"][:2000], "version": str(w.get("version") or 1)})
        # 7) estado del proyecto y siguiente acción (regla AlphaOps)
        open_items = [u for u in stories if STATUS_MAP.get(u["status"]) not in ("cerrado",)]
        if open_items and proj.get("stage") == "autorizado":
            nxt = sorted(open_items, key=lambda x: (x.get("due_date") or "9", x["ref"]))[0]
            self.bot_write("aq.ops.project", [pid], {"stage": "ejecucion", "next_action": ("Avanzar: " + nxt["subject"])[:200],
                                                     "next_action_owner_id": self.member_for(nxt.get("assigned_to") or "antonio@alphaqueb.com"),
                                                     "next_action_date": (nxt.get("due_date") or (datetime.utcnow() + timedelta(days=7)).isoformat())[:10]})
        elif not open_items and proj.get("stage") == "autorizado" and stories:
            self.bot_write("aq.ops.project", [pid], {"stage": "estabilizacion", "next_action": "Definir siguiente etapa con el cliente", "next_action_owner_id": self.member_for("antonio@alphaqueb.com"),
                                                     "next_action_date": (datetime.utcnow() + timedelta(days=7)).isoformat()[:10]})
        print("   historias: %d (saltadas por duplicado exacto: %d) · épicas: %d · grupos: %s" % (len([s for s in stories if not s.get("_skip")]), len([s for s in stories if s.get("_skip")]), len(data.get("epics", [])), list(groups.keys())))


if __name__ == "__main__":
    imp = Importer()
    for f in FILES:
        imp.import_project(f)
    print("\nResumen%s:" % (" (simulación)" if DRY else ""))
    for k, v in sorted(imp.stats.items()):
        print("  %-32s %d" % (k, v))

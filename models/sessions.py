# -*- coding: utf-8 -*-
"""Generador y mapa de sesiones: folio por serie, evento de Calendar con Meet e invitados, importación del histórico,
post-proceso con IA (resumen ejecutivo en plantilla de Google Docs, correo y actividades automáticas)."""
import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SessionType(models.Model):
    _name = "aq.ops.session.type"
    _description = "AlphaOps: tipo de sesión"
    _order = "sequence"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Como aparece en el título, p. ej. DAILY SYNC")
    sequence = fields.Integer(default=10)
    duration_minutes = fields.Integer(default=30)
    meeting_type = fields.Selection([("kickoff", "Kickoff"), ("seguimiento", "Seguimiento"), ("validacion", "Validación"), ("tecnica", "Técnica"),
                                     ("direccion", "Dirección"), ("cliente", "Con cliente"), ("retro", "Retrospectiva"), ("otra", "Otra")], default="cliente")
    agenda_template = fields.Text(string="Agenda predeterminada")
    invite_team = fields.Boolean(default=True, string="Invitar equipo interno del proyecto")
    invite_client = fields.Boolean(default=True, string="Invitar contactos del cliente")
    client_visible = fields.Boolean(default=True)
    auto_process = fields.Boolean(default=True, string="Procesar con IA al recibir transcripción")


class OpsProjectSessions(models.Model):
    _inherit = "aq.ops.project"

    session_prefix = fields.Char(string="Prefijo de sesiones", help="GRUPO del título: SOMGROUP, SOMCABO, GETTING, CREATTIVO, HMX…")
    session_seq = fields.Integer(string="Última sesión (#)", default=0)
    session_po = fields.Char(string="Referencia PO (formato SAI)", help="Si se define (p. ej. PO-25002), el folio usa 'PO-25002-SAI-Sesión #n'.")
    group_email = fields.Char(string="Grupo de correo del cliente", help="Opcional: lista/grupo (p. ej. odoo@cliente.com) que se invita siempre.")
    session_count = fields.Integer(compute="_compute_session_count")

    def _compute_session_count(self):
        for p in self:
            p.session_count = self.env["aq.ops.meeting"].search_count([("project_id", "=", p.id)])

    def next_folio(self, stype_name, when):
        """Folio siguiendo la nomenclatura histórica real."""
        self.ensure_one()
        n = self.session_seq + 1
        prefix = (self.session_prefix or (self.partner_id.name or "SESION").split()[0].upper())[:12]
        if self.session_po:
            title = "%s-%s-Sesión #%d - %s" % (self.session_po, prefix, n, stype_name)
        else:
            title = "SESIÓN #%d– %s– %s | %s" % (n, prefix, stype_name.upper(), when.strftime("%d/%m/%Y"))
        return n, title


class OpsMeetingSession(models.Model):
    _inherit = "aq.ops.meeting"

    folio = fields.Integer(string="Folio (#)", index=True)
    session_type_id = fields.Many2one("aq.ops.session.type", string="Tipo de sesión")
    processed = fields.Boolean(string="Procesada por IA", readonly=True)
    exec_summary = fields.Html(string="Resumen ejecutivo", readonly=True)
    summary_doc_url = fields.Char(string="Resumen en Google Docs", readonly=True)
    summary_sent = fields.Boolean(readonly=True, string="Resumen enviado por correo")
    imported = fields.Boolean(string="Importada del histórico", readonly=True)

    # ------------------------------------------------------------------ generador
    @api.model
    def generate_session(self, project, stype, start_dt, duration=None, extra_emails=None, agenda=None, user=None):
        project.ensure_one()
        acc = self.env["aq.google.sync"]._account()
        n, title = project.next_folio(stype.name, start_dt)
        emails = set(e.strip().lower() for e in (extra_emails or []) if e and "@" in e)
        members = project.team_member_ids | project.pm_id | project.functional_lead_id | project.tech_lead_id
        if stype.invite_team:
            emails |= {m.email.lower() for m in members if m.email}
        if stype.invite_client:
            emails |= {p.email.lower() for p in project.client_contact_ids if p.email}
            if project.group_email:
                emails.add(project.group_email.lower())
        end_dt = start_dt + timedelta(minutes=duration or stype.duration_minutes or 30)
        body = {"summary": title, "description": (agenda or stype.agenda_template or "") + "\n\n— Generado por AlphaOps", "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "America/Mexico_City"},
                "end": {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "America/Mexico_City"},
                "attendees": [{"email": e} for e in sorted(emails)], "conferenceData": {"createRequest": {"requestId": "aqops-%s-%s" % (project.id, fields.Datetime.now().strftime("%H%M%S")), "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
                "guestsCanModify": False, "reminders": {"useDefault": True}}
        ev = acc._call("POST", "https://www.googleapis.com/calendar/v3/calendars/%s/events" % (acc.calendar_id or "primary"), params={"conferenceDataVersion": 1, "sendUpdates": "all"}, json=body)
        meet = ev.get("hangoutLink") or next((p.get("uri") for p in (ev.get("conferenceData", {}).get("entryPoints") or []) if p.get("entryPointType") == "video"), "")
        m = self.create({"name": title, "project_id": project.id, "date": start_dt, "meeting_type": stype.meeting_type, "session_type_id": stype.id, "folio": n,
                         "member_ids": [(6, 0, members.ids)] if stype.invite_team else False, "client_partner_ids": [(6, 0, project.client_contact_ids.ids)] if stype.invite_client else False,
                         "agenda": agenda or stype.agenda_template, "location": meet, "google_event_id": ev.get("id"), "meet_code": (ev.get("conferenceData", {}).get("conferenceId") or ""),
                         "client_visible": stype.client_visible})
        project.with_context(aq_skip_activity=True).write({"session_seq": n})
        return m, ev

    # ------------------------------------------------------------------ post-proceso (transcripción → resumen ejecutivo → Docs → correo → actividades)
    def process_with_ai(self):
        AI = self.env["aq.ops.ai"].sudo()
        Brand = self.env["aq.portal.branding"]
        icp = self.env["ir.config_parameter"].sudo()
        auto_items = icp.get_param("aq_ops.auto_confirm_agreements", "1") == "1"
        for m in self:
            text = re.sub(r"<[^>]+>", " ", m.transcript or m.minutes or m.agenda or "")
            if not text.strip():
                raise UserError(_("La sesión no tiene transcripción ni minuta."))
            data = AI.summarize_meeting(m)  # crea acuerdos propuestos + resumen corto
            exec_json = self.build_exec_summary(m.name, m.project_id.name, m.date, text)
            exec_json = exec_json if exec_json.get("resumen") or exec_json.get("acuerdos") else {"objetivo": "", "resumen": data.get("summary") or text[:800], "temas": [], "decisiones": data.get("decisions") and [d.get("name") for d in data["decisions"]] or [],
                                      "acuerdos": [{"acuerdo": a.get("name"), "responsable": a.get("owner"), "fecha": a.get("due_date")} for a in data.get("agreements", [])],
                                      "pendientes_cliente": [], "riesgos": data.get("risks", []), "siguientes_pasos": [], "proxima_sesion": ""}
            html = self._exec_html(m, exec_json)
            m.with_context(aq_skip_activity=True).write({"exec_summary": html, "processed": True, "state": "realizada" if m.state == "programada" else m.state})
            # actividades automáticas desde acuerdos
            if auto_items:
                for a in m.agreement_ids.filtered(lambda x: not x.confirmed and (x.owner_id or x.owner_partner_id or True)):
                    try:
                        a.with_context(portal_user_id=self.env.context.get("portal_user_id")).action_confirm()
                    except Exception as e:  # noqa
                        _logger.info("Acuerdo %s: %s", a.name, e)
            # Google Doc con la plantilla
            try:
                m._create_summary_doc(exec_json)
            except Exception as e:  # noqa
                _logger.warning("Doc de resumen: %s", e)
            # correo
            try:
                m._send_summary_email(html)
            except Exception as e:  # noqa
                _logger.warning("Correo de resumen: %s", e)
            self.env["aq.ops.notification"].sudo().notify_role(m.project_id, ["pm"], "resumen", _("Resumen ejecutivo listo: %s") % m.name, "meetings", m.id)
        return True

    @api.model
    def build_exec_summary(self, name, project_name, date, text):
        """Genera el JSON del resumen ejecutivo a partir de una transcripción, sin requerir reunión ni proyecto."""
        AI = self.env["aq.ops.ai"].sudo()
        out = AI.chat_json("Eres el redactor ejecutivo de AlphaQueb Consulting. Redacta en español profesional, prosa natural (nunca JSON ni Markdown dentro de los textos). "
                           "Devuelve exclusivamente un objeto JSON con esta forma: "
                           "{\"objetivo\": str, \"resumen\": str (2-3 párrafos narrativos), \"temas\": [{\"titulo\": str, \"detalle\": str (párrafo)}], \"decisiones\": [str], "
                           "\"acuerdos\": [{\"acuerdo\": str, \"responsable\": str, \"fecha\": str}], \"pendientes_cliente\": [str], \"riesgos\": [str], \"siguientes_pasos\": [str], \"proxima_sesion\": str}. "
                           "Sesión: %s · Proyecto: %s · Fecha: %s.\nTranscripción:\n%s"
                           % (name, project_name or "(por identificar)", date, text[:14000]), max_tokens=2800, tier="deep")
        if out:
            return out
        # sin IA: heurística mínima
        h = self.env["aq.ops.ai"]._heuristic_meeting(text)
        return {"objetivo": "", "resumen": h.get("summary"), "temas": [], "decisiones": [], "acuerdos": h.get("agreements", []),
                "pendientes_cliente": [], "riesgos": h.get("risks", []), "siguientes_pasos": [], "proxima_sesion": ""}

    @api.model
    def exec_html(self, name, project_name, date, folio, d):
        class _M:  # adaptador mínimo
            pass
        m = _M(); m.name = name; m.folio = folio; m.date = date
        class _P:
            pass
        m.project_id = _P(); m.project_id.name = project_name or "(por identificar)"
        return self._exec_html(m, d)

    @api.model
    def create_summary_doc_generic(self, title, project_name, partner_name, date, d):
        """Copia la plantilla membretada y escribe el resumen como contenido con formato (títulos, párrafos y viñetas).
        Si la plantilla tuviera marcadores {{...}}, se usan; si su cuerpo está vacío (membrete), se inserta el contenido."""
        acc = self.env["aq.google.sync"]._account()
        template = self.env["aq.ops.meeting"]._template_id(acc)
        copy = acc.post("https://www.googleapis.com/drive/v3/files/%s/copy" % template, {"name": "Resumen Ejecutivo · %s" % title[:110], "parents": [acc.drive_folder_id("AlphaOps")]})
        did = copy["id"]
        tpl_text = ""
        try:
            tpl_text = acc.doc_text(template) or ""
        except Exception:
            pass
        def plain(i):
            return re.sub(r"<[^>]+>", "", self._fmt_item(i))
        if "{{" in tpl_text:
            def txt(items):
                return "\n".join("• " + plain(i) for i in (items or []) if i) or "—"
            repl = {"{{FOLIO}}": title, "{{PROYECTO}}": project_name or "(por identificar)", "{{CLIENTE}}": partner_name or "", "{{FECHA}}": str(date or ""),
                    "{{OBJETIVO}}": d.get("objetivo") or "—", "{{RESUMEN}}": d.get("resumen") or "—", "{{TEMAS}}": txt(d.get("temas")), "{{DECISIONES}}": txt(d.get("decisiones")),
                    "{{ACUERDOS}}": txt(d.get("acuerdos")), "{{PENDIENTES}}": txt(d.get("pendientes_cliente")), "{{RIESGOS}}": txt(d.get("riesgos")), "{{PASOS}}": txt(d.get("siguientes_pasos")), "{{PROXIMA}}": d.get("proxima_sesion") or "por definir"}
            acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": [{"replaceAllText": {"containsText": {"text": k, "matchCase": True}, "replaceText": (v or "")[:6000]}} for k, v in repl.items()]})
        else:
            acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": self._docs_requests(title, project_name, partner_name, date, d)})
        return "https://docs.google.com/document/d/%s/edit" % did

    @api.model
    def _docs_requests(self, title, project_name, partner_name, date, d):
        """Construye el contenido con estilos nativos de Google Docs sobre el membrete."""
        segs = []  # (texto, estilo, bullet)
        def seg(t, style="NORMAL_TEXT", bullet=False):
            t = (t or "").replace("\r", "").strip()
            if t:
                segs.append((t, style, bullet))
        def items(lst):
            for i in (lst or []):
                if i:
                    seg(re.sub(r"<[^>]+>", "", self._fmt_item(i)), "NORMAL_TEXT", True)
        seg("Resumen Ejecutivo de Sesión", "HEADING_1")
        seg(title, "HEADING_2")
        seg("%s · %s · %s" % (project_name or "(por identificar)", partner_name or "", str(date or "")), "SUBTITLE")
        if d.get("objetivo"):
            seg("Objetivo", "HEADING_2"); seg(d["objetivo"])
        seg("Resumen", "HEADING_2")
        for par in (d.get("resumen") or "—").split("\n"):
            seg(par)
        for t in (d.get("temas") or []):
            seg(t.get("titulo") or "Tema", "HEADING_3"); seg(t.get("detalle"))
        if d.get("decisiones"):
            seg("Decisiones", "HEADING_2"); items(d["decisiones"])
        seg("Acuerdos y compromisos", "HEADING_2")
        if d.get("acuerdos"):
            items(d["acuerdos"])
        else:
            seg("Sin acuerdos registrados.")
        if d.get("pendientes_cliente"):
            seg("Pendientes del cliente", "HEADING_2"); items(d["pendientes_cliente"])
        if d.get("riesgos"):
            seg("Riesgos", "HEADING_2"); items(d["riesgos"])
        if d.get("siguientes_pasos"):
            seg("Siguientes pasos", "HEADING_2"); items(d["siguientes_pasos"])
        seg("Próxima sesión", "HEADING_2"); seg(d.get("proxima_sesion") or "Por definir")
        full = "".join(t + "\n" for t, _st, _b in segs)
        def u16(x):
            return len(x.encode("utf-16-le")) // 2
        reqs = [{"insertText": {"location": {"index": 1}, "text": full}}]
        idx = 1
        bullet_start = None
        for i, (t, st, b) in enumerate(segs):
            start, end = idx, idx + u16(t) + 1
            if st != "NORMAL_TEXT" or not b:
                reqs.append({"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": end}, "paragraphStyle": {"namedStyleType": st}, "fields": "namedStyleType"}})
            if b and bullet_start is None:
                bullet_start = start
            if (not b or i == len(segs) - 1) and bullet_start is not None:
                bend = end if b else start
                reqs.append({"createParagraphBullets": {"range": {"startIndex": bullet_start, "endIndex": bend}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
                bullet_start = None
            idx = end
        return reqs

    @staticmethod
    def _fmt_item(i):
        if isinstance(i, str):
            return i
        if isinstance(i, dict):
            if "acuerdo" in i:
                return "<b>%s</b> — %s · %s" % (i.get("acuerdo", ""), i.get("responsable") or "por asignar", i.get("fecha") or "sin fecha")
            if "titulo" in i:
                return "<b>%s.</b> %s" % (i.get("titulo", ""), i.get("detalle", ""))
            return " · ".join("%s" % v for v in i.values() if v)
        return str(i)

    def _exec_html(self, m, d):
        def ul(items):
            items = [i for i in (items or []) if i]
            return "<ul>%s</ul>" % "".join("<li>%s</li>" % self._fmt_item(i) for i in items) if items else "<p>—</p>"
        acuerdos = "".join("<li>%s</li>" % self._fmt_item(a) for a in (d.get("acuerdos") or []))
        temas = "".join("<h4>%s</h4><p>%s</p>" % (t.get("titulo", ""), t.get("detalle", "")) for t in (d.get("temas") or []))
        return ("<h2>%s</h2><p><b>Proyecto:</b> %s · <b>Fecha:</b> %s · <b>Folio:</b> %s</p><h3>Objetivo</h3><p>%s</p><h3>Resumen</h3><p>%s</p>%s"
                "<h3>Decisiones</h3>%s<h3>Acuerdos y compromisos</h3><ul>%s</ul><h3>Pendientes del cliente</h3>%s<h3>Riesgos</h3>%s<h3>Siguientes pasos</h3>%s<p><b>Próxima sesión:</b> %s</p>") % (
            m.name, m.project_id.name, m.date, m.folio or "—", d.get("objetivo") or "—", (d.get("resumen") or "").replace("\n", "<br/>"), temas,
            ul(d.get("decisiones")), acuerdos or "<li>—</li>", ul(d.get("pendientes_cliente")), ul(d.get("riesgos")), ul(d.get("siguientes_pasos")), d.get("proxima_sesion") or "por definir")

    @api.model
    def _template_id(self, acc):
        icp = self.env["ir.config_parameter"].sudo()
        tid = icp.get_param("aq_google.session_template_doc_id")
        if tid:
            return tid
        found = acc.drive_search("mimeType='application/vnd.google-apps.document' and trashed=false and (name contains 'Plantilla' and (name contains 'Sesi' or name contains 'Resumen' or name contains 'Minuta'))")
        if found:
            icp.set_param("aq_google.session_template_doc_id", found[0]["id"])
            return found[0]["id"]
        # crea una plantilla base con los marcadores
        folder = acc.drive_folder_id("AlphaOps")
        text = ("{{FOLIO}}\n{{PROYECTO}} · {{CLIENTE}} · {{FECHA}}\n\nOBJETIVO\n{{OBJETIVO}}\n\nRESUMEN EJECUTIVO\n{{RESUMEN}}\n\nTEMAS TRATADOS\n{{TEMAS}}\n\nDECISIONES\n{{DECISIONES}}\n\n"
                "ACUERDOS Y COMPROMISOS\n{{ACUERDOS}}\n\nPENDIENTES DEL CLIENTE\n{{PENDIENTES}}\n\nRIESGOS\n{{RIESGOS}}\n\nSIGUIENTES PASOS\n{{PASOS}}\n\nPRÓXIMA SESIÓN\n{{PROXIMA}}\n\n— AlphaQueb Consulting · alphaqueb.com")
        tid, _url = acc.create_doc("Plantilla · Resumen Ejecutivo de Sesión (AlphaOps)", text, folder)
        icp.set_param("aq_google.session_template_doc_id", tid)
        return tid

    def _create_summary_doc(self, d):
        self.ensure_one()
        url = self.create_summary_doc_generic(self.name, self.project_id.name, self.project_id.partner_id.name, self.date, d)
        self.with_context(aq_skip_activity=True).write({"summary_doc_url": url, "google_doc_url": url})
        self.env["aq.ops.document"].sudo().create({"name": "Resumen · %s" % self.name, "doc_type": "minuta", "project_id": self.project_id.id, "drive_url": url, "meeting_id": self.id, "client_visible": self.client_visible})
        return url

    def _send_summary_email(self, html):
        self.ensure_one()
        Brand = self.env["aq.portal.branding"]
        emails = set(self.member_ids.filtered("email").mapped("email"))
        for u in self.env["aq.portal.user"].sudo().search([("role", "=", "direccion"), ("active", "=", True)]):
            emails.add(u.email)
        body = Brand.wrap(_("Resumen ejecutivo · %s") % self.name, html + (("<p><a href='%s'>Documento en Google Docs</a></p>" % self.summary_doc_url) if self.summary_doc_url else ""),
                          _("Ver sesión en Operaciones"), Brand.portal_url("meetings", self.id))
        for e in emails:
            self.env["mail.mail"].sudo().create({"subject": _("Resumen ejecutivo · %s") % self.name, "email_to": e, "body_html": body}).send()
        self.with_context(aq_skip_activity=True).write({"summary_sent": True})

    def action_process_ai(self):
        return self.process_with_ai()


class SessionImport(models.AbstractModel):
    """Importa el histórico de Calendar para construir el mapa de sesiones."""
    _name = "aq.ops.session.importer"
    _description = "AlphaOps: importador de sesiones históricas"

    PREFIX_MAP = {"STONIA": "Stonia", "SOMGROUP": "Stonia", "SOM": "Stonia", "SOMCABO": "SOM Cabos", "GETTING": "Getting Ready", "CREATTIVO": "Creattivo", "SAI": "SAI", "HMX": "Hexágonos", "HEXÁGONOS": "Hexágonos", "HEXAGONOS": "Hexágonos"}
    DOMAIN_MAP = {"somgroup.mx": "Stonia", "stonia.com.mx": "Stonia", "hexagonosmexicanos.com": "Hexágonos", "creattivo.mx": "Creattivo"}
    TYPE_PATTERNS = [("DAILY", "Daily Sync"), ("RETROSPECTIVA", "Retrospectiva"), ("CAPACITACI", "Capacitación"), ("ENTREGA", "Entrega"), ("VALIDACI", "Validación"),
                     ("PRUEBAS", "Pruebas / UAT"), ("UAT", "Pruebas / UAT"), ("KICK", "Kickoff"), ("SEGUIMIENTO", "Seguimiento"), ("REVISI", "Revisión"), ("EMERGENCIA", "Emergencia"), ("PRODUC", "Producción")]

    def _project(self, hint):
        return self.env["aq.ops.project"].sudo().search([("name", "ilike", hint)], limit=1)

    @api.model
    def import_history(self, months=12):
        acc = self.env["aq.google.sync"]._account()
        Meeting = self.env["aq.ops.meeting"].sudo()
        Types = {t.name: t for t in self.env["aq.ops.session.type"].sudo().search([])}
        now = fields.Datetime.now()
        events, token = [], None
        while True:
            params = {"timeMin": (now - timedelta(days=30 * months)).strftime("%Y-%m-%dT%H:%M:%SZ"), "timeMax": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}
            if token:
                params["pageToken"] = token
            r = acc.get("https://www.googleapis.com/calendar/v3/calendars/%s/events" % (acc.calendar_id or "primary"), params)
            events += r.get("items", [])
            token = r.get("nextPageToken")
            if not token:
                break
        stats = {"creadas": 0, "actualizadas": 0, "sin_proyecto": 0, "total": len(events)}
        maxseq = {}
        for ev in events:
            title = (ev.get("summary") or "").strip()
            if not title or ev.get("status") == "cancelled":
                continue
            start = (ev.get("start") or {}).get("dateTime") or ((ev.get("start") or {}).get("date", "") + "T09:00:00")
            up = title.upper()
            folio, prefix, po = 0, None, None
            m1 = re.search(r"SESI[ÓO]N\s*(?:DE\s+\w+\s*)?#(\d+)\s*[–\-]*\s*([A-ZÁÉÍÓÚ]+)?", up)
            m2 = re.search(r"(PO-\d{4,6})-([A-Z]+)-SESI[ÓO]N\s*#(\d+)", up)
            if m2:
                po, prefix, folio = m2.group(1), m2.group(2), int(m2.group(3))
            elif m1:
                folio, prefix = int(m1.group(1)), (m1.group(2) or "")
            hint = self.PREFIX_MAP.get(prefix or "", None)
            if not hint:
                for k, v in self.PREFIX_MAP.items():
                    if k in up:
                        hint = v; break
            if not hint:
                doms = {a.get("email", "").split("@")[-1].lower() for a in ev.get("attendees", [])}
                hint = next((v for d, v in self.DOMAIN_MAP.items() if d in doms), None)
            project = self._project(hint) if hint else self.env["aq.ops.project"].sudo()
            if not project:
                stats["sin_proyecto"] += 1
                continue
            stype_name = next((n for k, n in self.TYPE_PATTERNS if k in up), "Seguimiento")
            stype = Types.get(stype_name)
            vals = {"name": title[:200], "project_id": project.id, "date": fields.Datetime.to_datetime(start[:19].replace("T", " ")), "folio": folio or False,
                    "session_type_id": stype.id if stype else False, "meeting_type": stype.meeting_type if stype else "cliente", "google_event_id": ev.get("id"),
                    "meet_code": (ev.get("conferenceData") or {}).get("conferenceId") or "", "location": ev.get("hangoutLink"), "state": "realizada", "imported": True,
                    "client_visible": True}
            existing = Meeting.search([("google_event_id", "=", ev["id"])], limit=1)
            if existing:
                existing.with_context(aq_skip_activity=True).write({"folio": folio or existing.folio, "session_type_id": vals["session_type_id"] or existing.session_type_id.id, "imported": True})
                stats["actualizadas"] += 1
            else:
                Meeting.create(vals)
                stats["creadas"] += 1
            if folio and prefix:
                key = (project.id, prefix, po)
                maxseq[key] = max(maxseq.get(key, 0), folio)
            self.env.cr.commit()
        # secuencias y prefijos por proyecto (el prefijo más reciente gana: STONIA→SOMGROUP)
        for (pid, prefix, po), n in sorted(maxseq.items(), key=lambda x: x[1]):
            p = self.env["aq.ops.project"].sudo().browse(pid)
            vals = {}
            if n > p.session_seq:
                vals["session_seq"] = n
            if prefix and prefix not in ("STONIA",):
                vals["session_prefix"] = prefix
            elif prefix and not p.session_prefix:
                vals["session_prefix"] = prefix
            if po:
                vals["session_po"] = po
            if vals:
                p.with_context(aq_skip_activity=True).write(vals)
        # tarea pendiente: procesar transcripciones históricas
        for p in self.env["aq.ops.project"].sudo().search([("session_seq", ">", 0)]):
            if not self.env["aq.ops.item"].sudo().search_count([("project_id", "=", p.id), ("name", "=", "Procesar transcripciones de sesiones históricas")]):
                self.env["aq.ops.item"].sudo().create({"name": "Procesar transcripciones de sesiones históricas", "item_type": "tarea", "project_id": p.id, "state": "backlog",
                                                       "description": "<p>Tarea futura: recuperar y procesar con IA las transcripciones/notas de las sesiones importadas del histórico (mapa de sesiones).</p>", "tags": "sesiones,historico"})
        self.env.cr.commit()
        return stats

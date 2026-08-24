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
    _description = "Alphaops: tipo de sesión"
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
    drive_folder_id = fields.Char(string="Carpeta de Drive del proyecto", help="Si se define, los documentos del proyecto se guardan ahí. Si se deja vacío, se crea Alphaops/<Proyecto>.")
    drive_folder_url = fields.Char(string="Enlace de la carpeta", compute="_compute_folder_url")

    def _compute_folder_url(self):
        for p in self:
            p.drive_folder_url = ("https://drive.google.com/drive/folders/%s" % p.drive_folder_id) if p.drive_folder_id else False

    def ensure_drive_folder(self, acc):
        """Carpeta destino de los documentos del proyecto (la crea la primera vez)."""
        self.ensure_one()
        if self.drive_folder_id:
            return self.drive_folder_id
        root = acc.drive_folder_id("Alphaops")
        fid = acc.drive_child_folder(self.name[:80], root)
        self.with_context(aq_skip_activity=True).write({"drive_folder_id": fid})
        return fid
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
    def suggested_invitees(self, project, stype):
        """Invitados sugeridos (pre-llenado editable): equipo interno, contactos del cliente y grupo de correo."""
        out = []
        members = project.team_member_ids | project.pm_id | project.functional_lead_id | project.tech_lead_id
        for m in members.filtered("email"):
            out.append({"email": m.email.lower(), "name": m.name, "kind": "interno", "checked": stype.invite_team})
        for pc in project.client_contact_ids.filtered("email"):
            out.append({"email": pc.email.lower(), "name": pc.name, "kind": "cliente", "checked": stype.invite_client})
        if project.group_email:
            out.append({"email": project.group_email.lower(), "name": _("Grupo del cliente"), "kind": "grupo", "checked": stype.invite_client})
        seen, dedup = set(), []
        for i in out:
            if i["email"] not in seen:
                seen.add(i["email"]); dedup.append(i)
        return dedup

    DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    MESES_C = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    @api.model
    def session_brief(self, project, stype, context, start_dt=None, duration=None):
        """Convierte un contexto breve ('vamos a ver el módulo de compras') en objetivo, agenda y mensaje de invitación."""
        ctx = {"proyecto": project.name, "cliente": project.partner_id.name or "", "tipo": stype.name, "duracion": duration or stype.duration_minutes or 30,
               "contexto": (context or "").strip(), "fecha": self.human_when(start_dt) if start_dt else "", "etapa": dict(project._fields["stage"].selection).get(project.stage, "")}
        out = self.env["aq.ai.prompt"].sudo().render("session_brief", ctx)
        if not isinstance(out, dict):
            base = (context or "").strip() or stype.agenda_template or _("Sesión de trabajo del proyecto.")
            return {"objetivo": base[:200], "agenda": stype.agenda_template or base, "mensaje": base[:300]}
        agenda = out.get("agenda")
        if isinstance(agenda, list):
            agenda = "\n".join("%d. %s" % (i + 1, a) for i, a in enumerate(agenda) if a)
        return {"objetivo": out.get("objetivo") or "", "agenda": agenda or stype.agenda_template or "", "mensaje": out.get("mensaje") or out.get("objetivo") or ""}

    @api.model
    def human_when(self, dt):
        return "%s %d de %s · %s h" % (self.DIAS[dt.weekday()], dt.day, self.MESES_C[dt.month - 1], dt.strftime("%H:%M"))

    @api.model
    def share_text(self, title, project, start_dt, meet_link, note=None, duration=None):
        cuando = self.human_when(start_dt)
        fin = ""
        if duration:
            end = start_dt + timedelta(minutes=int(duration))
            fin = " a %s h" % end.strftime("%H:%M")
        cuerpo = ("\n%s\n" % note.strip()) if note else ""
        return (u"¡Hola! 👋\n\nTe invitamos de parte del equipo de Alphaqueb a la sesión:\n\n"
                u"📌 %s\n🏷️ Proyecto: %s\n🗓️ %s%s (hora del centro de México)\n%s\n🔗 Únete por Google Meet:\n%s\n\n"
                u"Si quieres sumar algún tema a la agenda, coméntanos por aquí. ¡Nos vemos!\n— Equipo Alphaqueb") % (
            title, project.name, cuando.capitalize(), fin, cuerpo, meet_link or "(liga por confirmar)")

    @api.model
    def generate_session(self, project, stype, start_dt, duration=None, extra_emails=None, agenda=None, user=None, attendees=None, send_invites=True, context_note=None, share_note=None):
        project.ensure_one()
        acc = self.env["aq.google.sync"]._account()
        n, title = project.next_folio(stype.name, start_dt)
        if attendees is not None:
            emails = set(e.strip().lower() for e in attendees if e and "@" in e)
        else:
            emails = set()
            members = project.team_member_ids | project.pm_id | project.functional_lead_id | project.tech_lead_id
            if stype.invite_team:
                emails |= {m.email.lower() for m in members if m.email}
            if stype.invite_client:
                emails |= {p.email.lower() for p in project.client_contact_ids if p.email}
                if project.group_email:
                    emails.add(project.group_email.lower())
        emails |= set(e.strip().lower() for e in (extra_emails or []) if e and "@" in e)
        members = project.team_member_ids | project.pm_id | project.functional_lead_id | project.tech_lead_id
        end_dt = start_dt + timedelta(minutes=duration or stype.duration_minutes or 30)
        desc = (agenda or stype.agenda_template or "").strip()
        if context_note and context_note.strip() not in desc:
            desc = (context_note.strip() + ("\n\n" + desc if desc else ""))
        body = {"summary": title, "description": desc + "\n\n— Generado por Alphaops", "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "America/Mexico_City"},
                "end": {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "America/Mexico_City"},
                "attendees": [{"email": e} for e in sorted(emails)], "conferenceData": {"createRequest": {"requestId": "aqops-%s-%s" % (project.id, fields.Datetime.now().strftime("%H%M%S")), "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
                "guestsCanModify": False, "reminders": {"useDefault": True}}
        ev = acc._call("POST", "https://www.googleapis.com/calendar/v3/calendars/%s/events" % (acc.calendar_id or "primary"), params={"conferenceDataVersion": 1, "sendUpdates": "all" if send_invites else "none"}, json=body)
        meet = ev.get("hangoutLink") or next((p.get("uri") for p in (ev.get("conferenceData", {}).get("entryPoints") or []) if p.get("entryPointType") == "video"), "")
        invited_members = members.filtered(lambda x: x.email and x.email.lower() in emails)
        invited_clients = project.client_contact_ids.filtered(lambda x: x.email and x.email.lower() in emails)
        m = self.create({"name": title, "project_id": project.id, "date": start_dt, "meeting_type": stype.meeting_type, "session_type_id": stype.id, "folio": n,
                         "member_ids": [(6, 0, invited_members.ids)], "client_partner_ids": [(6, 0, invited_clients.ids)],
                         "agenda": desc or stype.agenda_template, "location": meet, "google_event_id": ev.get("id"), "meet_code": (ev.get("conferenceData", {}).get("conferenceId") or ""),
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
        out = self.env["aq.ai.prompt"].sudo().render("session_exec_summary", {
            "titulo": name, "proyecto": project_name or "(por identificar)", "fecha": str(date or ""), "transcripcion": text[:14000]})
        if isinstance(out, dict) and (out.get("resumen") or out.get("acuerdos")):
            return out
        out = AI.chat_json("Eres el redactor ejecutivo de Alphaqueb Consulting. Redacta en español profesional, prosa natural (nunca JSON ni Markdown dentro de los textos). "
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

    @staticmethod
    def _fmt_item(i):
        """Convierte un elemento (texto o diccionario) en una línea legible; nunca deja JSON crudo."""
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
        """Versión HTML del documento (para el portal y el cuerpo del correo)."""
        def ul(items):
            items = [i for i in (items or []) if i]
            return "<ul>%s</ul>" % "".join("<li>%s</li>" % self._fmt_item(i) for i in items) if items else "<p>—</p>"
        acuerdos = "".join("<li>%s</li>" % self._fmt_item(a) for a in (d.get("acuerdos") or []))
        temas = "".join("<h4>%s</h4><p>%s</p>" % (t.get("titulo", ""), t.get("detalle", "")) if isinstance(t, dict) else "<p>%s</p>" % t for t in (d.get("temas") or []))
        return ("<h2>%s</h2><p><b>Proyecto:</b> %s · <b>Fecha:</b> %s%s</p><h3>Objetivo</h3><p>%s</p><h3>Resumen ejecutivo</h3><p>%s</p>%s"
                "<h3>Decisiones</h3>%s<h3>Acuerdos y compromisos</h3><ul>%s</ul><h3>Pendientes del cliente</h3>%s<h3>Riesgos</h3>%s<h3>Siguientes pasos</h3>%s<p><b>Próxima sesión:</b> %s</p>") % (
            m.name, m.project_id.name, m.date, (" · <b>Folio:</b> %s" % m.folio) if getattr(m, "folio", None) else "", d.get("objetivo") or "—",
            (d.get("resumen") or "").replace("\n", "<br/>"), temas, ul(d.get("decisiones")), acuerdos or "<li>—</li>",
            ul(d.get("pendientes_cliente")), ul(d.get("riesgos")), ul(d.get("siguientes_pasos")), d.get("proxima_sesion") or "por definir")

    @api.model
    def create_summary_doc_generic(self, title, project_name, partner_name, date, d, project=None, meeting=None):
        """Documento formal (no un simple resumen): portada, ficha, secciones numeradas, tablas de acuerdos y cierre."""
        acc = self.env["aq.google.sync"]._account()
        template = self.env["aq.ops.meeting"]._template_id(acc)
        folder = project.ensure_drive_folder(acc) if project else acc.drive_folder_id("Alphaops")
        blocks = self._doc_blocks(title, project_name, partner_name, date, d, meeting)
        did, url = self.env["aq.doc.builder"].build(acc, template, folder, "Resumen Ejecutivo · %s" % title[:110], blocks)
        return url if not self.env.context.get("aq_return_id") else (did, url)

    @api.model
    def _doc_blocks(self, title, project_name, partner_name, date, d, meeting=None):
        """Especificación del documento: bloques con jerarquía tipográfica de marca."""
        MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        dt = fields.Datetime.to_datetime(date) if date else fields.Datetime.now()
        fecha_larga = "%d de %s de %d · %s h" % (dt.day, MESES[dt.month - 1], dt.year, dt.strftime("%H:%M"))
        participantes = ""
        tipo = ""
        if meeting:
            internos = ", ".join(meeting.member_ids.mapped("name"))
            clientes = ", ".join(meeting.client_partner_ids.mapped("name"))
            participantes = " · ".join([x for x in (internos, clientes) if x])
            tipo = meeting.session_type_id.name or dict(meeting._fields["meeting_type"].selection).get(meeting.meeting_type, "")
        blocks = [
            {"type": "eyebrow", "text": "Alphaqueb Consulting · Documento de sesión"},
            {"type": "title", "text": title},
            {"type": "subtitle", "text": " · ".join([x for x in (project_name or "", partner_name or "", fecha_larga) if x])},
            {"type": "rule", "text": ""},
            {"type": "table", "header": False, "rows": [r for r in [
                ["Proyecto", project_name or "Por identificar"],
                ["Cliente", partner_name or "—"],
                ["Tipo de sesión", tipo or "Sesión de trabajo"],
                ["Fecha y hora", fecha_larga],
                ["Participantes", participantes or "—"],
                ["Elaborado por", "Alphaops · copiloto documental (revisión humana)"],
            ] if r[1]]},
            {"type": "spacer", "text": ""},
        ]
        n = [0]
        def section(titulo):
            n[0] += 1
            blocks.append({"type": "h1", "text": "%02d · %s" % (n[0], titulo)})
        def paras(txt):
            for par in [p.strip() for p in str(txt or "").split("\n") if p.strip()]:
                blocks.append({"type": "p", "text": par})
        def bullets(items):
            for i in (items or []):
                t = re.sub(r"<[^>]+>", "", self._fmt_item(i)).strip()
                if t:
                    blocks.append({"type": "bullet", "text": t})
        if d.get("objetivo"):
            section("Objetivo de la sesión"); paras(d["objetivo"])
        section("Resumen ejecutivo"); paras(d.get("resumen") or "Sin contenido registrado.")
        if d.get("temas"):
            section("Temas tratados")
            for t in d["temas"]:
                if isinstance(t, dict):
                    blocks.append({"type": "h2", "text": t.get("titulo") or "Tema"}); paras(t.get("detalle"))
                else:
                    blocks.append({"type": "bullet", "text": str(t)})
        if d.get("decisiones"):
            section("Decisiones tomadas"); bullets(d["decisiones"])
        section("Acuerdos y compromisos")
        acuerdos = d.get("acuerdos") or []
        if acuerdos:
            rows = [["Acuerdo / compromiso", "Responsable", "Fecha compromiso"]]
            for a in acuerdos:
                if isinstance(a, dict):
                    rows.append([a.get("acuerdo") or "", a.get("responsable") or "Por asignar", a.get("fecha") or "Por definir"])
                else:
                    rows.append([str(a), "Por asignar", "Por definir"])
            blocks.append({"type": "table", "header": True, "rows": rows})
            blocks.append({"type": "spacer", "text": ""})
        else:
            blocks.append({"type": "p", "text": "No se registraron acuerdos formales en esta sesión."})
        if d.get("pendientes_cliente"):
            section("Pendientes a cargo del cliente"); bullets(d["pendientes_cliente"])
        if d.get("riesgos"):
            section("Riesgos y alertas"); bullets(d["riesgos"])
        if d.get("siguientes_pasos"):
            section("Siguientes pasos"); bullets(d["siguientes_pasos"])
        section("Próxima sesión"); paras(d.get("proxima_sesion") or "Por definir en el seguimiento del proyecto.")
        blocks += [
            {"type": "rule", "text": ""},
            {"type": "note", "text": "Documento elaborado por Alphaops a partir de la transcripción de la sesión y revisado por el equipo de Alphaqueb Consulting. "
                                     "La información aquí contenida es confidencial y de uso exclusivo de las partes involucradas en el proyecto."},
        ]
        return blocks

    def _create_summary_doc(self, d):
        self.ensure_one()
        url = self.create_summary_doc_generic(self.name, self.project_id.name, self.project_id.partner_id.name, self.date, d, project=self.project_id, meeting=self)
        self.with_context(aq_skip_activity=True).write({"summary_doc_url": url, "google_doc_url": url})
        self.env["aq.ops.document"].sudo().create({"name": "Resumen · %s" % self.name, "doc_type": "minuta", "project_id": self.project_id.id, "drive_url": url, "meeting_id": self.id, "client_visible": self.client_visible})
        return url

    def _send_summary_email(self, html):
        """Envía el documento: lo comparte en Drive con los participantes y adjunta el PDF."""
        self.ensure_one()
        Brand = self.env["aq.portal.branding"]
        emails = set(e.lower() for e in self.member_ids.filtered("email").mapped("email"))
        emails |= set(e.lower() for e in self.client_partner_ids.filtered("email").mapped("email"))
        for u in self.env["aq.portal.user"].sudo().search([("role", "=", "direccion"), ("active", "=", True)]):
            if u.email:
                emails.add(u.email.lower())
        attachments = []
        doc_id = (self.summary_doc_url or "").split("/d/")[-1].split("/")[0] if self.summary_doc_url else None
        if doc_id:
            try:
                acc = self.env["aq.google.sync"]._account()
                acc.drive_share(doc_id, list(emails), role="writer" if not self.client_partner_ids else "reader")
                pdf = acc.drive_export_pdf(doc_id)
                att = self.env["ir.attachment"].sudo().create({"name": "Resumen Ejecutivo · %s.pdf" % self.name[:80], "datas": pdf, "mimetype": "application/pdf",
                                                               "res_model": self._name, "res_id": self.id})
                attachments = [(4, att.id)]
            except Exception as e:  # noqa
                _logger.warning("Compartir/adjuntar documento: %s", e)
        intro = ("<p>Hola:</p><p>Compartimos el <b>documento formal</b> de la sesión <b>%s</b>. Puedes abrirlo en Google Docs "
                 "(ya tienes acceso con tu correo) o revisar el PDF adjunto.</p>") % self.name
        links = ""
        if self.summary_doc_url:
            links += "<p><a href='%s'><b>📄 Abrir documento en Google Docs</b></a></p>" % self.summary_doc_url
        if self.project_id.drive_folder_url:
            links += "<p><a href='%s'>Carpeta del proyecto en Drive</a></p>" % self.project_id.drive_folder_url
        body = Brand.wrap(_("Resumen ejecutivo · %s") % self.name, intro + links + "<hr/>" + html,
                          _("Ver sesión en Operaciones"), Brand.portal_url("meetings", self.id))
        for e in sorted(emails):
            self.env["mail.mail"].sudo().create({"subject": _("Resumen ejecutivo · %s") % self.name, "email_to": e, "body_html": body,
                                                 "attachment_ids": attachments}).send()
        self.with_context(aq_skip_activity=True).write({"summary_sent": True})

    def action_process_ai(self):
        return self.process_with_ai()


class SessionImport(models.AbstractModel):
    """Importa el histórico de Calendar para construir el mapa de sesiones."""
    _name = "aq.ops.session.importer"
    _description = "Alphaops: importador de sesiones históricas"

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

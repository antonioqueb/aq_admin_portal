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
    session_po = fields.Char(string="Referencia del cliente (PO)", help="Referencia del cliente, p. ej. PO-25002. Su consecutivo es del cliente, no nuestro.")
    folio_scheme = fields.Selection([("interno", "Nuestro consecutivo (SESIÓN #n– SERIE– TIPO)"),
                                     ("cliente", "Consecutivo del cliente (PO-…-Sesión #n)")], default="interno", required=True,
                                    string="Nomenclatura del título", help="Con qué numeración se titula la sesión ante el cliente. El folio interno de Alphaqueb siempre se lleva aparte.")
    session_stage = fields.Integer(string="Etapa actual del proyecto", default=1,
                                   help="Cada etapa reinicia el consecutivo de sesiones en #1 (p. ej. SAI etapa 2).")
    stage_started_on = fields.Date(string="Inicio de la etapa actual")
    client_seq = fields.Integer(string="Última sesión del consecutivo del cliente", default=0,
                                help="Numeración que lleva el cliente (p. ej. SAI). No es nuestro folio interno.")
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

    def folios_usados(self, kind="interno", stage=None):
        """Folios ocupados. kind='interno' → consecutivo de Alphaqueb (de la etapa indicada); kind='cliente' → del cliente."""
        self.ensure_one()
        Meeting = self.env["aq.ops.meeting"].sudo()
        usados = set()
        dom = [("project_id", "=", self.id)]
        if kind == "interno":
            dom.append(("stage_no", "=", stage or self.session_stage or 1))
        for m in Meeting.search(dom):
            info = Meeting.parse_folio(m.name)
            if kind == "cliente":
                if m.client_folio:
                    usados.add(m.client_folio)
                elif info["client_folio"]:
                    usados.add(info["client_folio"])
            else:
                if m.folio:
                    usados.add(m.folio)
                elif info["folio"]:
                    usados.add(info["folio"])
        return usados

    def next_client_number(self):
        """Siguiente número del consecutivo que lleva el cliente (no es nuestro folio)."""
        self.ensure_one()
        usados = self.folios_usados("cliente")
        n = max([self.client_seq or 0] + list(usados) or [0]) + 1
        while n in usados:
            n += 1
        return n

    def next_folio_number(self):
        """Siguiente consecutivo de la ETAPA ACTUAL: continúa del folio más alto usado en esa etapa."""
        self.ensure_one()
        usados = self.folios_usados("interno", self.session_stage or 1)
        base = (self.session_seq or 0) if (self.session_stage or 1) == 1 or usados else 0
        n = max([base] + list(usados) or [0]) + 1
        while n in usados:
            n += 1
        return n

    def action_start_new_stage(self):
        """Inicia una nueva etapa del proyecto: el consecutivo de sesiones vuelve a #1."""
        for p in self:
            nueva = (p.session_stage or 1) + 1
            p.with_context(aq_skip_activity=True).write({"session_stage": nueva, "stage_started_on": fields.Date.context_today(p), "session_seq": 0})
            p.message_post(body=_("Inicia la etapa %d del proyecto: las sesiones vuelven a numerarse desde #1.") % nueva)
        return True

    def next_folio(self, stype_name, when, folio=None, client_folio=None):
        """Devuelve (folio interno, folio del cliente, título). El título usa la nomenclatura acordada con el cliente."""
        self.ensure_one()
        n = folio or self.next_folio_number()
        prefix = (self.session_prefix or (self.partner_id.name or "SESION").split()[0].upper())[:12]
        etapa = self.session_stage or 1
        cn = 0
        if self.folio_scheme == "cliente" and self.session_po:
            cn = client_folio or self.next_client_number()
            title = "%s-%s-Sesión #%d - %s" % (self.session_po, prefix, cn, stype_name)
        elif etapa > 1:
            title = "SESIÓN #%d ETAPA %d– %s– %s | %s" % (n, etapa, prefix, stype_name.upper(), when.strftime("%d/%m/%Y"))
        else:
            title = "SESIÓN #%d– %s– %s | %s" % (n, prefix, stype_name.upper(), when.strftime("%d/%m/%Y"))
        return n, cn, title

    def action_assign_missing_folios(self):
        """Integra al consecutivo INTERNO de Alphaqueb las sesiones que aún no lo tienen (orden cronológico).
        No toca el consecutivo del cliente ni renombra sesiones tituladas con la referencia del cliente."""
        Meeting = self.env["aq.ops.meeting"].sudo()
        total = 0
        for p in self:
            for m in Meeting.search([("project_id", "=", p.id), ("folio", "in", (False, 0))], order="date asc, id asc"):
                info = Meeting.parse_folio(m.name)
                usados = p.folios_usados("interno")
                n = info["folio"] if (info["folio"] and info["folio"] not in usados) else p.next_folio_number()
                vals = {"folio": n}
                if info["client_folio"] and not m.client_folio:
                    vals["client_folio"] = info["client_folio"]
                m.with_context(aq_skip_activity=True).write(vals)
                if n > (p.session_seq or 0):
                    p.with_context(aq_skip_activity=True).write({"session_seq": n})
                total += 1
            cli = p.folios_usados("cliente")
            if cli and max(cli) > (p.client_seq or 0):
                p.with_context(aq_skip_activity=True).write({"client_seq": max(cli)})
        return total


class OpsMeetingSession(models.Model):
    _inherit = "aq.ops.meeting"

    folio = fields.Integer(string="Folio (#)", index=True)
    session_type_id = fields.Many2one("aq.ops.session.type", string="Tipo de sesión")
    processed = fields.Boolean(string="Procesada por IA", readonly=True)
    exec_summary = fields.Html(string="Resumen ejecutivo", readonly=True)
    summary_doc_url = fields.Char(string="Resumen en Google Docs", readonly=True)
    summary_sent = fields.Boolean(readonly=True, string="Resumen enviado por correo")
    imported = fields.Boolean(string="Importada del histórico", readonly=True)
    stage_no = fields.Integer(string="Etapa del proyecto", default=1, index=True)
    original_title = fields.Char(string="Título original en Calendar", readonly=True)
    duplicate_of_id = fields.Many2one("aq.ops.meeting", string="Duplicado de", readonly=True)
    client_folio = fields.Integer(string="# del consecutivo del cliente", index=True, help="Numeración que lleva el cliente (p. ej. PO-25002-SAI-Sesión #45). No es nuestro folio.")
    followups_log = fields.Text(string="Seguimiento generado", readonly=True)
    followups_count = fields.Integer(string="Elementos de seguimiento", readonly=True)

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
        n, cn, title = project.next_folio(stype.name, start_dt)
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
        m = self.create({"name": title, "project_id": project.id, "date": start_dt, "meeting_type": stype.meeting_type, "session_type_id": stype.id, "folio": n, "client_folio": cn or False,
                         "stage_no": project.session_stage or 1,
                         "member_ids": [(6, 0, invited_members.ids)], "client_partner_ids": [(6, 0, invited_clients.ids)],
                         "agenda": desc or stype.agenda_template, "location": meet, "google_event_id": ev.get("id"), "meet_code": (ev.get("conferenceData", {}).get("conferenceId") or ""),
                         "client_visible": stype.client_visible})
        upd = {}
        if n > (project.session_seq or 0):
            upd["session_seq"] = n
        if cn and cn > (project.client_seq or 0):
            upd["client_seq"] = cn
        if upd:
            project.with_context(aq_skip_activity=True).write(upd)
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
            if m.project_id and not m.folio:
                try:
                    m.action_assign_folio()
                except Exception as e:  # noqa
                    _logger.info("Folio automático: %s", e)
            # se condensa UNA vez (map-reduce) y ambos análisis usan la misma versión sin perder contenido
            text = AI.condense_transcript(text, 13000)
            roster = m._roster_text()
            data = AI.summarize_meeting(m, text=text)  # crea acuerdos propuestos + resumen corto
            exec_json = self.build_exec_summary(m.name, m.project_id.name, m.date, text, roster=roster)
            exec_json = exec_json if exec_json.get("resumen") or exec_json.get("acuerdos") else {"objetivo": "", "resumen": data.get("summary") or text[:800], "temas": [], "decisiones": data.get("decisions") and [d.get("name") for d in data["decisions"]] or [],
                                      "acuerdos": [{"acuerdo": a.get("name"), "responsable": a.get("owner"), "fecha": a.get("due_date"), "tipo": a.get("kind")} for a in data.get("agreements", [])],
                                      "pendientes_cliente": [], "riesgos": data.get("risks", []), "siguientes_pasos": [], "preguntas_abiertas": data.get("questions", []), "proxima_sesion": ""}
            html = self._exec_html(m, exec_json)
            m.with_context(aq_skip_activity=True).write({"exec_summary": html, "processed": True, "state": "realizada" if m.state == "programada" else m.state})
            # ---- seguimiento: acuerdos → actividades, decisiones, riesgos, preguntas y siguiente acción
            resumen_seg = {}
            if m.project_id:
                try:
                    m._merge_agreements(exec_json)
                    if auto_items:
                        for a in m.agreement_ids.filtered(lambda x: not x.confirmed):
                            try:
                                a.with_context(portal_user_id=self.env.context.get("portal_user_id")).action_confirm()
                            except Exception as e:  # noqa
                                _logger.info("Acuerdo %s: %s", a.name, e)
                    resumen_seg = m._create_followups(exec_json) or {}
                    tareas = len(m.agreement_ids.filtered(lambda x: x.item_id))
                    cambios = len(m.agreement_ids.filtered(lambda x: x.change_id))
                    resumen_seg.update(tareas=tareas, cambios=cambios)
                    partes = []
                    if tareas: partes.append(_("%d actividades") % tareas)
                    if cambios: partes.append(_("%d solicitudes de cambio") % cambios)
                    if resumen_seg.get("decisiones"): partes.append(_("%d decisiones") % resumen_seg["decisiones"])
                    if resumen_seg.get("riesgos"): partes.append(_("%d riesgos") % resumen_seg["riesgos"])
                    if resumen_seg.get("preguntas"): partes.append(_("%d preguntas abiertas") % resumen_seg["preguntas"])
                    log = _("Seguimiento generado: %s.") % ", ".join(partes) if partes else _("No se detectaron compromisos en esta sesión.")
                    if resumen_seg.get("siguiente_accion"):
                        log += _(" Siguiente acción del proyecto actualizada: %s") % resumen_seg["siguiente_accion"]
                    m.with_context(aq_skip_activity=True).write({"followups_log": log, "followups_count": tareas + cambios + resumen_seg.get("decisiones", 0) + resumen_seg.get("riesgos", 0) + resumen_seg.get("preguntas", 0)})
                except Exception as e:  # noqa
                    _logger.exception("Seguimiento de sesión %s", m.name)
                    m.with_context(aq_skip_activity=True).write({"followups_log": _("Error al generar el seguimiento: %s") % e})
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
            self.env["aq.ops.notification"].sudo().notify_role(m.project_id, ["pm"], "resumen",
                                                                _("Sesión procesada: %s") % m.name, "meetings", m.id, body=m.followups_log or "")
        return True

    @api.model
    def build_exec_summary(self, name, project_name, date, text, roster=None):
        """Genera el JSON del resumen ejecutivo a partir de una transcripción, sin requerir reunión ni proyecto.
        `roster`: participantes reales para que los responsables salgan con nombres exactos y se vinculen solos."""
        AI = self.env["aq.ops.ai"].sudo()
        text = AI.condense_transcript(text or "", 14000)
        out = self.env["aq.ai.prompt"].sudo().render("session_exec_summary", {
            "titulo": name, "proyecto": project_name or "(por identificar)", "fecha": str(date or ""),
            "participantes": roster or "(no registrados)", "transcripcion": text[:14000]})
        if isinstance(out, dict) and (out.get("resumen") or out.get("acuerdos")) and not AI.looks_meta(out.get("resumen") or ""):
            return out
        out = AI.chat_json("Eres el redactor ejecutivo de Alphaqueb Consulting. Redacta en español profesional, prosa natural (nunca JSON ni Markdown dentro de los textos). "
                           "Devuelve exclusivamente un objeto JSON con esta forma: "
                           "{\"objetivo\": str, \"resumen\": str (2-3 párrafos narrativos), \"temas\": [{\"titulo\": str, \"detalle\": str (párrafo)}], \"decisiones\": [str], "
                           "\"acuerdos\": [{\"acuerdo\": str, \"responsable\": str, \"fecha\": str, \"tipo\": \"compromiso\"|\"acuerdo\"|\"tarea\"|\"cambio\"}], "
                           "\"pendientes_cliente\": [str], \"riesgos\": [str], \"preguntas_abiertas\": [str], \"siguientes_pasos\": [str], \"proxima_sesion\": str}. "
                           "En \"tipo\": usa \"cambio\" si implica alcance nuevo o modificar lo contratado; \"tarea\" si es trabajo interno; \"acuerdo\" si es una regla o criterio pactado; \"compromiso\" en lo demás. "
                           "En \"responsable\": usa exactamente uno de los participantes listados (o 'Por asignar'). En \"fecha\": resuelve expresiones como 'el viernes' a formato AAAA-MM-DD tomando como referencia la fecha de la sesión; si no se mencionó, 'Por definir'. "
                           "Sesión: %s · Proyecto: %s · Fecha: %s.\nParticipantes:\n%s\nTranscripción:\n%s"
                           % (name, project_name or "(por identificar)", date, roster or "(no registrados)", text[:14000]), max_tokens=2800, tier="deep")
        if isinstance(out, dict) and out and not AI.looks_meta(out.get("resumen") or ""):
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
    def parse_folio(self, title):
        """Distingue las dos numeraciones:
        · 'PO-25002-SAI-Sesión #45' → consecutivo DEL CLIENTE (client_folio), nunca el nuestro.
        · 'SESIÓN #175– SOMGROUP– DAILY SYNC' → consecutivo INTERNO de Alphaqueb (folio)."""
        up = (title or "").upper()
        m2 = re.search(r"(PO-\d{4,6})-([A-ZÁÉÍÓÚ]+)-SESI[ÓO]N\s*#\s*(\d+)", up)
        if m2:
            return {"folio": 0, "client_folio": int(m2.group(3)), "prefix": m2.group(2), "po": m2.group(1), "scheme": "cliente"}
        m1 = re.search(r"SESI[ÓO]N\s*(?:DE\s+\w+\s+)?#\s*(\d+)\s*[–\-—]*\s*([A-ZÁÉÍÓÚ]+)?", up)
        if m1:
            return {"folio": int(m1.group(1)), "client_folio": 0, "prefix": (m1.group(2) or "").strip(), "po": None, "scheme": "interno"}
        return {"folio": 0, "client_folio": 0, "prefix": None, "po": None, "scheme": None}

    def action_assign_folio(self):
        """Asigna el folio INTERNO de Alphaqueb respetando el consecutivo del proyecto.
        Si el título lleva la referencia del cliente (PO-…), la conserva tal cual."""
        for m in self:
            if m.folio or not m.project_id:
                continue
            info = self.parse_folio(m.name)
            usados = m.project_id.folios_usados("interno")
            n = info["folio"] if (info["folio"] and info["folio"] not in usados) else m.project_id.next_folio_number()
            vals = {"folio": n}
            if info["client_folio"] and not m.client_folio:
                vals["client_folio"] = info["client_folio"]
            if info["scheme"] is None and m.project_id.folio_scheme == "interno":
                stype = m.session_type_id.name if m.session_type_id else _("Sesión")
                _n, _cn, titulo = m.project_id.next_folio(stype, m.date or fields.Datetime.now(), folio=n)
                vals["name"] = titulo
            m.with_context(aq_skip_activity=True).write(vals)
            if n > (m.project_id.session_seq or 0):
                m.project_id.with_context(aq_skip_activity=True).write({"session_seq": n})
        return True

    # ------------------------------------------------------------------ seguimiento automático
    def _roster_text(self):
        """Lista de participantes reales (equipo y cliente) para que la IA atribuya responsables con nombres exactos."""
        self.ensure_one()
        p = self.project_id
        internos = self.member_ids
        clientes = self.client_partner_ids
        if p:
            internos |= p.pm_id | p.tech_lead_id
            clientes |= p.client_contact_ids
        lin = "; ".join("%s%s" % (m.name, " (PM)" if p and m == p.pm_id else "") for m in internos if m.name)
        lcl = "; ".join(c.name for c in clientes if c.name)
        out = []
        if lin:
            out.append("Equipo Alphaqueb: %s" % lin)
        if lcl:
            out.append("Por el cliente: %s" % lcl)
        return "\n".join(out)

    def _find_member(self, name):
        if not name or not isinstance(name, str):
            return self.env["aq.portal.member"]
        Member = self.env["aq.portal.member"].sudo()
        n = name.strip()
        if "@" in n:
            return Member.search([("email", "=ilike", n)], limit=1)
        m = Member.search([("name", "=ilike", n)], limit=1) or Member.search([("name", "ilike", n.split()[0])], limit=1)
        return m

    def _find_client_contact(self, name):
        self.ensure_one()
        if not name or not isinstance(name, str):
            return self.env["res.partner"]
        n = name.strip()
        pool = self.client_partner_ids | self.project_id.client_contact_ids
        for p in pool:
            if p.name and (p.name.lower() == n.lower() or n.lower() in p.name.lower() or (p.email and p.email.lower() == n.lower())):
                return p
        return self.env["res.partner"]

    def _parse_due(self, value):
        if not value or not isinstance(value, str):
            return False
        v = value.strip().lower()
        base = fields.Date.context_today(self)
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            try:
                return fields.Date.to_date(m.group(0))
            except Exception:
                return False
        m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", v)
        if m:
            d, mo = int(m.group(1)), int(m.group(2))
            y = int(m.group(3) or base.year)
            y = y + 2000 if y < 100 else y
            try:
                return fields.Date.to_date("%04d-%02d-%02d" % (y, mo, d))
            except Exception:
                return False
        dias = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
        for k, wd in dias.items():
            if k in v:
                delta = (wd - base.weekday()) % 7 or 7
                return fields.Date.add(base, days=delta)
        if "hoy" in v:
            return base
        if "mañana" in v or "manana" in v:
            return fields.Date.add(base, days=1)
        if "semana" in v:
            return fields.Date.add(base, days=7)
        return False

    CAMBIO_RE = r"alcance|cotizaci|no contemplado|adicional(es)?\b|fuera de (lo )?contratado|nuevo requerimiento|propuesta econ[óo]mica|orden de cambio"

    def _agreement_kind(self, item, nombre):
        """Tipo del acuerdo: el que declare la IA ('tipo'/'kind') o, en su defecto, detección de cambio de alcance."""
        kind = ((item.get("tipo") or item.get("kind") or "") if isinstance(item, dict) else "").strip().lower()
        if kind in ("compromiso", "acuerdo", "tarea", "cambio"):
            return kind
        return "cambio" if re.search(self.CAMBIO_RE, nombre, re.I) else "compromiso"

    @staticmethod
    def _is_dup(nombre, existentes):
        """Duplicado si coincide o si un nombre contiene al otro (la IA repite compromisos con distinta redacción)."""
        n = nombre.lower()
        return any(n == e or (len(n) > 25 and len(e) > 25 and (n in e or e in n)) for e in existentes)

    def _merge_agreements(self, d):
        """Lleva TODO lo accionable del resumen ejecutivo a la capa confirmable (sin duplicar):
        acuerdos (con su tipo: compromiso/acuerdo/tarea/cambio), pendientes del cliente y siguientes pasos."""
        self.ensure_one()
        Agreement = self.env["aq.ops.meeting.agreement"].sudo()
        existentes = {(a.name or "").strip().lower() for a in self.agreement_ids}
        nuevos = 0
        for a in (d.get("acuerdos") or []):
            nombre = (a.get("acuerdo") if isinstance(a, dict) else str(a) or "").strip()
            if not nombre or self._is_dup(nombre, existentes):
                continue
            resp = a.get("responsable") if isinstance(a, dict) else ""
            member = self._find_member(resp)
            contacto = self._find_client_contact(resp) if not member else self.env["res.partner"]
            Agreement.create({"meeting_id": self.id, "name": nombre[:200], "owner_id": member.id, "owner_partner_id": contacto.id,
                              "due_date": self._parse_due(a.get("fecha") if isinstance(a, dict) else ""),
                              "kind": self._agreement_kind(a, nombre), "proposed_by_ai": True})
            existentes.add(nombre.lower()); nuevos += 1
        for p in (d.get("pendientes_cliente") or []):
            nombre = (p if isinstance(p, str) else str(p)).strip()
            if not nombre or self._is_dup(nombre, existentes):
                continue
            Agreement.create({"meeting_id": self.id, "name": nombre[:200], "owner_partner_id": (self.client_partner_ids[:1] or self.project_id.client_contact_ids[:1]).id or False,
                              "kind": "compromiso", "proposed_by_ai": True})
            existentes.add(nombre.lower()); nuevos += 1
        # siguientes pasos: trabajo interno que también debe quedar repartido (tarea del PM si nadie más lo asume)
        for p in (d.get("siguientes_pasos") or []):
            nombre = re.sub(r"<[^>]+>", "", p if isinstance(p, str) else self._fmt_item(p)).strip()
            if not nombre or self._is_dup(nombre, existentes):
                continue
            Agreement.create({"meeting_id": self.id, "name": nombre[:200],
                              "owner_id": self.project_id.pm_id.id or self.project_id.tech_lead_id.id,
                              "kind": "tarea", "proposed_by_ai": True})
            existentes.add(nombre.lower()); nuevos += 1
        return nuevos

    def _create_followups(self, d):
        """Crea todo lo necesario para dar seguimiento después de la sesión: decisiones, riesgos, preguntas
        abiertas y la siguiente acción del proyecto (las tareas nacen de los acuerdos confirmados)."""
        self.ensure_one()
        project = self.project_id
        if not project:
            return {}
        Decision = self.env["aq.ops.decision"].sudo()
        Raid = self.env["aq.ops.raid"].sudo()
        Question = self.env["aq.ops.meeting.question"].sudo()
        hoy = fields.Date.context_today(self)
        # La decisión registrada en sesión ya fue tomada por las personas presentes: se aprueba sin más trámite
        # (si se detecta un error, se corrige con "Nueva versión", nunca editando en silencio).
        auto_dec = self.env["ir.config_parameter"].sudo().get_param("aq_ops.auto_approve_decisions", "1") == "1"
        res = {"decisiones": 0, "riesgos": 0, "preguntas": 0, "siguiente_accion": False}
        for dec in (d.get("decisiones") or []):
            texto = (dec if isinstance(dec, str) else self._fmt_item(dec)).strip()
            if not texto or Decision.search_count([("meeting_id", "=", self.id), ("name", "=ilike", texto[:120])]):
                continue
            rec = Decision.create({"name": texto[:120], "project_id": project.id, "meeting_id": self.id, "decision_text": texto,
                                   "context_text": _("Registrada en la sesión %s.") % self.name, "date": (self.date or fields.Datetime.now()).date(),
                                   "decided_by_id": project.pm_id.id, "state": "propuesta", "client_visible": self.client_visible})
            if auto_dec:
                rec.write({"state": "aprobada", "approved_date": hoy})
            res["decisiones"] += 1
        for r in (d.get("riesgos") or []):
            texto = (r if isinstance(r, str) else self._fmt_item(r)).strip()
            if not texto or Raid.search_count([("project_id", "=", project.id), ("name", "=ilike", texto[:120]), ("state", "not in", ("cerrado",))]):
                continue
            Raid.create({"name": texto[:120], "raid_type": "risk", "project_id": project.id, "meeting_id": self.id, "description": texto,
                         "owner_id": project.pm_id.id, "probability": "2", "impact": "2", "state": "abierto",
                         "next_action": _("Evaluar y definir mitigación"), "next_action_date": fields.Date.add(hoy, days=7),
                         "due_date": fields.Date.add(hoy, days=7)})
            res["riesgos"] += 1
        data_q = (d.get("preguntas") or d.get("preguntas_abiertas") or [])
        for q in data_q:
            texto = (q if isinstance(q, str) else (q.get("pregunta") or self._fmt_item(q))).strip()
            if not texto or Question.search_count([("meeting_id", "=", self.id), ("name", "=ilike", texto[:120])]):
                continue
            resp_q = q.get("responsable") if isinstance(q, dict) else ""
            member_q = self._find_member(resp_q)
            Question.create({"meeting_id": self.id, "name": texto[:200], "owner_id": member_q.id,
                             "owner_partner_id": (self._find_client_contact(resp_q) if not member_q else self.env["res.partner"]).id or (self.client_partner_ids[:1]).id or False,
                             "client_visible": self.client_visible})
            res["preguntas"] += 1
        pasos = [p for p in (d.get("siguientes_pasos") or []) if p]
        if pasos and (not project.has_next_action or (project.next_action_date and project.next_action_date < hoy)):
            paso = pasos[0] if isinstance(pasos[0], str) else self._fmt_item(pasos[0])
            paso = re.sub(r"<[^>]+>", "", paso)[:200]
            project.with_context(aq_skip_activity=True).write({"next_action": paso, "next_action_owner_id": project.pm_id.id or project.tech_lead_id.id,
                                                               "next_action_date": fields.Date.add(hoy, days=3)})
            res["siguiente_accion"] = paso
        if d.get("proxima_sesion") and not self.next_meeting_date:
            nd = self._parse_due(d["proxima_sesion"])
            if nd:
                self.with_context(aq_skip_activity=True).write({"next_meeting_date": fields.Datetime.to_datetime("%s 09:00:00" % nd)})
        return res

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
                "<h3>Decisiones</h3>%s<h3>Acuerdos y compromisos</h3><ul>%s</ul><h3>Pendientes del cliente</h3>%s<h3>Preguntas abiertas</h3>%s<h3>Riesgos</h3>%s<h3>Siguientes pasos</h3>%s<p><b>Próxima sesión:</b> %s</p>") % (
            m.name, m.project_id.name, m.date, (" · <b>Folio:</b> %s" % m.folio) if getattr(m, "folio", None) else "", d.get("objetivo") or "—",
            (d.get("resumen") or "").replace("\n", "<br/>"), temas, ul(d.get("decisiones")), acuerdos or "<li>—</li>",
            ul(d.get("pendientes_cliente")), ul(d.get("preguntas_abiertas") or d.get("preguntas")), ul(d.get("riesgos")), ul(d.get("siguientes_pasos")), d.get("proxima_sesion") or "por definir")

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
        rows = [["Acuerdo / compromiso", "Responsable", "Fecha compromiso"]]
        for a in (d.get("acuerdos") or []):
            texto = ((a.get("acuerdo") if isinstance(a, dict) else str(a)) or "").strip()
            if not texto:
                continue  # filas vacías ("Por asignar / Por definir" sin acuerdo) no van al documento
            rows.append([texto, (a.get("responsable") if isinstance(a, dict) else None) or "Por asignar",
                         (a.get("fecha") if isinstance(a, dict) else None) or "Por definir"])
        if len(rows) > 1:
            blocks.append({"type": "table", "header": True, "rows": rows})
            blocks.append({"type": "spacer", "text": ""})
        else:
            blocks.append({"type": "p", "text": "No se registraron acuerdos formales en esta sesión."})
        if d.get("pendientes_cliente"):
            section("Pendientes a cargo del cliente"); bullets(d["pendientes_cliente"])
        if d.get("preguntas_abiertas") or d.get("preguntas"):
            section("Preguntas abiertas"); bullets(d.get("preguntas_abiertas") or d.get("preguntas"))
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
                                                 "headers": {"X-Alphaqueb-Portal": "1"},  # el sincronizador de Gmail lo reconoce y no lo reprocesa
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
            info = Meeting.parse_folio(title)
            folio, prefix, po, client_folio = info["folio"], info["prefix"], info["po"], info["client_folio"]
            doms = {a.get("email", "").split("@")[-1].lower() for a in ev.get("attendees", [])}
            project = self.env["aq.ops.session.normalizer"].detect_project(title, doms)
            if not project:
                hint = self.PREFIX_MAP.get(prefix or "", None) or next((v for d, v in self.DOMAIN_MAP.items() if d in doms), None)
                project = self._project(hint) if hint else self.env["aq.ops.project"].sudo()
            if not project:
                stats["sin_proyecto"] += 1
                continue
            stype_name = next((n for k, n in self.TYPE_PATTERNS if k in up), "Seguimiento")
            stype = Types.get(stype_name)
            vals = {"name": title[:200], "project_id": project.id, "date": fields.Datetime.to_datetime(start[:19].replace("T", " ")), "folio": folio or False, "client_folio": client_folio or False,
                    "session_type_id": stype.id if stype else False, "meeting_type": stype.meeting_type if stype else "cliente", "google_event_id": ev.get("id"),
                    "meet_code": (ev.get("conferenceData") or {}).get("conferenceId") or "", "location": ev.get("hangoutLink"), "state": "realizada", "imported": True,
                    "client_visible": True, "original_title": title[:200]}
            existing = Meeting.search([("google_event_id", "=", ev["id"])], limit=1)
            if existing:
                existing.with_context(aq_skip_activity=True).write({"folio": folio or existing.folio, "client_folio": client_folio or existing.client_folio,
                                                                   "session_type_id": vals["session_type_id"] or existing.session_type_id.id, "imported": True})
                stats["actualizadas"] += 1
            else:
                Meeting.create(vals)
                stats["creadas"] += 1
            if prefix and (folio or client_folio):
                key = (project.id, prefix, po, info["scheme"])
                maxseq[key] = max(maxseq.get(key, 0), folio or client_folio)
            self.env.cr.commit()
        # secuencias y prefijos por proyecto (el prefijo más reciente gana: STONIA→SOMGROUP)
        for (pid, prefix, po, scheme), n in sorted(maxseq.items(), key=lambda x: x[1]):
            p = self.env["aq.ops.project"].sudo().browse(pid)
            vals = {}
            if scheme == "cliente":
                if n > (p.client_seq or 0):
                    vals["client_seq"] = n
                if po:
                    vals["session_po"] = po
                vals["folio_scheme"] = "cliente"
            elif n > (p.session_seq or 0):
                vals["session_seq"] = n
            if prefix and (prefix not in ("STONIA",) or not p.session_prefix):
                vals["session_prefix"] = prefix
            if vals:
                p.with_context(aq_skip_activity=True).write(vals)
        # tarea pendiente: procesar transcripciones históricas
        for p in self.env["aq.ops.project"].sudo().search([("session_seq", ">", 0)]):
            if not self.env["aq.ops.item"].sudo().search_count([("project_id", "=", p.id), ("name", "=", "Procesar transcripciones de sesiones históricas")]):
                self.env["aq.ops.item"].sudo().create({"name": "Procesar transcripciones de sesiones históricas", "item_type": "tarea", "project_id": p.id, "state": "backlog",
                                                       "description": "<p>Tarea futura: recuperar y procesar con IA las transcripciones/notas de las sesiones importadas del histórico (mapa de sesiones).</p>", "tags": "sesiones,historico"})
        self.env.cr.commit()
        return stats


class SessionNormalizer(models.AbstractModel):
    """Pone orden en el histórico: deduplica sesiones repetidas, reconoce las nomenclaturas usadas a lo largo
    del tiempo y renumera todo en un consecutivo interno limpio por proyecto (cronológico)."""
    _name = "aq.ops.session.normalizer"
    _description = "Alphaops: recuento y orden de sesiones"

    # nomenclaturas encontradas en el histórico de Alphaqueb
    PATTERNS = [
        (r"(PO-\d{4,6})-([A-ZÁÉÍÓÚ]+)-SESI[ÓO]N\s*#\s*(\d+)", "cliente"),          # PO-25002-SAI-Sesión #34
        (r"(PIC-\d{4,6})-[A-ZÁÉÍÓÚ]+-SESI[ÓO]N\s+INTERNA\s*#\s*(\d+)", "interna"),  # PIC-25002-Alphaqueb-Sesión interna #9
        (r"SESI[ÓO]N\s*#\s*(\d+)", "interno"),                                       # SESIÓN #14 / SESIÓN #03–
        (r"SESI[ÓO]N\s+(\d+)\s*[:\-]", "interno"),                                   # Sesión 5: Recepción…
        (r"^\s*#\s*(\d+)\b", "interno"),                                            # #9 | 30/04/2025 – …
        (r"SESI[ÓO]N\s*#\s*(\d+)\s+ETAPA", "interno"),                              # SESIÓN # 1 ETAPA 2 …
    ]
    STOP = ("VISITA", "PROSPECTO", "CEN SYSTEMS", "AXE")

    @staticmethod
    def norm(txt):
        t = (txt or "").upper()
        for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N")):
            t = t.replace(a, b)
        t = re.sub(r"SESI[OÓ]N\s*#?\s*\d*", " ", t)
        t = re.sub(r"\d{1,4}[/-]\d{1,2}[/-]\d{2,4}", " ", t)
        t = re.sub(r"[^A-Z0-9 ]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    @api.model
    def detect_project(self, title, attendee_domains=()):
        """Reglas de negocio de Alphaqueb:
        1) Si la sesión es INTERNA con Creattivo o un DAILY de Creattivo → serie de Creattivo TI, sin importar el tema.
        2) Si la sesión es con SAI (o habla de manifiestos/acopio/PO del proyecto) → serie de SAI.
        3) Después Stonia/SOM, Hexágonos y, en último caso, Creattivo."""
        up = self.norm(title)
        Project = self.env["aq.ops.project"].sudo()
        def find(hint):
            return Project.search([("name", "ilike", hint)], limit=1)
        if "CREATTIVO" in up and any(k in up for k in ("INTERNA", "INTERNO", "DAILY", "COORDINACION INTERNA")):
            return find("Creattivo")
        if any(k in up for k in ("SAI", "MANIFIESTO", "ACOPIO", "CA SAI", "PO 25002")):
            return find("SAI")
        if any(k in up for k in ("STONIA", "STONE PROFIT", "SP 0", "SOMGROUP", "SOM ")):
            return find("Stonia")
        if any(k in up for k in ("SOMCABO", "SOM CABOS", "CABOS")):
            return find("SOM Cabos")
        if any(k in up for k in ("HMX", "HEXAGONOS")):
            return find("Hexágonos")
        if "CREATTIVO" in up:
            return find("Creattivo")
        if "GETTING" in up:
            return find("Getting Ready")
        for d in attendee_domains:
            for dom, hint in (("somgroup.mx", "Stonia"), ("stonia.com.mx", "Stonia"), ("creattivo.mx", "Creattivo"), ("hexagonosmexicanos.com", "Hexágonos")):
                if dom in d:
                    return find(hint)
        return Project

    @api.model
    def read_numbering(self, title):
        """Devuelve (numero, tipo) según la nomenclatura histórica; tipo: cliente | interna | interno | None."""
        up = (title or "").upper()
        for rx, kind in self.PATTERNS:
            m = re.search(rx, up)
            if m:
                nums = [g for g in m.groups() if g and g.isdigit()]
                if nums:
                    return int(nums[-1]), kind
        return 0, None

    @api.model
    def read_stage(self, title):
        """Detecta la etapa declarada en el título: 'SESIÓN # 1 ETAPA 2 …' → 2."""
        m = re.search(r"ETAPA\s*(\d+)", (title or "").upper())
        return int(m.group(1)) if m else 0

    @api.model
    def guess_type(self, title):
        up = self.norm(title)
        Types = self.env["aq.ops.session.type"].sudo()
        for key, name in (("DAILY", "Daily Sync"), ("RETROSPECTIVA", "Retrospectiva"), ("CAPACITACION", "Capacitación"), ("ENTREGA", "Entrega"),
                          ("DEMO", "Validación"), ("DEMOSTRACION", "Validación"), ("VALIDACION", "Validación"), ("PRUEBAS", "Pruebas / UAT"),
                          ("UAT", "Pruebas / UAT"), ("LEVANTAMIENTO", "Revisión"), ("ROADMAP", "Kickoff"), ("KICK", "Kickoff"),
                          ("MICROPLANNING", "Seguimiento"), ("SEGUIMIENTO", "Seguimiento"), ("REVISION", "Revisión"), ("PRODUCTIVO", "Producción")):
            if key in up:
                return Types.search([("name", "=", name)], limit=1)
        return Types.search([("name", "=", "Seguimiento")], limit=1)

    # ------------------------------------------------------------------ recuento
    @api.model
    def recount(self, project_ids=None, apply=False, dedupe=True):
        """Cuenta las sesiones reales por proyecto y las renumera 1..N en orden cronológico.
        apply=False devuelve solo la vista previa. Preserva el título original y el consecutivo del cliente."""
        Meeting = self.env["aq.ops.meeting"].sudo()
        Project = self.env["aq.ops.project"].sudo()
        projects = Project.browse(project_ids) if project_ids else Project.search([])
        reporte = []
        for p in projects:
            sesiones = Meeting.search([("project_id", "=", p.id)], order="date asc, id asc")
            if not sesiones:
                continue
            vistos, unicos, duplicadas = {}, [], []
            for m in sesiones:
                clave = (m.date and m.date.strftime("%Y-%m-%d %H:%M")[:15] or str(m.id), self.norm(m.name)[:45])
                if clave in vistos and dedupe:
                    previo = vistos[clave]
                    mejor = max([previo, m], key=lambda x: (bool(x.transcript), bool(x.processed), bool(x.google_event_id), len(x.agreement_ids)))
                    peor = m if mejor == previo else previo
                    vistos[clave] = mejor
                    if mejor != previo:
                        unicos[unicos.index(previo)] = mejor
                    duplicadas.append(peor)
                else:
                    vistos[clave] = m
                    unicos.append(m)
            cambios, contador, etapa_actual = [], {}, 1
            for m in unicos:
                declarada = self.read_stage(m.original_title or m.name)
                if declarada > etapa_actual:
                    etapa_actual = declarada          # a partir de aquí, todo pertenece a la nueva etapa
                etapa = etapa_actual
                contador[etapa] = contador.get(etapa, 0) + 1
                n = contador[etapa]
                num, kind = self.read_numbering(m.original_title or m.name)
                cf = num if kind == "cliente" else (m.client_folio or 0)
                cambios.append({"id": m.id, "fecha": str(m.date or "")[:16], "titulo": m.name, "folio_actual": m.folio or 0,
                                "folio_nuevo": n, "etapa": etapa, "client": cf})
                if apply:
                    vals = {"folio": n, "stage_no": etapa, "original_title": m.original_title or m.name}
                    if cf and cf != m.client_folio:
                        vals["client_folio"] = cf
                    if not m.session_type_id:
                        t = self.guess_type(m.name)
                        if t:
                            vals["session_type_id"] = t.id
                    m.with_context(aq_skip_activity=True).write(vals)
            n = contador.get(etapa_actual, 0)
            if apply:
                for d in duplicadas:
                    principal = None
                    for u in unicos:
                        if u.date == d.date and self.norm(u.name)[:45] == self.norm(d.name)[:45]:
                            principal = u; break
                    d.with_context(aq_skip_activity=True).write({"active": False, "duplicate_of_id": principal.id if principal else False})
                cli = p.folios_usados("cliente")
                vals = {"session_seq": n, "session_stage": etapa_actual}
                if etapa_actual > 1 and not p.stage_started_on:
                    primera = next((c for c in cambios if c["etapa"] == etapa_actual), None)
                    if primera:
                        vals["stage_started_on"] = primera["fecha"][:10]
                if cli:
                    vals["client_seq"] = max(cli)
                    vals["folio_scheme"] = "cliente" if p.session_po else p.folio_scheme
                p.with_context(aq_skip_activity=True).write(vals)
                self.env.cr.commit()
            reporte.append({"project_id": p.id, "project": p.name, "prefijo": p.session_prefix, "total_previo": len(sesiones), "duplicadas": len(duplicadas),
                            "etapa": etapa_actual, "por_etapa": contador, "sesiones": sum(contador.values()), "sesiones_etapa": n, "proximo_folio": n + 1, "consecutivo_cliente": max(p.folios_usados("cliente") or [0]) or None,
                            "muestra": cambios[:5] + ([{"...": "..."}] if len(cambios) > 5 else []) + cambios[-3:] if len(cambios) > 8 else cambios})
        return {"aplicado": apply, "proyectos": reporte}

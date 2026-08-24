# -*- coding: utf-8 -*-
"""Integración Google Workspace (Gmail, Calendar, Meet, Drive, Docs, Sheets) para Administración y Operaciones.
Cuenta conectada por OAuth 2.0; sincronización por cron; enrutamiento por reglas + copiloto (DeepSeek)."""
import base64
import datetime
import json
import logging
import os
import re
from datetime import timedelta
from email.utils import parseaddr

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/meetings.space.readonly",
          "https://www.googleapis.com/auth/userinfo.email", "openid"]
MEET_SENDERS = ("meet-recordings-noreply@google.com", "gemini-noreply@google.com", "calendar-notification@google.com")
# "Plantilla Membretada Pro" (Drive de antonio@alphaqueb.com): membrete oficial sobre el que se maquetan los documentos.
DOC_TEMPLATE_DEFAULT = "1ep_RM47LalrjXY5D9XLou60AF5DTSqc2fop8t9Sw2EE"


def _extract_attachment_text(filename, raw):
    """Texto legible de un adjunto (PDF, texto plano o DOCX); cadena vacía si no se puede extraer."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            try:
                import io
                from pdfminer.high_level import extract_text
                return extract_text(io.BytesIO(raw)) or ""
            except ImportError:
                return ""
        if name.endswith((".txt", ".csv", ".md", ".json", ".xml", ".htm", ".html")):
            return raw.decode("utf-8", errors="ignore")
        if name.endswith(".docx"):
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                return re.sub(r"<[^>]+>", " ", z.read("word/document.xml").decode("utf-8", errors="ignore"))
    except Exception as e:  # noqa
        _logger.info("extraer adjunto %s: %s", filename, e)
    return ""


def _cfg(env):
    icp = env["ir.config_parameter"].sudo()
    return {"client_id": os.environ.get("GOOGLE_CLIENT_ID") or icp.get_param("GOOGLE_CLIENT_ID") or icp.get_param("aq_google.client_id") or "",
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET") or icp.get_param("GOOGLE_CLIENT_SECRET") or icp.get_param("aq_google.client_secret") or "",
            "redirect": (icp.get_param("aq_admin_portal.base_url") or icp.get_param("web.base.url")).rstrip("/") + "/aq_portal/google/callback"}


class GoogleAccount(models.Model):
    _name = "aq.google.account"
    _description = "Google: cuenta conectada"
    _order = "id"

    name = fields.Char(string="Etiqueta", required=True, default="Cuenta principal")
    email = fields.Char(readonly=True)
    refresh_token = fields.Char(groups="base.group_system", copy=False)
    access_token = fields.Char(groups="base.group_system", copy=False)
    token_expiry = fields.Datetime(groups="base.group_system")
    scopes = fields.Char(readonly=True)
    connected_by_id = fields.Many2one("aq.portal.user", string="Conectó", readonly=True)
    connected_at = fields.Datetime(readonly=True)
    active = fields.Boolean(default=True)
    state = fields.Selection([("pendiente", "Sin conectar"), ("conectada", "Conectada"), ("error", "Error")], default="pendiente")
    last_error = fields.Text()
    # sincronización
    sync_gmail = fields.Boolean(default=True, string="Sincronizar Gmail")
    sync_calendar = fields.Boolean(default=True, string="Sincronizar Calendar")
    sync_meet = fields.Boolean(default=True, string="Sincronizar Meet (transcripciones)")
    sync_drive = fields.Boolean(default=True, string="Sincronizar Drive (notas de Gemini)")
    gmail_query = fields.Char(default="newer_than:3d -in:spam -in:trash -category:promotions -category:social", string="Consulta Gmail")
    gmail_label_done = fields.Char(default="Alphaqueb/Procesado", string="Etiqueta al procesar")
    calendar_id = fields.Char(default="primary")
    drive_folder_name = fields.Char(default="Meet Recordings", string="Carpeta de Drive de grabaciones/notas")
    last_gmail_sync = fields.Datetime()
    last_calendar_sync = fields.Datetime()
    last_meet_sync = fields.Datetime()
    last_drive_sync = fields.Datetime()
    messages_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        for a in self:
            a.messages_count = self.env["aq.google.message"].search_count([("account_id", "=", a.id)])

    # ------------------------------------------------------------------ OAuth
    @api.model
    def auth_url(self, state):
        c = _cfg(self.env)
        if not c["client_id"]:
            raise UserError(_("Falta GOOGLE_CLIENT_ID (variable de entorno o parámetro del sistema)."))
        from urllib.parse import urlencode
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"client_id": c["client_id"], "redirect_uri": c["redirect"], "response_type": "code", "scope": " ".join(SCOPES),
                                                                          "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state})

    @api.model
    def exchange_code(self, code, portal_user):
        c = _cfg(self.env)
        if not c["client_secret"]:
            raise UserError(_("Falta GOOGLE_CLIENT_SECRET."))
        r = requests.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": c["client_id"], "client_secret": c["client_secret"], "redirect_uri": c["redirect"], "grant_type": "authorization_code"}, timeout=30)
        if r.status_code != 200:
            raise UserError(_("Google rechazó el código: %s") % r.text[:300])
        t = r.json()
        info = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": "Bearer " + t["access_token"]}, timeout=20).json()
        email = info.get("email")
        acc = self.sudo().search([("email", "=", email)], limit=1) or self.sudo().search([("state", "=", "pendiente")], limit=1) or self.sudo().create({"name": email or "Cuenta Google"})
        vals = {"email": email, "access_token": t["access_token"], "token_expiry": fields.Datetime.now() + timedelta(seconds=int(t.get("expires_in", 3600)) - 60),
                "scopes": t.get("scope"), "connected_by_id": portal_user.id if portal_user else False, "connected_at": fields.Datetime.now(), "state": "conectada", "last_error": False, "active": True}
        if t.get("refresh_token"):
            vals["refresh_token"] = t["refresh_token"]
        acc.write(vals)
        return acc

    def _token(self):
        self.ensure_one()
        me = self.sudo()
        if me.access_token and me.token_expiry and me.token_expiry > fields.Datetime.now():
            return me.access_token
        if not me.refresh_token:
            raise UserError(_("La cuenta %s no tiene token de actualización; vuelva a conectarla.") % (me.email or me.name))
        c = _cfg(self.env)
        r = requests.post("https://oauth2.googleapis.com/token", data={"refresh_token": me.refresh_token, "client_id": c["client_id"], "client_secret": c["client_secret"], "grant_type": "refresh_token"}, timeout=30)
        if r.status_code != 200:
            me.write({"state": "error", "last_error": r.text[:500]})
            raise UserError(_("No se pudo renovar el token de Google: %s") % r.text[:200])
        t = r.json()
        me.write({"access_token": t["access_token"], "token_expiry": fields.Datetime.now() + timedelta(seconds=int(t.get("expires_in", 3600)) - 60), "state": "conectada", "last_error": False})
        return t["access_token"]

    def _call(self, method, url, **kw):
        headers = kw.pop("headers", {}); headers["Authorization"] = "Bearer " + self._token()
        r = requests.request(method, url, headers=headers, timeout=kw.pop("timeout", 60), **kw)
        if r.status_code >= 400:
            raise UserError(_("Google API %s %s → %s: %s") % (method, url.split("?")[0][-60:], r.status_code, r.text[:300]))
        return r.json() if r.content and "json" in r.headers.get("Content-Type", "") else r.text

    def get(self, url, params=None):
        return self._call("GET", url, params=params)

    def post(self, url, body=None, params=None):
        return self._call("POST", url, json=body, params=params)

    def action_disconnect(self):
        self.sudo().write({"refresh_token": False, "access_token": False, "state": "pendiente"})
        return True

    def action_sync_now(self):
        self.env["aq.google.sync"].sync_account(self)
        return True

    # ------------------------------------------------------------------ Gmail helpers
    def gmail_list(self, q, max_results=50):
        out, token = [], None
        while True:
            r = self.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", {"q": q, "maxResults": max_results, "pageToken": token})
            out += r.get("messages", [])
            token = r.get("nextPageToken")
            if not token or len(out) >= max_results:
                break
        return out

    def gmail_get(self, mid):
        return self.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s" % mid, {"format": "full"})

    @staticmethod
    def gmail_attachment_parts(payload):
        """Lista recursiva de adjuntos del mensaje: [{filename, id, mime, size}]."""
        out = []
        def walk(p):
            if p.get("filename") and (p.get("body") or {}).get("attachmentId"):
                out.append({"filename": p["filename"], "id": p["body"]["attachmentId"], "mime": p.get("mimeType"), "size": (p.get("body") or {}).get("size", 0)})
            for sp in p.get("parts", []) or []:
                walk(sp)
        walk(payload or {})
        return out

    def gmail_attachment(self, mid, att_id):
        r = self.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s/attachments/%s" % (mid, att_id))
        data = r.get("data") or ""
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def gmail_label_id(self, name):
        labels = self.get("https://gmail.googleapis.com/gmail/v1/users/me/labels").get("labels", [])
        for l in labels:
            if l["name"] == name:
                return l["id"]
        return self.post("https://gmail.googleapis.com/gmail/v1/users/me/labels", {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})["id"]

    def gmail_add_label(self, mid, label_id):
        try:
            self.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s/modify" % mid, {"addLabelIds": [label_id]})
        except UserError:
            pass

    @staticmethod
    def gmail_text(payload):
        """Extrae texto plano (o HTML sin etiquetas) del mensaje."""
        def walk(p):
            mime = p.get("mimeType", "")
            data = p.get("body", {}).get("data")
            if data and mime in ("text/plain", "text/html"):
                txt = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="ignore")
                return txt if mime == "text/plain" else re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S))
            for sp in p.get("parts", []) or []:
                t = walk(sp)
                if t:
                    return t
            return ""
        return re.sub(r"[ \t]+", " ", walk(payload)).strip()

    # ------------------------------------------------------------------ Calendar / Meet / Drive / Docs / Sheets helpers
    def calendar_events(self, time_min, time_max):
        return self.get("https://www.googleapis.com/calendar/v3/calendars/%s/events" % (self.calendar_id or "primary"),
                        {"timeMin": time_min, "timeMax": time_max, "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}).get("items", [])

    def meet_conference_records(self, start_iso):
        return self.get("https://meet.googleapis.com/v2/conferenceRecords", {"filter": 'start_time>="%s"' % start_iso, "pageSize": 50}).get("conferenceRecords", [])

    def meet_transcript_text(self, record_name):
        out = []
        for tr in self.get("https://meet.googleapis.com/v2/%s/transcripts" % record_name).get("transcripts", []):
            token = None
            while True:
                r = self.get("https://meet.googleapis.com/v2/%s/entries" % tr["name"], {"pageSize": 100, "pageToken": token})
                for e in r.get("transcriptEntries", []):
                    out.append("%s: %s" % ((e.get("participant") or "").split("/")[-1], e.get("text", "")))
                token = r.get("nextPageToken")
                if not token:
                    break
            doc = (tr.get("docsDestination") or {}).get("document")
            if doc and not out:
                out.append(self.doc_text(doc))
        return "\n".join(out)

    def drive_search(self, q, fields_="files(id,name,mimeType,modifiedTime,webViewLink,parents)"):
        return self.get("https://www.googleapis.com/drive/v3/files", {"q": q, "fields": fields_, "pageSize": 100, "orderBy": "modifiedTime desc"}).get("files", [])

    def doc_text(self, file_id):
        return self._call("GET", "https://www.googleapis.com/drive/v3/files/%s/export" % file_id, params={"mimeType": "text/plain"})

    def drive_folder_id(self, name):
        """Reutiliza la carpeta existente aunque su nombre tenga otra grafía (p. ej. 'AlphaOps' → 'Alphaops')."""
        for candidate in dict.fromkeys([name, name.replace("ops", "Ops"), name.replace("Ops", "ops")]):
            f = self.drive_search("name='%s' and mimeType='application/vnd.google-apps.folder' and trashed=false" % candidate.replace("'", "\\'"))
            if f:
                return f[0]["id"]
        return self.post("https://www.googleapis.com/drive/v3/files", {"name": name, "mimeType": "application/vnd.google-apps.folder"})["id"]

    def drive_child_folder(self, name, parent_id):
        """Subcarpeta dentro de una carpeta (para organizar por proyecto)."""
        safe = name.replace("'", "\\'")
        f = self.drive_search("name='%s' and mimeType='application/vnd.google-apps.folder' and trashed=false and '%s' in parents" % (safe, parent_id))
        if f:
            return f[0]["id"]
        return self.post("https://www.googleapis.com/drive/v3/files", {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]})["id"]

    def drive_share(self, file_id, emails, role="reader", notify=False):
        """Comparte un archivo con los correos indicados (sin notificación de Google: el aviso lo manda el portal)."""
        done = []
        for e in dict.fromkeys([x.strip().lower() for x in emails if x and "@" in x]):
            try:
                self.post("https://www.googleapis.com/drive/v3/files/%s/permissions" % file_id,
                          {"type": "user", "role": role, "emailAddress": e}, params={"sendNotificationEmail": "true" if notify else "false"})
                done.append(e)
            except Exception as ex:  # noqa
                _logger.info("compartir %s con %s: %s", file_id, e, ex)
        return done

    def drive_export_pdf(self, file_id):
        """Devuelve el PDF del documento en base64 (para adjuntarlo al correo)."""
        import base64 as _b64
        token = self._token()
        r = requests.get("https://www.googleapis.com/drive/v3/files/%s/export" % file_id, params={"mimeType": "application/pdf"},
                         headers={"Authorization": "Bearer " + token}, timeout=90)
        r.raise_for_status()
        return _b64.b64encode(r.content)

    def create_doc(self, title, text, folder_id=None):
        doc = self.post("https://docs.googleapis.com/v1/documents", {"title": title})
        self.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % doc["documentId"], {"requests": [{"insertText": {"location": {"index": 1}, "text": text}}]})
        if folder_id:
            self._call("PATCH", "https://www.googleapis.com/drive/v3/files/%s" % doc["documentId"], params={"addParents": folder_id})
        return doc["documentId"], "https://docs.google.com/document/d/%s/edit" % doc["documentId"]

    def create_sheet(self, title, rows, folder_id=None):
        sh = self.post("https://sheets.googleapis.com/v4/spreadsheets", {"properties": {"title": title}})
        sid = sh["spreadsheetId"]
        self._call("PUT", "https://sheets.googleapis.com/v4/spreadsheets/%s/values/A1" % sid, params={"valueInputOption": "RAW"}, json={"values": rows})
        if folder_id:
            self._call("PATCH", "https://www.googleapis.com/drive/v3/files/%s" % sid, params={"addParents": folder_id})
        return sid, "https://docs.google.com/spreadsheets/d/%s/edit" % sid

    def update_sheet(self, sid, rows, range_="A1"):
        self._call("POST", "https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s:clear" % (sid, "A1:ZZ"), json={})
        self._call("PUT", "https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s" % (sid, range_), params={"valueInputOption": "RAW"}, json={"values": rows})


class GoogleRule(models.Model):
    """Reglas de enrutamiento: qué correo va a Administración u Operaciones y en qué se convierte."""
    _name = "aq.google.rule"
    _description = "Google: regla de enrutamiento de correo"
    _order = "sequence"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    match_from = fields.Char(string="Remitente contiene")
    match_to = fields.Char(string="Destinatario contiene")
    match_subject = fields.Char(string="Asunto contiene")
    match_keywords = fields.Char(string="Palabras clave (cuerpo, separadas por coma)")
    match_label = fields.Char(string="Etiqueta de Gmail")
    target_app = fields.Selection([("admin", "Administración"), ("ops", "Operaciones")], required=True, default="ops")
    target_type = fields.Selection([("inbox", "Solo bandeja (decide una persona)"), ("meeting_notes", "Notas/transcripción de reunión → Reunión (Operaciones)"),
                                    ("ops_request", "Solicitud (Operaciones)"), ("ops_incident", "Incidente (Operaciones)"), ("admin_agreement", "Pendiente/acuerdo (Administración)"),
                                    ("admin_receivable", "Seguimiento de cobranza (Administración)"), ("admin_payable", "Cuenta por pagar (Administración)"), ("ignore", "Ignorar")],
                                   default="inbox", required=True)
    auto_convert = fields.Boolean(string="Convertir automáticamente", default=False, help="Si no, queda en la bandeja para confirmación humana.")
    project_id = fields.Many2one("aq.ops.project", string="Proyecto fijo (opcional)")
    partner_id = fields.Many2one("res.partner", string="Cliente/proveedor fijo (opcional)")
    notes = fields.Text()

    def matches(self, msg):
        self.ensure_one()
        def has(v, t):
            return (v or "").lower() in (t or "").lower() if v else True
        kws = [k.strip().lower() for k in (self.match_keywords or "").split(",") if k.strip()]
        body = (msg.get("body") or "").lower()
        return has(self.match_from, msg.get("from")) and has(self.match_to, msg.get("to")) and has(self.match_subject, msg.get("subject")) and \
            (not kws or any(k in body or k in (msg.get("subject") or "").lower() for k in kws)) and (not self.match_label or self.match_label.lower() in " ".join(msg.get("labels", [])).lower())


class GoogleMessage(models.Model):
    """Bandeja unificada: correos, eventos y notas de Meet ya enrutados. Conversión con confirmación humana (o automática por regla)."""
    _name = "aq.google.message"
    _description = "Google: mensaje/evento enrutado"
    _order = "date desc"

    account_id = fields.Many2one("aq.google.account", required=True, ondelete="cascade")
    source = fields.Selection([("gmail", "Gmail"), ("calendar", "Calendar"), ("meet", "Meet"), ("drive", "Drive")], required=True, default="gmail")
    external_id = fields.Char(index=True, string="ID externo")
    thread_id = fields.Char()
    subject = fields.Char(required=True)
    sender = fields.Char(string="De")
    recipients = fields.Char(string="Para")
    date = fields.Datetime(default=fields.Datetime.now)
    snippet = fields.Char()
    body = fields.Text(string="Contenido")
    labels = fields.Char()
    link = fields.Char(string="Enlace")
    app = fields.Selection([("admin", "Administración"), ("ops", "Operaciones")], default="ops", string="Destino")
    category = fields.Selection([("meeting_notes", "Notas de reunión"), ("calendar", "Evento de calendario"), ("request", "Solicitud"), ("incident", "Incidente"), ("invoice", "Facturación / cobranza"),
                                 ("payable", "Pago / proveedor"), ("legal", "Legal / contrato"), ("hr", "Personal"), ("prospect", "Prospecto / comercial"), ("agreement", "Acuerdo / pendiente"),
                                 ("info", "Informativo"), ("other", "Otro")], default="other")
    routed_by = fields.Selection([("rule", "Regla"), ("ai", "Copiloto"), ("manual", "Manual"), ("system", "Sistema")], default="system")
    rule_id = fields.Many2one("aq.google.rule")
    partner_id = fields.Many2one("res.partner", string="Cliente/proveedor detectado")
    project_id = fields.Many2one("aq.ops.project", string="Proyecto detectado")
    ai_summary = fields.Text(string="Resumen del copiloto")
    ai_action = fields.Char(string="Acción sugerida")
    state = fields.Selection([("nuevo", "Nuevo"), ("procesado", "Procesado (resumen listo)"), ("convertido", "Convertido"), ("ignorado", "Ignorado")], default="nuevo", index=True)
    transcript = fields.Text(string="Transcripción completa (del documento)")
    exec_summary = fields.Html(string="Resumen ejecutivo", readonly=True)
    summary_doc_url = fields.Char(string="Mi documento (plantilla) en Google Docs", readonly=True)
    source_doc_url = fields.Char(string="Documento original (notas de Gemini)", readonly=True)
    res_model = fields.Char(string="Convertido en (modelo)")
    res_id = fields.Integer(string="Convertido en (id)")
    res_label = fields.Char(string="Convertido en")
    attachment_names = fields.Char()
    attachments_text = fields.Text(string="Contenido de adjuntos (extraído)", readonly=True)
    auto_attempts = fields.Integer(string="Intentos de proceso automático", default=0)

    # --- detección de cliente/proyecto por dominios de correo y palabras
    def _detect(self):
        Partner = self.env["res.partner"].sudo()
        Project = self.env["aq.ops.project"].sudo()
        for m in self:
            emails = re.findall(r"[\w.+-]+@([\w-]+\.[\w.-]+)", (m.sender or "") + " " + (m.recipients or ""))
            domains = {d.lower() for d in emails if not d.lower().endswith(("alphaqueb.com", "google.com", "gmail.com"))}
            partner = Partner
            for d in domains:
                partner = Partner.search([("is_company", "=", True), "|", ("email", "ilike", "@" + d), ("website", "ilike", d)], limit=1) or Partner.search([("email", "ilike", "@" + d)], limit=1).commercial_partner_id
                if partner:
                    break
            text = ((m.subject or "") + " " + (m.body or "")[:3000]).lower()
            proj = Project
            if partner:
                proj = Project.search([("partner_id", "=", partner.id), ("stage", "not in", ("cerrado",))], limit=1)
            if not proj:
                for p in Project.search([("stage", "not in", ("cerrado",))]):
                    key = p.name.split("·")[0].strip().lower()
                    if key and len(key) > 3 and key in text:
                        proj = p; break
            m.write({"partner_id": partner.id if partner else (proj.partner_id.id if proj else False), "project_id": proj.id if proj else False})

    # --- proceso automático: cada categoría sabe en qué convertirse sin intervención humana
    AUTO_ACTIONS = {"meeting_notes": "action_process_notes", "request": "action_to_ops_request", "incident": "action_to_ops_incident",
                    "agreement": "action_to_admin_agreement", "invoice": "action_to_admin_receivable", "payable": "action_to_admin_payable"}

    def _auto_convert(self):
        """Convierte el mensaje según su categoría; si falla, queda en la bandeja con el motivo visible.
        Reintentado por el cron hasta 3 veces (aq.google.sync.cron_autoprocess).
        Lo fechado antes del corte de automatización NO se procesa solo (evita resúmenes de sesiones pasadas)."""
        since = self.env["aq.google.sync"]._auto_since()
        for m in self:
            if m.state != "nuevo":
                continue
            if m.date and m.date < since:
                if not m.ai_action:
                    m.write({"ai_action": _("Anterior al inicio de la automatización; use las acciones de la ficha si desea procesarlo.")})
                continue
            m.write({"auto_attempts": m.auto_attempts + 1})
            action = self.AUTO_ACTIONS.get(m.category)
            if m.category == "incident" and not m.project_id:
                action = "action_to_ops_request"  # sin proyecto no puede haber incidente: entra como solicitud
            if not action:
                continue
            try:
                with self.env.cr.savepoint():
                    getattr(m, action)()
                if (m.ai_action or "").startswith("Proceso automático pendiente"):
                    m.write({"ai_action": False})
            except Exception as e:  # noqa
                if m.category == "invoice":
                    try:  # sin cuenta por cobrar relacionada: al menos queda como pendiente de Administración
                        with self.env.cr.savepoint():
                            m.action_to_admin_agreement()
                        continue
                    except Exception:  # noqa
                        pass
                m.write({"ai_action": _("Proceso automático pendiente (%d/3): %s") % (m.auto_attempts, str(e)[:160])})
        return True

    # --- conversiones
    def action_ignore(self):
        self.write({"state": "ignorado"})
        return True

    def _done(self, rec, label):
        self.write({"state": "convertido", "res_model": rec._name, "res_id": rec.id, "res_label": label})
        return rec

    def action_to_ops_request(self):
        for m in self:
            rec = self.env["aq.ops.request"].sudo().create({"name": m.subject[:200], "description": (m.body or "")[:8000] + "\n\nOrigen: %s %s" % (m.source, m.link or ""), "source": "correo",
                                                            "partner_id": m.partner_id.id or m.project_id.partner_id.id or self.env.company.partner_id.id, "project_id": m.project_id.id,
                                                            "requester_partner_id": False, "urgency": "alta" if re.search(r"urgente|crítico|caído|no funciona", (m.subject or "").lower()) else "media"})
            m._done(rec, _("Solicitud: %s") % rec.name)
        return True

    def action_to_ops_incident(self):
        for m in self:
            if not m.project_id:
                raise UserError(_("Indique el proyecto antes de crear el incidente."))
            rec = self.env["aq.ops.incident"].sudo().create({"name": m.subject[:200], "description": m.body, "project_id": m.project_id.id, "partner_id": m.project_id.partner_id.id, "severity": "S2"})
            m._done(rec, _("Incidente: %s") % rec.name)
        return True

    def action_to_ops_meeting(self):
        for m in self:
            rec = self.env["aq.google.sync"].meeting_from_notes(m)
            m._done(rec, _("Reunión: %s") % rec.name)
        return True

    def full_text(self):
        """Texto completo: prioriza el/los Google Docs referenciados (notas de Gemini con resumen + transcripción)."""
        self.ensure_one()
        body = self.transcript or self.body or ""
        ids = re.findall(r"docs\.google\.com/document/d/([\w-]+)", (self.body or "") + " " + (self.link or ""))
        if self.source == "drive" and self.external_id:
            ids = [self.external_id] + ids
        for did in dict.fromkeys(ids):
            try:
                t = self.account_id.doc_text(did)
                if t and len(t) > len(body) * 0.5:
                    self.write({"transcript": t[:120000], "source_doc_url": "https://docs.google.com/document/d/%s/edit" % did})
                    return t
            except Exception as e:  # noqa
                _logger.info("doc_text %s: %s", did, e)
        if self.attachments_text:
            body += "\n\n[Contenido de adjuntos]\n" + self.attachments_text
        return body

    def action_process_notes(self):
        """Procesa la transcripción SIN requerir proyecto: resumen ejecutivo + documento con la plantilla propia + liga.
        Si logra identificar proyecto/reunión, además la vincula y crea las actividades."""
        Session = self.env["aq.ops.meeting"].sudo()
        for m in self:
            text = m.full_text()
            if not (text or "").strip():
                raise UserError(_("El mensaje no contiene transcripción ni documento legible."))
            if not m.project_id:
                m._detect()
            linked = False
            if m.project_id:
                try:
                    meeting = self.env["aq.google.sync"].meeting_from_notes(m)
                    m._done(meeting, _("Reunión: %s") % meeting.name)
                    m.write({"exec_summary": meeting.exec_summary, "summary_doc_url": meeting.summary_doc_url or meeting.google_doc_url})
                    linked = True
                except Exception as e:  # noqa
                    _logger.info("vinculación: %s", e)
            if not linked:
                title = re.sub(r"^(notes|notas|transcripci[óo]n de meet)\s*[:\-–]*\s*", "", m.subject or _("Sesión"), flags=re.I).strip()[:150]
                d = Session.build_exec_summary(title, m.project_id.name if m.project_id else None, m.date, text)
                html = Session.exec_html(title, m.project_id.name if m.project_id else None, m.date, None, d)
                url = False
                try:
                    url = Session.create_summary_doc_generic(title, m.project_id.name if m.project_id else None, m.partner_id.name if m.partner_id else None, m.date, d)
                except Exception as e:  # noqa
                    _logger.warning("Doc plantilla: %s", e)
                m.write({"exec_summary": html, "summary_doc_url": url, "state": "procesado", "ai_summary": (d.get("resumen") or "")[:900],
                         "res_label": _("Resumen generado (sin proyecto)") if not m.project_id else m.res_label})
                Brand = self.env["aq.portal.branding"]
                body_mail = Brand.wrap(_("Resumen ejecutivo · %s") % title, html + (("<p><a href='%s'>Mi documento (plantilla)</a></p>" % url) if url else "") + (("<p><a href='%s'>Notas originales de Gemini</a></p>" % m.source_doc_url) if m.source_doc_url else ""),
                                       _("Ver en la bandeja"), Brand.portal_url() + "/ops/r/google_inbox/%d" % m.id)
                for u in self.env["aq.portal.user"].sudo().search([("role", "=", "direccion"), ("active", "=", True)]):
                    self.env["mail.mail"].sudo().create({"subject": _("Resumen ejecutivo · %s") % title, "email_to": u.email, "body_html": body_mail}).send()
        return True

    def action_assign_and_link(self):
        """Tras asignar proyecto manualmente en la ficha: vincula a reunión y crea actividades."""
        for m in self:
            if not m.project_id:
                raise UserError(_("Primero asigne el proyecto."))
            meeting = self.env["aq.google.sync"].meeting_from_notes(m)
            m._done(meeting, _("Reunión: %s") % meeting.name)
        return True

    def action_to_admin_agreement(self):
        for m in self:
            admin_proj = self.env["aq.portal.project"].sudo().search([("partner_id", "=", m.partner_id.id)], limit=1) if m.partner_id else self.env["aq.portal.project"].sudo()
            rec = self.env["aq.portal.agreement"].sudo().create({"name": m.subject[:200], "description": (m.body or "")[:8000], "source": "correo", "requested_by": m.sender, "project_id": admin_proj.id,
                                                                 "meeting_ref": m.link or m.external_id})
            m._done(rec, _("Pendiente: %s") % rec.name)
        return True

    def action_to_admin_receivable(self):
        for m in self:
            Recv = self.env["aq.portal.receivable"].sudo()
            inv = re.search(r"\b([A-Z]{1,4}[- ]?\d{2,8})\b", m.subject or "")
            rec = (Recv.search([("invoice_number", "ilike", inv.group(1))], limit=1) if inv else Recv) or (Recv.search([("partner_id", "=", m.partner_id.id), ("state", "!=", "pagada")], limit=1) if m.partner_id else Recv)
            if not rec:
                raise UserError(_("No se encontró una cuenta por cobrar relacionada; conviértalo en pendiente o créela manualmente."))
            f = self.env["aq.portal.followup"].sudo().create({"receivable_id": rec.id, "channel": "correo", "note": "%s\n\n%s" % (m.subject, (m.body or "")[:3000]), "contact": m.sender})
            m._done(rec, _("Seguimiento de cobranza: %s") % rec.display_name)
        return True

    def action_to_admin_payable(self):
        for m in self:
            amount = re.search(r"\$\s?([\d,]+\.?\d*)", m.body or "")
            rec = self.env["aq.portal.payable"].sudo().create({"name": m.subject[:200], "category": "proveedor", "partner_id": m.partner_id.id, "due_date": fields.Date.add(fields.Date.today(), days=15),
                                                               "amount": float(amount.group(1).replace(",", "")) if amount else 0.0, "invoice_ref": m.subject[:60], "notes": (m.body or "")[:3000]})
            m._done(rec, _("Cuenta por pagar: %s") % rec.name)
        return True

    def action_to_ops_comment(self):
        """Adjunta el correo como comunicación en el proyecto detectado."""
        for m in self:
            if not m.project_id:
                raise UserError(_("Indique el proyecto."))
            rec = self.env["aq.ops.comment"].sudo().create({"project_id": m.project_id.id, "body": "[Correo · %s · %s]\n%s\n\n%s" % (m.sender, m.date, m.subject, (m.body or "")[:4000]), "internal": True})
            m._done(rec, _("Comunicación en %s") % m.project_id.name)
        return True


class GoogleSync(models.AbstractModel):
    _name = "aq.google.sync"
    _description = "Google: sincronización"

    @api.model
    def cron_sync(self):
        for acc in self.env["aq.google.account"].sudo().search([("refresh_token", "!=", False), ("active", "=", True)]):
            try:
                self.sync_account(acc)
            except Exception as e:  # noqa
                _logger.exception("Google sync %s", acc.email)
                acc.write({"state": "error", "last_error": str(e)[:500]})
        try:
            self.cron_autoprocess()
        except Exception:  # noqa
            _logger.exception("Google autoprocess")
        return True

    @api.model
    def _auto_since(self):
        """Fecha de corte de la automatización: solo se procesa automáticamente lo fechado a partir de aquí.
        Se fija sola la primera vez que corre (el 'hoy' del arranque); editable en Parámetros del sistema
        (aq_google.auto_process_since). Lo anterior queda en la bandeja para proceso manual, sin correos."""
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param("aq_google.auto_process_since")
        if not val:
            val = fields.Datetime.to_string(fields.Datetime.now())
            icp.set_param("aq_google.auto_process_since", val)
        try:
            return fields.Datetime.to_datetime(val)
        except Exception:  # noqa
            return fields.Datetime.now()

    @api.model
    def cron_autoprocess(self):
        """Red de seguridad: reintenta los mensajes que quedaron en la bandeja sin procesar (máx. 3 intentos por mensaje).
        Nunca procesa nada anterior a la fecha de corte de la automatización."""
        if self.env["ir.config_parameter"].sudo().get_param("aq_google.auto_convert", "1") != "1":
            return 0
        start = max(self._auto_since(), fields.Datetime.now() - timedelta(days=14))
        pend = self.env["aq.google.message"].sudo().search([("state", "=", "nuevo"), ("auto_attempts", "<", 3),
                                                            ("date", ">=", start)], limit=50)
        pend._auto_convert()
        self.env.cr.commit()
        return len(pend)

    @api.model
    def sync_account(self, acc, stages=None):
        """Incremental: cada etapa confirma su trabajo (commit) para que una corrida larga no se pierda."""
        acc = acc.sudo()
        errors = []
        for stage, flag in (("calendar", acc.sync_calendar), ("meet", acc.sync_meet), ("drive", acc.sync_drive), ("gmail", acc.sync_gmail)):
            if not flag or (stages and stage not in stages):
                continue
            try:
                getattr(self, "sync_" + stage)(acc)
                self.env.cr.commit()
            except Exception as e:  # noqa
                _logger.exception("Google %s", stage)
                self.env.cr.rollback()
                errors.append("%s: %s" % (stage, str(e)[:200]))
        acc.write({"state": "error" if errors else "conectada", "last_error": "\n".join(errors) if errors else False})
        self.env.cr.commit()

    # ------------------------------------------------------------------ Gmail → bandeja enrutada
    @api.model
    def sync_gmail(self, acc):
        Msg = self.env["aq.google.message"].sudo()
        label_done = acc.gmail_label_id(acc.gmail_label_done) if acc.gmail_label_done else None
        days = self.env.context.get("aq_gmail_days")
        limit = int(self.env["ir.config_parameter"].sudo().get_param("aq_google.gmail_batch", "25"))
        if days:
            q = "newer_than:%dd -in:spam -in:trash" % int(days)
            limit = max(limit, 200)
        else:
            q = acc.gmail_query or "newer_than:3d"
        if acc.gmail_label_done:
            q += ' -label:"%s"' % acc.gmail_label_done
        n = 0
        for ref in acc.gmail_list(q, max_results=limit):
            if n >= limit:
                break
            if Msg.search_count([("external_id", "=", ref["id"]), ("source", "=", "gmail")]):
                continue
            full = acc.gmail_get(ref["id"])
            headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
            body = acc.gmail_text(full.get("payload", {}))
            parts = acc.gmail_attachment_parts(full.get("payload", {}))
            msg = {"from": headers.get("from", ""), "to": headers.get("to", ""), "subject": headers.get("subject", "(sin asunto)"), "body": body, "labels": full.get("labelIds", [])}
            mdate = datetime.datetime.utcfromtimestamp(int(full["internalDate"]) // 1000) if full.get("internalDate") else fields.Datetime.now()
            rec = Msg.create({"account_id": acc.id, "source": "gmail", "external_id": ref["id"], "thread_id": full.get("threadId"), "subject": msg["subject"][:250], "sender": msg["from"][:250],
                              "recipients": msg["to"][:500], "date": mdate,
                              "snippet": (full.get("snippet") or "")[:300], "body": body[:20000], "labels": ",".join(full.get("labelIds", [])),
                              "attachment_names": ", ".join(p["filename"] for p in parts)[:500],
                              "link": "https://mail.google.com/mail/u/0/#all/%s" % full.get("threadId")})
            # adjuntos: se guardan en el mensaje y su texto se extrae para el análisis
            texts = []
            for p in parts[:10]:
                if (p.get("size") or 0) > 15 * 1024 * 1024:
                    continue
                try:
                    raw = acc.gmail_attachment(ref["id"], p["id"])
                    self.env["ir.attachment"].sudo().create({"name": p["filename"], "raw": raw, "mimetype": p.get("mime"), "res_model": rec._name, "res_id": rec.id})
                    t = _extract_attachment_text(p["filename"], raw)
                    if t and t.strip():
                        texts.append("· %s:\n%s" % (p["filename"], t.strip()[:8000]))
                except Exception as e:  # noqa
                    _logger.info("adjunto %s: %s", p.get("filename"), e)
            if texts:
                rec.write({"attachments_text": "\n\n".join(texts)[:60000]})
                msg["body"] = (msg["body"] or "") + "\n\n[Contenido de adjuntos]\n" + "\n\n".join(texts)[:6000]
            rec._detect()
            self.route(rec, msg)
            if label_done:
                acc.gmail_add_label(ref["id"], label_done)
            n += 1
            self.env.cr.commit()
        acc.write({"last_gmail_sync": fields.Datetime.now()})
        return n

    @api.model
    def route(self, rec, msg):
        """1) Notas de Meet → reunión; 2) reglas; 3) copiloto (DeepSeek) decide app y categoría; 4) conversión automática
        de toda categoría accionable (aq_google.auto_convert=1, activado por defecto)."""
        auto_all = self.env["ir.config_parameter"].sudo().get_param("aq_google.auto_convert", "1") == "1"
        sender = (msg.get("from") or "").lower()
        subj = (msg.get("subject") or "").lower()
        if any(s in sender for s in MEET_SENDERS) or subj.startswith(("notes:", "notas:", "notas de la reunión", "notes from", "resumen de la reunión", "transcripción")):
            rec.write({"app": "ops", "category": "meeting_notes", "routed_by": "system"})
            if rec.date and rec.date < self._auto_since():
                rec.write({"ai_action": _("Sesión anterior al inicio de la automatización; use 'Procesar transcripción' si desea el resumen.")})
                return
            try:
                rec.action_process_notes()
            except Exception as e:  # noqa
                _logger.warning("Notas de Meet: %s", e)
            return
        for rule in self.env["aq.google.rule"].sudo().search([("active", "=", True)]):
            if rule.matches(msg):
                vals = {"app": rule.target_app, "routed_by": "rule", "rule_id": rule.id,
                        "category": {"meeting_notes": "meeting_notes", "ops_request": "request", "ops_incident": "incident", "admin_agreement": "agreement", "admin_receivable": "invoice", "admin_payable": "payable", "inbox": "other", "ignore": "info"}[rule.target_type]}
                if rule.project_id: vals["project_id"] = rule.project_id.id
                if rule.partner_id: vals["partner_id"] = rule.partner_id.id
                rec.write(vals)
                if rule.target_type == "ignore":
                    rec.write({"state": "ignorado"})
                elif rule.target_type != "inbox" and (rule.auto_convert or auto_all):
                    rec._auto_convert()
                return
        # copiloto — recibe la cartera real (clientes y proyectos activos) para clasificar Y vincular
        AI = self.env["aq.ops.ai"].sudo()
        d = None
        if AI.available():
            try:
                proys = "; ".join(p.name for p in self.env["aq.ops.project"].sudo().search([("stage", "not in", ("cerrado",))], limit=40))
                clientes = "; ".join(p.name for p in self.env["res.partner"].sudo().search([("is_company", "=", True)], limit=60))
                ctx = {"remitente": msg.get("from"), "asunto": msg.get("subject"), "cuerpo": (msg.get("body") or "")[:3000],
                       "destinatario": msg.get("to") or "", "proyectos": proys or "(sin proyectos activos)", "clientes": clientes or "(sin clientes registrados)"}
                d = self.env["aq.ai.prompt"].sudo().render("email_routing", ctx)
                if not (isinstance(d, dict) and d.get("app")):
                    d = AI.chat_json("Clasifica este correo para Alphaqueb Consulting (consultora Odoo). Responde JSON {\"app\": \"admin\"|\"ops\", \"category\": meeting_notes|request|incident|invoice|payable|legal|hr|prospect|agreement|info|other, "
                                     "\"summary\": str (2 líneas), \"action\": str (acción sugerida, una línea), \"project\": str (nombre EXACTO de la lista de proyectos o vacío), \"partner\": str (nombre EXACTO de la lista de clientes o vacío)}. "
                                     "Administración = contratos, facturación, cobranza, pagos, legal, RH, prospectos. Operaciones = proyectos, requerimientos, incidencias, reuniones, entregables.\n"
                                     "Proyectos activos: %s\nClientes: %s\nDe: %s\nAsunto: %s\nCuerpo:\n%s"
                                     % (ctx["proyectos"], ctx["clientes"], msg.get("from"), msg.get("subject"), (msg.get("body") or "")[:3000]), max_tokens=400)
            except Exception as e:  # noqa — sin copiloto se clasifica por heurística; la sincronización no se detiene
                _logger.info("Enrutamiento IA: %s", e)
                d = None
        if isinstance(d, dict) and d.get("app"):
            vals = {"app": d.get("app") if d.get("app") in ("admin", "ops") else "ops",
                    "category": d.get("category") if d.get("category") in dict(rec._fields["category"].selection) else "other",
                    "ai_summary": d.get("summary"), "ai_action": d.get("action"), "routed_by": "ai"}
            if d.get("project") and not rec.project_id:
                proj = self.env["aq.ops.project"].sudo().search([("name", "ilike", str(d["project"])[:60]), ("stage", "not in", ("cerrado",))], limit=1)
                if proj:
                    vals["project_id"] = proj.id
                    vals.setdefault("partner_id", proj.partner_id.id)
            if d.get("partner") and not rec.partner_id and "partner_id" not in vals:
                partner = self.env["res.partner"].sudo().search([("name", "ilike", str(d["partner"])[:60])], limit=1)
                if partner:
                    vals["partner_id"] = partner.id
            rec.write(vals)
            if auto_all:
                rec._auto_convert()
            return
        # heurística sin IA
        text = subj + " " + (msg.get("body") or "")[:2000].lower()
        cat, app = "other", "ops"
        if re.search(r"factura|cfdi|pago|cobro|complemento|estado de cuenta", text): cat, app = "invoice", "admin"
        elif re.search(r"contrato|nda|convenio|legal|aviso de privacidad", text): cat, app = "legal", "admin"
        elif re.search(r"cotizaci|propuesta|prospecto|presupuesto", text): cat, app = "prospect", "admin"
        elif re.search(r"error|falla|no funciona|urgente|caído|incidente", text): cat, app = "incident", "ops"
        elif re.search(r"solicit|requerimiento|necesitamos|favor de", text): cat, app = "request", "ops"
        rec.write({"app": app, "category": cat, "routed_by": "system"})
        if auto_all:
            rec._auto_convert()

    # ------------------------------------------------------------------ Calendar → reuniones
    @api.model
    def sync_calendar(self, acc):
        Meeting = self.env["aq.ops.meeting"].sudo()
        now = fields.Datetime.now()
        events = acc.calendar_events((now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), (now + timedelta(days=21)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        n = 0
        for ev in events:
            if ev.get("status") == "cancelled" or not ev.get("id"):
                continue
            start = (ev.get("start") or {}).get("dateTime") or ((ev.get("start") or {}).get("date") + "T09:00:00")
            emails = [a.get("email", "").lower() for a in ev.get("attendees", [])]
            external = [e for e in emails if e and not e.endswith(("alphaqueb.com", "google.com", "calendar.google.com"))]
            partner_ids = self.env["res.partner"].sudo().search([("email", "in", external)]) if external else self.env["res.partner"].sudo()
            project = self._project_for(ev.get("summary", ""), partner_ids, external)
            if not project and not external:
                continue  # reuniones internas sin cliente ni proyecto no se crean
            if not project:
                continue
            members = self.env["aq.portal.member"].sudo().search([("email", "in", [e for e in emails if e.endswith("alphaqueb.com")])])
            info = Meeting.parse_folio(ev.get("summary") or "")
            folio, prefix, po, client_folio = info["folio"], info["prefix"], info["po"], info["client_folio"]
            vals = {"name": (ev.get("summary") or _("Reunión"))[:200], "project_id": project.id, "folio": folio or False, "client_folio": client_folio or False,
                    "date": fields.Datetime.to_datetime(start[:19].replace("T", " ")) if "T" in start else start,
                    "member_ids": [(6, 0, members.ids)], "client_partner_ids": [(6, 0, partner_ids.ids)], "location": ev.get("hangoutLink") or ev.get("location"),
                    "agenda": (ev.get("description") or "")[:4000], "google_event_id": ev["id"], "meet_code": ((ev.get("conferenceData") or {}).get("conferenceId") or "")}
            m = Meeting.search([("google_event_id", "=", ev["id"])], limit=1)
            if m:
                keep = {k: v for k, v in vals.items() if k in ("name", "date", "location", "agenda", "client_partner_ids", "member_ids", "meet_code")}
                if folio and not m.folio:
                    keep["folio"] = folio
                if client_folio and not m.client_folio:
                    keep["client_folio"] = client_folio
                m.with_context(aq_skip_activity=True).write(keep)
            else:
                m = Meeting.create(dict(vals, meeting_type="cliente" if external else "interna"))
                n += 1
            upd = {}
            if folio and folio > (project.session_seq or 0):
                upd["session_seq"] = folio
            if client_folio and client_folio > (project.client_seq or 0):
                upd["client_seq"] = client_folio
            if prefix and not project.session_prefix:
                upd["session_prefix"] = prefix
            if po and not project.session_po:
                upd["session_po"] = po
                upd["folio_scheme"] = "cliente"
            if upd:
                project.with_context(aq_skip_activity=True).write(upd)
            if m.date and m.date < now and m.state == "programada":
                m.with_context(aq_skip_activity=True).write({"state": "realizada"})
        acc.write({"last_calendar_sync": now})
        return n

    def _project_for(self, title, partners, external_emails):
        Project = self.env["aq.ops.project"].sudo()
        t = (title or "").lower()
        for p in Project.search([("stage", "not in", ("cerrado",))]):
            key = p.name.split("·")[0].strip().lower()
            if key and key in t:
                return p
        partner = partners.mapped("commercial_partner_id")[:1] if partners else False
        if not partner and external_emails:
            dom = external_emails[0].split("@")[-1]
            c = self.env["res.partner"].sudo().search([("is_company", "=", True), ("email", "ilike", "@" + dom)], limit=1)
            partner = c or (self.env["res.partner"].sudo().search([("email", "ilike", "@" + dom)], limit=1).commercial_partner_id)
        if partner:
            return Project.search([("partner_id", "=", partner.id), ("stage", "not in", ("cerrado",))], limit=1)
        return Project

    # ------------------------------------------------------------------ Meet → transcripciones
    @api.model
    def sync_meet(self, acc):
        Meeting = self.env["aq.ops.meeting"].sudo()
        since = (acc.last_meet_sync or (fields.Datetime.now() - timedelta(days=7))).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            records = acc.meet_conference_records(since)
        except UserError as e:
            _logger.info("Meet API: %s", e)
            return 0
        n = 0
        for rec in records:
            code = (rec.get("space") or "").split("/")[-1]
            start = rec.get("startTime", "")[:19].replace("T", " ")
            m = Meeting.search([("meet_record", "=", rec["name"])], limit=1)
            if m:
                continue
            m = Meeting.search([("meet_code", "=", code)], order="date desc", limit=1) if code else Meeting
            if not m and start:
                m = Meeting.search([("date", ">=", fields.Datetime.to_datetime(start) - timedelta(hours=2)), ("date", "<=", fields.Datetime.to_datetime(start) + timedelta(hours=2))], limit=1)
            text = acc.meet_transcript_text(rec["name"])
            if not text.strip():
                continue
            started = fields.Datetime.to_datetime(start) if start else fields.Datetime.now()
            is_old = started < self._auto_since()
            if not m:
                msg = self.env["aq.google.message"].sudo().create({"account_id": acc.id, "source": "meet", "external_id": rec["name"], "subject": _("Transcripción de Meet %s") % start, "body": text[:20000],
                                                                   "app": "ops", "category": "meeting_notes", "routed_by": "system", "date": started})
                msg._detect()
                if is_old:
                    msg.write({"ai_action": _("Sesión anterior al inicio de la automatización; use 'Procesar transcripción' si desea el resumen.")})
                    continue
                try:
                    msg.action_process_notes()
                except Exception as e:  # noqa
                    _logger.info("Meet standalone: %s", e)
                continue
            m.with_context(aq_skip_activity=True).write({"transcript": text, "meet_record": rec["name"], "state": "realizada" if m.state == "programada" else m.state})
            if is_old:  # la transcripción se conserva como evidencia, pero sin proceso IA ni correos retroactivos
                continue
            try:
                if not m.session_type_id or m.session_type_id.auto_process:
                    m.process_with_ai()
                else:
                    self.env["aq.ops.ai"].sudo().summarize_meeting(m)
            except Exception as e:  # noqa
                _logger.info("Proceso IA: %s", e)
            self.env["aq.ops.notification"].sudo().notify_role(m.project_id, ["pm"], "accion_requerida", _("Transcripción de Meet recibida: %s — confirme acuerdos propuestos") % m.name, "meetings", m.id)
            n += 1
        acc.write({"last_meet_sync": fields.Datetime.now()})
        return n

    # ------------------------------------------------------------------ Drive → notas de Gemini
    @api.model
    def sync_drive(self, acc):
        Msg = self.env["aq.google.message"].sudo()
        since = (acc.last_drive_sync or (fields.Datetime.now() - timedelta(days=7))).strftime("%Y-%m-%dT%H:%M:%S")
        try:
            files = acc.drive_search("mimeType='application/vnd.google-apps.document' and modifiedTime > '%s' and trashed=false and (name contains 'Notes by Gemini' or name contains 'Notas de Gemini' or name contains 'Notas por Gemini' or name contains 'Gemini')" % since)
        except UserError as e:
            _logger.info("Drive: %s", e); return 0
        n = 0
        for f in files:
            if Msg.search_count([("external_id", "=", f["id"]), ("source", "=", "drive")]):
                continue
            text = acc.doc_text(f["id"])
            rec = Msg.create({"account_id": acc.id, "source": "drive", "external_id": f["id"], "subject": f["name"][:250], "body": (text or "")[:30000], "link": f.get("webViewLink"),
                              "date": fields.Datetime.to_datetime(f.get("modifiedTime", "")[:19].replace("T", " ")) if f.get("modifiedTime") else fields.Datetime.now(), "app": "ops", "category": "meeting_notes", "routed_by": "system"})
            rec._detect()
            if rec.date and rec.date < self._auto_since():
                rec.write({"ai_action": _("Sesión anterior al inicio de la automatización; use 'Procesar transcripción' si desea el resumen.")})
                n += 1
                continue
            try:
                rec.action_process_notes()
            except Exception as e:  # noqa
                rec.write({"ai_action": str(e)[:200]})
            n += 1
        acc.write({"last_drive_sync": fields.Datetime.now()})
        return n

    @api.model
    def meeting_from_notes(self, msg):
        """Convierte notas/transcripción (correo de Meet, doc de Gemini o transcripción) en una reunión de Operaciones y pide al copiloto las propuestas."""
        Meeting = self.env["aq.ops.meeting"].sudo()
        title = re.sub(r"^(notes|notas|notas de la reunión|resumen de la reunión|transcripción)\s*[:\-–]\s*", "", msg.subject or "", flags=re.I).strip() or _("Reunión")
        title = re.sub(r"\s*[-–]\s*(Notes|Notas) (by|de|por) Gemini.*$", "", title, flags=re.I).strip()
        m = Meeting.search([("google_event_id", "!=", False), ("name", "ilike", title[:40]), ("date", ">=", (msg.date or fields.Datetime.now()) - timedelta(days=2)), ("date", "<=", (msg.date or fields.Datetime.now()) + timedelta(days=1))], limit=1)
        if not m:
            if not msg.project_id:
                msg._detect()
            if not msg.project_id:
                raise UserError(_("No se pudo asociar las notas a un proyecto; asigne el proyecto en la bandeja y vuelva a convertir."))
            m = Meeting.create({"name": title[:200], "project_id": msg.project_id.id, "date": msg.date or fields.Datetime.now(), "meeting_type": "cliente", "state": "realizada", "location": msg.link})
        body = msg.full_text()
        m.with_context(aq_skip_activity=True).write({"transcript": body if len(body) > 2000 else m.transcript, "minutes": (m.minutes or "") + "<p><b>%s</b></p><pre>%s</pre>" % (msg.subject, body[:6000].replace("<", "&lt;")) if len(body) <= 2000 else m.minutes or "<p>%s</p>" % msg.subject,
                                                     "state": "realizada"})
        try:
            if not m.session_type_id or m.session_type_id.auto_process:
                m.process_with_ai()
            else:
                self.env["aq.ops.ai"].sudo().summarize_meeting(m)
        except Exception as e:  # noqa
            _logger.info("Proceso IA: %s", e)
        if not m.summary_doc_url and not m.google_doc_url:
            try:  # aunque la IA falle, la minuta siempre queda en Google Docs
                m.action_create_google_doc()
            except Exception as e:  # noqa
                _logger.info("Doc de minuta: %s", e)
        msg.write({"exec_summary": m.exec_summary or msg.exec_summary,
                   "summary_doc_url": m.summary_doc_url or m.google_doc_url or msg.summary_doc_url})
        self.env["aq.ops.notification"].sudo().notify_role(m.project_id, ["pm"], "accion_requerida", _("Notas de reunión recibidas: %s — revise y confirme acuerdos") % m.name, "meetings", m.id)
        return m

    # ------------------------------------------------------------------ salidas a Docs / Sheets
    @api.model
    def _account(self):
        """La conexión persiste por refresh token (sobrevive reinicios); un error transitorio de sincronización no la invalida."""
        Acc = self.env["aq.google.account"].sudo()
        acc = Acc.search([("state", "=", "conectada")], limit=1) or Acc.search([("refresh_token", "!=", False), ("active", "=", True)], limit=1)
        if not acc:
            raise UserError(_("No hay una cuenta de Google conectada (Integraciones → Google)."))
        return acc

    @api.model
    def export_portfolio_sheet(self):
        acc = self._account()
        rows = [["Proyecto", "Cliente", "PM", "Etapa", "Salud", "Prioridad", "Riesgo", "% horas", "Horas consumidas", "Horas autorizadas", "Próximo hito", "Fecha hito", "Siguiente acción", "Responsable", "Fecha compromiso"]]
        for p in self.env["aq.ops.project"].sudo().search([("stage", "!=", "cerrado")]):
            nm = p.next_milestone_id
            rows.append([p.name, p.partner_id.name, p.pm_id.name or "", p.stage, p.health, p.priority, p.risk_level, round(p.hours_pct, 1), p.hours_consumed, p.hours_authorized, nm.name or "", str(nm.date_current or ""), p.next_action or "", p.next_action_owner_id.name or "", str(p.next_action_date or "")])
        icp = self.env["ir.config_parameter"].sudo()
        sid = icp.get_param("aq_google.portfolio_sheet_id")
        folder = acc.drive_folder_id("Alphaops")
        if sid:
            try:
                acc.update_sheet(sid, rows)
                return "https://docs.google.com/spreadsheets/d/%s/edit" % sid
            except UserError:
                sid = None
        sid, url = acc.create_sheet("Alphaops · Portafolio", rows, folder)
        icp.set_param("aq_google.portfolio_sheet_id", sid)
        return url


class OpsMeetingGoogle(models.Model):
    _inherit = "aq.ops.meeting"

    google_event_id = fields.Char(string="ID de evento de Calendar", readonly=True, index=True)
    meet_code = fields.Char(string="Código de Meet", readonly=True)
    meet_record = fields.Char(string="Registro de Meet", readonly=True)
    google_doc_url = fields.Char(string="Minuta en Google Docs", readonly=True)

    # ------------------------------------------------------------------ plantilla membretada
    @api.model
    def _template_id(self, acc):
        """Google Doc plantilla (membrete A4 con marca) sobre el que se maquetan todos los documentos.
        Orden: parámetro aq_google.doc_template_id (acepta ID o URL) → búsqueda por nombre en Drive →
        se crea una sola vez y se recuerda. Para usar una plantilla propia, pegue su URL en el parámetro."""
        icp = self.env["ir.config_parameter"].sudo()
        tid = (icp.get_param("aq_google.doc_template_id") or "").strip() or DOC_TEMPLATE_DEFAULT
        if tid:
            mm = re.search(r"/d/([\w-]+)", tid)
            tid = mm.group(1) if mm else tid
            try:
                info = acc.get("https://www.googleapis.com/drive/v3/files/%s" % tid, {"fields": "id,trashed"})
                if not info.get("trashed"):
                    icp.set_param("aq_google.doc_template_id", tid)
                    return tid
            except UserError:
                _logger.info("Plantilla configurada inaccesible (%s); se busca o regenera otra", tid)
        files = acc.drive_search("name = 'Plantilla membretada Alphaqueb' and mimeType='application/vnd.google-apps.document' and trashed=false")
        tid = files[0]["id"] if files else self._create_letterhead_template(acc)
        icp.set_param("aq_google.doc_template_id", tid)
        return tid

    @api.model
    def _create_letterhead_template(self, acc):
        """Crea el membrete de marca: página A4, encabezado con logo (o wordmark) y línea lima, pie de contacto."""
        from .doc_builder import PURPLE, MUTED, LIME, LINE, F_TITLE, F_LABEL, _rgb, u16
        icp = self.env["ir.config_parameter"].sudo()
        did = acc.post("https://docs.googleapis.com/v1/documents", {"title": "Plantilla membretada Alphaqueb"})["documentId"]
        batch = "https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did
        try:
            acc._call("PATCH", "https://www.googleapis.com/drive/v3/files/%s" % did, params={"addParents": acc.drive_folder_id("Alphaops")})
        except Exception as e:  # noqa
            _logger.info("Carpeta de plantilla: %s", e)
        r = acc.post(batch, {"requests": [
            {"updateDocumentStyle": {"documentStyle": {
                "pageSize": {"width": {"magnitude": 595.28, "unit": "PT"}, "height": {"magnitude": 841.89, "unit": "PT"}},
                "marginTop": {"magnitude": 84, "unit": "PT"}, "marginBottom": {"magnitude": 72, "unit": "PT"},
                "marginLeft": {"magnitude": 56, "unit": "PT"}, "marginRight": {"magnitude": 56, "unit": "PT"},
                "marginHeader": {"magnitude": 26, "unit": "PT"}, "marginFooter": {"magnitude": 22, "unit": "PT"}},
                "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight,marginHeader,marginFooter"}},
            {"createHeader": {"type": "DEFAULT"}},
            {"createFooter": {"type": "DEFAULT"}},
        ]})
        hid = fid = None
        for rep in r.get("replies", []):
            hid = rep.get("createHeader", {}).get("headerId") or hid
            fid = rep.get("createFooter", {}).get("footerId") or fid
        reqs = []
        if hid:
            base = (icp.get_param("aq_admin_portal.base_url") or icp.get_param("web.base.url") or "").rstrip("/")
            placed = False
            if base:
                try:  # logo real; Google debe poder descargar la URL pública
                    acc.post(batch, {"requests": [{"insertInlineImage": {
                        "location": {"segmentId": hid, "index": 0}, "uri": base + "/aq_admin_portal/static/description/logo.png",
                        "objectSize": {"height": {"magnitude": 26, "unit": "PT"}}}}]})
                    placed = True
                except Exception as e:  # noqa
                    _logger.info("Logo en membrete: %s", e)
            if not placed:  # wordmark tipográfico con los colores de marca
                reqs += [{"insertText": {"location": {"segmentId": hid, "index": 0}, "text": "ALPHAQUEB"}},
                         {"updateTextStyle": {"range": {"segmentId": hid, "startIndex": 0, "endIndex": 9},
                                              "textStyle": {"weightedFontFamily": {"fontFamily": F_TITLE}, "fontSize": {"magnitude": 17, "unit": "PT"},
                                                            "foregroundColor": _rgb(PURPLE)},
                                              "fields": "weightedFontFamily,fontSize,foregroundColor"}}]
            reqs.append({"updateParagraphStyle": {"range": {"segmentId": hid, "startIndex": 0, "endIndex": 1},
                                                  "paragraphStyle": {"borderBottom": {"color": _rgb(LIME), "width": {"magnitude": 1.5, "unit": "PT"},
                                                                                      "padding": {"magnitude": 6, "unit": "PT"}, "dashStyle": "SOLID"}},
                                                  "fields": "borderBottom"}})
        if fid:
            foot = "Alphaqueb Consulting · Consultoría e implementación de Odoo · alphaqueb.com"
            reqs += [{"insertText": {"location": {"segmentId": fid, "index": 0}, "text": foot}},
                     {"updateTextStyle": {"range": {"segmentId": fid, "startIndex": 0, "endIndex": u16(foot)},
                                          "textStyle": {"weightedFontFamily": {"fontFamily": F_LABEL}, "fontSize": {"magnitude": 8, "unit": "PT"},
                                                        "foregroundColor": _rgb(MUTED)},
                                          "fields": "weightedFontFamily,fontSize,foregroundColor"}},
                     {"updateParagraphStyle": {"range": {"segmentId": fid, "startIndex": 0, "endIndex": u16(foot)},
                                               "paragraphStyle": {"alignment": "CENTER",
                                                                  "borderTop": {"color": _rgb(LINE), "width": {"magnitude": 0.75, "unit": "PT"},
                                                                                "padding": {"magnitude": 4, "unit": "PT"}, "dashStyle": "SOLID"}},
                                               "fields": "alignment,borderTop"}}]
        if reqs:
            acc.post(batch, {"requests": reqs})
        return did

    def action_create_google_doc(self):
        """Minuta en Google Docs SIEMPRE con la plantilla de marca (el texto plano queda solo como último recurso)."""
        Session = self.env["aq.ops.meeting"]
        for m in self:
            d = {"objetivo": "",
                 "resumen": re.sub(r"<[^>]+>", " ", m.minutes or m.agenda or "").strip() or _("Minuta de la sesión %s.") % m.name,
                 "temas": [], "decisiones": [],
                 "acuerdos": [{"acuerdo": a.name, "responsable": a.owner_id.name or a.owner_partner_id.name or _("Por asignar"),
                               "fecha": str(a.due_date) if a.due_date else _("Por definir")} for a in m.agreement_ids],
                 "pendientes_cliente": [], "riesgos": [], "siguientes_pasos": [],
                 "proxima_sesion": str(m.next_meeting_date or "")}
            try:
                url = Session.create_summary_doc_generic(m.name, m.project_id.name, m.project_id.partner_id.name, m.date, d, project=m.project_id, meeting=m)
            except Exception as e:  # noqa — último recurso: documento simple, pero que nunca falte la minuta
                _logger.warning("Constructor de marca no disponible (%s); se genera documento simple", e)
                acc = self.env["aq.google.sync"]._account()
                rows = "\n".join("- %s (%s, %s)" % (a.name, a.owner_id.name or a.owner_partner_id.name or "-", a.due_date or "-") for a in m.agreement_ids)
                text = "%s\n%s · %s\n\nAgenda:\n%s\n\nMinuta:\n%s\n\nAcuerdos:\n%s\n" % (m.name, m.project_id.name, m.date, m.agenda or "", re.sub(r"<[^>]+>", " ", m.minutes or ""), rows)
                _, url = acc.create_doc("Minuta · %s · %s" % (m.project_id.name, m.name), text, acc.drive_folder_id("Alphaops"))
            m.write({"google_doc_url": url})
            self.env["aq.ops.document"].sudo().create({"name": "Minuta · %s" % m.name, "doc_type": "minuta", "project_id": m.project_id.id, "drive_url": url, "meeting_id": m.id, "client_visible": m.client_visible})
        return True


class OpsProjectGoogle(models.Model):
    _inherit = "aq.ops.project"

    def action_export_sheet(self):
        url = self.env["aq.google.sync"].export_portfolio_sheet()
        for p in self:
            p.message_post(body=_("Portafolio exportado a Google Sheets: <a href='%s'>%s</a>") % (url, url))
        return True

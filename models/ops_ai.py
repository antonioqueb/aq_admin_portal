# -*- coding: utf-8 -*-
"""AlphaOps · Copiloto de IA (DeepSeek por API). Solo propone; nunca aprueba, acepta, autoriza, cambia fechas ni cierra."""
import json
import logging
import os
import re
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
SYSTEM = ("Eres el copiloto operativo de AlphaQueb Consulting (consultora Odoo, México). Respondes en español, con precisión y brevedad. "
          "Solo propones: nunca apruebas cambios, alteras alcance, aceptas entregables, autorizas liberaciones, cambias fechas comprometidas, "
          "envías comunicaciones vinculantes, cierras incidentes ni tomas decisiones comerciales. Toda propuesta requiere confirmación humana.")


class OpsAI(models.AbstractModel):
    _name = "aq.ops.ai"
    _description = "AlphaOps: copiloto IA (DeepSeek)"

    @api.model
    def _integration(self):
        return self.env["aq.ops.integration"].sudo().search([("kind", "=", "deepseek")], limit=1)

    @api.model
    def _config(self):
        """Única fuente de configuración para TODAS las herramientas de IA.
        La API key se toma, en este orden: variable de entorno DEEPSEEK_API_KEY (recomendado; nunca se guarda en BD),
        parámetro del sistema aq_ops.deepseek_api_key, y por último el campo del registro de integración."""
        i = self._integration()
        icp = self.env["ir.config_parameter"].sudo()
        key = (os.environ.get("DEEPSEEK_API_KEY") or icp.get_param("aq_ops.deepseek_api_key") or icp.get_param("DEEPSEEK_API_KEY") or (i.api_key if i else "") or "").strip()
        enabled = bool(key) and (not i or i.enabled or bool(os.environ.get("DEEPSEEK_API_KEY")))
        return {"key": key, "enabled": enabled, "base_url": (os.environ.get("DEEPSEEK_BASE_URL") or (i.base_url if i else "") or "https://api.deepseek.com").rstrip("/"),
                "model": os.environ.get("DEEPSEEK_MODEL") or icp.get_param("aq_ops.deepseek_model_auto") or (i.model if i else "") or "deepseek-chat", "record": i,
                "source": "env" if os.environ.get("DEEPSEEK_API_KEY") else "param" if (icp.get_param("aq_ops.deepseek_api_key") or icp.get_param("DEEPSEEK_API_KEY")) else "record" if key else "none"}

    @api.model
    def list_models(self):
        c = self._config()
        if not c["key"]:
            return []
        r = requests.get(c["base_url"] + "/models", headers={"Authorization": "Bearer %s" % c["key"]}, timeout=20)
        r.raise_for_status()
        return [m.get("id") for m in r.json().get("data", []) if m.get("id")]

    @api.model
    def pick_latest_model(self, prefer_reasoning=False):
        """Elige el modelo más reciente disponible en la cuenta de DeepSeek y lo guarda (aq_ops.deepseek_model_auto)."""
        icp = self.env["ir.config_parameter"].sudo()
        try:
            models_ = self.list_models()
        except Exception as e:  # noqa
            return {"model": self._config()["model"], "error": str(e)}
        if not models_:
            return {"model": self._config()["model"], "models": []}
        def score(mid):
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", mid)]
            return (max(nums) if nums else 0.0, 1 if ("reasoner" in mid) == prefer_reasoning else 0, mid)
        # Los alias 'deepseek-chat' / 'deepseek-reasoner' apuntan siempre a la última versión publicada por DeepSeek.
        versioned = [m for m in models_ if re.search(r"\d", m)]
        chosen = max(versioned, key=score) if versioned else ("deepseek-reasoner" if prefer_reasoning and "deepseek-reasoner" in models_ else "deepseek-chat" if "deepseek-chat" in models_ else models_[0])
        icp.set_param("aq_ops.deepseek_model_auto", chosen)
        i = self._integration()
        if i:
            i.write({"model": chosen, "enabled": True})
        return {"model": chosen, "models": models_}

    @api.model
    def available(self):
        return self._config()["enabled"]

    @api.model
    def status(self):
        c = self._config()
        return {"available": c["enabled"], "source": c["source"], "model": c["model"], "base_url": c["base_url"], "key_hint": ("…" + c["key"][-4:]) if c["key"] else ""}

    @api.model
    def test_connection(self):
        """Prueba real contra DeepSeek; devuelve el texto o el error."""
        try:
            out = self.chat("Responde únicamente: OK", max_tokens=5)
            return {"ok": bool(out), "answer": out, "status": self.status()}
        except Exception as e:  # noqa
            return {"ok": False, "error": str(e), "status": self.status()}

    @api.model
    def chat(self, prompt, system=SYSTEM, json_mode=False, max_tokens=1500):
        """Llamada al endpoint compatible de DeepSeek (/chat/completions). Devuelve texto (o None sin integración)."""
        c = self._config()
        if not c["enabled"]:
            return None
        url = c["base_url"] + "/chat/completions"
        body = {"model": c["model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": 0.2, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = requests.post(url, json=body, headers={"Authorization": "Bearer %s" % c["key"], "Content-Type": "application/json"}, timeout=60)
            r.raise_for_status()
            if c["record"]:
                c["record"].write({"last_used": fields.Datetime.now()})
            return r.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            _logger.warning("DeepSeek no disponible: %s", e)
            raise UserError(_("El copiloto (DeepSeek) no respondió: %s") % e)

    # ------------------------------------------------------------------ capacidades
    @api.model
    def summarize_meeting(self, meeting):
        text = meeting.transcript or meeting.minutes or meeting.agenda or ""
        if not text.strip():
            raise UserError(_("La reunión no tiene transcripción, minuta ni agenda."))
        prompt = ("Resume esta reunión y extrae en JSON: {\"summary\": str, \"agreements\": [{\"name\", \"owner\", \"due_date\", \"kind\": compromiso|acuerdo|tarea|cambio}], "
                  "\"decisions\": [{\"name\", \"decision\"}], \"questions\": [str], \"risks\": [str]}. Proyecto: %s. Texto:\n%s") % (meeting.project_id.name, re.sub(r"<[^>]+>", " ", text)[:12000])
        out = self.chat(prompt, json_mode=True, max_tokens=2500)
        if out is None:
            data = self._heuristic_meeting(text)
        else:
            try:
                data = json.loads(out)
            except Exception:
                data = {"summary": out, "agreements": [], "decisions": [], "questions": [], "risks": []}
        meeting.write({"ai_summary": data.get("summary"), "ai_proposals_json": json.dumps(data, ensure_ascii=False)})
        Agreement = self.env["aq.ops.meeting.agreement"]
        for a in data.get("agreements", []):
            if a.get("name") and not Agreement.search_count([("meeting_id", "=", meeting.id), ("name", "=", a["name"])]):
                owner = self.env["aq.portal.member"].search([("name", "ilike", a.get("owner") or "___")], limit=1)
                Agreement.create({"meeting_id": meeting.id, "name": a["name"], "owner_id": owner.id, "due_date": a.get("due_date") if re.match(r"\d{4}-\d{2}-\d{2}", str(a.get("due_date") or "")) else False,
                                  "kind": a.get("kind") if a.get("kind") in ("compromiso", "acuerdo", "tarea", "cambio") else "compromiso", "proposed_by_ai": True})
        for q in data.get("questions", []):
            self.env["aq.ops.meeting.question"].create({"meeting_id": meeting.id, "name": q[:200]})
        return data

    def _heuristic_meeting(self, text):
        plain = re.sub(r"<[^>]+>", " ", text)
        sentences = [s.strip() for s in re.split(r"[.\n]", plain) if len(s.strip()) > 20]
        agreements = [{"name": s[:150], "owner": "", "due_date": "", "kind": "compromiso"} for s in sentences if re.search(r"\b(se acuerda|acordamos|compromiso|queda de|enviar[áa]|entregar[áa]|revisar[áa]|va a)\b", s, re.I)][:10]
        questions = [s[:150] for s in sentences if "?" in s or re.search(r"\b(pendiente de definir|por confirmar|duda)\b", s, re.I)][:5]
        risks = [s[:150] for s in sentences if re.search(r"\b(riesgo|retraso|bloqueo|depende de|no está listo)\b", s, re.I)][:5]
        return {"summary": " ".join(sentences[:4])[:600], "agreements": agreements, "decisions": [], "questions": questions, "risks": risks}

    @api.model
    def explain_project(self, project):
        p = project
        facts = {"salud": p.health, "razón": p.health_reason, "etapa": p.stage, "horas": "%.0f/%.0f (%.0f%%)" % (p.hours_consumed, p.hours_authorized, p.hours_pct),
                 "bloqueados": p.blocked_items, "en_validacion": p.in_validation, "riesgos": p.open_risks, "decisiones_pendientes": p.pending_decisions,
                 "esperando_cliente": p.client_dependent, "dias_sin_actividad": p.days_without_activity, "siguiente_accion": p.next_action, "fecha": str(p.next_action_date),
                 "restriccion_comercial": p.commercial_restriction, "hitos_desviados": [(m.name, m.deviation_days) for m in p.milestone_ids if m.deviation_days > 0]}
        prompt = "Explica en 5 líneas por qué el proyecto está en %s y recomienda la siguiente acción concreta. Datos: %s" % (p.health, json.dumps(facts, ensure_ascii=False, default=str))
        out = self.chat(prompt)
        if out is None:
            reasons = []
            if p.blocked_items: reasons.append("%d elementos bloqueados" % p.blocked_items)
            if p.hours_pct >= 80: reasons.append("consumo de horas al %.0f%%" % p.hours_pct)
            if p.client_dependent: reasons.append("hay trabajo esperando al cliente")
            if facts["hitos_desviados"]: reasons.append("hitos desviados: " + ", ".join("%s (+%dd)" % x for x in facts["hitos_desviados"]))
            if p.days_without_activity > 5: reasons.append("%d días sin actividad" % p.days_without_activity)
            if p.commercial_restriction: reasons.append("restricción comercial vigente")
            rec = "Definir siguiente acción con responsable y fecha" if not p.has_next_action else "Desbloquear: %s" % (p.item_ids.filtered(lambda i: i.state == "bloqueado")[:1].name or p.next_action)
            out = "Proyecto en %s. %s. Recomendación: %s." % (p.health, "; ".join(reasons) or p.health_reason, rec)
        return out

    @api.model
    def draft_report(self, project):
        rep = self.env["aq.ops.status.report"].generate(project)
        out = self.chat("Redacta un reporte de estado ejecutivo (máx. 200 palabras, HTML simple) para el cliente a partir de: %s" % re.sub(r"<[^>]+>", " ", rep.summary)[:6000])
        if out:
            rep.write({"summary": out + "<hr/>" + rep.summary, "generated_by_ai": True})
        return rep

    @api.model
    def compare_scope(self, request):
        scope = request.project_id.scope_current or ""
        out = self.chat("Alcance vigente:\n%s\n\nNueva solicitud: %s\n%s\n\n¿Está incluida? Responde JSON {\"in_scope\": true|false|null, \"reason\": str, \"classification\": pregunta|solicitud_operativa|defecto|incidente|requerimiento|cambio_alcance|mejora|deuda_tecnica|capacitacion|acceso_configuracion|administrativo}" % (scope[:6000], request.name, request.description or ""), json_mode=True)
        if out is None:
            toks = set(re.findall(r"[a-záéíóúñ]{5,}", (request.name + " " + (request.description or "")).lower()))
            hits = len([t for t in toks if t in scope.lower()])
            return {"in_scope": None if not scope else hits >= 3, "reason": "Coincidencia de términos con el alcance: %d" % hits, "classification": "requerimiento"}
        try:
            return json.loads(out)
        except Exception:
            return {"in_scope": None, "reason": out, "classification": "sin_clasificar"}

    @api.model
    def suggest_tests(self, item):
        out = self.chat("Propón 5 casos de prueba (JSON {\"cases\": [{\"name\", \"steps\", \"expected\"}]}) para: %s. Criterios: %s" % (item.name, item.acceptance_criteria or item.description or ""), json_mode=True)
        cases = []
        if out:
            try:
                cases = json.loads(out).get("cases", [])
            except Exception:
                cases = []
        if not cases:
            cases = [{"name": "Flujo principal: %s" % item.name, "steps": "Ejecutar el flujo descrito en los criterios", "expected": item.acceptance_criteria or "Cumple criterios"},
                     {"name": "Validación de datos obligatorios", "steps": "Omitir campos requeridos", "expected": "El sistema impide continuar"},
                     {"name": "Permisos", "steps": "Ejecutar con un usuario sin permisos", "expected": "Acceso denegado"}]
        for c in cases[:8]:
            self.env["aq.ops.test.case"].create({"name": c.get("name", "Caso")[:200], "steps": c.get("steps"), "expected": c.get("expected"), "item_id": item.id, "project_id": item.project_id.id, "generated_by_ai": True})
        return len(cases)

    @api.model
    def summarize_incident(self, incident):
        log = "\n".join("%s: %s" % (c.create_date, c.body) for c in incident.comment_ids)
        text = "Incidente %s (%s). Reporte: %s. Contención: %s. Diagnóstico: %s. Corrección: %s. Bitácora:\n%s" % (incident.name, incident.severity, incident.description, incident.containment, incident.diagnosis, incident.correction, log)
        out = self.chat("Resume el historial de este incidente en 6 líneas y sugiere acción preventiva: %s" % text[:8000])
        return out or ("Incidente %s en paso '%s'. %s" % (incident.name, incident.step, (incident.diagnosis or incident.description or "")[:300]))

    @api.model
    def next_action(self, project):
        items = project.item_ids.filtered(lambda i: i.state not in ("cerrado", "cancelado", "aceptado", "liberado", "verificado")).sorted(lambda i: (i.state != "bloqueado", i.priority != "2", i.date_due or fields.Date.today()))
        cand = items[:1]
        sug = "Desbloquear '%s'" % cand.name if cand and cand.state == "bloqueado" else "Avanzar '%s' (%s)" % (cand.name, cand.assignee_id.name or "sin responsable") if cand else "Definir primer hito"
        out = self.chat("Proyecto %s: elementos abiertos: %s. Recomienda UNA siguiente acción concreta con responsable sugerido (una línea)." % (project.name, "; ".join("%s[%s]" % (i.name, i.state) for i in items[:15])))
        return out or sug

    @api.model
    def duplicates(self, project):
        items = project.item_ids.filtered(lambda i: i.state not in ("cerrado", "cancelado"))
        pairs = []
        toks = {i.id: set(re.findall(r"[a-záéíóúñ0-9]{4,}", i.name.lower())) for i in items}
        ids = list(items)
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                ta, tb = toks[ids[a].id], toks[ids[b].id]
                if ta and tb and len(ta & tb) / len(ta | tb) >= 0.6:
                    pairs.append({"a": {"id": ids[a].id, "name": ids[a].name}, "b": {"id": ids[b].id, "name": ids[b].name}})
        return pairs[:20]

    @api.model
    def suggest_dependencies(self, item):
        words = set(re.findall(r"[a-záéíóúñ0-9]{5,}", item.name.lower()))
        cands = item.project_id.item_ids.filtered(lambda i: i.id != item.id and i.state not in ("cerrado", "cancelado") and i.item_type in ("tarea", "requerimiento", "historia", "entregable"))
        scored = sorted(((len(words & set(re.findall(r"[a-záéíóúñ0-9]{5,}", c.name.lower()))), c) for c in cands), key=lambda x: -x[0])
        return [{"id": c.id, "name": c.name, "score": s} for s, c in scored[:5] if s]

    # ------------------------------------------------------------------ asistente genérico (todas las fichas)
    TASKS = {
        "summarize": "Resume este registro en 5 líneas, con lo importante primero.",
        "next": "Propón la siguiente acción concreta (una línea), con responsable sugerido y fecha relativa.",
        "risks": "Identifica riesgos, supuestos y dependencias implícitas en este registro. Lista breve.",
        "improve": "Reescribe el texto indicado con claridad profesional, sin cambiar el sentido; devuelve solo el texto.",
        "draft": "Redacta un borrador breve y profesional del texto solicitado para el campo indicado; devuelve solo el texto.",
        "questions": "Lista las preguntas abiertas que habría que resolver antes de avanzar.",
        "criteria": "Propón criterios de aceptación verificables (Dado/Cuando/Entonces) para este elemento.",
        "classify": "Clasifica y propón determinación.",
        "email": "Redacta un correo breve y cordial al cliente sobre este registro; devuelve solo el cuerpo.",
    }

    @api.model
    def assist(self, record, task, field=None, text=None, instructions=None):
        """Asistencia sobre cualquier registro: se serializa lo esencial (sin campos sensibles) y se consulta al modelo."""
        hidden = {"api_key", "password_hash", "mfa_secret", "mfa_pending_secret", "bank_info", "payment_amount", "reset_token_hash", "token_hash", "internal_notes"}
        facts = {}
        for name, f in record._fields.items():
            if name in hidden or name.startswith("message_") or name.startswith("activity_") or f.type in ("binary", "one2many", "many2many") or name in ("id", "create_uid", "write_uid"):
                continue
            v = record[name]
            if f.type == "many2one":
                v = v.display_name if v else None
            elif f.type == "html" and v:
                v = re.sub(r"<[^>]+>", " ", v)
            if v in (None, False, "", 0, 0.0):
                continue
            facts[f.string or name] = str(v)[:600]
        task_text = self.TASKS.get(task, task)
        extra = ("\nCampo objetivo: %s" % field) if field else ""
        extra += ("\nTexto base:\n%s" % text) if text else ""
        extra += ("\nInstrucciones adicionales: %s" % instructions) if instructions else ""
        prompt = "Registro (%s):\n%s\n\nTarea: %s%s" % (record._description, json.dumps(facts, ensure_ascii=False)[:9000], task_text, extra)
        out = self.chat(prompt, max_tokens=1200)
        if out is None:
            out = self._assist_heuristic(record, task, facts)
        return out

    def _assist_heuristic(self, record, task, facts):
        name = facts.get("Nombre") or record.display_name
        if task == "summarize":
            return "%s. " % name + " ".join("%s: %s." % (k, v[:80]) for k, v in list(facts.items())[:6])
        if task == "next":
            return "Definir siguiente acción para '%s' con responsable y fecha (sin IA conectada: configure DEEPSEEK_API_KEY)." % name
        if task == "criteria":
            return "Dado el contexto de '%s', cuando se ejecute el flujo principal, entonces el resultado cumple lo descrito.\n- Validación de datos obligatorios\n- Permisos por perfil" % name
        return "Copiloto sin conexión a DeepSeek. Resumen disponible: %s" % name

    @api.model
    def classify_request(self, request):
        """Al crear una solicitud: propone clasificación, determinación y posibles duplicados (no decide: sugiere)."""
        try:
            a = self.compare_scope(request)
        except Exception as e:  # noqa
            a = {"in_scope": None, "reason": str(e), "classification": "sin_clasificar"}
        det = "en_alcance" if a.get("in_scope") is True else "estimacion" if a.get("in_scope") is False else "pendiente"
        dups = ", ".join(request.potential_duplicate_ids.mapped("name")[:3])
        text = "Sugerencia del copiloto: clasificación '%s', determinación '%s'. %s%s" % (a.get("classification"), det, a.get("reason", ""), (" Posibles duplicados: %s." % dups) if dups else "")
        request.with_context(aq_skip_activity=True).write({"ai_suggestion": text})
        return text

    @api.model
    def digest_summary(self, lines):
        out = self.chat("Resume en 4 líneas ejecutivas, priorizando lo crítico, estas alertas/notificaciones:\n" + "\n".join(lines[:80]), max_tokens=400)
        return out or ""

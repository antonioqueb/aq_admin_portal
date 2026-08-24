# -*- coding: utf-8 -*-
"""Biblioteca de prompts de Alphaqueb: cada proceso de IA usa un prompt versionado, editable y probable
desde el portal (sin tocar código). Incluye la 'voz de marca' que se antepone a todos los sistemas."""
import json
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class AiPrompt(models.Model):
    _name = "aq.ai.prompt"
    _description = "Alphaqueb: prompt de proceso"
    _order = "category, sequence, code"
    _inherit = ["mail.thread"]

    code = fields.Char(required=True, index=True, help="Clave que invoca el proceso (no cambiar).")
    name = fields.Char(required=True, tracking=True)
    category = fields.Selection([("sesiones", "Sesiones y reuniones"), ("documentos", "Documentos y reportes"), ("correo", "Correo y enrutamiento"),
                                 ("proyectos", "Proyectos y portafolio"), ("calidad", "Calidad y requerimientos"), ("marca", "Voz de marca"), ("otro", "Otro")],
                                default="otro", required=True, tracking=True)
    sequence = fields.Integer(default=10)
    purpose = fields.Text(string="Para qué sirve", help="Explicación funcional para quien edite el prompt.")
    tier = fields.Selection([("fast", "Rápido · V4 Flash"), ("deep", "Profundo · V4 Pro"), ("vision", "Visión · Flash Vision Exp")], default="fast", required=True, tracking=True)
    system_prompt = fields.Text(string="Instrucción de sistema (rol)", tracking=True)
    user_template = fields.Text(string="Plantilla del mensaje", required=True, tracking=True,
                                help="Usa variables {{nombre}}. Se sustituyen con el contexto del proceso.")
    json_mode = fields.Boolean(string="Respuesta en JSON", tracking=True)
    json_schema_hint = fields.Text(string="Forma esperada del JSON", help="Se anexa a la instrucción cuando la respuesta es JSON.")
    max_tokens = fields.Integer(default=1500)
    temperature = fields.Float(default=0.2)
    include_brand_voice = fields.Boolean(string="Anteponer voz de marca", default=True)
    active = fields.Boolean(default=True)
    version = fields.Integer(default=1, readonly=True)
    variables_hint = fields.Char(string="Variables disponibles", readonly=True, compute="_compute_vars")
    last_used = fields.Datetime(readonly=True)
    use_count = fields.Integer(readonly=True)
    last_output = fields.Text(string="Última prueba", readonly=True)
    editable_by_direction = fields.Boolean(default=True, string="Editable desde el portal")

    _sql_constraints = [("code_uniq", "unique(code)", "Ya existe un prompt con esa clave.")]

    @api.depends("user_template", "system_prompt")
    def _compute_vars(self):
        for p in self:
            p.variables_hint = ", ".join(sorted(set(VAR_RE.findall((p.user_template or "") + " " + (p.system_prompt or ""))))) or "—"

    def write(self, vals):
        if any(k in vals for k in ("system_prompt", "user_template", "json_schema_hint", "tier")):
            for p in self:
                super(AiPrompt, p).write({"version": p.version + 1})
        return super().write(vals)

    # ------------------------------------------------------------------ motor
    @api.model
    def brand_voice(self):
        p = self.sudo().search([("code", "=", "brand_voice"), ("active", "=", True)], limit=1)
        return (p.system_prompt or p.user_template or "") if p else ""

    @api.model
    def render(self, code, ctx=None, fallback_system=None, fallback_template=None, tier=None, images=None):
        """Ejecuta el prompt 'code' con el contexto dado. Si no existe, usa el respaldo del código."""
        ctx = ctx or {}
        p = self.sudo().search([("code", "=", code), ("active", "=", True)], limit=1)
        AI = self.env["aq.ops.ai"].sudo()
        if p:
            system = (p.system_prompt or "").strip()
            if p.include_brand_voice and p.category != "marca":
                bv = self.brand_voice()
                system = (bv + "\n\n" + system).strip() if bv else system
            body = self._fill(p.user_template, ctx)
            if p.json_mode and p.json_schema_hint:
                body += "\n\nDevuelve exclusivamente un objeto JSON con esta forma:\n" + p.json_schema_hint.strip()
            out = AI.chat(body, system=system or AI.SYSTEM_DEFAULT, json_mode=p.json_mode, max_tokens=p.max_tokens or 1500, tier=tier or p.tier, images=images)
            p.sudo().write({"last_used": fields.Datetime.now(), "use_count": p.use_count + 1})
            return AI.parse_json(out) if (p.json_mode and out) else out
        # respaldo: comportamiento embebido
        body = self._fill(fallback_template or "", ctx)
        out = AI.chat(body, system=fallback_system or AI.SYSTEM_DEFAULT, json_mode=bool(images is None and fallback_system and "JSON" in (fallback_template or "")), max_tokens=2000, tier=tier or "fast", images=images)
        return out

    @api.model
    def _fill(self, template, ctx):
        def sub(m):
            key = m.group(1)
            val = ctx
            for part in key.split("."):
                val = (val or {}).get(part) if isinstance(val, dict) else getattr(val, part, None)
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False, default=str)
            return str(val)
        return VAR_RE.sub(sub, template or "")

    def action_test(self):
        """Prueba el prompt con un contexto de ejemplo tomado del propio sistema."""
        self.ensure_one()
        sample = {"titulo": "SESIÓN #99– DEMO– DAILY SYNC | hoy", "proyecto": "Proyecto de demostración", "cliente": "Cliente Demo", "fecha": str(fields.Date.today()),
                  "transcripcion": "Antonio: revisamos el avance del módulo de inventario. Dayana: quedan pendientes dos reportes. "
                                   "Acordamos que Jhon entrega el reporte de existencias el viernes y el cliente enviará el catálogo actualizado el jueves.",
                  "texto": "Texto de ejemplo para la prueba del prompt.", "asunto": "Factura F-1024 pendiente de pago", "remitente": "contacto@cliente.com",
                  "alcance": "Implementación de inventario y compras.", "solicitud": "Necesitamos un reporte nuevo de existencias por almacén.",
                  "registro": {"nombre": "Elemento demo", "estado": "en progreso"}, "elementos": "Elemento A [en progreso]; Elemento B [bloqueado]"}
        out = self.render(self.code, sample)
        self.sudo().write({"last_output": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=2)})
        return True

    def action_duplicate_version(self):
        for p in self:
            p.copy({"code": "%s_v%d" % (p.code, p.version + 1), "name": "%s (copia)" % p.name, "active": False})
        return True

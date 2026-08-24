# -*- coding: utf-8 -*-
from odoo import api, fields, models

DOC_TYPES = [("blueprint", "Blueprint"), ("as_is", "AS-IS"), ("to_be", "TO-BE"), ("gap", "GAP"), ("manual", "Manual"), ("runbook", "Runbook"),
             ("arquitectura", "Arquitectura"), ("procedimiento", "Procedimiento"), ("minuta", "Minuta"), ("decision", "Decisión"),
             ("capacitacion", "Material de capacitación"), ("evidencia", "Evidencia"), ("entregable", "Entregable"), ("otro", "Otro")]


class OpsDocument(models.Model):
    """5.13 Biblioteca operativa conectada con Drive (referencias seguras, versiones lógicas, documento vigente)."""
    _name = "aq.ops.document"
    _description = "Alphaops: documento"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "doc_type, name"

    name = fields.Char(required=True, tracking=True)
    doc_type = fields.Selection(DOC_TYPES, required=True, default="otro")
    project_id = fields.Many2one("aq.ops.project", required=True)
    partner_id = fields.Many2one(related="project_id.partner_id", store=True)
    drive_url = fields.Char(string="Enlace en Google Drive")
    drive_file_id = fields.Char(string="ID de archivo Drive")
    version = fields.Char(default="1.0")
    is_current = fields.Boolean(default=True, string="Documento vigente", tracking=True)
    is_canonical = fields.Boolean(string="Documento canónico")
    superseded_by_id = fields.Many2one("aq.ops.document", string="Reemplazado por", readonly=True)
    replaces_id = fields.Many2one("aq.ops.document", string="Reemplaza a", readonly=True)
    owner_id = fields.Many2one("aq.portal.member", string="Responsable")
    item_ids = fields.Many2many("aq.ops.item", string="Elementos relacionados")
    decision_id = fields.Many2one("aq.ops.decision")
    meeting_id = fields.Many2one("aq.ops.meeting")
    client_visible = fields.Boolean(default=False, string="Autorizado para el cliente")
    summary = fields.Text(string="Contexto / resumen")

    def action_new_version(self):
        for d in self:
            try:
                major, minor = d.version.split("."); nv = "%s.%d" % (major, int(minor) + 1)
            except Exception:
                nv = d.version + ".1"
            new = d.copy({"version": nv, "replaces_id": d.id, "is_current": True, "superseded_by_id": False})
            d.write({"is_current": False, "superseded_by_id": new.id})
        return True

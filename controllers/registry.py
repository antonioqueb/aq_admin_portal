# -*- coding: utf-8 -*-
"""Registro de recursos expuestos por la API del portal.

Cada recurso define: modelo, etiqueta, sección, columnas de lista, grupos del formulario,
pestañas (one2many -> sub-recurso), acciones permitidas, campos que solo Dirección puede
modificar y permisos por rol.  El frontend construye listas y formularios a partir de esto.
"""

ROLE_ALL = ["direccion", "coordinacion", "equipo", "consulta"]
ROLE_WRITE = ["direccion", "coordinacion"]
ROLE_TEAM = ["direccion", "coordinacion", "equipo"]

SECTIONS = [
    {"key": "inicio", "label": "Inicio"},
    {"key": "prioritarias", "label": "1. Funciones prioritarias"},
    {"key": "progresivas", "label": "2. Implementación progresiva"},
    {"key": "mediano", "label": "3. Mediano plazo"},
    {"key": "ritmo", "label": "4-5. Ritmo y entregables"},
    {"key": "admin", "label": "Administración"},
]

COMMON_HIDDEN = {"portal_create_user_id", "portal_write_user_id", "message_ids", "message_follower_ids",
                 "message_partner_ids", "website_message_ids", "activity_ids", "rating_ids", "message_main_attachment_id",
                 "has_message", "message_needaction", "message_needaction_counter", "message_has_error",
                 "message_has_error_counter", "message_attachment_count", "message_is_follower", "message_has_sms_error",
                 "my_activity_date_deadline", "activity_state", "activity_user_id", "activity_type_id", "activity_type_icon",
                 "activity_date_deadline", "activity_summary", "activity_exception_decoration", "activity_exception_icon",
                 "activity_calendar_event_id", "id", "__last_update", "create_uid", "write_uid", "create_date", "write_date",
                 "display_name", "password_hash", "reset_token_hash", "reset_token_expiry", "token_hash"}

RESOURCES = {
    # ------------------------------------------------------------------ 1.1
    "projects": {
        "model": "aq.portal.project", "label": "Control maestro de proyectos", "singular": "Proyecto",
        "section": "prioritarias", "icon": "folder", "order": 10, "attachments": True, "chatter": True,
        "list": ["name", "partner_id", "responsible_id", "stage", "next_action", "next_action_responsible_id", "next_action_date",
                 "days_without_activity", "billing_status", "collection_status", "requires_direction"],
        "filters": ["stage", "is_stale", "requires_direction", "billing_status", "collection_status", "responsible_id"],
        "groups": [
            {"title": "Cliente y equipo", "fields": ["name", "code", "partner_id", "contact_id", "contact_name", "contact_email", "contact_phone",
                                                      "responsible_id", "member_ids", "stage", "priority"]},
            {"title": "Alcance y fechas", "fields": ["scope", "contract_ref", "legal_item_id", "date_start", "date_end_planned",
                                                      "next_deliverable", "next_deliverable_date"]},
            {"title": "Siguiente acción", "fields": ["next_action", "next_action_responsible_id", "next_action_date"]},
            {"title": "Bloqueos y pendientes", "fields": ["blockers", "pending_client_info", "pending_validations"]},
            {"title": "Facturación y cobranza", "fields": ["billing_status", "collection_status", "amount_invoiced", "receivable_balance"]},
            {"title": "Horas", "fields": ["hours_contracted", "hours_executed", "hours_billed", "hours_unbilled"]},
            {"title": "Dirección", "fields": ["risks", "requires_direction", "direction_decision", "direction_decision_date"]},
            {"title": "Seguimiento", "fields": ["days_without_activity", "is_stale", "has_next_action", "client_dependent", "open_agreement_count",
                                                "overdue_agreement_count", "repeated_agreement_count", "step_progress", "last_activity_date", "notes"]},
        ],
        "tabs": [
            {"field": "agreement_ids", "resource": "agreements", "parent_field": "project_id", "label": "Acuerdos y pendientes"},
            {"field": "step_ids", "resource": "project_steps", "parent_field": "project_id", "label": "Procedimiento (15 pasos)"},
            {"field": "date_ids", "resource": "project_dates", "parent_field": "project_id", "label": "Fechas relevantes"},
            {"field": "deliverable_ids", "resource": "deliverables", "parent_field": "project_id", "label": "Entregables"},
            {"field": "invoice_schedule_ids", "resource": "invoices", "parent_field": "project_id", "label": "Facturación"},
            {"field": "receivable_ids", "resource": "receivables", "parent_field": "project_id", "label": "Cobranza"},
            {"field": "hour_bucket_ids", "resource": "hours", "parent_field": "project_id", "label": "Horas"},
            {"field": "change_request_ids", "resource": "changes", "parent_field": "project_id", "label": "Control de cambios"},
            {"field": "document_ids", "resource": "documents", "parent_field": "project_id", "label": "Documentos"},
            {"field": "risk_ids", "resource": "risks", "parent_field": "project_id", "label": "Riesgos"},
            {"field": "followup_ids", "resource": "followups", "parent_field": "project_id", "label": "Seguimientos"},
        ],
        "actions": [
            {"name": "action_request_update", "label": "Solicitar actualización", "roles": ROLE_WRITE},
            {"name": "action_escalate", "label": "Escalar a Dirección", "roles": ROLE_WRITE},
        ],
        "direction_fields": ["direction_decision", "direction_decision_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "project_steps": {
        "model": "aq.portal.project.step", "label": "Pasos del procedimiento", "singular": "Paso", "section": None,
        "list": ["sequence", "name", "state", "responsible_id", "date_done", "evidence"],
        "groups": [{"title": "Paso", "fields": ["sequence", "name", "state", "responsible_id", "date_done", "evidence", "notes"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "project_dates": {
        "model": "aq.portal.project.date", "label": "Fechas relevantes", "singular": "Fecha", "section": None,
        "list": ["date", "name", "date_type", "responsible_id", "done"],
        "groups": [{"title": "Fecha", "fields": ["name", "date", "date_type", "responsible_id", "done"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ROLE_WRITE},
    },
    "procedure_steps": {
        "model": "aq.portal.procedure.step", "label": "Plantilla del procedimiento de proyectos", "singular": "Paso", "section": "progresivas", "order": 30,
        "list": ["sequence", "name", "required_evidence"],
        "groups": [{"title": "Paso", "fields": ["sequence", "name", "description", "required_evidence"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.2
    "agreements": {
        "model": "aq.portal.agreement", "label": "Acuerdos y pendientes", "singular": "Acuerdo / pendiente",
        "section": "prioritarias", "icon": "check", "order": 20, "attachments": True, "chatter": True,
        "list": ["name", "project_id", "executor_id", "due_date", "state", "in_scope", "authorization_state", "escalated", "is_repeated", "needs_formalization"],
        "filters": ["state", "is_overdue", "executor_id", "project_id", "meeting_id", "escalated", "is_repeated", "needs_formalization", "risk_type", "in_scope"],
        "groups": [
            {"title": "Acuerdo", "fields": ["name", "description", "project_id", "partner_id", "meeting_id", "meeting_date", "meeting_ref", "source", "needs_formalization", "formalized"]},
            {"title": "Responsables", "fields": ["requested_by", "requested_by_partner_id", "executor_id", "due_date", "client_dependent", "priority"]},
            {"title": "Alcance y autorización", "fields": ["info_required", "in_scope", "requires_authorization", "authorization_state", "authorized_by_id", "authorization_date", "change_request_id"]},
            {"title": "Validación y cierre", "fields": ["completion_evidence", "validator_id", "validator_partner_id", "state", "closed_date", "closure_evidence", "closure_validated"]},
            {"title": "Seguimiento y escalamiento", "fields": ["last_update_request_date", "update_request_count", "escalated", "escalation_date", "escalation_reason",
                                                               "risk_type", "is_repeated", "repeat_count", "is_overdue", "days_overdue", "notes"]},
        ],
        "tabs": [{"field": "followup_ids", "resource": "followups", "parent_field": "agreement_id", "label": "Seguimientos"}],
        "actions": [
            {"name": "action_request_update", "label": "Solicitar actualización", "roles": ROLE_WRITE},
            {"name": "action_escalate", "label": "Escalar", "roles": ROLE_WRITE},
            {"name": "action_close", "label": "Cerrar", "roles": ROLE_TEAM},
            {"name": "action_authorize", "label": "Autorizar (Dirección)", "roles": ["direccion"]},
            {"name": "action_reject", "label": "Rechazar (Dirección)", "roles": ["direccion"]},
        ],
        "direction_fields": ["authorization_state", "authorized_by_id", "authorization_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    "meetings": {
        "model": "aq.portal.meeting", "label": "Reuniones, minutas y revisiones administrativas", "singular": "Reunión",
        "section": "prioritarias", "icon": "calendar", "order": 25, "attachments": True, "chatter": True,
        "list": ["date", "name", "meeting_type", "project_id", "partner_id", "convened_by_id", "agreement_count", "open_agreement_count", "state", "next_meeting_date"],
        "filters": ["meeting_type", "state", "project_id", "partner_id", "convened_by_id"],
        "groups": [
            {"title": "Reunión", "fields": ["name", "meeting_type", "date", "location", "convened_by_id", "member_ids", "external_attendees", "state"]},
            {"title": "Relación", "fields": ["project_id", "partner_id", "prospect_id", "next_meeting_date", "notified", "minutes_sent_date"]},
            {"title": "Orden del día y minuta", "fields": ["agenda", "minutes", "agreement_count", "open_agreement_count", "notes"]},
        ],
        "tabs": [{"field": "agreement_ids", "resource": "agreements", "parent_field": "meeting_id", "label": "Acuerdos y pendientes"}],
        "actions": [
            {"name": "action_convene", "label": "Convocar (enviar convocatoria)", "roles": ROLE_WRITE},
            {"name": "action_mark_done", "label": "Marcar realizada", "roles": ROLE_TEAM},
            {"name": "action_send_minutes", "label": "Enviar minuta a convocados", "roles": ROLE_WRITE},
        ],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    "clients": {
        "model": "res.partner", "label": "Clientes (directorio)", "singular": "Cliente", "section": "prioritarias", "icon": "building", "order": 75,
        "domain": [("is_company", "=", True)], "defaults": {"is_company": True},
        "only_fields": ["name", "vat", "email", "phone", "website", "street", "street2", "city", "state_id", "zip", "country_id",
                        "is_company", "parent_id", "child_ids", "function", "comment", "active"],
        "list": ["name", "vat", "email", "phone", "city", "country_id"],
        "filters": ["country_id"],
        "groups": [
            {"title": "Razón social y datos fiscales", "fields": ["name", "vat", "email", "phone", "website"]},
            {"title": "Domicilio fiscal", "fields": ["street", "street2", "city", "state_id", "zip", "country_id"]},
            {"title": "Notas", "fields": ["comment"]},
        ],
        "tabs": [{"field": "child_ids", "resource": "contacts", "parent_field": "parent_id", "label": "Contactos"}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": []},
    },
    "contacts": {
        "model": "res.partner", "label": "Contactos", "singular": "Contacto", "section": None,
        "only_fields": ["name", "function", "email", "phone", "parent_id", "comment", "active"],
        "list": ["name", "function", "email", "phone"],
        "groups": [{"title": "Contacto", "fields": ["name", "function", "email", "phone", "comment"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": []},
    },
    # ------------------------------------------------------------------ 1.3
    "invoices": {
        "model": "aq.portal.invoice.schedule", "label": "Calendario de facturación", "singular": "Factura programada",
        "section": "prioritarias", "icon": "file-text", "order": 30, "attachments": True, "chatter": True,
        "list": ["scheduled_date", "name", "partner_id", "project_id", "billing_type", "amount_total", "state", "issue_date", "sent_date", "reception_confirmed", "due_date"],
        "filters": ["state", "is_late", "billing_type", "partner_id", "project_id", "requires_payment_complement"],
        "groups": [
            {"title": "Qué se factura", "fields": ["name", "partner_id", "project_id", "basis_type", "basis_ref", "period_start", "period_end", "billing_type", "scheduled_date"]},
            {"title": "Evidencia", "fields": ["evidence_required", "evidence_received"]},
            {"title": "Datos fiscales", "fields": ["fiscal_name", "fiscal_vat", "fiscal_regime", "fiscal_zip", "cfdi_use", "payment_method", "payment_form"]},
            {"title": "Concepto e importes", "fields": ["concept", "currency_id", "amount_untaxed", "tax_rate", "amount_tax", "amount_total"]},
            {"title": "Envío", "fields": ["send_to_name", "send_to_email", "send_cc_email", "issuer_id", "info_sent_to_issuer_date"]},
            {"title": "Emisión y seguimiento", "fields": ["invoice_id", "invoice_number", "issue_date", "reviewed_vs_agreement", "sent_date", "reception_confirmed", "reception_date",
                                                          "due_date", "requires_payment_complement", "complement_state", "state", "receivable_id"]},
            {"title": "Validación de Dirección", "fields": ["hold_reason", "validation_requested", "validated_by_direction", "validated_by_id", "validation_date", "notes"]},
        ],
        "actions": [
            {"name": "action_hold", "label": "Detener y solicitar validación", "roles": ROLE_WRITE},
            {"name": "action_validate_direction", "label": "Validar (Dirección)", "roles": ["direccion"]},
            {"name": "action_mark_issued", "label": "Marcar emitida (crea CxC)", "roles": ROLE_WRITE},
            {"name": "action_mark_sent", "label": "Marcar enviada", "roles": ROLE_WRITE},
            {"name": "action_confirm_reception", "label": "Confirmar recepción", "roles": ROLE_WRITE},
        ],
        "direction_fields": ["validated_by_direction", "validated_by_id", "validation_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.4
    "receivables": {
        "model": "aq.portal.receivable", "label": "Cuentas por cobrar y cobranza", "singular": "Cuenta por cobrar",
        "section": "prioritarias", "icon": "dollar", "order": 40, "attachments": True, "chatter": True,
        "list": ["partner_id", "invoice_number", "issue_date", "amount_total", "due_date", "days_elapsed", "days_overdue", "amount_paid", "balance",
                 "last_followup_date", "promised_payment_date", "next_action", "responsible_id", "risk", "state"],
        "filters": ["state", "risk", "partner_id", "responsible_id", "promise_state", "escalated"],
        "groups": [
            {"title": "Factura", "fields": ["partner_id", "project_id", "invoice_schedule_id", "invoice_id", "invoice_number", "issue_date", "currency_id", "amount_total", "due_date"]},
            {"title": "Saldo", "fields": ["days_elapsed", "days_overdue", "days_to_due", "amount_paid", "balance", "paid_date", "collected_on_time", "collection_days"]},
            {"title": "Seguimiento", "fields": ["last_followup_date", "last_followup_note", "promised_payment_date", "promise_state", "next_action", "next_action_date", "responsible_id", "risk", "state", "escalated", "escalation_date"]},
            {"title": "Convenios (autoriza Dirección)", "fields": ["arrangement_type", "arrangement_description", "arrangement_authorized", "arrangement_authorized_by_id", "arrangement_date", "notes"]},
        ],
        "tabs": [
            {"field": "followup_ids", "resource": "followups", "parent_field": "receivable_id", "label": "Seguimientos"},
            {"field": "payment_ids", "resource": "payments", "parent_field": "receivable_id", "label": "Pagos recibidos"},
        ],
        "actions": [
            {"name": "action_escalate", "label": "Escalar internamente", "roles": ROLE_WRITE},
            {"name": "action_promise_kept", "label": "Compromiso cumplido", "roles": ROLE_WRITE},
            {"name": "action_promise_broken", "label": "Compromiso incumplido", "roles": ROLE_WRITE},
            {"name": "action_authorize_arrangement", "label": "Autorizar convenio (Dirección)", "roles": ["direccion"]},
        ],
        "direction_fields": ["arrangement_authorized", "arrangement_authorized_by_id", "arrangement_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "payments": {
        "model": "aq.portal.receivable.payment", "label": "Pagos recibidos", "singular": "Pago", "section": None,
        "list": ["date", "amount", "reference", "verified", "complement_issued"],
        "groups": [{"title": "Pago", "fields": ["date", "amount", "reference", "verified", "complement_issued"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.5
    "payables": {
        "model": "aq.portal.payable", "label": "Cuentas por pagar", "singular": "Cuenta por pagar",
        "section": "prioritarias", "icon": "credit-card", "order": 50, "attachments": True, "chatter": True,
        "list": ["due_date", "name", "category", "vendor_id", "project_id", "amount", "invoice_ref", "authorization_state", "payment_state", "payment_date"],
        "filters": ["category", "payment_state", "authorization_state", "is_overdue", "vendor_id", "project_id", "is_recurring"],
        "groups": [
            {"title": "Obligación", "fields": ["name", "category", "vendor_id", "partner_id", "project_id", "invoice_ref", "has_receipt", "reported_by_accounting"]},
            {"title": "Importe y fechas", "fields": ["currency_id", "amount", "due_date", "proposed_payment_date", "account_ref", "payment_method", "alert_days", "days_to_due"]},
            {"title": "Recurrencia", "fields": ["is_recurring", "recurrence"]},
            {"title": "Autorización (Dirección)", "fields": ["authorization_state", "authorized_by_id", "authorization_date"]},
            {"title": "Pago", "fields": ["payment_state", "payment_date", "payment_evidence", "paid_by_id", "notes"]},
        ],
        "actions": [
            {"name": "action_authorize", "label": "Autorizar pago (Dirección)", "roles": ["direccion"]},
            {"name": "action_reject", "label": "Rechazar (Dirección)", "roles": ["direccion"]},
            {"name": "action_mark_paid", "label": "Registrar pago ejecutado", "roles": ["direccion"]},
        ],
        "direction_fields": ["authorization_state", "authorized_by_id", "authorization_date", "payment_state", "payment_date", "payment_evidence", "paid_by_id"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.6
    "hours": {
        "model": "aq.portal.hour.bucket", "label": "Horas, alcances y trabajo facturable", "singular": "Bolsa de horas",
        "section": "prioritarias", "icon": "clock", "order": 60, "chatter": True,
        "list": ["project_id", "name", "hours_contracted", "hours_estimated", "hours_executed", "hours_registered", "hours_billed", "hours_paid",
                 "hours_unbilled", "hours_out_of_scope", "pct_consumed", "near_depletion", "state"],
        "filters": ["project_id", "state", "near_depletion", "over_budget", "has_unauthorized_work"],
        "groups": [
            {"title": "Bolsa / alcance", "fields": ["name", "project_id", "partner_id", "basis_ref", "period_start", "period_end", "hourly_rate", "state"]},
            {"title": "Horas", "fields": ["hours_contracted", "hours_estimated", "hours_executed", "hours_registered", "hours_billed", "hours_paid"]},
            {"title": "Hallazgos", "fields": ["hours_unbilled", "hours_unregistered", "hours_out_of_scope", "hours_remaining", "pct_consumed", "variance_quoted_vs_executed",
                                             "near_depletion", "over_budget", "has_unauthorized_work", "deliverables_pending_acceptance", "notes"]},
        ],
        "tabs": [{"field": "entry_ids", "resource": "hour_entries", "parent_field": "bucket_id", "label": "Registro de horas"}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "hour_entries": {
        "model": "aq.portal.hour.entry", "label": "Registro de horas", "singular": "Registro", "section": None,
        "list": ["date", "member_id", "hours", "description", "billable", "registered", "billed", "paid", "out_of_scope", "authorized"],
        "groups": [{"title": "Registro", "fields": ["date", "member_id", "hours", "description", "billable", "registered", "billed", "paid", "out_of_scope", "authorized", "change_request_id"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ROLE_WRITE},
    },
    "deliverables": {
        "model": "aq.portal.deliverable", "label": "Entregables y aceptación", "singular": "Entregable", "section": "prioritarias", "order": 65, "attachments": True,
        "list": ["project_id", "name", "due_date", "delivered_date", "responsible_id", "accepted", "acceptance_date", "billed", "state"],
        "filters": ["project_id", "state", "accepted", "billed"],
        "groups": [{"title": "Entregable", "fields": ["name", "project_id", "due_date", "delivered_date", "responsible_id", "validator_partner_id", "acceptance_criteria"]},
                   {"title": "Aceptación", "fields": ["accepted", "acceptance_date", "acceptance_evidence", "billed", "state", "notes"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ROLE_WRITE},
    },
    # ------------------------------------------------------------------ 1.7
    "prospects": {
        "model": "aq.portal.prospect", "label": "Control de prospectos", "singular": "Prospecto",
        "section": "prioritarias", "icon": "target", "order": 70, "attachments": True, "chatter": True,
        "list": ["name", "contact_name", "origin", "service_interest", "sales_responsible_id", "last_interaction_date", "next_action", "followup_date", "stage", "probability", "proposal_valid_until"],
        "filters": ["stage", "is_abandoned", "sales_responsible_id", "origin", "service_interest", "result"],
        "groups": [
            {"title": "Empresa y contacto", "fields": ["name", "contact_name", "contact_email", "contact_phone", "origin"]},
            {"title": "Necesidad", "fields": ["need_detected", "service_interest", "sales_responsible_id"]},
            {"title": "Seguimiento", "fields": ["last_interaction_date", "next_action", "followup_date", "pending_info", "days_without_followup", "is_abandoned"]},
            {"title": "Propuesta", "fields": ["proposal_sent", "proposal_ref", "proposal_date", "proposal_valid_until", "currency_id", "proposal_amount", "proposal_expired"]},
            {"title": "Etapa y resultado", "fields": ["stage", "probability", "result", "lost_reason", "lost_reason_detail", "partner_id", "project_id", "notes"]},
        ],
        "tabs": [{"field": "followup_ids", "resource": "followups", "parent_field": "prospect_id", "label": "Interacciones"}],
        "actions": [
            {"name": "action_mark_won", "label": "Marcar ganado", "roles": ROLE_WRITE},
            {"name": "action_mark_lost", "label": "Marcar perdido", "roles": ROLE_WRITE},
            {"name": "action_convert", "label": "Convertir en cliente y proyecto", "roles": ROLE_WRITE},
        ],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.8
    "documents": {
        "model": "aq.portal.document", "label": "Organización documental", "singular": "Documento",
        "section": "prioritarias", "icon": "archive", "order": 80, "attachments": True, "chatter": True,
        "list": ["folder_type", "name", "document_type", "partner_id", "version", "version_status", "is_signed", "confidentiality", "responsible_id", "state", "is_missing", "is_duplicate"],
        "filters": ["folder_type", "version_status", "is_signed", "confidentiality", "state", "is_missing", "is_duplicate", "sensitive"],
        "groups": [
            {"title": "Identificación", "fields": ["name", "folder_type", "document_type", "doc_date", "version", "version_status", "is_signed", "signed_date", "responsible_id"]},
            {"title": "Relaciones", "fields": ["partner_id", "project_id", "prospect_id", "employee_id", "vendor_id", "legal_item_id"]},
            {"title": "Clasificación y control", "fields": ["confidentiality", "sensitive", "required", "is_missing", "is_duplicate", "duplicate_of_id", "state", "change_validated_by_id"]},
            {"title": "Ubicación", "fields": ["storage_location", "external_url", "attachment_count", "notes"]},
        ],
        "actions": [{"name": "action_mark_final", "label": "Marcar como versión final", "roles": ROLE_WRITE}],
        "direction_fields": ["change_validated_by_id"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 1.9
    "legal": {
        "model": "aq.portal.legal.item", "label": "Inventario legal / matriz de contratos", "singular": "Documento legal",
        "section": "prioritarias", "icon": "shield", "order": 90, "attachments": True, "chatter": True,
        "list": ["category", "name", "partner_id", "exists", "is_current", "is_missing", "date_end", "risk_level", "priority", "status", "responsible_id"],
        "filters": ["category", "status", "exists", "is_current", "is_missing", "risk_level", "priority", "needs_redo", "is_expired"],
        "groups": [
            {"title": "Documento", "fields": ["name", "category", "partner_id", "employee_id", "vendor_id", "project_id", "template_id"]},
            {"title": "Estado real", "fields": ["exists", "is_current", "is_missing", "is_signed", "date_signed", "date_start", "date_end", "days_to_expiry", "is_expired", "status", "needs_redo"]},
            {"title": "Riesgo y prioridad", "fields": ["risk_level", "priority", "responsible_id", "review_date", "findings", "action_plan", "notes"]},
        ],
        "tabs": [{"field": "document_ids", "resource": "documents", "parent_field": "legal_item_id", "label": "Documentos en expediente"}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 2.1
    "templates": {
        "model": "aq.portal.template", "label": "Biblioteca legal (formatos y modelos)", "singular": "Formato",
        "section": "progresivas", "icon": "book", "order": 10, "attachments": True, "chatter": True,
        "list": ["category", "subtype", "name", "version", "version_date", "reviewer_id", "approval_state", "approved_by_id", "can_be_used"],
        "filters": ["category", "subtype", "approval_state", "can_be_used", "reviewer_id"],
        "groups": [
            {"title": "Formato", "fields": ["name", "category", "subtype", "version", "version_date", "previous_version_id", "external_url"]},
            {"title": "Revisión y aprobación", "fields": ["reviewer_id", "approval_state", "approved_by_id", "approval_date", "can_be_used"]},
            {"title": "Contenido", "fields": ["usage_notes", "content", "notes"]},
        ],
        "actions": [
            {"name": "action_submit_review", "label": "Enviar a revisión", "roles": ROLE_WRITE},
            {"name": "action_approve", "label": "Aprobar (Dirección)", "roles": ["direccion"]},
            {"name": "action_new_version", "label": "Nueva versión", "roles": ROLE_WRITE},
        ],
        "direction_fields": ["approval_state", "approved_by_id", "approval_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 2.2
    "employees": {
        "model": "aq.portal.employee", "label": "Administración de personal (expedientes)", "singular": "Expediente",
        "section": "progresivas", "icon": "users", "order": 20, "attachments": True, "chatter": True, "sensitive": True,
        "list": ["name", "relation_type", "position", "date_joined", "payment_scheme", "contract_signed", "nda_signed", "state", "missing_documents", "open_access_count"],
        "filters": ["relation_type", "state", "contract_signed", "nda_signed", "has_active_access_after_exit"],
        "groups": [
            {"title": "Identificación", "fields": ["name", "member_id", "relation_type", "position", "responsibilities", "date_joined", "date_left", "state"]},
            {"title": "Datos personales y fiscales (confidencial)", "fields": ["email", "phone", "rfc", "curp", "nss", "birth_date", "address", "fiscal_regime", "emergency_contact", "bank_info"]},
            {"title": "Contrato y confidencialidad", "fields": ["contract_legal_item_id", "contract_type", "contract_signed", "nda_signed", "ip_agreement_signed", "privacy_notice_delivered"]},
            {"title": "Esquema de pago", "fields": ["payment_scheme", "currency_id", "payment_amount", "payment_period"]},
            {"title": "Indicadores", "fields": ["missing_documents", "open_access_count", "has_active_access_after_exit", "onboarding_progress", "offboarding_progress", "notes"]},
        ],
        "tabs": [
            {"field": "required_document_ids", "resource": "employee_documents", "parent_field": "employee_id", "label": "Documentos requeridos"},
            {"field": "asset_ids", "resource": "assets", "parent_field": "employee_id", "label": "Equipo asignado"},
            {"field": "access_ids", "resource": "accesses", "parent_field": "employee_id", "label": "Accesos a sistemas"},
            {"field": "event_ids", "resource": "employee_events", "parent_field": "employee_id", "label": "Vacaciones, permisos, capacitaciones y cambios"},
            {"field": "checklist_ids", "resource": "checklist", "parent_field": "employee_id", "label": "Incorporación / separación"},
            {"field": "document_ids", "resource": "documents", "parent_field": "employee_id", "label": "Expediente documental"},
        ],
        "actions": [
            {"name": "action_activate", "label": "Marcar activo", "roles": ROLE_WRITE},
            {"name": "action_start_offboarding", "label": "Iniciar separación", "roles": ["direccion"]},
            {"name": "action_finish_offboarding", "label": "Concluir separación", "roles": ["direccion"]},
        ],
        "direction_fields": ["payment_amount"],
        "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "employee_documents": {"model": "aq.portal.employee.document", "label": "Documentos requeridos", "singular": "Documento", "section": None,
                           "list": ["name", "received", "date_received", "document_id", "notes"],
                           "groups": [{"title": "Documento", "fields": ["name", "received", "date_received", "document_id", "notes"]}],
                           "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ROLE_WRITE}},
    "assets": {"model": "aq.portal.asset", "label": "Equipo asignado", "singular": "Equipo", "section": None,
               "list": ["name", "serial", "delivered_date", "responsiva_signed", "returned_date", "state"],
               "groups": [{"title": "Equipo", "fields": ["name", "serial", "delivered_date", "responsiva_signed", "returned_date", "state"]}],
               "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ROLE_WRITE}},
    "accesses": {"model": "aq.portal.access", "label": "Accesos a sistemas", "singular": "Acceso", "section": None,
                 "list": ["system", "account", "granted_date", "owner_id", "state", "revoked_date"],
                 "groups": [{"title": "Acceso", "fields": ["system", "account", "granted_date", "owner_id", "state", "revoked_date"]}],
                 "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ROLE_WRITE}},
    "employee_events": {"model": "aq.portal.employee.event", "label": "Eventos de personal", "singular": "Evento", "section": None,
                        "list": ["event_type", "date_from", "date_to", "description", "approved"],
                        "groups": [{"title": "Evento", "fields": ["event_type", "date_from", "date_to", "description", "approved", "approved_by_id"]}],
                        "direction_fields": ["approved", "approved_by_id"],
                        "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ROLE_WRITE}},
    "checklist": {"model": "aq.portal.checklist.item", "label": "Checklist", "singular": "Elemento", "section": None,
                  "list": ["sequence", "kind", "name", "responsible_id", "done", "date_done", "evidence"],
                  "groups": [{"title": "Elemento", "fields": ["sequence", "kind", "name", "responsible_id", "done", "date_done", "evidence"]}],
                  "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_WRITE, "delete": ROLE_WRITE}},
    # ------------------------------------------------------------------ 2.4
    "changes": {
        "model": "aq.portal.change.request", "label": "Control de cambios y trabajo adicional", "singular": "Solicitud de cambio",
        "section": "progresivas", "icon": "git-branch", "order": 40, "attachments": True, "chatter": True,
        "list": ["request_date", "name", "project_id", "classification", "estimate_hours", "estimate_amount", "quotation_ref", "authorization_state", "can_execute", "executed", "state"],
        "filters": ["project_id", "classification", "authorization_state", "state", "executed_without_authorization"],
        "groups": [
            {"title": "Solicitud", "fields": ["name", "project_id", "partner_id", "requested_by", "request_date", "received_by_id", "description"]},
            {"title": "Clasificación y estimación", "fields": ["classification", "analysis", "estimate_hours", "currency_id", "estimate_amount", "estimated_by_id", "quotation_ref"]},
            {"title": "Autorización", "fields": ["authorization_state", "authorized_by_id", "authorization_date", "authorization_evidence", "can_execute"]},
            {"title": "Ejecución", "fields": ["executed", "executed_without_authorization", "state", "notes"]},
        ],
        "tabs": [{"field": "agreement_ids", "resource": "agreements", "parent_field": "change_request_id", "label": "Pendientes derivados"},
                 {"field": "hour_entry_ids", "resource": "hour_entries", "parent_field": "change_request_id", "label": "Horas ejecutadas"}],
        "actions": [
            {"name": "action_authorize_client", "label": "Registrar autorización del cliente", "roles": ROLE_WRITE},
            {"name": "action_authorize_direction", "label": "Autorizar excepción (Dirección)", "roles": ["direccion"]},
            {"name": "action_reject", "label": "Rechazar", "roles": ["direccion"]},
        ],
        "direction_fields": ["authorization_state", "authorized_by_id", "authorization_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 2.5
    "vendors": {
        "model": "aq.portal.vendor", "label": "Proveedores, licencias y servicios recurrentes", "singular": "Proveedor / servicio",
        "section": "progresivas", "icon": "server", "order": 50, "attachments": True, "chatter": True,
        "list": ["name", "service", "service_type", "responsible_id", "cost", "periodicity", "renewal_date", "payment_method", "operational_risk", "is_critical", "state"],
        "filters": ["service_type", "state", "operational_risk", "is_critical", "periodicity", "responsible_id"],
        "groups": [
            {"title": "Proveedor y servicio", "fields": ["name", "partner_id", "service", "service_type", "responsible_id", "project_id", "state"]},
            {"title": "Costo y renovación", "fields": ["currency_id", "cost", "periodicity", "renewal_date", "days_to_renewal", "auto_renew", "payment_method", "cancellation_notice_days"]},
            {"title": "Contrato y cuenta", "fields": ["contract_ref", "legal_item_id", "account_holder", "credential_location"]},
            {"title": "Riesgo operativo", "fields": ["operational_risk", "is_critical", "risk_description", "notes"]},
        ],
        "tabs": [{"field": "payable_ids", "resource": "payables", "parent_field": "vendor_id", "label": "Pagos"}],
        "actions": [{"name": "action_generate_payable", "label": "Generar cuenta por pagar", "roles": ROLE_WRITE}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 2.6
    "obligations": {
        "model": "aq.portal.obligation", "label": "Calendario de obligaciones", "singular": "Obligación",
        "section": "progresivas", "icon": "calendar", "order": 60, "attachments": True, "chatter": True,
        "list": ["date", "name", "obligation_type", "responsible_id", "partner_id", "recurrence", "state", "done_date"],
        "filters": ["obligation_type", "state", "responsible_id", "recurrence"],
        "groups": [
            {"title": "Obligación", "fields": ["name", "obligation_type", "date", "reminder_days", "days_to_date", "responsible_id", "recurrence", "state"]},
            {"title": "Relaciones", "fields": ["partner_id", "project_id", "vendor_id", "legal_item_id"]},
            {"title": "Cumplimiento", "fields": ["done_date", "evidence", "notes"]},
        ],
        "actions": [{"name": "action_done", "label": "Marcar cumplida", "roles": ROLE_TEAM}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 2.7
    "privacy": {
        "model": "aq.portal.data.inventory", "label": "Privacidad y manejo de información", "singular": "Tratamiento de datos",
        "section": "progresivas", "icon": "lock", "order": 70, "attachments": True, "chatter": True,
        "list": ["name", "data_subjects", "storage_location", "retention_period", "requires_special_controls", "responsible_id", "review_date", "state"],
        "filters": ["data_subjects", "state", "requires_special_controls", "responsible_id"],
        "groups": [
            {"title": "Datos", "fields": ["name", "data_subjects", "data_description", "purpose"]},
            {"title": "Almacenamiento y acceso", "fields": ["storage_location", "access_who", "access_member_ids", "shared_with", "retention_period"]},
            {"title": "Procedimientos", "fields": ["arco_procedure", "offboarding_action", "requires_special_controls", "special_controls", "privacy_notice_template_id"]},
            {"title": "Control", "fields": ["responsible_id", "review_date", "state", "notes"]},
        ],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 3.3
    "risks": {
        "model": "aq.portal.risk", "label": "Matriz de riesgos", "singular": "Riesgo",
        "section": "mediano", "icon": "alert-triangle", "order": 30, "attachments": True, "chatter": True,
        "list": ["name", "category", "risk_type", "probability", "impact", "severity", "responsible_id", "review_date", "state", "auto_generated"],
        "filters": ["category", "risk_type", "state", "responsible_id", "auto_generated"],
        "groups": [
            {"title": "Riesgo", "fields": ["name", "category", "risk_type", "description", "probability", "impact", "severity"]},
            {"title": "Control", "fields": ["responsible_id", "preventive_action", "mitigation_action", "review_date", "state"]},
            {"title": "Relaciones", "fields": ["project_id", "partner_id", "vendor_id", "employee_id", "auto_generated", "notes"]},
        ],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 3.4
    "manuals": {
        "model": "aq.portal.manual", "label": "Manuales y procedimientos internos", "singular": "Procedimiento",
        "section": "mediano", "icon": "book-open", "order": 40, "attachments": True, "chatter": True,
        "list": ["process_type", "name", "version", "owner_id", "state", "approval_date", "review_date"],
        "filters": ["process_type", "state", "owner_id"],
        "groups": [
            {"title": "Procedimiento", "fields": ["name", "process_type", "purpose", "scope_text", "version", "owner_id", "external_url", "review_date"]},
            {"title": "Aprobación", "fields": ["state", "approved_by_id", "approval_date"]},
            {"title": "Contenido", "fields": ["content", "notes"]},
        ],
        "actions": [{"name": "action_approve", "label": "Aprobar (Dirección)", "roles": ["direccion"]}],
        "direction_fields": ["approved_by_id", "approval_date"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 3.5
    "corporate": {
        "model": "aq.portal.corporate", "label": "Gobierno corporativo", "singular": "Documento corporativo",
        "section": "mediano", "icon": "briefcase", "order": 50, "attachments": True, "chatter": True, "sensitive": True,
        "list": ["date", "doc_type", "name", "parties", "signatories", "valid_until", "state", "responsible_id"],
        "filters": ["doc_type", "state", "responsible_id"],
        "groups": [
            {"title": "Documento", "fields": ["name", "doc_type", "date", "parties", "signatories", "valid_until", "state", "responsible_id"]},
            {"title": "Contenido", "fields": ["summary", "document_id", "legal_item_id", "notes"]},
        ],
        "roles": {"read": ROLE_WRITE, "write": ["direccion"], "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 3.6
    "tenders": {
        "model": "aq.portal.tender", "label": "Gobierno y sector público", "singular": "Procedimiento público",
        "section": "mediano", "icon": "landmark", "order": 60, "attachments": True, "chatter": True,
        "list": ["name", "entity", "tender_type", "reference", "deadline", "responsible_id", "scope_defined", "compliance_pct", "state"],
        "filters": ["tender_type", "state", "scope_defined", "responsible_id"],
        "groups": [
            {"title": "Procedimiento", "fields": ["name", "entity", "tender_type", "reference", "portal_url", "deadline", "responsible_id", "scope_defined", "state", "project_id"]},
            {"title": "Alcance y obligaciones", "fields": ["summary", "deliverables", "guarantees", "special_obligations", "compliance_pct", "notes"]},
        ],
        "tabs": [{"field": "requirement_ids", "resource": "checklist", "parent_field": "tender_id", "label": "Matriz de cumplimiento", "defaults": {"kind": "licitacion"}}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 3.7
    "improvements": {
        "model": "aq.portal.improvement", "label": "Mejora continua", "singular": "Propuesta",
        "section": "mediano", "icon": "zap", "order": 70, "chatter": True,
        "list": ["date", "name", "improvement_type", "proposed_by_id", "priority", "state", "responsible_id", "target_date"],
        "filters": ["improvement_type", "state", "priority", "proposed_by_id"],
        "groups": [
            {"title": "Propuesta", "fields": ["name", "improvement_type", "description", "expected_benefit", "proposed_by_id", "date", "priority"]},
            {"title": "Decisión e implementación", "fields": ["state", "decision_notes", "responsible_id", "target_date", "notes"]},
        ],
        "direction_fields": ["decision_notes"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_TEAM, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ 4/5
    "onboarding": {
        "model": "aq.portal.onboarding.deliverable", "label": "Entregables de incorporación", "singular": "Entregable",
        "section": "ritmo", "icon": "flag", "order": 20,
        "list": ["phase", "sequence", "name", "due_date", "responsible_id", "state", "delivered_date", "evidence"],
        "filters": ["phase", "state", "responsible_id"],
        "groups": [{"title": "Entregable", "fields": ["name", "phase", "sequence", "due_date", "responsible_id", "link_resource", "state", "delivered_date", "evidence", "notes"]}],
        "actions": [{"name": "action_deliver", "label": "Marcar entregado", "roles": ROLE_WRITE},
                    {"name": "action_validate", "label": "Validar (Dirección)", "roles": ["direccion"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "routines": {
        "model": "aq.portal.routine", "label": "Catálogo de rutinas", "singular": "Rutina", "section": "ritmo", "order": 30,
        "list": ["frequency", "sequence", "name", "link_resource", "active"],
        "groups": [{"title": "Rutina", "fields": ["name", "frequency", "sequence", "description", "link_resource", "active"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "reports": {
        "model": "aq.portal.report", "label": "Reportes ejecutivos", "singular": "Reporte", "section": "ritmo", "icon": "bar-chart", "order": 40,
        "list": ["date_to", "report_type", "name", "prepared_by_id", "sent_to_direction", "sent_date"],
        "filters": ["report_type", "sent_to_direction"],
        "groups": [{"title": "Reporte", "fields": ["name", "report_type", "date_from", "date_to", "prepared_by_id", "sent_to_direction", "sent_date", "direction_comments"]},
                   {"title": "Contenido", "fields": ["content"]}],
        "actions": [{"name": "action_send_direction", "label": "Entregar a Dirección", "roles": ROLE_WRITE}],
        "direction_fields": ["direction_comments"],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    # ------------------------------------------------------------------ comunes
    "followups": {
        "model": "aq.portal.followup", "label": "Seguimientos", "singular": "Seguimiento", "section": None,
        "list": ["date", "kind", "channel", "contact", "note", "result", "next_action", "next_date", "member_id"],
        "groups": [{"title": "Seguimiento", "fields": ["date", "kind", "channel", "contact", "note", "result", "next_action", "next_date", "promised_date", "member_id"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": ROLE_TEAM, "delete": ROLE_WRITE},
    },
    "google_inbox": {
        "model": "aq.google.message", "label": "Bandeja de correo y reuniones (Google)", "singular": "Mensaje", "section": "admin", "icon": "mail", "order": 5, "attachments": False,
        "domain": [("app", "=", "admin")],
        "list": ["date", "source", "subject", "sender", "category", "partner_id", "routed_by", "state", "res_label"],
        "filters": ["state", "category", "source", "routed_by", "partner_id"],
        "groups": [{"title": "Mensaje", "fields": ["subject", "sender", "recipients", "date", "source", "link", "attachment_names", "attachments_text", "labels"]},
                   {"title": "Enrutamiento", "fields": ["app", "category", "routed_by", "rule_id", "partner_id", "project_id", "ai_summary", "ai_action", "state", "res_label"]},
                   {"title": "Contenido", "fields": ["body"]}],
        "actions": [{"name": "action_to_admin_agreement", "label": "→ Pendiente / acuerdo", "roles": ROLE_WRITE}, {"name": "action_to_admin_receivable", "label": "→ Seguimiento de cobranza", "roles": ROLE_WRITE},
                    {"name": "action_to_admin_payable", "label": "→ Cuenta por pagar", "roles": ROLE_WRITE},
                    {"name": "action_reanalyze", "label": "Reanalizar (dominios / reglas / copiloto)", "roles": ROLE_WRITE}, {"name": "action_ignore", "label": "Ignorar", "roles": ROLE_WRITE}],
        "roles": {"read": ROLE_WRITE, "write": ROLE_WRITE, "create": [], "delete": ["direccion"]},
    },
    "google_rules": {
        "model": "aq.google.rule", "label": "Reglas de enrutamiento de correo", "singular": "Regla", "section": "admin", "order": 6,
        "list": ["sequence", "name", "match_from", "match_subject", "match_keywords", "target_app", "target_type", "auto_convert", "active"],
        "filters": ["target_app", "target_type", "active"],
        "groups": [{"title": "Regla", "fields": ["name", "sequence", "active", "notes"]}, {"title": "Coincidencia", "fields": ["match_from", "match_to", "match_subject", "match_keywords", "match_label"]},
                   {"title": "Destino", "fields": ["target_app", "target_type", "auto_convert", "project_id", "partner_id"]}],
        "roles": {"read": ROLE_WRITE, "write": ["direccion"], "create": ["direccion"], "delete": ["direccion"]},
    },
    "members": {
        "model": "aq.portal.member", "label": "Integrantes del equipo", "singular": "Integrante", "section": "admin", "icon": "user", "order": 20,
        "list": ["name", "email", "member_type", "position", "is_direction", "open_agreement_count", "overdue_agreement_count", "active"],
        "filters": ["member_type", "is_direction", "active"],
        "groups": [{"title": "Integrante", "fields": ["name", "email", "phone", "member_type", "position", "is_direction", "active", "employee_id", "notes"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_WRITE, "create": ROLE_WRITE, "delete": ["direccion"]},
    },
    "alerts": {
        "model": "aq.portal.alert", "label": "Alertas", "singular": "Alerta", "section": None,
        "list": ["severity", "date", "alert_type", "name", "responsible_id", "resource", "dismissed"],
        "groups": [{"title": "Alerta", "fields": ["name", "alert_type", "severity", "date", "responsible_id", "resource", "res_id", "dismissed"]}],
        "roles": {"read": ROLE_ALL, "write": ROLE_TEAM, "create": [], "delete": []},
    },
    "audit": {
        "model": "aq.portal.audit.log", "label": "Bitácora de auditoría", "singular": "Registro", "section": "admin", "icon": "list", "order": 30,
        "list": ["create_date", "user_id", "action", "resource", "res_id", "summary", "ip"],
        "filters": ["action", "user_id", "resource"],
        "groups": [{"title": "Registro", "fields": ["create_date", "user_id", "action", "resource", "res_model", "res_id", "summary", "changes", "ip"]}],
        "roles": {"read": ["direccion", "coordinacion"], "write": [], "create": [], "delete": []},
    },
}

# Modelos a los que se permite buscar por nombre (selectores many2one)
NAME_SEARCH_MODELS = {r["model"] for r in RESOURCES.values()} | {"res.partner", "res.currency", "account.move", "aq.ops.project", "aq.google.rule"}
NAME_SEARCH_DOMAINS = {"account.move": [("move_type", "in", ("out_invoice", "out_refund"))]}


def resource_for_model(model):
    if model == "res.partner":
        return "clients"
    for key, r in RESOURCES.items():
        if r["model"] == model and r.get("section") is not None:
            return key
    for key, r in RESOURCES.items():
        if r["model"] == model:
            return key
    return None

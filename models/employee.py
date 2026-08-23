from odoo import api, fields, models, _

ONBOARDING_ITEMS = [
    "Contrato firmado", "Acuerdo de confidencialidad firmado", "Aviso de privacidad entregado",
    "Documentos personales y fiscales recibidos", "Alta en nómina / esquema de pago definido",
    "Equipo entregado (responsiva firmada)", "Accesos a sistemas creados y registrados",
    "Políticas internas entregadas", "Puesto y responsabilidades documentadas",
]
OFFBOARDING_ITEMS = [
    "Entrega de pendientes y documentación del puesto", "Devolución de equipo (responsiva)",
    "Revocación de accesos a sistemas y credenciales", "Entrega de información y archivos",
    "Documentos de separación firmados", "Finiquito / liquidación o pago final documentado",
    "Baja en nómina / esquema de pago", "Recordatorio de obligaciones de confidencialidad posteriores",
]


class Employee(models.Model):
    """2.2 Administración de personal: expediente por integrante."""
    _name = "aq.portal.employee"
    _description = "Portal: expediente de integrante"
    _inherit = ["aq.portal.mixin", "mail.thread"]
    _order = "name"

    name = fields.Char(string="Nombre completo", required=True, tracking=True)
    member_id = fields.Many2one("aq.portal.member", string="Integrante del equipo")
    relation_type = fields.Selection([("empleado", "Empleado"), ("prestador", "Prestador de servicios"), ("socio", "Socio")],
                                     default="empleado", required=True, string="Tipo de relación")
    # datos personales y fiscales
    email = fields.Char(string="Correo personal")
    phone = fields.Char(string="Teléfono")
    rfc = fields.Char(string="RFC")
    curp = fields.Char(string="CURP")
    nss = fields.Char(string="NSS")
    birth_date = fields.Date(string="Fecha de nacimiento")
    address = fields.Text(string="Domicilio")
    fiscal_regime = fields.Char(string="Régimen fiscal")
    emergency_contact = fields.Char(string="Contacto de emergencia")
    bank_info = fields.Char(string="Datos bancarios (referencia, no números completos)")
    # contrato y confidencialidad
    contract_legal_item_id = fields.Many2one("aq.portal.legal.item", string="Contrato (inventario legal)")
    contract_type = fields.Char(string="Tipo de contrato")
    contract_signed = fields.Boolean(string="Contrato firmado", tracking=True)
    nda_signed = fields.Boolean(string="Confidencialidad firmada", tracking=True)
    ip_agreement_signed = fields.Boolean(string="Propiedad intelectual firmada")
    privacy_notice_delivered = fields.Boolean(string="Aviso de privacidad entregado")
    position = fields.Char(string="Puesto")
    responsibilities = fields.Text(string="Responsabilidades")
    date_joined = fields.Date(string="Fecha de ingreso", tracking=True)
    date_left = fields.Date(string="Fecha de salida", tracking=True)
    payment_scheme = fields.Selection([("nomina", "Nómina"), ("honorarios", "Honorarios"), ("asimilados", "Asimilados"),
                                       ("mixto", "Mixto"), ("socio", "Distribución de socios")], string="Esquema de pago")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    payment_amount = fields.Monetary(string="Monto acordado", currency_field="currency_id", groups="base.group_system")
    payment_period = fields.Selection([("semanal", "Semanal"), ("quincenal", "Quincenal"), ("mensual", "Mensual"),
                                       ("por_proyecto", "Por proyecto")], string="Periodicidad de pago")
    state = fields.Selection([("alta_proceso", "En proceso de incorporación"), ("activo", "Activo"),
                              ("baja_proceso", "En proceso de separación"), ("baja", "Baja")],
                             default="alta_proceso", string="Estado", tracking=True)
    required_document_ids = fields.One2many("aq.portal.employee.document", "employee_id", string="Documentos requeridos")
    asset_ids = fields.One2many("aq.portal.asset", "employee_id", string="Equipo asignado")
    access_ids = fields.One2many("aq.portal.access", "employee_id", string="Accesos a sistemas")
    event_ids = fields.One2many("aq.portal.employee.event", "employee_id", string="Vacaciones, permisos, ausencias, capacitaciones y cambios")
    checklist_ids = fields.One2many("aq.portal.checklist.item", "employee_id", string="Checklist de incorporación / separación")
    document_ids = fields.One2many("aq.portal.document", "employee_id", string="Expediente documental")
    open_access_count = fields.Integer(compute="_compute_flags", string="Accesos activos")
    has_active_access_after_exit = fields.Boolean(compute="_compute_flags", store=True, string="Accesos activos tras salida (riesgo)")
    missing_documents = fields.Integer(compute="_compute_flags", string="Documentos faltantes")
    onboarding_progress = fields.Float(compute="_compute_flags", string="Avance de incorporación (%)")
    offboarding_progress = fields.Float(compute="_compute_flags", string="Avance de separación (%)")

    @api.depends("access_ids.state", "state", "required_document_ids.received", "checklist_ids.done", "checklist_ids.kind")
    def _compute_flags(self):
        for e in self:
            active_access = e.access_ids.filtered(lambda a: a.state == "activo")
            e.open_access_count = len(active_access)
            e.has_active_access_after_exit = e.state == "baja" and bool(active_access)
            e.missing_documents = len(e.required_document_ids.filtered(lambda d: not d.received))
            on = e.checklist_ids.filtered(lambda c: c.kind == "alta")
            off = e.checklist_ids.filtered(lambda c: c.kind == "baja")
            e.onboarding_progress = (len(on.filtered("done")) / len(on) * 100.0) if on else 0.0
            e.offboarding_progress = (len(off.filtered("done")) / len(off) * 100.0) if off else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for e in recs:
            e._ensure_checklist("alta", ONBOARDING_ITEMS)
        return recs

    def _ensure_checklist(self, kind, items):
        for e in self:
            existing = e.checklist_ids.filtered(lambda c: c.kind == kind).mapped("name")
            for seq, name in enumerate(items):
                if name not in existing:
                    self.env["aq.portal.checklist.item"].create({"employee_id": e.id, "kind": kind, "name": name, "sequence": seq})

    def action_start_offboarding(self):
        for e in self:
            e._ensure_checklist("baja", OFFBOARDING_ITEMS)
            e.write({"state": "baja_proceso"})
        return True

    def action_activate(self):
        self.write({"state": "activo"})
        return True

    def action_finish_offboarding(self):
        for e in self:
            e.write({"state": "baja", "date_left": e.date_left or fields.Date.today()})
        return True


class EmployeeDocument(models.Model):
    _name = "aq.portal.employee.document"
    _description = "Portal: documento requerido de integrante"

    employee_id = fields.Many2one("aq.portal.employee", required=True, ondelete="cascade")
    name = fields.Char(required=True, string="Documento")
    received = fields.Boolean(string="Recibido")
    date_received = fields.Date(string="Fecha")
    document_id = fields.Many2one("aq.portal.document", string="Documento en expediente")
    notes = fields.Char()


class Asset(models.Model):
    _name = "aq.portal.asset"
    _description = "Portal: equipo asignado"

    employee_id = fields.Many2one("aq.portal.employee", required=True, ondelete="cascade")
    name = fields.Char(required=True, string="Equipo")
    serial = fields.Char(string="Serie / identificador")
    delivered_date = fields.Date(string="Fecha de entrega")
    returned_date = fields.Date(string="Fecha de devolución")
    responsiva_signed = fields.Boolean(string="Responsiva firmada")
    state = fields.Selection([("asignado", "Asignado"), ("devuelto", "Devuelto"), ("extraviado", "Extraviado")], default="asignado")


class Access(models.Model):
    _name = "aq.portal.access"
    _description = "Portal: acceso a sistemas"

    employee_id = fields.Many2one("aq.portal.employee", required=True, ondelete="cascade")
    system = fields.Char(required=True, string="Sistema / herramienta")
    account = fields.Char(string="Cuenta / usuario (sin contraseña)")
    granted_date = fields.Date(string="Fecha de alta")
    revoked_date = fields.Date(string="Fecha de revocación")
    owner_id = fields.Many2one("aq.portal.member", string="Quién administra el acceso")
    state = fields.Selection([("activo", "Activo"), ("revocado", "Revocado")], default="activo")


class EmployeeEvent(models.Model):
    _name = "aq.portal.employee.event"
    _description = "Portal: evento de integrante"
    _order = "date_from desc"

    employee_id = fields.Many2one("aq.portal.employee", required=True, ondelete="cascade")
    event_type = fields.Selection([("vacaciones", "Vacaciones"), ("permiso", "Permiso"), ("ausencia", "Ausencia"),
                                   ("capacitacion", "Capacitación"), ("cambio_puesto", "Cambio de puesto"),
                                   ("cambio_condiciones", "Cambio de condiciones"), ("reconocimiento", "Reconocimiento"),
                                   ("incidencia", "Incidencia")], required=True, string="Tipo")
    date_from = fields.Date(required=True, string="Desde")
    date_to = fields.Date(string="Hasta")
    description = fields.Text(string="Descripción")
    approved = fields.Boolean(string="Autorizado")
    approved_by_id = fields.Many2one("aq.portal.user", string="Autorizó", readonly=True)


class ChecklistItem(models.Model):
    """Checklist genérico (incorporación/separación de personal, requisitos de licitación, etc.)."""
    _name = "aq.portal.checklist.item"
    _description = "Portal: elemento de checklist"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, string="Actividad / requisito")
    kind = fields.Selection([("alta", "Incorporación"), ("baja", "Separación"), ("licitacion", "Requisito público"),
                             ("otro", "Otro")], default="otro", string="Tipo")
    employee_id = fields.Many2one("aq.portal.employee", ondelete="cascade")
    tender_id = fields.Many2one("aq.portal.tender", ondelete="cascade")
    done = fields.Boolean(string="Cumplido")
    date_done = fields.Date(string="Fecha")
    responsible_id = fields.Many2one("aq.portal.member", string="Responsable")
    evidence = fields.Char(string="Evidencia")

    def write(self, vals):
        if vals.get("done") and not vals.get("date_done"):
            vals["date_done"] = fields.Date.today()
        return super().write(vals)

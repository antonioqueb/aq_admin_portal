import json
from datetime import timedelta
from odoo import api, fields, models, _


class Report(models.Model):
    """Resúmenes ejecutivos (semanal / mensual / integral) y tablero 3.1 + indicadores 3.2."""
    _name = "aq.portal.report"
    _description = "Portal: reporte ejecutivo"
    _order = "date_to desc"

    name = fields.Char(required=True)
    report_type = fields.Selection([("semanal", "Resumen ejecutivo semanal"), ("mensual", "Reporte administrativo mensual"),
                                    ("integral", "Reporte administrativo integral"), ("cierre_facturacion", "Cierre de facturación"),
                                    ("conciliacion_horas", "Conciliación de horas ejecutadas, facturadas y pagadas")], required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    content = fields.Html(string="Contenido")
    data_json = fields.Text(string="Datos (JSON)")
    prepared_by_id = fields.Many2one("aq.portal.user", string="Preparado por")
    sent_to_direction = fields.Boolean(string="Entregado a Dirección")
    sent_date = fields.Date()
    direction_comments = fields.Text(string="Comentarios de Dirección")

    # ----------------------------------------------------------------- tablero
    @api.model
    def dashboard_data(self, date_from=None, date_to=None):
        env = self.env
        today = fields.Date.today()
        date_from = date_from or today.replace(day=1)
        date_to = date_to or today
        P, A, I, R, Y, H, PR, L, V, O, RK, CR, D, E = (env[m] for m in (
            "aq.portal.project", "aq.portal.agreement", "aq.portal.invoice.schedule", "aq.portal.receivable", "aq.portal.payable",
            "aq.portal.hour.bucket", "aq.portal.prospect", "aq.portal.legal.item", "aq.portal.vendor", "aq.portal.obligation",
            "aq.portal.risk", "aq.portal.change.request", "aq.portal.deliverable", "aq.portal.employee"))

        def rec(r, name, **extra):
            return dict(id=r.id, name=name, **extra)

        active_projects = P.search([("stage", "not in", ("cierre", "cancelado", "pausado"))])
        paused = P.search([("stage", "=", "pausado")])
        open_agr = A.search([("state", "not in", ("cerrado", "cancelado"))])
        overdue_agr = open_agr.filtered("is_overdue")
        critical = overdue_agr.filtered(lambda a: a.priority == "2" or a.risk_type != "ninguno" or a.escalated)
        invoices_period = I.search([("scheduled_date", ">=", date_from), ("scheduled_date", "<=", date_to)])
        issued_period = I.search([("issue_date", ">=", date_from), ("issue_date", "<=", date_to)])
        receivables = R.search([("state", "not in", ("pagada", "incobrable"))])
        overdue_recv = receivables.filtered(lambda r: r.days_overdue > 0)
        payables = Y.search([("payment_state", "in", ("programado", "vencido"))])
        buckets = H.search([("state", "=", "activa")])
        prospects = PR.search([("stage", "not in", ("ganado", "perdido", "pausado"))])
        legal = L.search([])
        paid_period = R.search([("paid_date", ">=", date_from), ("paid_date", "<=", date_to)])
        deliverables = D.search([])
        accepted = deliverables.filtered("accepted")
        upcoming_deliverables = deliverables.filtered(lambda d: not d.accepted and d.due_date and d.due_date <= today + timedelta(days=14))
        # 3.2 indicadores
        def pct(n, d):
            return round(n / d * 100.0, 1) if d else 0.0
        members = env["aq.portal.member"].search([])
        overdue_by_member = [{"member": m.name, "count": len(overdue_agr.filtered(lambda a: a.executor_id == m))} for m in members]
        overdue_by_member = [x for x in overdue_by_member if x["count"]]
        resp_times = []
        for a in A.search([("state", "=", "cerrado"), ("closed_date", ">=", date_from), ("closed_date", "<=", date_to)]):
            if a.meeting_date and a.closed_date:
                resp_times.append((a.closed_date - a.meeting_date).days)
        closed_projects = P.search([("stage", "=", "cierre")])
        closed_complete = closed_projects.filtered(lambda p: p.deliverable_ids and all(d.accepted for d in p.deliverable_ids) and p.step_progress >= 99)

        data = {
            "period": {"from": str(date_from), "to": str(date_to), "today": str(today)},
            "summary": {
                "active_projects": len(active_projects), "paused_projects": len(paused),
                "stale_projects": len(active_projects.filtered("is_stale")),
                "projects_without_next_action": len(active_projects.filtered(lambda p: not p.has_next_action)),
                "open_agreements": len(open_agr), "overdue_agreements": len(overdue_agr), "critical_pending": len(critical),
                "invoices_scheduled_period": len(invoices_period), "invoices_issued_period": len(issued_period),
                "invoiced_amount_period": sum(issued_period.mapped("amount_total")),
                "invoices_late": len(I.search([("is_late", "=", True)])), "invoices_on_hold": len(I.search([("state", "=", "detenida")])),
                "receivable_total": sum(receivables.mapped("balance")), "receivable_overdue": sum(overdue_recv.mapped("balance")),
                "receivable_count": len(receivables), "receivable_overdue_count": len(overdue_recv),
                "collected_period": sum(paid_period.mapped("amount_total")),
                "payable_total": sum(payables.mapped("amount")), "payable_overdue": sum(payables.filtered(lambda p: p.payment_state == "vencido").mapped("amount")),
                "payable_pending_authorization": len(payables.filtered(lambda p: p.authorization_state == "pendiente")),
                "hours_unbilled": sum(buckets.mapped("hours_unbilled")), "hours_unregistered": sum(buckets.mapped("hours_unregistered")),
                "hours_out_of_scope": sum(buckets.mapped("hours_out_of_scope")), "buckets_near_depletion": len(buckets.filtered(lambda b: b.near_depletion or b.over_budget)),
                "prospects_open": len(prospects), "prospects_abandoned": len(prospects.filtered("is_abandoned")),
                "legal_missing": len(legal.filtered("is_missing")), "legal_expiring": len(legal.filtered(lambda l: l.date_end and 0 <= l.days_to_expiry <= 30)),
                "legal_expired": len(legal.filtered(lambda l: l.is_expired and l.status != "terminado")),
                "renewals_30d": len(V.search([("state", "=", "activo"), ("renewal_date", "<=", today + timedelta(days=30)), ("renewal_date", ">=", today)])),
                "obligations_30d": len(O.search([("state", "=", "pendiente"), ("date", "<=", today + timedelta(days=30))])),
                "obligations_overdue": len(O.search([("state", "=", "vencida")])),
                "risks_open": len(RK.search([("state", "not in", ("cerrado", "controlado"))])),
                "risks_high": len(RK.search([("state", "not in", ("cerrado", "controlado")), ("severity", ">=", 6)])),
                "changes_pending": len(CR.search([("authorization_state", "=", "pendiente"), ("classification", "not in", ("en_alcance", "correccion"))])),
                "changes_unauthorized_executed": len(CR.search([("executed_without_authorization", "=", True)])),
                "deliverables_pending_acceptance": len(deliverables.filtered(lambda d: d.state == "entregado")),
                "admin_backlog": len(env["aq.portal.routine.run"].search([("done", "=", False), ("period_date", "<", today)])),
                "alerts_active": env["aq.portal.alert"].search_count([("active", "=", True), ("dismissed", "=", False)]),
            },
            "kpis": {
                "invoices_on_time_pct": pct(len(issued_period.filtered("issued_on_time")), len(issued_period)),
                "collected_on_time_pct": pct(len(paid_period.filtered("collected_on_time")), len(paid_period)),
                "overdue_portfolio": sum(overdue_recv.mapped("balance")),
                "overdue_portfolio_pct": pct(sum(overdue_recv.mapped("balance")), sum(receivables.mapped("balance"))),
                "avg_collection_days": round(sum(paid_period.mapped("collection_days")) / len(paid_period), 1) if paid_period else 0,
                "executed_vs_billed_pct": pct(sum(buckets.mapped("hours_billed")), sum(buckets.mapped("hours_executed"))),
                "projects_with_next_action_pct": pct(len(active_projects.filtered("has_next_action")), len(active_projects)),
                "overdue_by_member": overdue_by_member,
                "deliverables_accepted": len(accepted), "deliverables_total": len(deliverables),
                "contracts_current": len(legal.filtered(lambda l: l.exists and l.is_current)), "contracts_missing": len(legal.filtered("is_missing")),
                "prospects_without_followup": len(prospects.filtered("is_abandoned")),
                "avg_admin_response_days": round(sum(resp_times) / len(resp_times), 1) if resp_times else 0,
                "complete_closures": len(closed_complete), "closed_projects": len(closed_projects),
                "employees_missing_docs": len(E.search([("state", "=", "activo")]).filtered(lambda e: e.missing_documents or not e.contract_signed or not e.nda_signed)),
            },
            "lists": {
                "active_projects": [rec(p, p.name, client=p.partner_id.name, stage=p.stage, next_action=p.next_action, next_action_date=str(p.next_action_date or ""),
                                        responsible=p.responsible_id.name, days_without_activity=p.days_without_activity, is_stale=p.is_stale,
                                        billing_status=p.billing_status, collection_status=p.collection_status, requires_direction=p.requires_direction)
                                    for p in active_projects],
                "paused_projects": [rec(p, p.name, client=p.partner_id.name) for p in paused],
                "upcoming_deliverables": [rec(d, d.name, project=d.project_id.name, due_date=str(d.due_date or ""), state=d.state) for d in upcoming_deliverables[:20]],
                "critical_pending": [rec(a, a.name, project=a.project_id.name, executor=a.executor_id.name, due_date=str(a.due_date or ""), days_overdue=a.days_overdue,
                                         escalated=a.escalated) for a in critical[:25]],
                "invoices_period": [rec(i, i.name, client=i.partner_id.name, scheduled_date=str(i.scheduled_date), state=i.state, amount=i.amount_total) for i in invoices_period[:30]],
                "receivables": [rec(r, r.invoice_number, client=r.partner_id.name, balance=r.balance, due_date=str(r.due_date), days_overdue=r.days_overdue, risk=r.risk,
                                    promised=str(r.promised_payment_date or ""), responsible=r.responsible_id.name) for r in receivables.sorted(lambda r: -r.days_overdue)[:30]],
                "payables": [rec(y, y.name, amount=y.amount, due_date=str(y.due_date), authorization=y.authorization_state, state=y.payment_state) for y in payables[:30]],
                "unbilled_work": [rec(b, b.name, project=b.project_id.name, hours_unbilled=b.hours_unbilled, hours_executed=b.hours_executed, pct_consumed=b.pct_consumed)
                                  for b in buckets.filtered(lambda b: b.hours_unbilled > 0)[:30]],
                "hours_by_project": [{"project": p.name, "contracted": p.hours_contracted, "executed": p.hours_executed, "billed": p.hours_billed, "unbilled": p.hours_unbilled}
                                     for p in active_projects if p.hours_contracted or p.hours_executed],
                "contract_risks": [rec(l, l.name, category=l.category, status=l.status, risk=l.risk_level, date_end=str(l.date_end or ""))
                                   for l in legal.filtered(lambda l: l.is_missing or l.is_expired or l.risk_level in ("alto", "critico"))[:30]],
                "prospects": [rec(p, p.name, stage=p.stage, next_action=p.next_action, followup_date=str(p.followup_date or ""), responsible=p.sales_responsible_id.name,
                                  abandoned=p.is_abandoned) for p in prospects[:30]],
                "renewals": [rec(v, v.name, service=v.service, renewal_date=str(v.renewal_date or ""), cost=v.cost, critical=v.is_critical)
                             for v in V.search([("state", "=", "activo"), ("renewal_date", "<=", today + timedelta(days=45))])[:30]],
                "obligations": [rec(o, o.name, date=str(o.date), type=o.obligation_type, state=o.state, responsible=o.responsible_id.name)
                                for o in O.search([("state", "in", ("pendiente", "vencida")), ("date", "<=", today + timedelta(days=30))])[:30]],
                "risks": [rec(r, r.name, severity=r.severity, state=r.state, responsible=r.responsible_id.name, review_date=str(r.review_date))
                          for r in RK.search([("state", "not in", ("cerrado", "controlado"))], order="severity desc")[:20]],
                "alerts": [{"id": a.id, "name": a.name, "type": a.alert_type, "severity": a.severity, "resource": a.resource, "res_id": a.res_id}
                           for a in env["aq.portal.alert"].search([("active", "=", True), ("dismissed", "=", False)], limit=50)],
            },
        }
        return data

    # ----------------------------------------------------------------- generación
    @api.model
    def generate(self, report_type, date_from=None, date_to=None, user_id=None):
        today = fields.Date.today()
        if report_type == "semanal":
            date_to = date_to or today
            date_from = date_from or (date_to - timedelta(days=6))
        else:
            date_from = date_from or today.replace(day=1)
            date_to = date_to or today
        data = self.dashboard_data(date_from, date_to)
        s, k = data["summary"], data["kpis"]
        labels = dict(self._fields["report_type"].selection)
        html = ["<h2>%s · %s a %s</h2>" % (labels[report_type], date_from, date_to)]
        html.append("<h3>Pendientes, avances y riesgos</h3><ul>")
        html.append("<li>Proyectos activos: <b>%s</b> (sin actividad: %s · sin siguiente acción: %s · pausados: %s)</li>" % (s["active_projects"], s["stale_projects"], s["projects_without_next_action"], s["paused_projects"]))
        html.append("<li>Pendientes abiertos: <b>%s</b>, vencidos: <b>%s</b>, críticos: <b>%s</b></li>" % (s["open_agreements"], s["overdue_agreements"], s["critical_pending"]))
        html.append("<li>Facturación del periodo: programadas %s, emitidas %s por $%s (atrasadas: %s, detenidas: %s)</li>" % (s["invoices_scheduled_period"], s["invoices_issued_period"], "{:,.2f}".format(s["invoiced_amount_period"]), s["invoices_late"], s["invoices_on_hold"]))
        html.append("<li>Cuentas por cobrar: $%s (vencido $%s en %s facturas) · cobrado en el periodo $%s</li>" % ("{:,.2f}".format(s["receivable_total"]), "{:,.2f}".format(s["receivable_overdue"]), s["receivable_overdue_count"], "{:,.2f}".format(s["collected_period"])))
        html.append("<li>Cuentas por pagar: $%s (vencido $%s · sin autorizar: %s)</li>" % ("{:,.2f}".format(s["payable_total"]), "{:,.2f}".format(s["payable_overdue"]), s["payable_pending_authorization"]))
        html.append("<li>Trabajo ejecutado sin facturar: <b>%.1f h</b> · sin registro: %.1f h · fuera de alcance: %.1f h · bolsas por agotarse: %s</li>" % (s["hours_unbilled"], s["hours_unregistered"], s["hours_out_of_scope"], s["buckets_near_depletion"]))
        html.append("<li>Prospectos abiertos: %s (sin seguimiento: %s)</li>" % (s["prospects_open"], s["prospects_abandoned"]))
        html.append("<li>Contratos: faltantes %s · por vencer %s · vencidos %s · renovaciones 30 días: %s · obligaciones 30 días: %s (vencidas %s)</li>" % (s["legal_missing"], s["legal_expiring"], s["legal_expired"], s["renewals_30d"], s["obligations_30d"], s["obligations_overdue"]))
        html.append("<li>Riesgos abiertos: %s (altos: %s) · cambios sin autorizar: %s · ejecutados sin autorización: %s</li>" % (s["risks_open"], s["risks_high"], s["changes_pending"], s["changes_unauthorized_executed"]))
        html.append("</ul><h3>Indicadores</h3><ul>")
        html.append("<li>Facturas emitidas a tiempo: %s%% · cobradas en fecha: %s%% · cartera vencida: %s%% · días promedio de cobranza: %s</li>" % (k["invoices_on_time_pct"], k["collected_on_time_pct"], k["overdue_portfolio_pct"], k["avg_collection_days"]))
        html.append("<li>Ejecutado vs facturado: %s%% · proyectos con siguiente acción: %s%% · entregables aceptados: %s/%s</li>" % (k["executed_vs_billed_pct"], k["projects_with_next_action_pct"], k["deliverables_accepted"], k["deliverables_total"]))
        html.append("<li>Contratos vigentes: %s · faltantes: %s · prospectos sin seguimiento: %s · tiempo de respuesta administrativo: %s días · cierres documentales completos: %s/%s</li>" % (k["contracts_current"], k["contracts_missing"], k["prospects_without_followup"], k["avg_admin_response_days"], k["complete_closures"], k["closed_projects"]))
        if k["overdue_by_member"]:
            html.append("<li>Pendientes vencidos por responsable: %s</li>" % ", ".join("%s (%s)" % (x["member"], x["count"]) for x in k["overdue_by_member"]))
        html.append("</ul>")
        if data["lists"]["critical_pending"]:
            html.append("<h3>Pendientes críticos</h3><ul>%s</ul>" % "".join("<li>%s — %s (%s, %s d de atraso)</li>" % (x["name"], x["project"] or "-", x["executor"] or "-", x["days_overdue"]) for x in data["lists"]["critical_pending"]))
        if data["lists"]["receivables"]:
            html.append("<h3>Cartera</h3><ul>%s</ul>" % "".join("<li>%s · %s · saldo $%s · vence %s (%s d) · riesgo %s</li>" % (x["name"], x["client"], "{:,.2f}".format(x["balance"]), x["due_date"], x["days_overdue"], x["risk"]) for x in data["lists"]["receivables"][:15]))
        if report_type == "conciliacion_horas":
            html.append("<h3>Conciliación de horas</h3><table border='1' cellpadding='4'><tr><th>Proyecto</th><th>Contratadas</th><th>Ejecutadas</th><th>Facturadas</th><th>Sin facturar</th></tr>%s</table>" %
                        "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (x["project"], x["contracted"], x["executed"], x["billed"], x["unbilled"]) for x in data["lists"]["hours_by_project"]))
        if data["lists"]["risks"]:
            html.append("<h3>Riesgos que requieren decisión</h3><ul>%s</ul>" % "".join("<li>%s (severidad %s, %s)</li>" % (x["name"], x["severity"], x["responsible"] or "-") for x in data["lists"]["risks"]))
        report = self.create({
            "name": "%s %s – %s" % (labels[report_type], date_from, date_to), "report_type": report_type,
            "date_from": date_from, "date_to": date_to, "content": "".join(html), "data_json": json.dumps(data, default=str, ensure_ascii=False),
            "prepared_by_id": user_id,
        })
        return report

    def action_send_direction(self):
        for r in self:
            r.write({"sent_to_direction": True, "sent_date": fields.Date.today()})
            for u in self.env["aq.portal.user"].search([("role", "=", "direccion"), ("active", "=", True)]):
                self.env["mail.mail"].sudo().create({"subject": r.name, "email_to": u.email, "body_html": r.content}).send()
        return True

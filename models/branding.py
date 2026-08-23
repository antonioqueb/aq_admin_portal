from odoo import api, fields, models, _

BRAND = {
    "bg": "#0a0a0c", "bg2": "#111114", "bg3": "#16161a", "line": "#2a2a32", "text": "#f3f3ef", "dim": "#9a9aa3",
    "lime": "#b9e856", "purple": "#723fa0", "purple_bright": "#c89eff", "red": "#ff6b6b", "amber": "#f5c542", "blue": "#3b82f6",
}
SEVERITY_STYLE = {"4": ("CRÍTICO", BRAND["red"]), "3": ("URGENTE", BRAND["amber"]), "2": ("ATENCIÓN", BRAND["purple_bright"]), "1": ("INFO", BRAND["blue"])}


class Branding(models.AbstractModel):
    """Plantilla HTML con el branding de AlphaQueb (alphaqueb.com) para correos del portal."""
    _name = "aq.portal.branding"
    _description = "Portal: branding de correos"

    @api.model
    def base_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        return (icp.get_param("aq_admin_portal.base_url") or icp.get_param("web.base.url") or "").rstrip("/")

    @api.model
    def portal_url(self, resource=None, res_id=None):
        url = self.env["aq.portal.user"]._portal_base_url()
        if resource and res_id:
            url += "/r/%s/%s" % (resource, res_id)
        return url

    @api.model
    def wrap(self, title, body_html, cta_label=None, cta_url=None, subtitle=None, preheader=None):
        b = BRAND
        logo = self.base_url() + "/aq_admin_portal/static/description/logo.png"
        cta = ""
        if cta_label and cta_url:
            cta = ("<table role='presentation' cellpadding='0' cellspacing='0' style='margin:24px 0 8px'><tr><td style='background:%s;border-radius:6px'>"
                   "<a href='%s' style='display:inline-block;padding:12px 22px;color:#0a0a0c;font-weight:700;text-decoration:none;"
                   "font-family:Oxanium,Roboto,Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase;font-size:13px'>%s</a></td></tr></table>"
                   % (b["lime"], cta_url, cta_label))
        return """
<div style="background:%(bg)s;padding:32px 12px;font-family:Roboto,Arial,Helvetica,sans-serif;color:%(text)s">
  <span style="display:none;max-height:0;overflow:hidden">%(pre)s</span>
  <table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;background:%(bg2)s;border:1px solid %(line)s;border-radius:12px;overflow:hidden">
    <tr><td style="padding:22px 28px;border-bottom:1px solid %(line)s;background:%(bg)s">
      <img src="%(logo)s" alt="AlphaQueb" height="44" style="height:44px;display:block"/>
    </td></tr>
    <tr><td style="padding:26px 28px 6px">
      <div style="font-family:Oxanium,Roboto,Arial,sans-serif;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:%(lime)s">Portal de control administrativo</div>
      <h1 style="margin:6px 0 4px;font-family:'Bebas Neue',Impact,'Arial Narrow',Arial,sans-serif;font-weight:400;font-size:30px;letter-spacing:.03em;color:%(text)s;line-height:1.1">%(title)s</h1>
      %(subtitle)s
    </td></tr>
    <tr><td style="padding:6px 28px 26px;font-size:14px;line-height:1.55;color:%(text)s">%(body)s%(cta)s</td></tr>
    <tr><td style="padding:16px 28px;border-top:1px solid %(line)s;background:%(bg)s;font-family:Oxanium,Roboto,Arial,sans-serif;font-size:11px;color:%(dim)s;letter-spacing:.04em">
      ALPHAQUEB CONSULTING &nbsp;·&nbsp; <a href="https://alphaqueb.com" style="color:%(lime)s;text-decoration:none">alphaqueb.com</a> &nbsp;·&nbsp; Mensaje automático del portal administrativo
    </td></tr>
  </table>
</div>""" % dict(b, logo=logo, title=title, body=body_html, cta=cta, pre=preheader or "",
                 subtitle=("<div style='color:%s;font-size:13px'>%s</div>" % (b["dim"], subtitle)) if subtitle else "")

    @api.model
    def alert_rows(self, alerts):
        """Tabla de alertas agrupada por severidad, con enlace al registro en el portal."""
        b = BRAND
        out = []
        for sev in ("4", "3", "2", "1"):
            group = alerts.filtered(lambda a: a.severity == sev)
            if not group:
                continue
            label, color = SEVERITY_STYLE[sev]
            out.append("<div style='margin:18px 0 8px;font-family:Oxanium,Roboto,Arial,sans-serif;font-size:11px;letter-spacing:.14em;color:%s'>"
                       "<span style='display:inline-block;width:8px;height:8px;border-radius:50%%;background:%s;margin-right:8px'></span>%s · %d</div>" % (color, color, label, len(group)))
            out.append("<table role='presentation' width='100%%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'>")
            for a in group:
                link = self.portal_url(a.resource, a.res_id) if a.resource and a.res_id else self.portal_url() + "/alerts"
                kind = dict(a._fields["alert_type"].selection).get(a.alert_type, a.alert_type)
                resp = (" &nbsp;·&nbsp; " + a.responsible_id.name) if a.responsible_id else ""
                out.append("<tr><td style='padding:10px 12px;border-left:3px solid %s;background:%s;border-bottom:1px solid %s'>"
                           "<a href='%s' style='color:%s;text-decoration:none;font-weight:500'>%s</a>"
                           "<div style='font-family:Oxanium,Roboto,Arial,sans-serif;font-size:11px;color:%s;margin-top:3px;letter-spacing:.03em'>%s%s</div></td></tr>"
                           % (color, b["bg3"], b["bg2"], link, b["text"], a.name, b["dim"], kind, resp))
            out.append("</table>")
        return "".join(out)

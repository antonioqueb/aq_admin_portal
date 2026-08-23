# -*- coding: utf-8 -*-
import os

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_path


class PortalSpa(http.Controller):
    """Sirve la aplicación React compilada (bundle independiente de los assets de Odoo)."""

    def _index(self):
        path = os.path.join(get_module_path("aq_admin_portal"), "static", "spa", "index.html")
        if not os.path.exists(path):
            return request.make_response(
                "<h1>Portal no compilado</h1><p>Ejecute <code>npm install && npm run build</code> dentro de "
                "<code>aq_admin_portal/spa</code> para generar <code>static/spa</code>.</p>",
                headers=[("Content-Type", "text/html; charset=utf-8")], status=503)
        with open(path, "rb") as f:
            html = f.read()
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"),
                                                    ("Cache-Control", "no-cache"),
                                                    ("X-Frame-Options", "SAMEORIGIN")])

    @http.route(["/admin-portal", "/admin-portal/", "/admin-portal/<path:path>"], type="http", auth="public", csrf=False)
    def spa(self, path=None, **kw):
        return self._index()

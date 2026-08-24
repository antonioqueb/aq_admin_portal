# -*- coding: utf-8 -*-
"""Constructor de documentos formales de Alphaqueb en Google Docs.

Sistema de diseño (derivado del branding: alphaqueb.com + plantilla membretada A4 con logo y pie de contacto):
  · Tipografías  : Bebas Neue (título), Oxanium (etiquetas y encabezados de sección), Roboto (cuerpo)
  · Color tinta  : #1F2024   · Apagado: #5F6470   · Línea: #E4E7EC
  · Marca        : Morado #723FA0 (jerarquía) · Lima #B9E856 (acentos, filas de encabezado)
Recibe una especificación de bloques y devuelve el documento maquetado sobre la plantilla membretada.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

INK = {"red": 0.121, "green": 0.125, "blue": 0.141}          # #1F2024
MUTED = {"red": 0.373, "green": 0.392, "blue": 0.451}        # #5F6470
PURPLE = {"red": 0.447, "green": 0.247, "blue": 0.627}       # #723FA0
LIME = {"red": 0.725, "green": 0.910, "blue": 0.337}         # #B9E856
LIME_DARK = {"red": 0.361, "green": 0.510, "blue": 0.106}    # #5C821B (lima legible sobre blanco)
LINE = {"red": 0.894, "green": 0.906, "blue": 0.925}         # #E4E7EC
WHITE = {"red": 1, "green": 1, "blue": 1}
SOFT = {"red": 0.973, "green": 0.976, "blue": 0.965}         # #F8F9F6

F_TITLE, F_LABEL, F_BODY = "Bebas Neue", "Oxanium", "Roboto"


def _rgb(c):
    return {"color": {"rgbColor": c}}


def u16(s):
    return len((s or "").encode("utf-16-le")) // 2


class DocBuilder(models.AbstractModel):
    """Uso:  self.env['aq.doc.builder'].build(acc, template_id, folder_id, nombre, bloques)"""
    _name = "aq.doc.builder"
    _description = "Alphaqueb: constructor de documentos con marca"

    # ---- estilos por tipo de bloque -------------------------------------------------
    STYLES = {
        "eyebrow": dict(font=F_LABEL, size=9, color=LIME_DARK, bold=True, spacing=1.0, space_below=2, upper=True, tracking=True),
        "title": dict(font=F_TITLE, size=30, color=INK, spacing=1.0, space_below=2),
        "subtitle": dict(font=F_LABEL, size=11, color=MUTED, space_below=10),
        "rule": dict(font=F_BODY, size=2, color=WHITE, border=LIME, space_below=14),
        "h1": dict(font=F_LABEL, size=13, color=PURPLE, bold=True, space_above=18, space_below=6, upper=True, tracking=True, border=LINE),
        "h2": dict(font=F_LABEL, size=11, color=INK, bold=True, space_above=12, space_below=4),
        "p": dict(font=F_BODY, size=10.5, color=INK, space_below=6, justify=True, line=1.25),
        "quote": dict(font=F_BODY, size=10.5, color=MUTED, italic=True, space_below=8, indent=18),
        "bullet": dict(font=F_BODY, size=10.5, color=INK, space_below=2, line=1.2),
        "note": dict(font=F_LABEL, size=8.5, color=MUTED, space_above=16),
        "spacer": dict(font=F_BODY, size=6, color=WHITE),
    }

    # ---- API principal --------------------------------------------------------------
    @api.model
    def build(self, acc, template_id, folder_id, name, blocks):
        """Copia la plantilla membretada e inserta los bloques con el diseño de marca. Devuelve (id, url)."""
        copy = acc.post("https://www.googleapis.com/drive/v3/files/%s/copy" % template_id,
                        {"name": name[:180], "parents": [folder_id] if folder_id else []})
        did = copy["id"]
        text_blocks = [b for b in blocks if b.get("type") != "table"]
        # 1) texto completo (las tablas se representan con un marcador propio)
        lines, meta = [], []
        for b in blocks:
            if b.get("type") == "table":
                marker = "⦙TBL%d⦙" % len(meta)
                lines.append(marker)
                meta.append({"kind": "table", "spec": b, "text": marker})
            else:
                t = (b.get("text") or "").replace("\r", "").replace("\n", " ").strip()
                if self.STYLES.get(b.get("type"), {}).get("upper"):
                    t = t.upper()
                lines.append(t)
                meta.append({"kind": b.get("type", "p"), "text": t, "spec": b})
        full = "".join(l + "\n" for l in lines)
        reqs = [{"insertText": {"location": {"index": 1}, "text": full}}]
        idx = 1
        bullets = []
        for m in meta:
            start = idx
            end = idx + u16(m["text"]) + 1
            m["start"], m["end"] = start, end
            if m["kind"] != "table":
                reqs += self._style_requests(m["kind"], start, end, m["text"], m["spec"])
                if m["kind"] == "bullet":
                    bullets.append((start, end))
            idx = end
        acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": reqs})
        # 2) viñetas nativas (agrupadas y en orden inverso para no mover índices)
        groups = []
        for s, e in bullets:
            if groups and groups[-1][1] == s:
                groups[-1] = (groups[-1][0], e)
            else:
                groups.append((s, e))
        if groups:
            acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": [
                {"createParagraphBullets": {"range": {"startIndex": s, "endIndex": e}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}} for s, e in reversed(groups)]})
        # 3) tablas (de la última a la primera)
        for m in reversed([m for m in meta if m["kind"] == "table"]):
            try:
                self._insert_table(acc, did, m["text"], m["spec"])
            except Exception as e:  # noqa
                _logger.warning("Tabla en documento: %s", e)
        return did, "https://docs.google.com/document/d/%s/edit" % did

    # ---- estilos --------------------------------------------------------------------
    def _style_requests(self, kind, start, end, text, spec=None):
        st = dict(self.STYLES.get(kind, self.STYLES["p"]))
        if (spec or {}).get("color"):
            st["color"] = spec["color"]
        out = []
        pstyle, fields_ = {"namedStyleType": "NORMAL_TEXT"}, ["namedStyleType"]
        if st.get("space_above"):
            pstyle["spaceAbove"] = {"magnitude": st["space_above"], "unit": "PT"}; fields_.append("spaceAbove")
        if st.get("space_below") is not None:
            pstyle["spaceBelow"] = {"magnitude": st.get("space_below", 0), "unit": "PT"}; fields_.append("spaceBelow")
        if st.get("justify"):
            pstyle["alignment"] = "JUSTIFIED"; fields_.append("alignment")
        if st.get("line"):
            pstyle["lineSpacing"] = st["line"] * 100; fields_.append("lineSpacing")
        if st.get("indent"):
            pstyle["indentStart"] = {"magnitude": st["indent"], "unit": "PT"}; fields_.append("indentStart")
        if st.get("border"):
            pstyle["borderBottom"] = {"color": _rgb(st["border"]), "width": {"magnitude": 1.5 if kind == "rule" else 0.75, "unit": "PT"},
                                      "padding": {"magnitude": 4 if kind != "rule" else 0, "unit": "PT"}, "dashStyle": "SOLID"}
            fields_.append("borderBottom")
        out.append({"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": end}, "paragraphStyle": pstyle, "fields": ",".join(fields_)}})
        if u16(text):
            tstyle = {"weightedFontFamily": {"fontFamily": st["font"]}, "fontSize": {"magnitude": st["size"], "unit": "PT"},
                      "foregroundColor": _rgb(st["color"]), "bold": bool(st.get("bold")), "italic": bool(st.get("italic"))}
            tfields = "weightedFontFamily,fontSize,foregroundColor,bold,italic"
            out.append({"updateTextStyle": {"range": {"startIndex": start, "endIndex": end - 1}, "textStyle": tstyle, "fields": tfields}})
        return out

    # ---- tablas ---------------------------------------------------------------------
    def _insert_table(self, acc, did, marker, spec):
        rows = spec.get("rows") or []
        if not rows:
            return
        cols = max(len(r) for r in rows)
        doc = acc.get("https://docs.googleapis.com/v1/documents/%s" % did)
        loc = self._find_marker(doc, marker)
        if loc is None:
            return
        start, end = loc
        acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": [
            {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end - 1}}},
            {"insertTable": {"rows": len(rows), "columns": cols, "location": {"index": start}}},
        ]})
        doc = acc.get("https://docs.googleapis.com/v1/documents/%s" % did)
        tbl, tbl_start = self._find_table(doc, start)
        if not tbl:
            return
        cells = []
        for ri, row in enumerate(tbl.get("tableRows", [])):
            for ci, cell in enumerate(row.get("tableCells", [])):
                txt = ""
                if ri < len(rows) and ci < len(rows[ri]):
                    txt = str(rows[ri][ci] or "").replace("\r", "").strip()
                cells.append((cell["content"][0]["startIndex"], txt))
        reqs = [{"insertText": {"location": {"index": i}, "text": t}} for i, t in reversed(cells) if t]
        if reqs:
            acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": reqs})
        # estilo: fila de encabezado + tipografía + bordes suaves
        doc = acc.get("https://docs.googleapis.com/v1/documents/%s" % did)
        tbl, tbl_start = self._find_table(doc, start)
        style_reqs = []
        header = spec.get("header", True)
        for ri, row in enumerate(tbl.get("tableRows", [])):
            for ci, cell in enumerate(row.get("tableCells", [])):
                s = cell["content"][0]["startIndex"]
                e = cell["content"][-1]["endIndex"] - 1
                is_head = header and ri == 0
                is_label = (not header) and ci == 0
                if e > s:
                    style_reqs.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": e}, "textStyle": {
                        "weightedFontFamily": {"fontFamily": F_LABEL if (is_head or is_label) else F_BODY},
                        "fontSize": {"magnitude": 9 if is_head else 9.5, "unit": "PT"},
                        "foregroundColor": _rgb(INK if is_head else (MUTED if is_label else INK)),
                        "bold": bool(is_head or is_label)}, "fields": "weightedFontFamily,fontSize,foregroundColor,bold"}})
                style_reqs.append({"updateParagraphStyle": {"range": {"startIndex": s, "endIndex": e + 1}, "paragraphStyle": {
                    "spaceAbove": {"magnitude": 3, "unit": "PT"}, "spaceBelow": {"magnitude": 3, "unit": "PT"}}, "fields": "spaceAbove,spaceBelow"}})
        style_reqs.append({"updateTableCellStyle": {"tableStartLocation": {"index": tbl_start}, "tableCellStyle": {
            "backgroundColor": _rgb(SOFT), "paddingLeft": {"magnitude": 6, "unit": "PT"}, "paddingRight": {"magnitude": 6, "unit": "PT"},
            "borderTop": {"color": _rgb(LINE), "width": {"magnitude": 0.5, "unit": "PT"}, "dashStyle": "SOLID"},
            "borderBottom": {"color": _rgb(LINE), "width": {"magnitude": 0.5, "unit": "PT"}, "dashStyle": "SOLID"},
            "borderLeft": {"color": _rgb(WHITE), "width": {"magnitude": 0.5, "unit": "PT"}, "dashStyle": "SOLID"},
            "borderRight": {"color": _rgb(WHITE), "width": {"magnitude": 0.5, "unit": "PT"}, "dashStyle": "SOLID"}},
            "fields": "backgroundColor,paddingLeft,paddingRight,borderTop,borderBottom,borderLeft,borderRight"}})
        if header:
            style_reqs.append({"updateTableCellStyle": {"tableRange": {"tableCellLocation": {"tableStartLocation": {"index": tbl_start}, "rowIndex": 0, "columnIndex": 0},
                                                                      "rowSpan": 1, "columnSpan": cols},
                                                        "tableCellStyle": {"backgroundColor": _rgb(LIME)}, "fields": "backgroundColor"}})
        if style_reqs:
            acc.post("https://docs.googleapis.com/v1/documents/%s:batchUpdate" % did, {"requests": style_reqs})

    def _find_marker(self, doc, marker):
        body = (doc.get("tabs", [{}])[0].get("documentTab", {}).get("body") if doc.get("tabs") else doc.get("body")) or {}
        for el in body.get("content", []):
            p = el.get("paragraph")
            if not p:
                continue
            txt = "".join(r.get("textRun", {}).get("content", "") for r in p.get("elements", []))
            if marker in txt:
                return el["startIndex"], el["endIndex"]
        return None

    def _find_table(self, doc, near_index):
        body = (doc.get("tabs", [{}])[0].get("documentTab", {}).get("body") if doc.get("tabs") else doc.get("body")) or {}
        best = None
        for el in body.get("content", []):
            if "table" in el and el["startIndex"] >= near_index - 2:
                if best is None or el["startIndex"] < best[1]:
                    best = (el["table"], el["startIndex"])
        return best if best else (None, None)

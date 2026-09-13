# -*- coding: utf-8 -*-
"""aq.portal.legal.item: el campo 'exists' pisaba el método BaseModel.exists() del ORM; se renombra a 'document_exists'."""


def migrate(cr, version):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'aq_portal_legal_item' AND column_name = 'exists'")
    if cr.fetchone():
        cr.execute('ALTER TABLE aq_portal_legal_item RENAME COLUMN "exists" TO document_exists')
    cr.execute("UPDATE ir_model_fields SET name = 'document_exists' WHERE model = 'aq.portal.legal.item' AND name = 'exists'")

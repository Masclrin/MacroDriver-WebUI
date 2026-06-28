# -*- coding: utf-8 -*-
from __future__ import annotations

from bridge.metadata import PARAM_DOCS, PARAM_SCHEMA, SECTION_META

_LITE_SECTIONS = {"executor", "interception", "webui"}

LITE_SECTION_META = {k: v for k, v in SECTION_META.items() if k in _LITE_SECTIONS}

LITE_PARAM_SCHEMA = {k: v for k, v in PARAM_SCHEMA.items() if k in _LITE_SECTIONS}

LITE_PARAM_DOCS = {k: v for k, v in PARAM_DOCS.items() if k.split(".", 1)[0] in _LITE_SECTIONS}

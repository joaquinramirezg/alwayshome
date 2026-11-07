"""Independent insurance gap analysis API; no property assessment or extraction."""
from .report import analyze_insurance_gap
from .adapter import adapt_inputs, map_rebuild_need

__all__ = ['analyze_insurance_gap', 'adapt_inputs', 'map_rebuild_need']

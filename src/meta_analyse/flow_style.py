"""Pure presentation rules for trader dashboard; never promote provisional data to verified."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

def flow_cell_style(column:int,value:str,quality:str):
    """Return (foreground, background) CSS hex colors for a table cell."""
    neutral=("#DCE6F4","#101C2D")
    if column==5:
        return {
            "PROVISIONAL":("#78C7E0","#163044"),
            "STALE":("#F0BC70","#44321D"),
            "UNVERIFIED":("#F09090","#40232D"),
        }.get(quality,neutral)
    if quality!="PROVISIONAL":
        return neutral
    if column not in (3,7):
        return neutral
    try:
        number=Decimal(value)
        if not number.is_finite():
            return neutral
    except (InvalidOperation,ValueError,TypeError):
        return neutral
    if number>0:
        return ("#68D7B0","#17372F")
    if number<0:
        return ("#F38B91","#3D222B")
    return neutral

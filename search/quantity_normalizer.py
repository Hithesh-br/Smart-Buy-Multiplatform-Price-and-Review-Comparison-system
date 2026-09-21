"""
search/quantity_normalizer.py
=============================
SmartBuy Quantity & Unit Price Normalization Engine.

Normalizes:
- Multi-pack and fractional weights/volumes:
  "500g x 2" -> total_quantity="1kg", pack_count=2, unit="kg"
  "250ml x 4" -> total_quantity="1L", pack_count=4, unit="L"
  "Pack of 6" -> pack_count=6
- Calculates meaningful unit price:
  e.g. ₹ per 100g, ₹ per 100ml, ₹ per kg, ₹ per item
- Standardizes electronics variants:
  RAM, Storage, screen size, battery, wattage.
"""

import re
from typing import Dict, Any, Optional, Tuple


def normalize_quantity_and_pack(
    title: str,
    weight_val: Optional[str] = None,
    volume_val: Optional[str] = None,
    pack_val: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Computes total normalized quantity, pack count, standard unit, and display text.
    Handles '500g x 2', '250ml * 4', 'Pack of 3', '1.5 kg', etc.
    """
    text = f"{title or ''} {weight_val or ''} {volume_val or ''}".lower()

    pack_count = 1
    if pack_val is not None:
        try:
            p_int = int(re.sub(r'[^\d]', '', str(pack_val)))
            if p_int > 0:
                pack_count = p_int
        except Exception:
            pass

    # Detect multiplier pattern e.g. "500g x 2", "500 g * 2", "2 x 500g"
    mult_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|gm|ml|l|litre|liter)s?\s*(?:x|\*)\s*(\d+)', text)
    if mult_match:
        base_num = float(mult_match.group(1))
        unit = mult_match.group(2).lower()
        multiplier = int(mult_match.group(3))
        pack_count = multiplier
        total_num = base_num * multiplier
        return _format_total(total_num, unit, pack_count)

    mult_match_rev = re.search(r'(\d+)\s*(?:x|\*)\s*(\d+(?:\.\d+)?)\s*(kg|g|gm|ml|l|litre|liter)s?', text)
    if mult_match_rev:
        multiplier = int(mult_match_rev.group(1))
        base_num = float(mult_match_rev.group(2))
        unit = mult_match_rev.group(3).lower()
        pack_count = multiplier
        total_num = base_num * multiplier
        return _format_total(total_num, unit, pack_count)

    # Check "Pack of N"
    pack_match = re.search(r'\b(?:pack\s*of\s*(\d+)|(\d+)\s*pack)\b', text)
    if pack_match:
        pack_count = int(pack_match.group(1) or pack_match.group(2))

    # Single weight / volume match
    single_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|gm|ml|l|litre|liter)s?\b', text)
    if single_match:
        base_num = float(single_match.group(1))
        unit = single_match.group(2).lower()
        total_num = base_num * pack_count if pack_count > 1 and "pack" in text else base_num
        return _format_total(total_num, unit, pack_count)

    return {
        "total_quantity": None,
        "pack_count": pack_count,
        "unit": None,
        "quantity_in_grams": None,
        "quantity_in_ml": None,
        "display_quantity": f"Pack of {pack_count}" if pack_count > 1 else None
    }


def _format_total(total_num: float, unit: str, pack_count: int) -> Dict[str, Any]:
    """Format total normalized quantity into standard metric units."""
    unit = unit.lower()
    grams = None
    mls = None

    if unit in ('g', 'gm'):
        grams = total_num
        if grams >= 1000:
            total_qty = f"{grams / 1000:g} kg"
            disp_unit = "kg"
        else:
            total_qty = f"{grams:g} g"
            disp_unit = "g"
    elif unit == 'kg':
        grams = total_num * 1000
        total_qty = f"{total_num:g} kg"
        disp_unit = "kg"
    elif unit in ('ml', 'milli'):
        mls = total_num
        if mls >= 1000:
            total_qty = f"{mls / 1000:g} L"
            disp_unit = "L"
        else:
            total_qty = f"{mls:g} ml"
            disp_unit = "ml"
    elif unit in ('l', 'litre', 'liter'):
        mls = total_num * 1000
        total_qty = f"{total_num:g} L"
        disp_unit = "L"
    else:
        total_qty = f"{total_num:g} {unit}"
        disp_unit = unit

    return {
        "total_quantity": total_qty,
        "pack_count": pack_count,
        "unit": disp_unit,
        "quantity_in_grams": grams,
        "quantity_in_ml": mls,
        "display_quantity": total_qty
    }


def calculate_standard_unit_price(price_num: Optional[int], qty_info: Dict[str, Any]) -> Optional[str]:
    """
    Computes comparable unit price (e.g. ₹ per 100g, ₹ per 100ml, ₹ per kg, or ₹ per item).
    """
    if not price_num or price_num <= 0 or not qty_info:
        return None

    grams = qty_info.get("quantity_in_grams")
    if grams and grams > 0:
        per_100g = round((price_num / grams) * 100, 1)
        return f"₹{per_100g:g} / 100g"

    mls = qty_info.get("quantity_in_ml")
    if mls and mls > 0:
        per_100ml = round((price_num / mls) * 100, 1)
        return f"₹{per_100ml:g} / 100ml"

    pack_count = qty_info.get("pack_count", 1)
    if pack_count and pack_count > 1:
        per_item = round(price_num / pack_count, 1)
        return f"₹{per_item:g} / item"

    return None


def normalize_electronics_specs(title: str, specs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Normalizes electronics specifications: RAM, Storage, screen size, battery, processor.
    """
    specs = specs or {}
    text = f"{title or ''} " + " ".join(f"{k} {v}" for k, v in specs.items())
    t_lower = text.lower()

    norm: Dict[str, Any] = {}

    # Storage
    st_match = re.search(r'\b(32|64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b', t_lower)
    if st_match:
        norm["storage"] = st_match.group(0).upper().replace(" ", "")

    # RAM
    ram_match = re.search(r'\b(2|3|4|6|8|12|16|32|64)\s*gb\s*(?:ram|lpddr\d?)?\b', t_lower)
    if ram_match:
        norm["ram"] = f"{ram_match.group(1)}GB"

    # Battery
    bat_match = re.search(r'\b(\d{4,5})\s*mah\b', t_lower)
    if bat_match:
        norm["battery"] = f"{bat_match.group(1)} mAh"

    # Screen Size
    screen_match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|"|-inch|cm)\b', t_lower)
    if screen_match:
        norm["screen_size"] = f"{screen_match.group(1)} inch"

    # Wattage / Power
    power_match = re.search(r'\b(\d{1,3})\s*(?:w|watt|watts)\b', t_lower)
    if power_match:
        norm["wattage"] = f"{power_match.group(1)}W"

    return norm

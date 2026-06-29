"""
Aqualine Site Assessment — Calculation Utilities
สูตรคำนวณอุปกรณ์รางน้ำฝน Aqualine Lindab จากคู่มือจริง
"""

import math

# ============================================================
# ค่าคงที่จากคู่มือ Aqualine Lindab
# ============================================================

GUTTER_LENGTH_STD   = 5.0   # ราง (R) 1 ท่อน = 5 ม.
DOWNPIPE_LENGTH_STD = 5.0   # ท่อลง (SROR) 1 ท่อน = 5 ม.

# ตะขอ: คู่มือระบุ 90–120 ซม. ค่าเฉลี่ย 100 ซม.
HOOK_SPACING_FLAT  = 1.0    # เชิงตรง  (KFK) — ทุก 100 ซม.
HOOK_SPACING_BEVEL = 1.0    # เชิงเอียง (SSK) — ทุก 100 ซม.

DOWNPIPE_ALLOWANCE        = 1.0   # ซม. ต่อด้าน (X1→X2)
DOWNPIPE_BRACKET_PER_5M   = 2     # ตะขอท่อลง (SSVH) ต่อ 5 เมตร
DOWNPIPE_ELBOW_PER_POINT  = 2     # ท่องอ (BK) ต่อ 1 จุดท่อลง
MIN_LADDER_CLEARANCE       = 180   # ซม.


# ============================================================
# 1. พื้นที่หลังคา
# ============================================================

def calc_roof_area(shape: str, dims: dict) -> float:
    if shape == "rectangle":
        return dims.get("width", 0) * dims.get("depth", 0)
    elif shape == "l_shape":
        return dims.get("w1", 0) * dims.get("d1", 0) + dims.get("w2", 0) * dims.get("d2", 0)
    elif shape == "hip":
        factor = 1 / math.cos(math.radians(dims.get("pitch_deg", 30)))
        return dims.get("width", 0) * dims.get("depth", 0) * factor
    else:
        return dims.get("area", 0)


def min_drain_points(area_sqm: float) -> int:
    """ทุก 200 ตร.ม. ต้องมี 1 จุดท่อลง (คู่มือ Aqualine)"""
    return max(1, math.ceil(area_sqm / 200))


# ============================================================
# 2. รางน้ำฝน (R)
# ============================================================

def calc_gutter(length_m: float) -> dict:
    """
    คำนวณจำนวนราง + ข้อต่อราง (RSK)
    - ราง 1 ท่อน = 5 ม.
    - ข้อต่อ RSK = จำนวนจุดต่อระหว่างท่อน = pieces - 1
    """
    pieces       = math.ceil(length_m / GUTTER_LENGTH_STD)
    joints       = max(0, pieces - 1)   # RSK: จุดเชื่อมต่อระหว่างท่อนราง
    total_length = pieces * GUTTER_LENGTH_STD
    excess       = round(total_length - length_m, 2)
    return {
        "length_input": length_m,
        "pieces":        pieces,
        "joints":        joints,    # RSK
        "total_length":  total_length,
        "excess_m":      excess,
    }


def calc_hooks(length_m: float, fascia_type: str = "flat") -> int:
    """
    ตะขอ KFK (เชิงตรง) หรือ SSK (เชิงเอียง)
    คู่มือ: ทุก 90–120 ซม. → ใช้ 100 ซม. เป็นค่ามาตรฐาน
    นับปลายสองข้างด้วย → +1
    """
    spacing = HOOK_SPACING_FLAT if fascia_type == "flat" else HOOK_SPACING_BEVEL
    return math.ceil(length_m / spacing) + 1


# ============================================================
# 3. ท่อลง (SROR)
# ============================================================

def calc_downpipe(wall_height_m: float, x1_cm: float, drain_points: int = 1) -> dict:
    """
    x1_cm  = ระยะจากปลายหลังคาถึงผนัง
    x2_cm  = ความยาวท่อที่ใช้จริง (หักค่าเผื่อเข้าท่องอด้านละ 1 ซม.)
    BK     = ท่องอ 2 ตัว/จุด (บนและล่าง)
    SOK    = ท่อเชื่อมราง 1 ตัว/จุด
    SSVH   = ตะขอยึดท่อ 2 ตัว/5ม.
    """
    x2_cm              = max(0, x1_cm - (DOWNPIPE_ALLOWANCE * 2))
    pieces_per_point   = math.ceil(wall_height_m / DOWNPIPE_LENGTH_STD)
    brackets_per_point = pieces_per_point * DOWNPIPE_BRACKET_PER_5M
    elbows_per_point   = DOWNPIPE_ELBOW_PER_POINT   # BK

    return {
        "x1_cm":              x1_cm,
        "x2_cm":              x2_cm,
        "wall_height_m":      wall_height_m,
        "pieces_per_point":   pieces_per_point,
        "total_pieces":       pieces_per_point   * drain_points,   # SROR
        "brackets_per_point": brackets_per_point,
        "total_brackets":     brackets_per_point * drain_points,   # SSVH
        "elbows_per_point":   elbows_per_point,
        "total_elbows":       elbows_per_point   * drain_points,   # BK
        "total_sok":          drain_points,                         # SOK (1 ต่อจุด)
        "drain_points":       drain_points,
    }


# ============================================================
# 4. มุม / ข้องอ
# ============================================================

def calc_corners(outer: int, inner: int) -> dict:
    """
    RVY = รางหักมุมนอก (ตาเข้ส้น)
    RVI = รางหักมุมใน  (ตาเข้ราว)
    """
    return {
        "outer_corners": outer,   # RVY
        "inner_corners": inner,   # RVI
        "total_corners": outer + inner,
    }


# ============================================================
# 5. บันได
# ============================================================

def check_ladder(clearance_cm: float) -> dict:
    ok = clearance_cm >= MIN_LADDER_CLEARANCE
    return {
        "clearance_cm":    clearance_cm,
        "min_required_cm": MIN_LADDER_CLEARANCE,
        "ok":              ok,
        "warning":         "" if ok else
            f"⚠️ ระยะ {clearance_cm} ซม. น้อยกว่าขั้นต่ำ {MIN_LADDER_CLEARANCE} ซม.",
    }


# ============================================================
# 6. BOQ รวม
# ============================================================

def calc_full_boq(sides: list, corners: dict, downpipe_info: dict,
                  fascia_type: str = "flat") -> dict:
    total_gutter_pieces = 0
    total_joints        = 0   # RSK
    total_hooks         = 0   # KFK หรือ SSK
    total_length        = 0.0
    side_details        = []

    for side in sides:
        g = calc_gutter(side["length_m"])
        h = calc_hooks(side["length_m"], fascia_type)
        total_gutter_pieces += g["pieces"]
        total_joints        += g["joints"]
        total_hooks         += h
        total_length        += side["length_m"]
        side_details.append({**side, **g, "hooks": h})

    c = calc_corners(corners.get("outer", 0), corners.get("inner", 0))

    # ฝาปิดปลายราง (RGT): ปลายเปิดทุกด้าน = sides*2 ลบด้วยที่มุมปิดแทน
    end_caps = max(0, (len(sides) * 2) - c["total_corners"])

    return {
        "summary": {
            # ── ราง ──
            "total_length_m":    round(total_length, 2),
            "gutter_pieces":     total_gutter_pieces,   # R
            "gutter_joints":     total_joints,           # RSK
            "hooks":             total_hooks,            # KFK / SSK
            "end_caps":          end_caps,               # RGT
            "outer_corners_RVY": c["outer_corners"],    # RVY
            "inner_corners_RVI": c["inner_corners"],    # RVI
            # ── ท่อลง ──
            "drain_points":      downpipe_info.get("drain_points",    0),
            "downpipe_pieces":   downpipe_info.get("total_pieces",    0),   # SROR
            "downpipe_brackets": downpipe_info.get("total_brackets",  0),   # SSVH
            "downpipe_elbows":   downpipe_info.get("total_elbows",    0),   # BK
            "downpipe_sok":      downpipe_info.get("total_sok",       0),   # SOK
        },
        "side_details": side_details,
        "corners":      c,
        "downpipe":     downpipe_info,
    }


# ============================================================
# 7. คำนวณราคา BOQ
# ============================================================

def calc_boq_cost(boq: dict, prices: dict) -> dict:
    """
    คูณ quantity × ราคาต่อหน่วยจาก prices dict
    คืน dict รายการพร้อม subtotal และ grand_total
    """
    s = boq["summary"]

    # map: (label, summary_key, price_key, unit)
    items = [
        ("ราง R",               "total_length_m",    "R",    "ม."),
        ("ข้อต่อ RSK",          "gutter_joints",     "RSK",  "ชิ้น"),
        ("ตะขอ KFK/SSK",        "hooks",             "KFK",  "ตัว"),
        ("ฝาปิดปลาย RGT",       "end_caps",          "RGT",  "ชิ้น"),
        ("มุมนอก RVY",          "outer_corners_RVY", "RVY",  "ชิ้น"),
        ("มุมใน RVI",           "inner_corners_RVI", "RVI",  "ชิ้น"),
        ("ท่อเชื่อมราง SOK",    "downpipe_sok",      "SOK",  "ชิ้น"),
        ("ท่อลง SROR",          "downpipe_pieces",   "SROR", "ท่อน"),
        ("ท่องอ BK",            "downpipe_elbows",   "BK",   "ชิ้น"),
        ("ตะขอท่อลง SSVH",      "downpipe_brackets", "SSVH", "ตัว"),
    ]

    rows       = []
    subtotal   = 0.0

    for label, qty_key, price_key, unit in items:
        qty   = s.get(qty_key, 0)
        price = prices.get(price_key, 0)
        total = qty * price
        subtotal += total
        rows.append({
            "label": label,
            "qty":   qty,
            "unit":  unit,
            "price": price,
            "total": total,
        })

    # ค่าแรง
    labor_price = prices.get("labor", 0)
    labor_total = s.get("total_length_m", 0) * labor_price
    subtotal   += labor_total
    rows.append({
        "label": "ค่าแรงติดตั้ง",
        "qty":   s.get("total_length_m", 0),
        "unit":  "ม.",
        "price": labor_price,
        "total": labor_total,
    })

    vat         = subtotal * 0.07
    grand_total = subtotal + vat

    return {
        "rows":        rows,
        "subtotal":    subtotal,
        "vat":         vat,
        "grand_total": grand_total,
    }


# ============================================================
# 8. Format text
# ============================================================

def format_boq_text(boq: dict) -> str:
    s = boq["summary"]
    lines = [
        "=== สรุป BOQ รางน้ำฝน Aqualine Lindab ===",
        "",
        f"ความยาวรางรวม        : {s['total_length_m']} ม.",
        f"ราง R (5 ม./ท่อน)    : {s['gutter_pieces']} ท่อน",
        f"ข้อต่อราง RSK         : {s['gutter_joints']} ชิ้น",
        f"ตะขอ KFK/SSK          : {s['hooks']} ตัว",
        f"ฝาปิดปลาย RGT         : {s['end_caps']} ชิ้น",
        f"มุมนอก RVY            : {s['outer_corners_RVY']} ชิ้น",
        f"มุมใน RVI             : {s['inner_corners_RVI']} ชิ้น",
        "",
        f"จุดท่อลง              : {s['drain_points']} จุด",
        f"ท่อเชื่อมราง SOK      : {s['downpipe_sok']} ชิ้น",
        f"ท่อลง SROR (5 ม./ท่อน): {s['downpipe_pieces']} ท่อน",
        f"ท่องอ BK              : {s['downpipe_elbows']} ชิ้น",
        f"ตะขอท่อลง SSVH        : {s['downpipe_brackets']} ตัว",
        "",
        "==========================================",
    ]
    return "\n".join(lines)

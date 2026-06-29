"""
หน้า 3 — ประเมินหน้างาน (8 จุดหลัก)
[v2] เพิ่ม: upload รูปหน้างาน + Export PDF 4 หน้า (ผ่าน assess_pdf_export.py)
"""
import streamlit as st
from pages.page_login import touch_session
import math
from utils.state import get_project, save_field
from utils.calculations import (
    calc_roof_area, min_drain_points,
    calc_gutter, calc_hooks,
    calc_downpipe, calc_corners,
    check_ladder, calc_full_boq,
)

# ── import PDF/Photo module (วางไฟล์ assess_pdf_export.py ใน root หรือ utils/) ──
try:
    from assess_pdf_export import render_photo_uploader, render_assess_pdf_button
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

# ── map ค่าเก่าที่อาจหลงเหลืออยู่ใน session ──────────────────────────
_SHAPE_COMPAT = {
    "rectangle": "gable",
    "l_shape":   "complex",
    "custom":    "shed",
    "hip":       "hip",
    "gable":     "gable",
    "shed":      "shed",
    "complex":   "complex",
    "lean_to":   "shed",
    "butterfly": "shed",
}

def _safe_shape(p: dict) -> str:
    raw = p.get("roof_shape", "gable")
    return _SHAPE_COMPAT.get(raw, "gable")

# =====================================================================
#  ROOF MODEL REGISTRY
# =====================================================================
ROOF_MODELS = {
    "gable":   {"title": "หลังคาทรงจั่ว"},
    "hip":     {"title": "หลังคาทรงปั้นหยา"},
    "shed":    {"title": "หลังคาทรงเพิงหมาแหงน"},
    "complex": {"title": "หลังคาทรงปั้นหยาตัวแอล"},
}

# =====================================================================
#  SVG TOP-VIEW  — ภาพมุมบนตามภาพอ้างอิง
# =====================================================================
def _svg_topview(shape_key: str, selected: bool = False) -> str:
    border_col = "#2563EB" if selected else "#CBD5E1"
    bw = "2.5" if selected else "1.5"

    THICK  = "#1E293B"; SW_THICK = "2.0"
    THIN   = "#475569"; SW_THIN  = "0.9"
    DASH   = "#64748B"; SW_DASH  = "1.0"
    FILL_R = "#E8EEF4"
    FONT   = "font-family='Arial,sans-serif'"
    FS     = "10"

    def sq_lbl(x, y, txt):
        return (
            f"<rect x='{x-8}' y='{y-9}' width='16' height='13' "
            f"fill='white' stroke='{THICK}' stroke-width='0.7'/>"
            f"<text x='{x}' y='{y}' text-anchor='middle' dominant-baseline='central' "
            f"{FONT} font-size='{FS}' fill='{THICK}' font-weight='600'>{txt}</text>"
        )

    def circ_lbl(x, y, txt):
        return (
            f"<circle cx='{x}' cy='{y}' r='8' fill='white' stroke='{THICK}' stroke-width='0.7'/>"
            f"<text x='{x}' y='{y}' text-anchor='middle' dominant-baseline='central' "
            f"{FONT} font-size='{FS}' fill='{THICK}' font-weight='600'>{txt}</text>"
        )

    def legend(vw):
        lx = vw - 118
        return (
            f"<rect x='{lx}' y='4' width='11' height='9' fill='{FILL_R}' stroke='{THICK}' stroke-width='0.6'/>"
            f"<text x='{lx+14}' y='12' {FONT} font-size='8' fill='{THICK}'>พื้นที่ส่วนหลังคา</text>"
            f"<circle cx='{lx}' cy='23' r='5' fill='white' stroke='{THICK}' stroke-width='0.6'/>"
            f"<text x='{lx+8}' y='27' {FONT} font-size='8' fill='{THICK}'>ระยะความยาว</text>"
        )

    if shape_key == "gable":
        W, H = 240, 145
        ox, oy, ow, oh = 18, 36, 204, 92
        ix, iy, iw, ih = 40, 44, 160, 76
        midy = iy + ih // 2
        body = f"""
  <text x='6' y='13' {FONT} font-size='9' fill='{THICK}' font-weight='600'>ภาพมุมบน</text>
  {legend(W)}
  <rect x='{ox}' y='{oy}' width='{ow}' height='{oh}' fill='none' stroke='{DASH}' stroke-width='{SW_DASH}' stroke-dasharray='6,4'/>
  <rect x='{ix}' y='{iy}' width='{iw}' height='{ih}' fill='{FILL_R}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <line x1='{ix}' y1='{midy}' x2='{ix+iw}' y2='{midy}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <line x1='{ix}' y1='{iy}' x2='{ox}' y2='{oy}' stroke='{THIN}' stroke-width='{SW_THIN}'/>
  <line x1='{ix}' y1='{iy+ih}' x2='{ox}' y2='{oy+oh}' stroke='{THIN}' stroke-width='{SW_THIN}'/>
  <line x1='{ix+iw}' y1='{iy}' x2='{ox+ow}' y2='{oy}' stroke='{THIN}' stroke-width='{SW_THIN}'/>
  <line x1='{ix+iw}' y1='{iy+ih}' x2='{ox+ow}' y2='{oy+oh}' stroke='{THIN}' stroke-width='{SW_THIN}'/>
  {circ_lbl(ix+iw//2, oy+8, 'C')}
  {circ_lbl(ix+iw//2, oy+oh+10, 'A')}
  {circ_lbl(ox+8, midy, 'B')}
  {circ_lbl(ox+ow+10, midy, 'D')}
  {sq_lbl(ix+iw//4, iy+ih//4, 'B')}
  {sq_lbl(ix+iw*3//4, iy+ih//4, 'B')}
  {sq_lbl(ix+iw//2, midy+5, 'E')}
  {sq_lbl(ix+iw//4, iy+ih*3//4, 'A')}
  {sq_lbl(ix+iw*3//4, iy+ih*3//4, 'A')}"""

    elif shape_key == "hip":
        W, H = 240, 145
        ox, oy, ow, oh = 16, 36, 208, 90
        ix, iy, iw, ih = 36, 44, 168, 74
        midy = iy + ih // 2
        hx1, hx2 = ix + 46, ix + iw - 46
        body = f"""
  <text x='6' y='13' {FONT} font-size='9' fill='{THICK}' font-weight='600'>ภาพมุมบน</text>
  {legend(W)}
  <rect x='{ox}' y='{oy}' width='{ow}' height='{oh}' fill='none' stroke='{DASH}' stroke-width='{SW_DASH}' stroke-dasharray='6,4'/>
  <rect x='{ix}' y='{iy}' width='{iw}' height='{ih}' fill='{FILL_R}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <line x1='{ix}'    y1='{iy}'    x2='{hx1}' y2='{midy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='5,3'/>
  <line x1='{ix+iw}' y1='{iy}'   x2='{hx2}' y2='{midy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='5,3'/>
  <line x1='{ix}'    y1='{iy+ih}' x2='{hx1}' y2='{midy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='5,3'/>
  <line x1='{ix+iw}' y1='{iy+ih}' x2='{hx2}' y2='{midy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='5,3'/>
  <line x1='{hx1}' y1='{midy}' x2='{hx2}' y2='{midy}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  {circ_lbl(ix+iw//2, oy+8, 'D')}
  {circ_lbl(ix+iw//2, oy+oh+10, 'A')}
  {circ_lbl(ox+8, midy, 'B')}
  {circ_lbl(ox+ow+10, midy, 'C')}
  {sq_lbl(hx1-14, iy+ih//4, 'B')}
  {sq_lbl(hx2+14, iy+ih//4, 'D')}
  {sq_lbl((hx1+hx2)//2, midy+5, 'E')}
  {sq_lbl(hx1-14, iy+ih*3//4, 'A')}
  {sq_lbl(hx2+14, iy+ih*3//4, 'A')}"""

    elif shape_key == "shed":
        W, H = 240, 145
        ox, oy, ow, oh = 16, 36, 208, 90
        ix, iy, iw, ih = 36, 44, 168, 74
        body = f"""
  <text x='6' y='13' {FONT} font-size='9' fill='{THICK}' font-weight='600'>ภาพมุมบน</text>
  {legend(W)}
  <rect x='{ox}' y='{oy}' width='{ow}' height='{oh}' fill='none' stroke='{DASH}' stroke-width='{SW_DASH}' stroke-dasharray='6,4'/>
  <rect x='{ix}' y='{iy}' width='{iw}' height='{ih}' fill='{FILL_R}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  {circ_lbl(ix+iw//2, oy+8, 'D')}
  {circ_lbl(ix+iw//2, oy+oh+10, 'A')}
  {circ_lbl(ox+8, iy+ih//2, 'B')}
  {circ_lbl(ox+ow+10, iy+ih//2, 'C')}
  {sq_lbl(ix+iw//2, iy+ih//2, 'A')}"""

    elif shape_key == "complex":
        W, H = 255, 180
        ux, uy, uw, uh = 10, 32, 200, 72
        umidy = uy + uh // 2
        uhx1, uhx2 = ux + 42, ux + uw - 42
        lx, ly, lw, lh = 10, 104, 108, 58
        lmidy = ly + lh // 2
        lhx1, lhx2 = lx + 26, lx + lw - 26
        body = f"""
  <text x='6' y='13' {FONT} font-size='9' fill='{THICK}' font-weight='600'>ภาพมุมบน</text>
  {legend(W)}
  <polyline points='{ux},{uy} {ux+uw},{uy} {ux+uw},{ly} {lx+lw},{ly} {lx+lw},{ly+lh} {lx},{ly+lh} {lx},{uy} {ux},{uy}'
    fill='none' stroke='{DASH}' stroke-width='{SW_DASH}' stroke-dasharray='6,4' stroke-linejoin='round'/>
  <rect x='{ux}' y='{uy}' width='{uw}' height='{uh}' fill='{FILL_R}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <line x1='{ux}'    y1='{uy}'    x2='{uhx1}' y2='{umidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{ux+uw}' y1='{uy}'   x2='{uhx2}' y2='{umidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{ux}'    y1='{uy+uh}' x2='{uhx1}' y2='{umidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{ux+uw}' y1='{uy+uh}' x2='{uhx2}' y2='{umidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{uhx1}' y1='{umidy}' x2='{uhx2}' y2='{umidy}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <rect x='{lx}' y='{ly}' width='{lw}' height='{lh}' fill='{FILL_R}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  <line x1='{lx}'    y1='{ly}'    x2='{lhx1}' y2='{lmidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{lx+lw}' y1='{ly}'   x2='{lhx2}' y2='{lmidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{lx}'    y1='{ly+lh}' x2='{lhx1}' y2='{lmidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{lx+lw}' y1='{ly+lh}' x2='{lhx2}' y2='{lmidy}' stroke='{THIN}' stroke-width='{SW_THIN}' stroke-dasharray='4,3'/>
  <line x1='{lhx1}' y1='{lmidy}' x2='{lhx2}' y2='{lmidy}' stroke='{THICK}' stroke-width='{SW_THICK}'/>
  {circ_lbl(ux+uw//2, uy-9, 'E')}
  {circ_lbl(lx+lw//2, ly+lh+11, 'A')}
  {circ_lbl(lx-10, umidy, 'B')}
  {circ_lbl(lx-10, lmidy, 'B')}
  {circ_lbl(ux+uw+11, umidy, 'F')}
  {circ_lbl(lx+lw+11, lmidy, 'F')}
  {sq_lbl(uhx1-16, uy+uh//4, 'B')}
  {sq_lbl(uhx2+16, uy+uh//4, 'C')}
  {sq_lbl((uhx1+uhx2)//2, umidy+5, 'E')}
  {sq_lbl(ux+uw-14, ly+6, 'D')}
  {sq_lbl(lhx1-14, ly+lh//4, 'B')}
  {sq_lbl(lx+lw//2, ly+lh//4, 'D')}
  {sq_lbl(lhx2+14, ly+lh//4, 'C')}
  {sq_lbl((lhx1+lhx2)//2, lmidy+5, 'A')}"""
    else:
        return ""

    return (
        f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' "
        f"style='border:{bw}px solid {border_col}; border-radius:8px; "
        f"background:white; width:100%;'>{body}\n</svg>"
    )


# =====================================================================
#  SELECTOR WIDGET
# =====================================================================
def render_visual_roof_selector(current_shape: str, tab_key: str = "") -> str:
    cols = st.columns(4)
    selected_shape = current_shape
    for i, (shape_key, info) in enumerate(ROOF_MODELS.items()):
        is_sel = (current_shape == shape_key)
        with cols[i]:
            top_svg = _svg_topview(shape_key, selected=is_sel)
            title_c = "#1D4ED8" if is_sel else "#334155"
            st.markdown(
                f"""<div style='padding:4px 0 2px 0;'>
                    {top_svg}
                    <div style='font-size:0.78rem; font-weight:600; color:{title_c};
                                text-align:center; margin-top:5px;'>{info['title']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            btn_clicked = st.button(
                "✔ เลือกแล้ว" if is_sel else "เลือก",
                key=f"rbtn_{shape_key}_{tab_key}",
                use_container_width=True,
                type="primary" if is_sel else "secondary",
            )
            if btn_clicked:
                selected_shape = shape_key
    return selected_shape


def _roof_selector_compact(p: dict, tab_key: str):
    cs = _safe_shape(p)
    top_svg = _svg_topview(cs, selected=False)
    st.markdown(
        f"""<div style='border:1.5px solid #BFDBFE; border-radius:8px;
                    background:#F8FAFF; padding:10px; margin-bottom:12px;'>
            <div style='font-size:0.78rem; font-weight:600; color:#1D4ED8; margin-bottom:6px;'>
                ภาพอ้างอิง — {ROOF_MODELS[cs]['title']}
            </div>
            {top_svg}
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("🏠 เปลี่ยนรูปแบบหลังคา", expanded=False):
        upd = render_visual_roof_selector(cs, tab_key=tab_key)
        if upd != cs:
            p["roof_shape"] = upd
            save_field("roof_shape", upd)
            st.rerun()


# =====================================================================
#  MAIN
# =====================================================================
def show():
    touch_session()
    p = get_project()
    if p is None:
        st.warning("⚠️ กรุณาเลือกหรือสร้างโปรเจกต์ก่อนครับ")
        if st.button("ไปหน้าโปรเจกต์"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    if p.get("roof_shape") not in ROOF_MODELS:
        p["roof_shape"] = _SHAPE_COMPAT.get(p.get("roof_shape", ""), "gable")

    st.markdown(f"## 📋 ประเมินหน้างาน — {p['name']}")
    st.markdown("กรอกข้อมูล 8 จุดหลัก แอปจะคำนวณจำนวนอุปกรณ์ให้อัตโนมัติ")

    tabs = st.tabs([
        "1️⃣ พื้นที่หลังคา",
        "2️⃣ ความยาวปลายหลังคา",
        "3️⃣ เชิงชาย",
        "4️⃣ มุมหลังคา",
        "5️⃣ ระยะปลายคา-ผนัง",
        "6️⃣ ความสูงผนัง",
        "7️⃣ จุดระบายน้ำ",
        "8️⃣ ระยะบันได",
    ])

    # ── TAB 1 ────────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown('<div class="section-header">จุดที่ 1 — พื้นที่หลังคา</div>', unsafe_allow_html=True)
        st.markdown("เลือกรูปแบบหลังคา แล้วกรอกขนาด")

        cs  = _safe_shape(p)
        upd = render_visual_roof_selector(cs, tab_key="tab1")
        if upd != cs:
            p["roof_shape"] = upd
            save_field("roof_shape", upd)
            st.rerun()
        roof_shape = _safe_shape(p)

        dims = p.get("roof_dims", {})
        area = 0.0
        st.markdown("---")

        if roof_shape in ("gable", "hip"):
            c1, c2, c3 = st.columns(3)
            dims["width"]     = c1.number_input("กว้าง (ม.)",       0.0, value=float(dims.get("width", 10.0)), step=0.5)
            dims["depth"]     = c2.number_input("ลึก / ยาว (ม.)",   0.0, value=float(dims.get("depth", 8.0)),  step=0.5)
            dims["pitch_deg"] = c3.number_input("ความชันหลังคา (°)", 7, max_value=45, value=int(dims.get("pitch_deg", 30)))
            area = calc_roof_area("hip" if roof_shape == "hip" else "rectangle", dims)
        elif roof_shape == "complex":
            st.markdown("**ส่วน A — หลังคาส่วนใหญ่**")
            c1, c2 = st.columns(2)
            dims["w1"] = c1.number_input("กว้าง A (ม.)", 0.0, value=float(dims.get("w1", 10.0)), step=0.5)
            dims["d1"] = c2.number_input("ลึก A (ม.)",   0.0, value=float(dims.get("d1", 6.0)),  step=0.5)
            st.markdown("**ส่วน B — ส่วนต่อเติม**")
            c3, c4 = st.columns(2)
            dims["w2"] = c3.number_input("กว้าง B (ม.)", 0.0, value=float(dims.get("w2", 5.0)),  step=0.5)
            dims["d2"] = c4.number_input("ลึก B (ม.)",   0.0, value=float(dims.get("d2", 4.0)),  step=0.5)
            area = calc_roof_area("l_shape", dims)
        else:
            dims["area"] = st.number_input("พื้นที่หลังคา (ตร.ม.)", 0.0, value=float(dims.get("area", 0.0)), step=1.0)
            area = dims["area"]

        p["roof_dims"] = dims
        min_pts = min_drain_points(area)
        col1, col2 = st.columns(2)
        col1.metric("พื้นที่หลังคา",    f"{area:.1f} ตร.ม.")
        col2.metric("จุดท่อลงขั้นต่ำ", f"{min_pts} จุด", help="ทุก 50 ตร.ม. = 1 จุด")
        if area > 0:
            st.markdown(
                f'<div class="ok-box">✅ หลังคา {area:.1f} ตร.ม. — ต้องการท่อลงอย่างน้อย <b>{min_pts} จุด</b></div>',
                unsafe_allow_html=True,
            )

    # ── TAB 2 ────────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown('<div class="section-header">จุดที่ 2 — ความยาวปลายหลังคา (แต่ละด้าน)</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab2")
        st.markdown("ใส่ความยาวปลายหลังคาแต่ละด้านที่ต้องติดรางน้ำฝน")

        sides_data = p.get("sides", [])
        if not sides_data:
            sides_data = [{"label": l, "length_m": 0.0} for l in ["A", "B", "C", "D"]]
        fascia_type = p.get("fascia_type", "flat")
        updated_sides = []
        total_len = total_pieces = total_joints = total_hooks = 0

        for i, side in enumerate(sides_data):
            with st.expander(f"ด้าน {side['label']}", expanded=True):
                c1, c2 = st.columns([2, 3])
                length = c1.number_input(
                    f"ความยาวด้าน {side['label']} (ม.)",
                    0.0, value=float(side.get("length_m", 0.0)), step=0.5,
                    key=f"side_{i}_len",
                )
                side["length_m"] = length
                updated_sides.append(side)
                if length <= 0:
                    c2.warning("⚠️ กรุณากรอกความยาวด้านให้มากกว่า 0")
                if length > 0:
                    g = calc_gutter(length)
                    h = calc_hooks(length, fascia_type)
                    total_len    += length
                    total_pieces += g["pieces"]
                    total_joints += g["joints"]
                    total_hooks  += h
                    c2.markdown(
                        f"""<div class="metric-card"><div class="label">คำนวณอัตโนมัติ</div>
                        <div style="display:flex;gap:16px;margin-top:4px">
                          <div><div class="label">ราง</div><div class="value" style="font-size:1.1rem">{g['pieces']}</div><div class="unit">ท่อน</div></div>
                          <div><div class="label">ข้อต่อ</div><div class="value" style="font-size:1.1rem">{g['joints']}</div><div class="unit">ชิ้น</div></div>
                          <div><div class="label">ตะขอ</div><div class="value" style="font-size:1.1rem">{h}</div><div class="unit">ตัว</div></div>
                        </div></div>""",
                        unsafe_allow_html=True,
                    )

        p["sides"] = updated_sides
        if total_len > 0:
            st.markdown("---")
            st.markdown("**รวมทุกด้าน**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ความยาวรวม", f"{total_len:.1f} ม.")
            c2.metric("ราง",        f"{total_pieces} ท่อน")
            c3.metric("ข้อต่อ",     f"{total_joints} ชิ้น")
            c4.metric("ตะขอ",       f"{total_hooks} ตัว")
        if st.button("➕ เพิ่มด้าน"):
            sides_data.append({"label": chr(ord("A") + len(sides_data)), "length_m": 0.0})
            p["sides"] = sides_data
            st.rerun()

    # ── TAB 3 ────────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown('<div class="section-header">จุดที่ 3 — ลักษณะเชิงชาย (Fascia)</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab3")
        fascia_type = st.radio(
            "ประเภทเชิงชาย",
            ["flat", "bevel"],
            format_func=lambda x: "เชิงตรง (Flat) — ตะขอทุก 50 ซม." if x == "flat" else "เชิงเอียง (Bevel) — ตะขอทุก 60 ซม.",
            horizontal=True,
            index=0 if p.get("fascia_type", "flat") == "flat" else 1,
        )
        p["fascia_type"] = fascia_type
        pitch_deg = st.slider(
            "ความชันเชิงชาย (°)",
            7, 45, int(p.get("pitch_deg", 15)),
            disabled=(fascia_type == "flat"),
        )
        p["pitch_deg"] = pitch_deg
        spacing = 50 if fascia_type == "flat" else 60
        st.markdown(
            f'<div class="ok-box">✅ ระยะห่างตะขอ: <b>{spacing} ซม.</b> ({fascia_type})</div>',
            unsafe_allow_html=True,
        )
        if fascia_type == "bevel":
            st.info(f"เชิงเอียง {pitch_deg}° — ใช้ตะขอแบบปรับองศาได้ตามคู่มือ Aqualine")

    # ── TAB 4 ────────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown('<div class="section-header">จุดที่ 4 — มุมหลังคา (Corners)</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab4")
        corners = p.get("corners", {"outer": 0, "inner": 0})
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**มุมนอก (RVY)**")
            outer = st.number_input("จำนวนมุมนอก", 0, value=int(corners.get("outer", 0)), step=1)
        with col2:
            st.markdown("**มุมใน (RVI)**")
            inner = st.number_input("จำนวนมุมใน", 0, value=int(corners.get("inner", 0)), step=1)
        p["corners"] = {"outer": outer, "inner": inner}
        st.markdown(
            f'<div class="ok-box">✅ มุมรวม: <b>{outer+inner} จุด</b> (RVY {outer} + RVI {inner})</div>',
            unsafe_allow_html=True,
        )

    # ── TAB 5 ────────────────────────────────────────────────────────
    with tabs[4]:
        st.markdown('<div class="section-header">จุดที่ 5 — ระยะปลายหลังคากับผนัง (X1)</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab5")
        st.markdown("X1 = ระยะจากปลายชายคาถึงผนัง (ซม.) | X2 = ความยาวท่อแนวราบ เผื่อ 1 ซม./ด้าน")
        x1 = st.number_input("X1 — ระยะปลายชายคาถึงผนัง (ซม.)", 0.0, value=float(p.get("x1_cm", 0.0)), step=1.0)
        p["x1_cm"] = x1
        x2 = max(0, x1 - 2)
        col1, col2 = st.columns(2)
        col1.metric("X1 (วัดได้)",     f"{x1:.0f} ซม.")
        col2.metric("X2 (ความยาวท่อ)", f"{x2:.0f} ซม.", delta="-2 ซม. (เผื่อ)")
        if x1 > 0:
            st.markdown(
                f'<div class="ok-box">✅ ตัดท่อแนวราบยาว <b>{x2:.0f} ซม.</b> ต่อจุด</div>',
                unsafe_allow_html=True,
            )

    # ── TAB 6 ────────────────────────────────────────────────────────
    with tabs[5]:
        st.markdown('<div class="section-header">จุดที่ 6 — ความสูงผนัง</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab6")
        wall_h = st.number_input("ความสูงผนัง (เมตร)", 0.0, value=float(p.get("wall_height_m", 3.0)), step=0.5)
        p["wall_height_m"] = wall_h
        if wall_h <= 0:
            st.warning("⚠️ กรุณากรอกความสูงผนังให้มากกว่า 0 เมตร")
        drain_pts = int(p.get("drain_points", 1))
        dp_info = calc_downpipe(wall_h, float(p.get("x1_cm", 0.0)), drain_pts)
        col1, col2, col3 = st.columns(3)
        col1.metric("ความสูงผนัง",   f"{wall_h:.1f} ม.")
        col2.metric("ท่อลง/จุด",     f"{dp_info['pieces_per_point']} ท่อน")
        col3.metric("ตะขอท่อลง/จุด", f"{dp_info['brackets_per_point']} ตัว")
        st.markdown(
            f'<div class="ok-box">✅ ท่อลงทั้งหมด <b>{dp_info["total_pieces"]} ท่อน</b> | '
            f'ตะขอยึดท่อ <b>{dp_info["total_brackets"]} ตัว</b> ({drain_pts} จุด)</div>',
            unsafe_allow_html=True,
        )

    # ── TAB 7 ────────────────────────────────────────────────────────
    with tabs[6]:
        st.markdown('<div class="section-header">จุดที่ 7 — ตำแหน่งและประเภทท่อลง</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab7")
        drain_type = st.selectbox(
            "ประเภทท่อลง",
            ["round", "square"],
            format_func=lambda x: "ท่อกลม" if x == "round" else "ท่อเหลี่ยม",
            index=0 if p.get("drain_type", "round") == "round" else 1,
        )
        p["drain_type"] = drain_type
        drain_pts = st.number_input("จำนวนจุดท่อลง", 1, value=int(p.get("drain_points", 1)), step=1)
        p["drain_points"] = drain_pts
        _rshape = _safe_shape(p)
        _ck = "hip" if _rshape == "hip" else ("l_shape" if _rshape == "complex" else "rectangle")
        area = calc_roof_area(_ck, p.get("roof_dims", {}))
        min_pts = min_drain_points(area) if area > 0 else 1
        if drain_pts < min_pts:
            st.markdown(
                f'<div class="warn-box">⚠️ จำนวนจุดระบายน้ำ {drain_pts} จุด น้อยกว่าขั้นต่ำ <b>{min_pts} จุด</b></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="ok-box">✅ {drain_pts} จุดท่อลง — เพียงพอสำหรับพื้นที่ {area:.0f} ตร.ม.</div>',
                unsafe_allow_html=True,
            )
        st.markdown("---")
        st.info("📌 ตำแหน่งท่อลงแนะนำให้อยู่ใกล้บ่อพักน้ำ หรือตำแหน่งที่ระบายออกได้สะดวก")

    # ── TAB 8 ────────────────────────────────────────────────────────
    with tabs[7]:
        st.markdown('<div class="section-header">จุดที่ 8 — ระยะวางบันได</div>', unsafe_allow_html=True)
        _roof_selector_compact(p, "tab8")
        st.markdown("ระยะห่างจากท่อลงถึงตำแหน่งวางบันไดต้องไม่น้อยกว่า **180 ซม.**")
        ladder_cm = st.number_input(
            "ระยะวางบันไดจากท่อลง (ซม.)",
            0.0, value=float(p.get("ladder_clearance_cm", 180.0)), step=10.0,
        )
        p["ladder_clearance_cm"] = ladder_cm
        chk = check_ladder(ladder_cm)
        if chk["ok"]:
            st.markdown(
                f'<div class="ok-box">✅ ระยะบันได <b>{ladder_cm:.0f} ซม.</b> — ผ่านเกณฑ์ (≥ 180 ซม.)</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<div class="warn-box">{chk["warning"]}</div>', unsafe_allow_html=True)

    # ── BOQ ──────────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 คำนวณ BOQ อัตโนมัติ", use_container_width=True, type="primary"):
            sides  = [s for s in p.get("sides", []) if s.get("length_m", 0) > 0]
            wall_h = p.get("wall_height_m", 3.0)
            errors = []
            if not sides:
                errors.append("❌ กรุณากรอกความยาวด้านอย่างน้อย 1 ด้าน (แท็บ จุดที่ 2)")
            if wall_h <= 0:
                errors.append("❌ กรุณากรอกความสูงผนัง (แท็บ จุดที่ 6)")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                corners   = p.get("corners", {"outer": 0, "inner": 0})
                x1        = p.get("x1_cm", 0.0)
                drain_pts = int(p.get("drain_points", 1))
                fascia    = p.get("fascia_type", "flat")
                dp_info   = calc_downpipe(wall_h, x1, drain_pts)
                boq       = calc_full_boq(sides, corners, dp_info, fascia)
                p["boq"]  = boq
                st.success("✅ คำนวณ BOQ เรียบร้อย!")
    with col2:
        if st.button("📦 ไปดู BOQ", use_container_width=True):
            st.session_state.current_page = "boq"
            st.rerun()

    # ── PHOTO UPLOAD + PDF EXPORT ─────────────────────────────────────
    st.markdown("---")
    if _PDF_OK:
        # Section: อัปโหลดรูปหน้างาน
        render_photo_uploader(p)

        st.markdown("---")
        # Section: Export PDF
        st.markdown("### 🖨️ Export ใบประเมินหน้างาน PDF")
        st.caption("PDF 4 หน้า A4 — ข้อมูลลูกค้า + BOQ + แบบแปลน + รูปหน้างาน")
        render_assess_pdf_button(p)
    else:
        st.warning(
            "⚠️ ไม่พบ `assess_pdf_export.py` — วางไฟล์นั้นไว้ใน root หรือ `utils/` "
            "แล้ว restart แอปเพื่อใช้งาน Export PDF"
        )

"""
หน้า 4 — BOQ / ใบเสนอราคา (Quotation Form)
[Architecture: 1:1 Template EX-01 Clone + Dynamic Pricing + Native Blueprint Engine]
"""
import streamlit as st
from pages.page_login import touch_session
from utils.ui_notify import toast, save_with_feedback
import datetime
import json
import streamlit.components.v1 as components
from utils.state import get_project, save_project
from utils.calculations import calc_full_boq, calc_downpipe, calc_boq_cost
from utils.storage import save_photos, load_photos, delete_photo, save_photo_bytes

# นำเข้าราคามาตรฐานเผื่อกรณี User ยังไม่เคยเข้าไปตั้งค่า
try:
    from pages.page_prices import DEFAULT_PRICES
except ImportError:
    DEFAULT_PRICES = {} # Fallback

# ==========================================
# 1. CORE LOGIC: DYNAMIC PRICING ENGINE
# ==========================================
def _get_active_price(item_code: str, is_premium: bool) -> float:
    """ดึงราคาแบบ Dynamic ตามการเลือกสี (Std vs Premium)"""
    tier = "premium" if is_premium else "std"
    
    # 1. เช็คว่ามี Custom Price ที่ User เคยเซฟไว้หรือไม่
    custom_prices = st.session_state.get("custom_prices", {}).get(tier, {})
    if item_code in custom_prices:
        return float(custom_prices[item_code])
    
    # 2. ถ้าไม่มี ให้ดึงจาก DEFAULT_PRICES
    if item_code in DEFAULT_PRICES:
        info = DEFAULT_PRICES[item_code]
        if info.get("color_only"):
            return float(info["price_std"])
        return float(info["price_std"] if tier == "std" else info["price_premium"])
    
    return 0.0 # ถ้าหาไม่เจอจริงๆ

def export_blueprint_images(project: dict, svg_items: list) -> tuple:
    """
    Render รายการ SVG (แปลนรางน้ำ + หน้าตัดท่อลง) เป็น PNG แล้วเซฟลง photos/ ของโปรเจกต์
    svg_items = [(filename.png, svg_string), ...]
    คืน (saved_names: list, error: str)  — ถ้า Playwright ไม่พร้อมจะคืน ([], เหตุผล) โดยไม่ทำให้ flow ส่งพัง
    ใช้ temp HTTP server + Google Fonts (Sarabun) เพื่อให้ตัวอักษรไทย (เช่น "ม.") render ครบ
    """
    svg_items = [(fn, sv) for fn, sv in (svg_items or []) if sv]
    if not svg_items:
        return [], ""
    try:
        import tempfile, os as _os, threading
        from playwright.sync_api import sync_playwright
        import http.server, socketserver, socket

        # ── สร้าง HTML รวมทุก SVG (แต่ละอันใน .shot) ──
        _blocks = "".join(
            f'<div class="shot" style="display:inline-block;background:#fff;">{sv}</div>'
            for _fn, sv in svg_items
        )
        _html = (
            '<html><head><meta charset="utf-8">'
            '<style>'
            "@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700&display=swap');"
            '*{font-family:Sarabun,sans-serif;} body{margin:0;padding:0;background:#fff;}'
            '</style></head><body>' + _blocks + '</body></html>'
        )

        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8",
                                         delete=False, dir=tempfile.gettempdir()) as _tf:
            _tf.write(_html)
            _tmp_html = _tf.name
        _html_filename = _os.path.basename(_tmp_html)
        _serve_dir = _os.path.dirname(_tmp_html)

        with socket.socket() as _s:
            _s.bind(("", 0)); _free_port = _s.getsockname()[1]

        class _SilentHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=_serve_dir, **kw)
            def log_message(self, *a):
                pass

        _httpd = socketserver.TCPServer(("", _free_port), _SilentHandler)
        _httpd.allow_reuse_address = True
        _t = threading.Thread(target=_httpd.serve_forever, daemon=True)
        _t.start()

        saved = []
        try:
            with sync_playwright() as _pw:
                try:
                    _browser = _pw.chromium.launch()
                except Exception as _le:
                    if "Executable doesn't exist" in str(_le):
                        import subprocess as _sp
                        _sp.run(["python", "-m", "playwright", "install", "chromium"], check=True)
                        _browser = _pw.chromium.launch()
                    else:
                        raise
                _pg = _browser.new_page(device_scale_factor=2)  # คมขึ้น 2x
                _pg.goto(f"http://localhost:{_free_port}/{_html_filename}",
                         wait_until="networkidle", timeout=30000)
                _pg.wait_for_timeout(1500)  # รอฟอนต์ไทย render
                _els = _pg.query_selector_all("svg")
                for _i, (_fn, _sv) in enumerate(svg_items):
                    if _i >= len(_els):
                        break
                    try:
                        _png = _els[_i].screenshot(omit_background=False)
                        ok, _ = save_photo_bytes(project, _fn, _png)
                        if ok:
                            saved.append(_fn)
                    except Exception as _se:
                        print(f"[blueprint export] screenshot {_fn} error: {_se}")
                _browser.close()
        finally:
            _httpd.shutdown()
            try: _os.unlink(_tmp_html)
            except Exception: pass

        return saved, ""
    except ImportError:
        return [], "ไม่พบ Playwright"
    except Exception as _e:
        print(f"[blueprint export] error: {_e}")
        return [], str(_e)


def calc_rsk_joints(main_lines: list, c_boq: dict) -> int:
    """
    คำนวณจำนวน ข้อต่อราง RSK ตามกฎที่ถูกต้อง:

    กฎที่ 1 — ราง "แนวตรง" (gutter line):
        แต่ละเส้นรางใช้ RSK = ceil(ความยาวเส้นนั้น / 5) - 1
        (ทุกท่อน 5ม. ต้องมีข้อต่อ 1 ชิ้นระหว่างท่อน ยกเว้นท่อนแรกและท่อนสุดท้าย
         ปลายรางสองข้างใช้ RGT หรือ RSK กับมุม ซึ่งนับในกฎที่ 2)

    กฎที่ 2 — มุม (Corners ทุกชนิด: RVY / RVI / 90° / 135°):
        แต่ละมุม 1 จุด ใช้ RSK เพิ่ม 2 ชิ้น
        (RSK ด้านซ้ายมุม 1 ชิ้น + ด้านขวามุม 1 ชิ้น)

    หมายเหตุ: ถ้า main_lines ว่างเปล่า จะใช้ gutter_pieces จาก c_boq เป็น fallback
              โดยสมมติว่ารางทั้งหมดเป็น segment เดียว (เหมาะกับกรณีไม่มีข้อมูล mainLines)
    """
    import math

    # --- ส่วนที่ 1: ข้อต่อกลางเส้น ---
    gutter_lines = [ln for ln in main_lines if ln.get("type") == "gutter"] if main_lines else []

    if gutter_lines:
        # มี mainLines จริง → คำนวณทีละ segment
        joints_from_lines = 0
        for ln in gutter_lines:
            length = ((ln["x2"] - ln["x1"]) ** 2 + (ln["y2"] - ln["y1"]) ** 2) ** 0.5
            pieces = math.ceil(length / 5)
            joints_from_lines += max(pieces - 1, 0)
    else:
        # Fallback: ไม่มี mainLines → ใช้ gutter_pieces รวมจาก c_boq
        # RSK ระหว่างท่อน = จำนวนท่อนทั้งหมด - จำนวน segment (ประมาณจากมุม)
        # วิธี: gutter_pieces - 1 คือ joints ทั้งหมดในรางถ้าเป็นเส้นตรงเดียว
        # แต่ทุกมุมตัดการนับ 1 ชิ้น (เพราะปลายที่ชนมุมไม่ใช่ joint กลางเส้น)
        total_corners = (
            c_boq.get("outer_corners",    0) +
            c_boq.get("outer_corners135", 0) +
            c_boq.get("inner_corners",    0) +
            c_boq.get("inner_corners135", 0)
        )
        gutter_pieces = c_boq.get("gutter_pieces", 0)
        # จำนวน segment = total_corners + 1 (มุมแบ่งรางเป็น segment)
        # joints กลางเส้น = gutter_pieces - จำนวน_segment
        num_segments  = max(total_corners + 1, 1)
        joints_from_lines = max(gutter_pieces - num_segments, 0)

    # --- ส่วนที่ 2: RSK จากมุม (ทุกมุม = 2 ชิ้น) ---
    total_corners = (
        c_boq.get("outer_corners",    0) +
        c_boq.get("outer_corners135", 0) +
        c_boq.get("inner_corners",    0) +
        c_boq.get("inner_corners135", 0)
    )
    joints_from_corners = total_corners * 2

    return joints_from_lines + joints_from_corners


def recalculate_boq_with_dynamic_prices(boq_data: dict, is_gutter_premium: bool, is_dp_premium: bool,
                                         main_lines: list = None) -> dict:
    """คำนวณราคาใหม่ทั้งบิล โดยแยก Tier รางน้ำ กับ ท่อลง"""
    if not boq_data: return {"rows": [], "subtotal": 0, "vat": 0, "grand_total": 0}
    
    s = boq_data["summary"]
    rows = []
    subtotal = 0.0

    def add_row(code, label, qty, unit, is_premium):
        if qty <= 0: return
        price = _get_active_price(code, is_premium)
        total = qty * price
        nonlocal subtotal
        subtotal += total
        rows.append({"code": code, "label": label, "qty": qty, "unit": unit, "price": price, "total": total})

    # คำนวณ RSK ด้วย logic ใหม่ถ้ามี main_lines ส่งเข้ามา
    if main_lines is not None:
        rsk_qty = calc_rsk_joints(main_lines, s)
    else:
        rsk_qty = s.get("gutter_joints", 0)

    # กลุ่มรางน้ำ (อิงสีราง)
    add_row("R",      "ท่อนราง R (5 ม./ท่อน)", s["gutter_pieces"], "ท่อน", is_gutter_premium)
    add_row("RSK",    "ข้อต่อราง RSK", rsk_qty, "ชิ้น", is_gutter_premium)
    add_row("KFK",    "ตะขอ KFK/SSK", s["hooks"], "ตัว", is_gutter_premium)
    add_row("RGT",    "ฝาปิดปลาย RGT", s["end_caps"], "ชิ้น", is_gutter_premium)
    add_row("RVY",    "มุมนอก RVY", s.get("outer_corners", 0) + s.get("outer_corners135", 0), "ชิ้น", is_gutter_premium)
    add_row("RVI",    "มุมใน RVI",  s.get("inner_corners", 0) + s.get("inner_corners135", 0), "ชิ้น", is_gutter_premium)

    # กลุ่มท่อลง (อิงสีท่อลง)
    add_row("SOK",    "ท่อเชื่อมราง SOK", s["downpipe_sok"], "ชิ้น", is_dp_premium)
    add_row("SROR",   "ท่อลง SROR (5 ม./ท่อน)", s["downpipe_pieces"], "ท่อน", is_dp_premium)
    add_row("BK",     "ท่องอ BK", s.get("downpipe_elbows", 0), "ชิ้น", is_dp_premium)
    add_row("SSVH",   "ตะขอท่อลง SSVH", s["downpipe_brackets"], "ตัว", is_dp_premium)

    vat = subtotal * 0.07
    return {
        "rows": rows,
        "subtotal": subtotal,
        "vat": vat,
        "grand_total": subtotal + vat
    }

# ==========================================
# 2. SVG ENGINE (CANVAS 1:1 CLONE)
# ==========================================
def generate_exact_blueprint(canvas_data: dict, is_sub: bool = False) -> str:
    """เรนเดอร์ SVG ให้หน้าตาเหมือน page_canvas.py 100% (คำนวณ Grid และสเกลเป๊ะๆ)"""
    lines = canvas_data.get("lines", [])
    poly = canvas_data.get("housePoly", [])
    
    if not lines and not poly:
        return "<div style='padding:20px; text-align:center; color:#94A3B8; background:#F8FAFC; border:1px dashed #CBD5E1;'>ไม่มีข้อมูลแปลน</div>"

    # หาขอบเขตพื้นที่ (Bounding Box)
    all_x = [p["x"] for p in poly] + [l["x1"] for l in lines if "x1" in l] + [l["x2"] for l in lines if "x2" in l]
    all_y = [p["y"] for p in poly] + [l["y1"] for l in lines if "y1" in l] + [l["y2"] for l in lines if "y2" in l]
    
    min_x, max_x = min(all_x) if all_x else 0, max(all_x) if all_x else 10
    min_y, max_y = min(all_y) if all_y else 0, max(all_y) if all_y else 10
    
    # กำหนด Padding และแปลงหน่วยเป็น Pixel (1 เมตร = 40px เพื่อให้ภาพคมชัด)
    PAD = 1 if is_sub else 2
    PPM = 40 
    width_px = (max_x - min_x + (PAD * 2)) * PPM
    height_px = (max_y - min_y + (PAD * 2)) * PPM
    
    def to_px(val, is_x=True):
        offset = min_x if is_x else min_y
        return (val - offset + PAD) * PPM

    svg_els = []
    
    # 1. วาดทรงบ้าน (Shape)
    if poly and not is_sub:
        pts = " ".join([f"{to_px(p['x'], True)},{to_px(p['y'], False)}" for p in poly])
        svg_els.append(f'<polygon points="{pts}" fill="rgba(148, 163, 184, 0.25)" stroke="#94A3B8" stroke-width="3"/>')
        # จุดเหลืองตามมุมบ้าน
        for p in poly:
            svg_els.append(f'<circle cx="{to_px(p["x"], True)}" cy="{to_px(p["y"], False)}" r="4" fill="#FCD34D" stroke="#0D2144" stroke-width="1.5"/>')

    # 2. วาดเส้นและข้อความ
    dp_counter = 1
    for ln in lines:
        if "x1" not in ln: continue
        x1, y1 = to_px(ln["x1"], True), to_px(ln["y1"], False)
        x2, y2 = to_px(ln["x2"], True), to_px(ln["y2"], False)
        
        is_gutter = ln.get("type") == "gutter"
        color = "#2563EB" if is_gutter else "#DC2626"
        sw = "5" if is_gutter else "3.5"
        
        # เส้น
        svg_els.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>')

        # ป้ายความยาว (ให้อยู่กึ่งกลางเส้น)
        mx, my = (x1+x2)/2, (y1+y2)/2
        length = ((ln["x2"]-ln["x1"])**2 + (ln["y2"]-ln["y1"])**2)**0.5
        text_color = "#1D4ED8" if is_gutter else "#B91C1C"
        svg_els.append(f'<text x="{mx}" y="{my-8}" font-family="Sarabun, Arial" font-size="14" font-weight="bold" fill="{text_color}" text-anchor="middle">{length:.2f}ม.</text>')

        # จุดมาร์คท่อลง
        if not is_sub and ln.get("type") == "downpipe":
            svg_els.append(f'<circle cx="{x1}" cy="{y1}" r="12" fill="#DC2626"/>')
            svg_els.append(f'<text x="{x1}" y="{y1+4}" font-family="Sarabun, Arial" font-size="12" font-weight="bold" fill="white" text-anchor="middle">{dp_counter}</text>')
            dp_counter += 1

    content = "".join(svg_els)
    grid_pattern = f"""
    <defs>
        <pattern id="grid_{is_sub}" width="{PPM}" height="{PPM}" patternUnits="userSpaceOnUse">
            <path d="M {PPM} 0 L 0 0 0 {PPM}" fill="none" stroke="#CBD5E1" stroke-width="1"/>
            <path d="M {PPM/2} 0 L {PPM/2} {PPM} M 0 {PPM/2} L {PPM} {PPM/2}" fill="none" stroke="#E2E8F0" stroke-width="0.5"/>
        </pattern>
    </defs>
    """
    
    bg_color = "white" if is_sub else "#F0F4FF"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    * {{margin:0;padding:0;box-sizing:border-box;}}
    html,body {{width:100%;height:100%;overflow:hidden;background:transparent;cursor:grab;}}
    body.panning {{cursor:grabbing;}}
    svg {{width:100%;height:100%;display:block;}}
    .zoom-hint {{position:fixed;bottom:6px;right:8px;font-size:10px;color:#94A3B8;font-family:sans-serif;pointer-events:none;}}
    </style></head><body>
    <svg id="svg" viewBox="0 0 {width_px} {height_px}" preserveAspectRatio="xMidYMid meet"
         style="background:{bg_color};border:1px solid #CBD5E1;border-radius:4px;">
        {grid_pattern}<rect width="100%" height="100%" fill="url(#grid_{is_sub})" />{content}
    </svg>
    <div class="zoom-hint">scroll=zoom • drag=pan</div>
    <script>
    const svg = document.getElementById('svg');
    let vx={0}, vy={0}, vw={width_px}, vh={height_px};
    let dragging=false, startX=0, startY=0, startVx=0, startVy=0;
    function setVB(){{ svg.setAttribute('viewBox', vx+' '+vy+' '+vw+' '+vh); }}
    svg.addEventListener('wheel', e=>{{
        e.preventDefault();
        const factor = e.deltaY > 0 ? 1.1 : 0.9;
        const rect = svg.getBoundingClientRect();
        const mx = (e.clientX - rect.left) / rect.width * vw + vx;
        const my = (e.clientY - rect.top) / rect.height * vh + vy;
        vw *= factor; vh *= factor;
        vx = mx - (e.clientX - rect.left) / rect.width * vw;
        vy = my - (e.clientY - rect.top) / rect.height * vh;
        setVB();
    }}, {{passive:false}});
    svg.addEventListener('mousedown', e=>{{
        dragging=true; startX=e.clientX; startY=e.clientY;
        startVx=vx; startVy=vy;
        document.body.classList.add('panning');
    }});
    window.addEventListener('mousemove', e=>{{
        if(!dragging) return;
        const rect = svg.getBoundingClientRect();
        const scaleX = vw / rect.width;
        const scaleY = vh / rect.height;
        vx = startVx - (e.clientX - startX) * scaleX;
        vy = startVy - (e.clientY - startY) * scaleY;
        setVB();
    }});
    window.addEventListener('mouseup', ()=>{{
        dragging=false;
        document.body.classList.remove('panning');
    }});
    </script></body></html>"""

# ==========================================
# 3. MAIN UI
# ==========================================
def show():
    from utils.storage import save_photos, load_photos, delete_photo  # guard against Streamlit module reload
    touch_session()
    p = get_project()
    if p is None:
        st.warning("⚠️ กรุณาเลือกหรือสร้างโปรเจกต์ก่อนครับ")
        return

    # ── CSS Injection (Pixel-Perfect EX-01 Template) ──
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&family=Kanit:wght@400;600;700&display=swap');
    .stApp { background-color: #F0F4FF; }
    * { font-family: 'Sarabun', sans-serif; font-size: 18px; }

    /* ── HIDE DEFAULT STREAMLIT PADDING ── */
    .block-container { padding-top: 1rem !important; }

    /* ── PAGE TITLE BAR (EX-01: ข้อมูลทั่วไปของลูกค้า | เลขที่ใบเสนอ) ── */
    .ex01-top-header {
        display: flex;
        align-items: stretch;
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        border-radius: 8px 8px 0 0;
        margin-bottom: 0;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(26,46,107,0.20);
    }
    .ex01-top-left {
        flex: 1;
        padding: 12px 20px;
        font-family: 'Kanit', sans-serif;
        font-size: 1.15rem; font-weight: 700; color: #FFFFFF;
        display: flex; align-items: center; gap: 8px;
    }
    .ex01-top-right {
        min-width: 220px;
        padding: 8px 20px;
        background: rgba(255,255,255,0.08);
        border-left: 1px solid rgba(255,255,255,0.15);
        display: flex; flex-direction: column; justify-content: center;
    }
    .ex01-top-right .doc-label {
        font-size: 0.65rem; color: rgba(255,255,255,0.65);
        font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
        margin-bottom: 2px;
    }
    .ex01-top-right .doc-no-val {
        font-family: 'Kanit', sans-serif;
        font-size: 1.05rem; font-weight: 700; color: #FFD700;
        letter-spacing: 1.5px;
    }

    /* ── FORM CARD / WHITE CONTAINER ── */
    .ex01-card {
        background: #FFFFFF;
        border: 1px solid #DDE5F5;
        border-radius: 0 0 8px 8px;
        padding: 14px 18px 10px 18px;
        box-shadow: 0 1px 6px rgba(13,33,68,0.06);
        margin-bottom: 0;
    }
    .ex01-card-standalone {
        background: #FFFFFF;
        border: 1px solid #DDE5F5;
        border-radius: 8px;
        padding: 14px 18px 10px 18px;
        box-shadow: 0 1px 6px rgba(13,33,68,0.06);
        margin-bottom: 12px;
    }

    /* ── SECTION BARS (เหมือน EX-01 ทุกจุด) ── */
    .ex01-section-bar {
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        color: #FFFFFF !important;
        padding: 8px 16px;
        font-family: 'Sarabun', sans-serif;
        font-size: 0.92rem; font-weight: 700;
        border-radius: 6px 6px 0 0;
        margin: 22px 0 0 0;
        display: flex; align-items: center; gap: 8px;
        box-shadow: 0 3px 8px rgba(26,46,107,0.18);
        letter-spacing: 0.2px;
    }
    .ex01-section-bar-alone {
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        color: #FFFFFF !important;
        padding: 8px 16px;
        font-family: 'Sarabun', sans-serif;
        font-size: 0.92rem; font-weight: 700;
        border-radius: 6px;
        margin: 22px 0 10px 0;
        display: flex; align-items: center; gap: 8px;
        box-shadow: 0 3px 8px rgba(26,46,107,0.18);
        letter-spacing: 0.2px;
    }

    /* ── INPUT LABELS ── */
    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stNumberInput"] label {
        font-size: 0.85rem !important;
        color: #4A5E85 !important;
        font-weight: 700 !important;
        letter-spacing: 0.3px !important;
    }

    /* ── PHOTO SECTION HEADER (EX-01) ── */
    .photo-section-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 16px;
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        border-radius: 6px 6px 0 0;
        margin: 22px 0 0 0;
    }
    .photo-section-header .psh-title {
        font-size: 0.92rem; font-weight: 700; color: #FFFFFF;
        display: flex; align-items: center; gap: 8px;
    }
    .photo-section-header .psh-badge {
        font-size: 0.70rem; color: #1A2E6B;
        background: #FFD700; border-radius: 20px;
        padding: 2px 12px; font-weight: 700;
        display: flex; align-items: center; gap: 4px;
    }
    .photo-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
        margin-top: 4px;
    }
    .photo-cell {
        height: 110px; background: #E8EDF5;
        border: 1px solid #C8D5E8; border-radius: 5px;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        color: #94A3B8; font-size: 0.78rem; gap: 4px;
        font-family: 'Sarabun', sans-serif;
    }
    .photo-cell .pc-icon { font-size: 1.5rem; }
    .photo-cell .pc-label { font-size: 0.72rem; color: #64748B; }

    /* ── BLUEPRINT SECTION ── */
    .bp-section {
        background: #FFFFFF; border: 1px solid #DDE5F5;
        border-radius: 0 0 8px 8px; padding: 14px;
        box-shadow: 0 1px 6px rgba(13,33,68,0.06);
        margin-bottom: 12px;
    }
    .bp-label {
        font-size: 0.8rem; font-weight: 700; color: #1E3A8A;
        background: #EEF3FF; border: 1px solid #C8D5F0;
        border-radius: 4px; padding: 3px 10px; margin-bottom: 8px;
        display: inline-block;
    }
    .bp-sublabel {
        font-size: 0.72rem; color: #64748B; text-align: center;
        margin-bottom: 4px; font-weight: 600;
    }
    .bp-sub-title {
        font-size: 0.78rem; font-weight: 700; color: #856404;
        background: #FFF3CD; border: 1px solid #FFC107;
        border-radius: 4px; padding: 3px 10px; margin-bottom: 8px;
        display: inline-block;
    }

    /* ── BOQ SUMMARY METRICS ── */
    .boq-metric-row {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
        margin-bottom: 10px;
    }
    .boq-metric {
        background: #F8FAFF; border: 1px solid #DDE5F5;
        border-top: 3px solid #2563EB;
        border-radius: 7px; padding: 10px 14px;
    }
    .boq-metric .bm-label { font-size: 0.68rem; color: #6B7A99; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .boq-metric .bm-value { font-size: 1.3rem; font-weight: 700; color: #0D2144; line-height: 1.1; }
    .boq-metric .bm-unit  { font-size: 0.72rem; color: #64748B; margin-top: 2px; }

    /* ── CONFIG DROPDOWNS ROW ── */
    .boq-config-bar {
        background: #F0F4FF; border: 1px solid #DDE5F5;
        border-radius: 7px; padding: 10px 14px;
        margin-bottom: 10px;
    }

    /* ── BOQ TABLE ── */
    .boq-table {
        width: 100%; border-collapse: collapse;
        font-family: 'Sarabun', sans-serif;
        font-size: 0.95rem; background: white;
        border: 1px solid #DDE5F5;
        box-shadow: 0 1px 4px rgba(13,33,68,0.06);
        border-radius: 6px; overflow: hidden;
    }
    .boq-table thead tr { background: #1E3A8A; }
    .boq-table th {
        color: #FFFFFF; font-weight: 700;
        padding: 10px 10px; text-align: center;
        font-size: 0.8rem; letter-spacing: 0.2px;
        border-right: 1px solid rgba(255,255,255,0.15);
    }
    .boq-table th:last-child { border-right: none; }
    .boq-table tbody tr:nth-child(even) td { background: #F8FAFF; }
    .boq-table tbody tr:hover td { background: #EEF3FF; }
    .boq-table td {
        padding: 9px 10px; border-bottom: 1px solid #EEF2F8;
        color: #0F172A; vertical-align: middle;
    }
    .boq-table .num { text-align: right; font-variant-numeric: tabular-nums; }
    .boq-table .ctr { text-align: center; }
    .boq-table .total-row td {
        background: #EEF3FF !important; font-weight: 700; color: #0D2144;
        border-top: 2px solid #B8C8E8; text-align: right;
    }
    .boq-table .vat-row td {
        background: #F5F8FF !important; font-weight: 600; color: #3B5999;
        text-align: right;
    }
    .boq-table .grand-row td {
        background: #1E3A8A !important; color: #FFFFFF;
        font-weight: 800; font-size: 1.0rem; text-align: right;
        border-top: none;
    }
    .boq-table .section-sub-head td {
        background: #F0F4FF; color: #1E3A8A; font-weight: 700;
        font-size: 0.85rem; padding: 6px 10px; letter-spacing: 0.5px;
        text-transform: uppercase; border-top: 1px solid #C8D5F0;
    }
    .color-badge {
        display: inline-block; font-size: 0.68rem;
        padding: 1px 7px; border-radius: 10px;
        background: #EEF3FF; color: #3B5999;
        border: 1px solid #C8D5F0; margin-left: 5px;
        font-weight: 600;
    }

    /* ── SECTION LABELS (ท่อลง / ตะไม้ / ขั้ว / อื่นๆ) ── */
    .sub-section-label {
        font-size: 0.75rem; font-weight: 700; color: #FFFFFF;
        padding: 5px 12px;
        background: #2E4A8B;
        border-radius: 4px;
        margin: 12px 0 6px 0;
        display: block;
    }
    .sub-section-label-gray {
        font-size: 0.75rem; font-weight: 700; color: #374151;
        padding: 5px 12px;
        background: #E5E9F2;
        border-radius: 4px;
        margin: 12px 0 6px 0;
        display: block;
    }

    /* ── UNIT SUFFIX LABELS ── */
    .unit-suffix {
        font-size: 0.72rem; color: #64748B;
        margin-top: 2px; padding-left: 4px;
    }

    /* ── FOOTER SAVE BUTTON BAR ── */
    .boq-save-footer {
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        border-radius: 8px;
        padding: 14px 20px;
        margin-top: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 3px 12px rgba(26,46,107,0.22);
    }

    div[data-testid="stFileUploaderFileList"] { display: none !important; }
    div[data-testid="stFileUploader"] section { padding: 4px 8px !important; min-height: unset !important; }
    </style>
    """, unsafe_allow_html=True)

    # ==========================================
    # PAGE TITLE + DOC NO  →  "ข้อมูลทั้งหมด | เลขที่ใบจอง"
    # ==========================================
    # ดึงข้อมูลจาก canvas (ความยาวรางน้ำ / ท่อลง)
    canvas_data_raw = p.get("canvas_data") or {}   # งานที่ยังไม่ได้วาด canvas_data = None → ใช้ dict ว่างกันพัง
    main_lines_raw  = canvas_data_raw.get("mainLines", [])
    sub_apps_raw    = canvas_data_raw.get("subApps", [])

    # คำนวณความยาวรวมราง R จากแปลนหลัก
    gutter_total_m = sum(
        ((ln["x2"]-ln["x1"])**2 + (ln["y2"]-ln["y1"])**2)**0.5
        for ln in main_lines_raw if ln.get("type") == "gutter"
    )
    # คำนวณความยาวรวมท่อลง SROR จากหน้าตัด (subApps)
    downpipe_total_m = sum(
        ((ln["x2"]-ln["x1"])**2 + (ln["y2"]-ln["y1"])**2)**0.5
        for sub in sub_apps_raw
        for ln in sub.get("lines", [])
        if ln.get("type") == "downpipe"
    )

    # ── Header Bar (เอาช่อง "เลขที่ใบจอง" ออกตามที่สั่ง) ──
    st.markdown('<div class="ex01-top-header"><div class="ex01-top-left">ข้อมูลทั้งหมด</div></div>',
                unsafe_allow_html=True)

    # ==========================================
    # SECTION 1: ข้อมูลทั้งหมด (White Card)
    # ==========================================
    st.markdown('<div class="ex01-card">', unsafe_allow_html=True)

    # ── แถว 1: เลขที่ใบเสนอราคา | รหัสลูกค้า | พนักงานขาย ──
    r1c1, r1c2, r1c3 = st.columns([3, 2, 2])
    r1c1.text_input("เลขที่ใบเสนอราคา", value=p.get("name", ""), key="boq_quoteno", disabled=True)
    r1c2.text_input("รหัสลูกค้า", value=p.get("customer_code", ""), key="boq_custcode", disabled=True)
    r1c3.text_input("พนักงานขาย", value=p.get("salesperson", ""), key="boq_salesperson", disabled=True)

    # ── แถว 2: ชื่อผู้ติดต่อ | บริษัท/หน่วยงาน | เลขประจำตัวผู้เสียภาษี ──
    r2ac1, r2ac2, r2ac3 = st.columns([3, 3, 2])
    r2ac1.text_input("ชื่อผู้ติดต่อ", value=p.get("customer", ""), key="boq_custname", disabled=True)
    r2ac2.text_input("บริษัท / หน่วยงาน", value=p.get("angency_name", ""), key="boq_angency_name", disabled=True)
    r2ac3.text_input("เลขประจำตัวผู้เสียภาษี", value=p.get("customer_taxid", ""), key="boq_taxid", disabled=True)

    # ── แถว 3: ที่อยู่บริษัท | ปุ่ม Location | โทร ──
    r2bc1, r2bc_loc, r2bc2 = st.columns([5, 0.65, 2])
    _address_val = p.get("address", "")
    r2bc1.text_input("ที่อยู่", value=_address_val, key="boq_address", disabled=True)

    # ── ปุ่ม "ขอ Location" ──
    with r2bc_loc:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("📍 Location", key="btn_location", help="ค้นหาบน Google Maps"):
            st.session_state["show_location_popup"] = not st.session_state.get("show_location_popup", False)

    r2bc2.text_input("โทรศัพท์", value=p.get("phone", ""), key="boq_phone", disabled=True)

    # ── Location Popup (แสดงเมื่อกดปุ่ม) ──
    if st.session_state.get("show_location_popup", False):
        _addr_encoded = _address_val.replace(" ", "+") if _address_val else ""
        _maps_search   = f"https://www.google.com/maps/search/?api=1&query={_addr_encoded}"
        _maps_dir      = f"https://www.google.com/maps/dir/?api=1&destination={_addr_encoded}"
        _maps_embed    = f"https://maps.google.com/maps?q={_addr_encoded}&output=embed&z=16"

        _line_url  = f"https://social-plugins.line.me/lineit/share?url={_maps_search}"
        _fb_url    = f"https://www.facebook.com/sharer/sharer.php?u={_maps_search}"
        _wa_url    = f"https://wa.me/?text={_address_val.replace(' ','%20')}%20{_maps_search}"
        _tw_url    = f"https://twitter.com/intent/tweet?text={_address_val.replace(' ','%20')}&url={_maps_search}"

        components.html(f"""<!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;}}
            body{{font-family:'Sarabun',sans-serif;background:transparent;}}
            .card{{background:#fff;border:1px solid #CBD5E1;border-radius:12px;
                   box-shadow:0 8px 32px rgba(26,46,107,0.18);overflow:hidden;}}
            .hdr{{background:linear-gradient(90deg,#1A2E6B,#243E8F);
                  padding:10px 16px;display:flex;align-items:center;justify-content:space-between;}}
            .hdr-addr{{color:#fff;font-size:14px;font-weight:700;flex:1;}}
            .hdr-tag{{color:#FFD700;font-size:11px;font-weight:700;margin-left:8px;flex-shrink:0;}}
            .map-frame{{border:0;display:block;width:100%;height:200px;}}
            /* ── top action bar (เส้นทาง / แผนที่ / คัดลอก) ── */
            .btns{{display:flex;gap:8px;padding:10px 14px;background:#f8fafc;
                   border-top:1px solid #E2E8F0;flex-wrap:wrap;}}
            .btn{{display:inline-flex;align-items:center;gap:6px;
                  background:#fff;border:1px solid #C7D4EE;border-radius:10px;
                  padding:8px 14px;font-size:13px;font-weight:700;color:#1A2E6B;
                  box-shadow:0 1px 4px rgba(0,0,0,0.07);cursor:pointer;
                  text-decoration:none;white-space:nowrap;}}
            .btn:hover{{background:#EEF2FF;}}
            /* ── share sheet ── */
            .share-bar{{display:flex;align-items:center;gap:6px;
                        padding:10px 14px 12px;background:#fff;
                        border-top:1px solid #E2E8F0;}}
            .share-label{{font-size:12px;color:#94A3B8;font-weight:700;
                          white-space:nowrap;margin-right:4px;}}
            .sicons{{display:flex;gap:10px;flex-wrap:wrap;}}
            .si{{display:flex;flex-direction:column;align-items:center;gap:3px;
                 text-decoration:none;cursor:pointer;}}
            .si-circle{{width:46px;height:46px;border-radius:50%;
                        display:flex;align-items:center;justify-content:center;
                        box-shadow:0 2px 6px rgba(0,0,0,0.12);}}
            .si span{{font-size:11px;font-weight:700;color:#475569;}}
            /* copy toast */
            #toast{{display:none;position:fixed;bottom:14px;left:50%;transform:translateX(-50%);
                    background:#1A2E6B;color:#fff;padding:7px 18px;border-radius:20px;
                    font-size:13px;font-weight:700;z-index:999;}}
        </style></head><body>
        <div class="card">
            <!-- Header -->
            <div class="hdr">
                <div class="hdr-addr">📍 {_address_val[:60] + ('...' if len(_address_val)>60 else '')}</div>
                <div class="hdr-tag">Google Maps</div>
            </div>

            <!-- Map -->
            <iframe class="map-frame" loading="lazy" referrerpolicy="no-referrer-when-downgrade"
                src="{_maps_embed}"></iframe>

            <!-- Top Buttons -->
            <div class="btns">
                <a class="btn" href="{_maps_dir}" target="_blank">🗺️ เส้นทาง</a>
                <a class="btn" href="{_maps_search}" target="_blank">🔍 เปิดแผนที่</a>
                <button class="btn" id="copyBtn" onclick="copyLink()">🔗 คัดลอกลิงก์</button>
            </div>

            <!-- Share Sheet Bar -->
            <div class="share-bar">
                <div class="share-label">ส่งให้ :</div>
                <div class="sicons">

                    <!-- LINE -->
                    <a class="si" href="{_line_url}" target="_blank">
                        <div class="si-circle" style="background:#06C755;">
                            <svg width="26" height="26" viewBox="0 0 48 48" fill="none">
                                <path fill="#fff" d="M24 4C12.95 4 4 11.8 4 21.4c0 6.3 4.1 11.8 10.3 15L12 40l8.5-3.2c1.1.2 2.3.3 3.5.3 11.05 0 20-7.8 20-17.4S35.05 4 24 4z"/>
                            </svg>
                        </div>
                        <span>LINE</span>
                    </a>

                    <!-- Facebook -->
                    <a class="si" href="{_fb_url}" target="_blank">
                        <div class="si-circle" style="background:#1877F2;">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff">
                                <path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/>
                            </svg>
                        </div>
                        <span>Facebook</span>
                    </a>

                    <!-- WhatsApp -->
                    <a class="si" href="{_wa_url}" target="_blank">
                        <div class="si-circle" style="background:#25D366;">
                            <svg width="26" height="26" viewBox="0 0 48 48" fill="#fff">
                                <path d="M24 4C13 4 4 13 4 24c0 3.6 1 7 2.7 9.9L4 44l10.4-2.7C17 43 20.4 44 24 44c11 0 20-9 20-20S35 4 24 4zm10.3 27.7c-.4 1.1-2.4 2.1-3.3 2.2-.8.1-1.9.1-3-.2-1.8-.5-4.1-1.8-6.8-4.5-2.7-2.7-4-5-4.5-6.8-.3-1.1-.3-2.2-.2-3 .1-.9 1.1-2.9 2.2-3.3.4-.1.8-.2 1.1-.2.3 0 .6 0 .8.1.3.1.8.2 1.1.9l1.5 3.5c.2.4.2.8 0 1.2l-.8 1.2c-.2.2-.2.5 0 .8.5.8 1.5 2 2.5 3 1 1 2.2 2 3 2.5.3.2.6.2.8 0l1.2-.8c.4-.2.8-.2 1.2 0l3.5 1.5c.7.3.8.8.9 1.1 0 .3 0 .6-.2.8z"/>
                            </svg>
                        </div>
                        <span>WhatsApp</span>
                    </a>

                    <!-- X / Twitter -->
                    <a class="si" href="{_tw_url}" target="_blank">
                        <div class="si-circle" style="background:#000;">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff">
                                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.402 6.23H2.744l7.737-8.844L1.254 2.25H8.08l4.258 5.63 5.906-5.63zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                            </svg>
                        </div>
                        <span>X</span>
                    </a>

                    <!-- SMS -->
                    <a class="si" href="sms:?body={_address_val.replace(' ','%20')}%20{_maps_search}" target="_blank">
                        <div class="si-circle" style="background:#6366F1;">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff">
                                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM7 9h10v2H7V9zm6 5H7v-2h6v2zm3-6H7V6h10v2z"/>
                            </svg>
                        </div>
                        <span>SMS</span>
                    </a>

                </div>
            </div>
        </div>

        <div id="toast">✅ คัดลอก link แล้ว!</div>

        <script>
        function copyLink() {{
            var url = '{_maps_search}';
            navigator.clipboard.writeText(url).then(function() {{
                var t = document.getElementById('toast');
                t.style.display = 'block';
                setTimeout(function(){{ t.style.display='none'; }}, 2000);
            }}).catch(function() {{
                window.open(url, '_blank');
            }});
        }}
        </script>
        </body></html>""", height=430, scrolling=False)

    # ── แถว 4: ชื่อโครงการ | สถานที่ติดตั้ง | PO Ref ──
    r3c1, r3c2, r3c3 = st.columns([3, 3, 2])
    r3c1.text_input("ชื่อโครงการ", value=p.get("project_name_site", ""), key="boq_projsite", disabled=True)
    r3c2.text_input("สถานที่ติดตั้ง", value=p.get("install_location", ""), key="boq_installloc", disabled=True)
    r3c3.text_input("เลขที่อ้างอิง PO", value=p.get("po_ref", ""), key="boq_poref", disabled=True)

    # ── แถว 2: สีรางน้ำ + จำนวน(เมตร) | สีท่อ + จำนวน(เมตร) ──
    COLOR_OPTIONS = [
        "", "สีขาว", "สีน้ำตาล", "สีเทา",
        "สีซิลเวอร์", "สีแอนทราไซต์", "สีดำ", "สีเทาแกรไฟต์"
    ]

    r2c1, r2c2, r2c3, r2c4, r2c5, r2c6 = st.columns([2, 0.6, 0.5, 2, 0.6, 0.5])

    color_g_sel = r2c1.selectbox(
        "สีรางน้ำ",
        options=COLOR_OPTIONS,
        index=COLOR_OPTIONS.index(p.get("boq_color_gutter", "")) if p.get("boq_color_gutter", "") in COLOR_OPTIONS else 0,
        key="boq_color_gutter_sel"
    )
    r2c2.text_input(
        "จำนวน",
        value=f"{gutter_total_m:.1f}",
        key="boq_gutter_qty",
        disabled=True
    )
    r2c3.markdown("<div style='margin-top:28px; font-size:0.82rem; color:#64748B;'>เมตร</div>",
                  unsafe_allow_html=True)

    color_d_sel = r2c4.selectbox(
        "สีท่อ",
        options=COLOR_OPTIONS,
        index=COLOR_OPTIONS.index(p.get("boq_color_dp", "")) if p.get("boq_color_dp", "") in COLOR_OPTIONS else 0,
        key="boq_color_dp_sel"
    )
    r2c5.text_input(
        "จำนวน",
        value=f"{downpipe_total_m:.1f}",
        key="boq_dp_qty",
        disabled=True
    )
    r2c6.markdown("<div style='margin-top:28px; font-size:0.82rem; color:#64748B;'>เมตร</div>",
                  unsafe_allow_html=True)

    # แสดงสีที่เลือกด้านล่าง (badge)
    if color_g_sel or color_d_sel:
        badge_cols = st.columns([2.6, 3.2, 2.6, 1])
        if color_g_sel:
            badge_cols[0].markdown(
                f'<span class="color-badge">🎨 {color_g_sel}</span>',
                unsafe_allow_html=True
            )
        if color_d_sel:
            badge_cols[2].markdown(
                f'<span class="color-badge">🎨 {color_d_sel}</span>',
                unsafe_allow_html=True
            )

    # ── แถว 3: วัสดุเชิงชาย | ลักษณะเชิงชาย | ประเภทหลังคา | ข้อมูลพิเศษเพิ่มเติม ──
    r3c1, r3c2, r3c3, r3c4 = st.columns([2, 2, 2, 2])

    FASCIA_MAT  = ["", "เชิงไม้", "เชิงชายปูน", "เชิงชายเหล็ก"]
    FASCIA_TYPE = ["", "เชิงชายตรง", "เชิงชายเอียง"]
    ROOF_TYPE   = ["", "ทรงจั่ว", "ทรงปั้นหยา", "ทรงเพิงหมาแหงน", "ทรงปั้นหยาตัวแอล"]

    fascia_mat_sel = r3c1.selectbox(
        "วัสดุเชิงชาย",
        options=FASCIA_MAT,
        index=FASCIA_MAT.index(p.get("boq_fascia_mat","")) if p.get("boq_fascia_mat","") in FASCIA_MAT else 0,
        key="boq_fascia_mat_sel"
    )
    fascia_type_sel = r3c2.selectbox(
        "ลักษณะเชิงชาย",
        options=FASCIA_TYPE,
        index=FASCIA_TYPE.index(p.get("boq_fascia_type","")) if p.get("boq_fascia_type","") in FASCIA_TYPE else 0,
        key="boq_fascia_type_sel"
    )
    roof_type_sel = r3c3.selectbox(
        "ประเภทหลังคา",
        options=ROOF_TYPE,
        index=ROOF_TYPE.index(p.get("boq_roof_type","")) if p.get("boq_roof_type","") in ROOF_TYPE else 0,
        key="boq_roof_type_sel"
    )
    special_note = r3c4.text_input(
        "ข้อมูลพิเศษเพิ่มเติม",
        value=p.get("boq_special_note", ""),
        key="boq_special_note_inp"
    )

    # แสดงค่า dropdown ที่เลือกด้านล่าง (badge แถว 3)
    sel3 = [(fascia_mat_sel, 0), (fascia_type_sel, 1), (roof_type_sel, 2)]
    if any(v for v, _ in sel3):
        b3cols = st.columns(4)
        for val, col_idx in sel3:
            if val:
                b3cols[col_idx].markdown(
                    f'<span class="color-badge">✔ {val}</span>',
                    unsafe_allow_html=True
                )

    # ── แถว 4: ชื่อผู้ประเมิน | ชื่อฝ่ายขาย | ในวันที่ ──
    r4c1, r4c2, r4c3 = st.columns([2.5, 2.5, 2])
    assessor_name = r4c1.text_input(
        "ชื่อผู้ประเมิน",
        value=p.get("boq_assessor", ""),
        key="boq_assessor_inp"
    )
    sales_name = r4c2.text_input(
        "ชื่อฝ่ายขาย",
        value=p.get("boq_sales", ""),
        key="boq_sales_inp"
    )
    boq_date = r4c3.date_input(
        "ในวันที่",
        value=datetime.date.today(),
        key="boq_date"
    )

    # ── Auto-save ค่าที่แก้ไขได้ทั้งหมดกลับลง project ──
    updated = False
    _fields = {
        "boq_color_gutter": color_g_sel,
        "boq_color_dp":     color_d_sel,
        "boq_fascia_mat":   fascia_mat_sel,
        "boq_fascia_type":  fascia_type_sel,
        "boq_roof_type":    roof_type_sel,
        "boq_special_note": special_note,
        "boq_assessor":     assessor_name,
        "boq_sales":        sales_name,
    }
    for field, val in _fields.items():
        if p.get(field) != val:
            p[field] = val
            updated = True
    if updated:
        save_project(p)

    # ── ส่งค่าสีไปใช้ในโค้ดส่วนล่าง (แทนตัวแปร color_g / color_d เดิม) ──
    color_g = color_g_sel + (" (Premium)" if color_g_sel in ["สีแอนทราไซต์","สีดำ","สีเทาแกรไฟต์"] else "")
    color_d = color_d_sel + (" (Premium)" if color_d_sel in ["สีแอนทราไซต์","สีดำ","สีเทาแกรไฟต์"] else "")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # SECTION 1: ข้อมูลโครงการ / ลูกค้า (ต่อจาก header โดยตรง)
    # ==========================================
    st.markdown('<div class="ex01-card">', unsafe_allow_html=True)

   

    # Auto-save changes
    

    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # SECTION 2: ภาพสถานที่จริง (Collapsible + Upload in Header)
    # ==========================================

    # ── State: ยุบ/ขยาย ──
    if "boq_photos_expanded" not in st.session_state:
        st.session_state["boq_photos_expanded"] = True

    # ── Header Bar ──
    ph_left, ph_upload, ph_info, ph_toggle = st.columns([3, 1.2, 2.5, 0.6])

    with ph_left:
        st.markdown(
            '<div style="background:linear-gradient(90deg,#1A2E6B 0%,#243E8F 100%);'
            'padding:8px 16px; border-radius:6px 0 0 6px; color:#fff; font-weight:700; font-size:0.92rem;">'
            '📸 &nbsp;ภาพสถานที่จริง</div>',
            unsafe_allow_html=True
        )

    with ph_upload:
        uploaded_files = st.file_uploader(
            "อัพโหลดไฟล์",
            accept_multiple_files=True,
            type=['png', 'jpg', 'jpeg', 'pdf'],
            key="boq_photos",
            label_visibility="collapsed"
        )
        # ── บันทึกลง disk ทันทีที่ upload + แสดงผล (Issue 1) ──
        if uploaded_files:
            saved, errors = save_photos(p, uploaded_files)
            # กันแจ้งซ้ำทุก rerun: จำชุดไฟล์ที่เพิ่งเซฟไว้ใน session
            _sig = "|".join(sorted(uf.name for uf in uploaded_files))
            if st.session_state.get("_last_photo_sig") != _sig:
                st.session_state["_last_photo_sig"] = _sig
                if errors:
                    for _e in errors:
                        st.error(f"❌ {_e}")
                if saved:
                    st.success(f"✅ บันทึกรูปสำเร็จ {len(saved)} ไฟล์")

    with ph_info:
        st.markdown(
            '<div style="background:linear-gradient(90deg,#1A2E6B 0%,#243E8F 100%);'
            'padding:8px 16px; color:rgba(255,255,255,0.70); font-size:0.78rem; height:100%;'
            'display:flex; align-items:center;">'
            '200MB per file &nbsp;•&nbsp; JPG, PNG, PDF</div>',
            unsafe_allow_html=True
        )

    with ph_toggle:
        arrow = "▲" if st.session_state["boq_photos_expanded"] else "▼"
        if st.button(arrow, key="boq_photos_toggle", help="ยุบ/ขยายส่วนภาพ", use_container_width=True):
            st.session_state["boq_photos_expanded"] = not st.session_state["boq_photos_expanded"]
            st.rerun()

    # ── โหลดรูปจาก disk เสมอ (ไม่หายแม้เปลี่ยนหน้า) ──
    saved_photos = load_photos(p)
    # แยก 3D model ออกจากรูปสถานที่จริง
    photo_3d = next((ph for ph in saved_photos if ph["name"] == "3D_Model.png"), None)
    # ไม่แสดง PNG แปลน/หน้าตัดที่ระบบ gen เอง (โชว์เป็น SVG ในส่วนแบบวาดอยู่แล้ว) — แต่ยังส่งเข้า Drive
    site_photos = [ph for ph in saved_photos
                   if ph["name"] != "3D_Model.png"
                   and not ph["name"].startswith(("01_plan", "02_downpipe"))]

    # แสดงภาพ 3D แยกออกมา
    if photo_3d:
        st.markdown(
            '<div class="ex01-section-bar" style="background:linear-gradient(90deg,#0D2144 0%,#1E3A8A 100%);">'
            '🏠&nbsp;&nbsp;แบบ 3D Isometric (สร้างอัตโนมัติจากการวาด)</div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="ex01-card" style="border-radius:0 0 8px 8px; padding:12px; background:#0A1628;">', unsafe_allow_html=True)
        c3d_col1, c3d_col2 = st.columns([3, 1])
        with c3d_col1:
            st.image(photo_3d["data"], caption="แบบ 3D Isometric (auto-captured)", use_container_width=True)
        with c3d_col2:
            st.markdown(
                '<div style="background:rgba(255,255,255,0.06); border-radius:6px; padding:10px; color:#8BA3CC; font-size:0.78rem;">'
                '<b style="color:#FCD34D;">หมายเหตุ</b><br>'
                'ภาพนี้ถูกบันทึกอัตโนมัติตอนกด 💾 บันทึก<br><br>'
                'เป็นมุมมอง Isometric 3D ของรางน้ำและหลังคาที่วาดไว้</div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    if site_photos and st.session_state["boq_photos_expanded"]:
        st.markdown('<div class="ex01-card" style="border-radius:0 0 8px 8px; padding:12px;">', unsafe_allow_html=True)
        img_cols = st.columns(3)
        for i, photo in enumerate(site_photos[:12]):
            with img_cols[i % 3]:
                if photo["suffix"] in (".jpg", ".jpeg", ".png"):
                    st.image(photo["data"], caption=photo["name"], use_container_width=True)
                else:
                    st.markdown(f'📄 {photo["name"]}')
                if st.button("🗑️", key=f"del_photo_{photo['name']}_{p['id']}", help=f"ลบ {photo['name']}"):
                    delete_photo(p, photo["name"])
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    elif not site_photos and st.session_state["boq_photos_expanded"]:
        if not photo_3d:
            st.info("💡 ยังไม่มีภาพถ่าย อัพโหลดภาพสถานที่จริงได้เลยครับ")

    # ==========================================
    # SECTION 3: แบบวาดแบบหน้าตัด (readonly จาก canvas component)
    # ==========================================
    st.markdown('<div class="ex01-section-bar">📐 &nbsp;แบบวาดแบบหน้าตัด และ แปลนด้านข้างท่อลง</div>', unsafe_allow_html=True)
    st.markdown('<div class="bp-section">', unsafe_allow_html=True)

    import os
    bridge_dir = os.path.join(os.path.dirname(__file__), "..", "utils", "canvas_bridge")
    if os.path.exists(bridge_dir):
        canvas_comp_ro = components.declare_component("canvas_bridge_boq", path=bridge_dir)
        canvas_comp_ro(
            project_name=p.get("name", ""),
            project_id=p.get("id", ""),
            canvas_data=p.get("canvas_data", {}),
            readonly=True,
            key=f"boq_canvas_{p['id']}"
        )
    else:
        st.info("💡 ยังไม่มีข้อมูลแบบวาด กรุณาไปวาดแบบที่หน้าวาดแบบก่อนครับ")

    st.markdown('</div>', unsafe_allow_html=True)

    # SECTION 4: รายการวัสดุอุปกรณ์ (BOQ)
    # ==========================================
    st.markdown('<div class="ex01-section-bar">📦 &nbsp;รายการวัสดุอุปกรณ์ที่ใช้สำหรับติดตั้ง</div>', unsafe_allow_html=True)

    # ── ดึงข้อมูล BOQ จาก canvas ──
    c_boq = p.get("canvas_boq", {})
    if not c_boq and p.get("sides"):
        assess_boq = calc_full_boq(
            p["sides"],
            p.get("corners", {"outer": 0, "inner": 0}),
            calc_downpipe(p.get("wall_height_m", 3), p.get("x1_cm", 0), int(p.get("drain_points", 1))),
            p.get("fascia_type", "flat")
        )
        if assess_boq:
            c_boq = assess_boq["summary"]

    if not c_boq:
        st.warning("⚠️ ไม่พบข้อมูลการประเมิน กรุณากลับไปวาดแบบหน้าตัด หรือคีย์ข้อมูลหน้าประเมิน")
        return

    # ── จำนวนจุดท่อลงทั้งหมด ──
    drain_pts_total = len([ln for ln in main_lines_raw if ln.get("type") == "downpipe"])

    # ── SLS/UTK: คำนวณจาก session_state (input จะอยู่ใน group ท่อลง) ──
    sls_ss_key = f"boq_inst_qty_SLS_{p['id']}"
    if sls_ss_key not in st.session_state:
        st.session_state[sls_ss_key] = 0.0
    sls_qty = int(st.session_state.get(sls_ss_key, 0))
    utk_qty = max(drain_pts_total - sls_qty, 0)

    # ── ค่าความยาว/จำนวนท่อน สำหรับแสดง info ──
    r_length_m    = c_boq.get("gutter_length",   0)
    r_pieces      = c_boq.get("gutter_pieces",   0)
    sror_length_m = c_boq.get("downpipe_length", 0)
    sror_pieces   = c_boq.get("downpipe_pieces", 0)

    # ── Mapping: canvas_boq keys → ค่าจำนวนแต่ละ item code ──
    CANVAS_QTY_MAP = {
        "R":        r_length_m, # หน่วย "เมตร" — ความยาวรวมจาก Canvas
        "SOK":      c_boq.get("downpipe_sok", 0),
        "RVY":      c_boq.get("outer_corners", 0) + c_boq.get("outer_corners135", 0),
        "RVI":      c_boq.get("inner_corners", 0) + c_boq.get("inner_corners135", 0),
        "RSK":      calc_rsk_joints(main_lines_raw, c_boq),
        "OSKR_H":   0,
        "OSK_H":    0,
        "RGT":      c_boq.get("end_caps", 0),
        "KFK":      c_boq.get("hooks", 0) if fascia_type_sel != "เชิงชายเอียง" else 0,
        "SSK":      c_boq.get("hooks", 0) if fascia_type_sel == "เชิงชายเอียง" else 0,
        "SROR":     sror_length_m, # หน่วย "เมตร" — ความยาวรวมจาก Canvas
        "BK":       c_boq.get("downpipe_elbows", 0),
        "GROR":     0,
        "UTK":      utk_qty,
        "FUTK":     0,
        "SSVH":     c_boq.get("downpipe_brackets", 0),
        "SSTV":     0,
        "SLS":      sls_qty,
        "Joint":    0,
        "PVC_loi":  0,
        "PVC_din":  0,
        "backflow": 0,
        "flashing": 0,
        "leafguard":  0,
        "support_ul": 0,
        "silicone":   0,
        "screw_fst":  0,
        "screw_fsbt": 0,
        "labor":    c_boq.get("gutter_length", 0),
    }

    # ── import GROUPS จาก page_prices ──
    try:
        from pages.page_prices import DEFAULT_PRICES as DP, GROUPS as GRP
    except ImportError:
        try:
            from page_prices import DEFAULT_PRICES as DP, GROUPS as GRP
        except ImportError:
            DP = DEFAULT_PRICES
            GRP = {
                "รางน้ำฝน":         ["R", "SOK", "RVY", "RVI", "RSK", "OSKR_H", "OSK_H", "RGT", "KFK", "SSK"],
                "ท่อลง":            ["SROR", "BK", "GROR", "FUTK", "SSVH", "SSTV", "UTK", "SLS"],
                "ตัวยึด":           [],
                "อื่นๆ":            ["Joint"],
                "อุปกรณ์เพิ่มเติม": ["PVC_loi", "PVC_din", "backflow", "flashing",
                                      "leafguard", "support_ul", "silicone", "screw_fst", "screw_fsbt"],
                "ค่าแรง":           ["labor"],
            }

    # ── CSS สำหรับ Section 4 ──
    st.markdown("""
    <style>
    .boq-inst-section {
        background: linear-gradient(90deg, #1A2E6B 0%, #243E8F 100%);
        color: #FFFFFF;
        padding: 9px 16px;
        font-size: 0.92rem; font-weight: 700;
        border-radius: 6px 6px 0 0;
        margin: 18px 0 0 0;
        display: flex; align-items: center; gap: 8px;
        box-shadow: 0 3px 8px rgba(26,46,107,0.18);
    }
    .boq-inst-card {
        background: #FFFFFF;
        border: 1px solid #DDE5F5;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 14px 18px 12px 18px;
        box-shadow: 0 1px 6px rgba(13,33,68,0.06);
        margin-bottom: 0;
    }
    .boq-item-label {
        font-size: 0.78rem; color: #374151; margin-bottom: 3px; line-height: 1.4;
    }
    .boq-item-label b { color: #0D2144; }
    .boq-unit-tag {
        color: #3B82F6; font-size: 0.72rem;
    }
    .boq-suggest-tag {
        color: #9CA3AF; font-size: 0.68rem; margin-left: 4px;
    }
    /* หน่วยที่แสดงหลัง number_input */
    .boq-unit-after {
        margin-top: 8px;
        font-size: 0.82rem;
        color: #64748B;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

    # รายการที่ดึงจาก canvas อัตโนมัติ
    CANVAS_AUTO_KEYS = {"R", "SOK", "RVY", "RVI", "RSK", "RGT", "KFK", "SROR", "BK", "SSVH"}

    GROUP_ICONS = {
        "รางน้ำฝน": "🌧️",
        "ท่อลง": "💧",
        "ตัวยึด": "🔩",
        "อื่นๆ": "🔧",
        "อุปกรณ์เพิ่มเติม": "📦",
        "ค่าแรง": "👷",
    }

    for group_name, keys in GRP.items():
        icon = GROUP_ICONS.get(group_name, "📌")
        st.markdown(f'<div class="boq-inst-section">{icon} &nbsp;{group_name}</div>', unsafe_allow_html=True)
        st.markdown('<div class="boq-inst-card">', unsafe_allow_html=True)

        items = [(k, DP[k]) for k in keys if k in DP and k not in ("UTK", "SLS")]

        for i in range(0, len(items), 3):
            pair = items[i:i+3]
            cols = st.columns(3)
            for j, (item_key, info) in enumerate(pair):
                with cols[j]:
                    has_color = info.get("has_color", False)
                    has_size  = info.get("has_size", False)
                    unit_str  = info["unit"]

                    canvas_qty = CANVAS_QTY_MAP.get(item_key, 0)
                    is_auto    = item_key in CANVAS_AUTO_KEYS

                    # ── Label ──
                    st.markdown(
                        f'<div class="boq-item-label">'
                        f'<b>[{info["code"]}]</b> {info["name"]} '
                        f'<span class="boq-unit-tag">({unit_str})</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    # ── number_input + หน่วย ──
                    qty_key = f"boq_inst_qty_{item_key}_{p['id']}"
                    if qty_key not in st.session_state:
                        st.session_state[qty_key] = float(canvas_qty)

                    inp_col, unit_col = st.columns([3, 1])
                    with inp_col:
                        help_txt = "🔗 ดึงจาก Canvas อัตโนมัติ (แก้ไขได้)" if is_auto and canvas_qty > 0 else None
                        st.number_input(
                            f"qty_{item_key}",
                            min_value=0.0,
                            value=float(canvas_qty) if is_auto else st.session_state[qty_key],
                            step=1.0,
                            key=qty_key,
                            label_visibility="collapsed",
                            help=help_txt,
                        )
                    with unit_col:
                        st.markdown(
                            f'<div class="boq-unit-after">{unit_str}</div>',
                            unsafe_allow_html=True
                        )

                    # ── แสดงความยาวรวม + จำนวนท่อน สำหรับ R และ SROR ──
                    if item_key == "R":
                        # แสดง sub-row: ท่อน R (5ม./ท่อน) ต่อจาก ราง R (เมตร)
                        st.markdown(
                            f'<div class="boq-item-label" style="margin-top:8px;">'
                            f'<b>ท่อน R</b> (5ม./ท่อน) '
                            f'<span class="boq-unit-tag">(ท่อน)</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        rp_inp_col, rp_unit_col = st.columns([3, 1])
                        with rp_inp_col:
                            st.number_input(
                                "r_pieces_display",
                                value=float(r_pieces),
                                min_value=0.0,
                                step=1.0,
                                key=f"boq_r_pieces_display_{p['id']}",
                                label_visibility="collapsed",
                                disabled=True,
                                help="🔗 คำนวณจาก ความยาวรวม ÷ 5 ม./ท่อน (อัตโนมัติ)"
                            )
                        with rp_unit_col:
                            st.markdown('<div class="boq-unit-after">ท่อน</div>', unsafe_allow_html=True)
                    elif item_key == "SROR":
                        # แสดง sub-row: ท่อน SROR (5ม./ท่อน) ต่อจาก ท่อรางน้ำ SROR (เมตร)
                        st.markdown(
                            f'<div class="boq-item-label" style="margin-top:8px;">'
                            f'<b>ท่อน SROR</b> (5ม./ท่อน) '
                            f'<span class="boq-unit-tag">(ท่อน)</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        sp_inp_col, sp_unit_col = st.columns([3, 1])
                        with sp_inp_col:
                            st.number_input(
                                "sror_pieces_display",
                                value=float(sror_pieces),
                                min_value=0.0,
                                step=1.0,
                                key=f"boq_sror_pieces_display_{p['id']}",
                                label_visibility="collapsed",
                                disabled=True,
                                help="🔗 คำนวณจาก ความยาวรวม ÷ 5 ม./ท่อน (อัตโนมัติ)"
                            )
                        with sp_unit_col:
                            st.markdown('<div class="boq-unit-after">ท่อน</div>', unsafe_allow_html=True)

                    # ── ช่องสี ──
                    if has_color:
                        color_k = f"boq_inst_color_{item_key}_{p['id']}"
                        if color_k not in st.session_state:
                            st.session_state[color_k] = ""
                        st.text_input(
                            f"สี — {info['name']}",
                            value=st.session_state[color_k],
                            placeholder="ระบุสี เช่น ขาว / RAL9010 / ดำ",
                            key=color_k,
                            label_visibility="collapsed"
                        )

                    # ── ช่องขนาด ──
                    if has_size:
                        size_k = f"boq_inst_size_{item_key}_{p['id']}"
                        if size_k not in st.session_state:
                            st.session_state[size_k] = ""
                        st.text_input(
                            f"ขนาด (นิ้ว) — {info['name']}",
                            value=st.session_state[size_k],
                            placeholder='เช่น 4", 6", 8"',
                            key=size_k,
                            label_visibility="collapsed"
                        )

        # ── กรอบพิเศษ UTK + SLS + สามทางวาย Y (เฉพาะ group ท่อลง) ──
        if group_name == "ท่อลง" and "UTK" in DP and "SLS" in DP:

            # key สำหรับ SLS และ สามทางวาย Y
            _sls_key  = f"boq_inst_qty_SLS_{p['id']}"
            _ytee_key = f"boq_inst_qty_YTEE_{p['id']}"
            if _ytee_key not in st.session_state:
                st.session_state[_ytee_key] = float(p.get("boq_ytee_qty", 0.0))

            # คำนวณ UTK = total - SLS - สามทางวาย Y (ไม่ติดลบ)
            _sls_now  = int(st.session_state.get(_sls_key,  0))
            _ytee_now = int(st.session_state.get(_ytee_key, 0))
            _utk_now  = max(drain_pts_total - _sls_now - _ytee_now, 0)

            st.markdown(
                f'<div style="border:2px solid #E2E8F0; border-radius:8px; padding:12px 16px; margin-top:12px; background:#F8FAFF;">'
                f'<div style="color:#DC2626; font-weight:700; font-size:0.85rem; margin-bottom:10px;">'
                f'จุดลงท่อรวม {drain_pts_total} จุด &nbsp;'
                f'<span style="color:#6B7A99; font-weight:400; font-size:0.78rem;">'
                f'(UTK + SLS + สามทางวาย Y รวมกันต้องไม่เกิน {drain_pts_total} จุด)</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            utk_info  = DP["UTK"]
            sls_info  = DP["SLS"]
            utk_col_a, sls_col_a, ytee_col_a = st.columns(3)

            # ── UTK (คำนวณอัตโนมัติ) ──
            with utk_col_a:
                st.markdown(
                    f'<div class="boq-item-label"><b>[{utk_info["code"]}]</b> {utk_info["name"]} '
                    f'<span class="boq-unit-tag">({utk_info["unit"]})</span></div>',
                    unsafe_allow_html=True
                )
                utk_inp_col, utk_unit_col = st.columns([3, 1])
                with utk_inp_col:
                    st.markdown(
                        f'<div style="border:1px solid #E2E8F0; border-radius:6px; '
                        f'padding:8px 12px; background:#F1F5F9; font-size:1rem; '
                        f'font-weight:700; color:#0D2144; min-height:38px;">'
                        f'{float(_utk_now):.2f}</div>',
                        unsafe_allow_html=True
                    )
                with utk_unit_col:
                    st.markdown(f'<div class="boq-unit-after">{utk_info["unit"]}</div>', unsafe_allow_html=True)

            # ── SLS (กรอกได้) ──
            with sls_col_a:
                st.markdown(
                    f'<div class="boq-item-label"><b>[{sls_info["code"]}]</b> {sls_info["name"]} '
                    f'<span class="boq-unit-tag">({sls_info["unit"]})</span></div>',
                    unsafe_allow_html=True
                )
                sls_inp_col, sls_unit_col = st.columns([3, 1])
                with sls_inp_col:
                    _sls_max = float(max(drain_pts_total - _ytee_now, 0))
                    st.number_input(
                        "qty_SLS",
                        min_value=0.0,
                        max_value=_sls_max,
                        value=float(min(st.session_state.get(_sls_key, 0), _sls_max)),
                        step=1.0,
                        key=_sls_key,
                        label_visibility="collapsed",
                        help=f"กรอกได้สูงสุด {drain_pts_total} จุด (รวมกับสามทางวาย Y)"
                    )
                with sls_unit_col:
                    st.markdown(f'<div class="boq-unit-after">{sls_info["unit"]}</div>', unsafe_allow_html=True)

            # ── สามทางวาย Y (กรอกได้) ──
            with ytee_col_a:
                st.markdown(
                    '<div class="boq-item-label"><b>[Y-TEE]</b> สามทางวาย Y '
                    '<span class="boq-unit-tag">(ชิ้น)</span></div>',
                    unsafe_allow_html=True
                )
                ytee_inp_col, ytee_unit_col = st.columns([3, 1])
                with ytee_inp_col:
                    _ytee_max = float(max(drain_pts_total - _sls_now, 0))
                    _ytee_val = st.number_input(
                        "qty_YTEE",
                        min_value=0.0,
                        max_value=_ytee_max,
                        value=float(min(st.session_state.get(_ytee_key, 0), _ytee_max)),
                        step=1.0,
                        key=_ytee_key,
                        label_visibility="collapsed",
                        help=f"กรอกได้สูงสุด {drain_pts_total} จุด (รวมกับ SLS)"
                    )
                with ytee_unit_col:
                    st.markdown('<div class="boq-unit-after">ชิ้น</div>', unsafe_allow_html=True)
                # บันทึกลง project
                if p.get("boq_ytee_qty") != _ytee_val:
                    p["boq_ytee_qty"] = _ytee_val
                    save_project(p)

            st.markdown('</div>', unsafe_allow_html=True)  # ปิดกรอบ

        st.markdown('</div>', unsafe_allow_html=True)  # ปิด boq-inst-card

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 4.5: ส่วนลดพิเศษ
    # ==========================================
    _disc_cols = st.columns(2)

    with _disc_cols[0]:
        st.markdown('<div class="boq-inst-section">💸 &nbsp;ส่วนลดพิเศษ</div>', unsafe_allow_html=True)
        st.markdown('<div class="boq-inst-card">', unsafe_allow_html=True)

        _disc_pct_key = f"boq_discount_pct_{p['id']}"
        if _disc_pct_key not in st.session_state:
            st.session_state[_disc_pct_key] = float(p.get("boq_discount_pct", 0.0))

        st.markdown(
            '<div class="boq-item-label"><b>ส่วนลดพิเศษ</b> '
            '<span class="boq-unit-tag">(เปอร์เซ็นต์)</span></div>',
            unsafe_allow_html=True
        )
        _dc1, _dc2 = st.columns([3, 1])
        with _dc1:
            _disc_pct = st.number_input(
                "discount_pct",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state[_disc_pct_key],
                step=0.5,
                key=_disc_pct_key,
                label_visibility="collapsed",
                help="ส่วนลดจากยอดรวมก่อน VAT (0–100%)"
            )
        with _dc2:
            st.markdown('<div class="boq-unit-after">เปอร์เซ็นต์</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="margin-top:8px;">'
            '<span style="color:#DC2626;font-weight:700;font-size:0.82rem;">'
            'ต้องได้รับอนุมัติจากผู้มีอำนาจเท่านั้น*</span>'
            '&nbsp;&nbsp;'
            '<span style="color:#6B7A99;font-size:0.99rem;">'
            '(กรุณากรอกรหัส ของผู้มีอำนาจในการให้ส่วนลด)</span>'
            '</div>',
            unsafe_allow_html=True
        )

        if p.get("boq_discount_pct") != _disc_pct:
            p["boq_discount_pct"] = _disc_pct
            from utils.storage import save_project as _sp
            _sp(p)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 4.7: ปุ่มบันทึกและยืนยันข้อมูลถูกต้อง
    # ==========================================
    _confirm_key = f"boq_show_confirm_popup_{p['id']}"
    if _confirm_key not in st.session_state:
        st.session_state[_confirm_key] = False

    _confirm_done_key = f"boq_confirm_done_{p['id']}"

    # ── ปุ่มหลัก (เปิด popup) ──
    _btn_col1, _btn_col2, _btn_col3 = st.columns([1, 2, 1])
    with _btn_col2:
        if st.button(
            "✅  บันทึกและยืนยันข้อมูลถูกต้อง",
            key=f"boq_confirm_btn_{p['id']}",
            type="primary",
            use_container_width=True,
        ):
            # บันทึกข้อมูลทั้งหมดก่อนแสดง popup
            save_project(p)
            st.session_state[_confirm_key] = True
            st.rerun()

    # ── Popup สีแดงโปร่งแสง (ถ้า state เปิดอยู่) ──
    if st.session_state.get(_confirm_key):
        components.html(f"""<!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap');
        *{{margin:0;padding:0;box-sizing:border-box;}}
        body{{font-family:'Sarabun',sans-serif;background:transparent;}}
        .overlay{{
            position:fixed;inset:0;
            background:rgba(0,0,0,0.45);
            display:flex;align-items:center;justify-content:center;
            z-index:9999;
        }}
        .popup{{
            background:rgba(185,28,28,0.93);
            border-radius:16px;
            padding:32px 36px 28px 36px;
            max-width:560px;
            width:90%;
            box-shadow:0 8px 40px rgba(0,0,0,0.45);
            color:#FFFFFF;
        }}
        .popup-title{{
            font-size:1.15rem;font-weight:700;
            margin-bottom:18px;
            border-bottom:1px solid rgba(255,255,255,0.3);
            padding-bottom:10px;
            letter-spacing:0.3px;
        }}
        .popup ol{{
            padding-left:20px;
            line-height:1.85;
            font-size:0.97rem;
            font-weight:400;
        }}
        .popup ol li{{margin-bottom:10px;}}
        .popup ol li b{{font-weight:700;}}
        .confirm-btn{{
            margin-top:22px;
            width:100%;
            padding:12px;
            background:#FFFFFF;
            color:#B91C1C;
            font-family:'Sarabun',sans-serif;
            font-size:1rem;
            font-weight:700;
            border:none;
            border-radius:10px;
            cursor:pointer;
            letter-spacing:0.3px;
            transition:background 0.15s;
        }}
        .confirm-btn:hover{{background:#FEE2E2;}}
        </style>
        </head><body>
        <div class="overlay" onclick="if(event.target===this)closePopup()">
            <div class="popup">
                <div class="popup-title">⚠️ กรุณาตรวจสอบก่อนยืนยัน</div>
                <ol>
                    <li>กรุณาตรวจสอบ <b>"จุดท่อน้ำทิ้ง"</b> ว่าบ้านลูกค้าต้องการให้ติดตั้ง
                        <b>ท่อน้ำทิ้ง (UTK)</b>, <b>ที่กรองขยะ (SLS)</b>, หรือ <b>สามทางวาย Y</b>
                    </li>
                    <li>กรุณาตรวจสอบ <b>"ตัวยึดท่อ"</b> ว่าบ้านลูกค้าต้องติดตั้ง
                        <b>ตัวยึดท่อธรรมดา (SSVH)</b>, <b>ตัวยึดท่อแบบตะปู (SSTV)</b>,
                        หรือคละกันตามความเหมาะสมหน้างาน<br>
                        <span style="font-size:0.87rem;opacity:0.85;">
                        (ข้อนี้ต้องตรวจสอบจำนวนให้ถูกต้อง ว่าตัวยึดท่อชนิดไหนใช้จำนวนเท่าไหร่)
                        </span>
                    </li>
                </ol>
                <button class="confirm-btn" onclick="closePopup()">
                    ✅&nbsp; ตรวจสอบแล้ว — บันทึกและยืนยันข้อมูลถูกต้อง
                </button>
            </div>
        </div>
        <script>
        function closePopup(){{
            window.parent.postMessage({{type:'boq_confirm_close'}}, '*');
        }}
        </script>
        </body></html>""", height=420, scrolling=False)

        # รับ message จาก JS ผ่าน Streamlit query param workaround
        # ใช้ปุ่ม Streamlit ด้านล่าง popup เป็น fallback สำหรับปิด
        _close_col1, _close_col2, _close_col3 = st.columns([1, 2, 1])
        with _close_col2:
            if st.button(
                "✅ ตรวจสอบแล้ว — ยืนยันและปิด",
                key=f"boq_confirm_close_{p['id']}",
                use_container_width=True,
            ):
                st.session_state[_confirm_key]    = False
                st.session_state[_confirm_done_key] = True
                save_project(p)
                st.success("✅ บันทึกและยืนยันข้อมูลเรียบร้อยแล้ว!")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 5: รายงาน BOQ (พิมพ์ได้ / A4)
    # ==========================================
    st.markdown('<div class="ex01-section-bar">🖨️ &nbsp;รายการวัสดุและแบบ (พิมพ์ได้)</div>', unsafe_allow_html=True)
    st.markdown('<div class="ex01-card">', unsafe_allow_html=True)

    # ── คำนวณราคาจาก CANVAS_QTY_MAP + DEFAULT_PRICES ──
    is_gutter_premium = color_g_sel in ["สีแอนทราไซต์", "สีดำ", "สีเทาแกรไฟต์"]
    is_dp_premium     = color_d_sel in ["สีแอนทราไซต์", "สีดำ", "สีเทาแกรไฟต์"]

    # ── Python ไม่คิดราคาแล้ว: เก็บแค่ "จำนวนอุปกรณ์" (ราคาคิดที่ฝ่ายประสานงาน/GAS) ──
    # สำคัญ: ไม่ตัดอุปกรณ์ที่ราคา = 0 ทิ้งอีกต่อไป → ของครบทุกชิ้นส่งถึงประสานงาน
    report_rows = []
    for item_key, qty_raw in CANVAS_QTY_MAP.items():
        # อ่านจาก session_state (user อาจแก้ไขแล้ว)
        qty_key = f"boq_inst_qty_{item_key}_{p['id']}"
        qty = float(st.session_state.get(qty_key, qty_raw))
        if qty <= 0:
            continue
        if item_key not in DP:
            continue
        info = DP[item_key]
        report_rows.append({
            "code":  info["code"],
            "name":  info["name"],
            "qty":   qty,
            "unit":  info["unit"],
            "price": 0.0,   # ราคาคิดที่ฝ่ายประสานงาน (GAS) เท่านั้น
            "total": 0.0,
        })

    # UTK และ SLS อ่านจาก session_state โดยตรง
    for item_key in ("UTK", "SLS"):
        qty_ss = float(st.session_state.get(f"boq_inst_qty_{item_key}_{p['id']}", 0))
        if qty_ss <= 0 or item_key not in DP:
            continue
        # ลบแถวเดิมออก (ถ้ามี) แล้วใส่ใหม่
        report_rows = [r for r in report_rows if r["code"] != DP[item_key]["code"]]
        info  = DP[item_key]
        report_rows.append({
            "code":  info["code"],
            "name":  info["name"],
            "qty":   qty_ss,
            "unit":  info["unit"],
            "price": 0.0,
            "total": 0.0,
        })

    # ── ส่วนลด %: เก็บค่าไว้ส่งต่อ แต่ "ราคา/VAT" คิดที่ฝ่ายประสานงาน (GAS) ──
    _disc_pct_val = float(st.session_state.get(f"boq_discount_pct_{p['id']}", p.get("boq_discount_pct", 0.0)))
    report_subtotal = 0.0
    report_discount = 0.0
    report_after_discount = 0.0
    report_vat   = 0.0
    report_grand = 0.0

    # ── โหลดโลโก้ base64 (ถ้ามี assets/logo.png) ──
    import os, base64
    _logo_html = ""
    _logo_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "logo.jpg"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "logo.svg"),
        "assets/logo.png", "assets/logo.jpg",
    ]
    for _lp in _logo_candidates:
        if os.path.exists(_lp):
            _ext = os.path.splitext(_lp)[1].lower()
            _mime = "image/svg+xml" if _ext == ".svg" else ("image/jpeg" if _ext in (".jpg",".jpeg") else "image/png")
            with open(_lp, "rb") as _lf:
                _b64 = base64.b64encode(_lf.read()).decode()
            _logo_html = f'<img src="data:{_mime};base64,{_b64}" style="height:48px;max-width:180px;object-fit:contain;" alt="Logo">'
            break
    # ถ้าไม่มีโลโก้ ใช้ข้อความ fallback
    if not _logo_html:
        _logo_html = '<span style="font-size:1.5rem;font-weight:800;color:#1A2E6B;letter-spacing:2px;">💧 AQUALINE</span>'

    # ── สร้าง SVG แบบวาดแปลนหลัก (รางน้ำ + ท่อลง) ──
    def _build_svg_for_report(canvas_data: dict, width_px: int = 714) -> str:
        """สร้าง SVG inline สำหรับใส่ใน HTML report — ใช้ mainLines/housePoly จาก canvas_data จริง"""
        lines = canvas_data.get("mainLines", [])   # ← แก้จาก "lines" → "mainLines"
        poly  = canvas_data.get("housePoly", [])
        if not lines and not poly:
            return '<div style="padding:20px;text-align:center;color:#94A3B8;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:4px;font-size:0.8rem;">ไม่มีข้อมูลแปลน</div>'

        all_x = [pt["x"] for pt in poly]
        all_y = [pt["y"] for pt in poly]
        for l in lines:
            if "x1" in l:
                all_x += [l["x1"], l["x2"]]; all_y += [l["y1"], l["y2"]]
        if not all_x: return ""
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        PAD = 1.5; PPM = 38
        vw = (max_x - min_x + PAD * 2) * PPM
        vh = (max_y - min_y + PAD * 2) * PPM
        scale = width_px / vw if vw > 0 else 1
        svg_h = int(vh * scale)

        def tx(v): return (v - min_x + PAD) * PPM
        def ty(v): return (v - min_y + PAD) * PPM

        els = []
        # grid
        els.append(f'<defs><pattern id="rg" width="{PPM}" height="{PPM}" patternUnits="userSpaceOnUse"><path d="M {PPM} 0 L 0 0 0 {PPM}" fill="none" stroke="#CBD5E1" stroke-width="0.8"/></pattern></defs>')
        els.append(f'<rect width="{vw:.1f}" height="{vh:.1f}" fill="url(#rg)"/>')
        # polygon บ้าน
        if poly:
            pts = " ".join(f"{tx(pt['x']):.1f},{ty(pt['y']):.1f}" for pt in poly)
            els.append(f'<polygon points="{pts}" fill="rgba(148,163,184,0.15)" stroke="#94A3B8" stroke-width="2"/>')
            for pt in poly:
                els.append(f'<circle cx="{tx(pt["x"]):.1f}" cy="{ty(pt["y"]):.1f}" r="3.5" fill="#FCD34D" stroke="#0D2144" stroke-width="1"/>')
        # เส้นหลัก (gutter=น้ำเงิน, downpipe=แดง, house/roof=เทา)
        dp_n = 1
        for ln in lines:
            ltype = ln.get("type", "")
            if ltype in ("house", "roof"):
                # เส้นทรงบ้าน — วาดสีเทาแบบปะ
                if "x1" not in ln: continue
                x1,y1 = tx(ln["x1"]), ty(ln["y1"])
                x2,y2 = tx(ln["x2"]), ty(ln["y2"])
                els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#94A3B8" stroke-width="1.5" stroke-dasharray="4,3"/>')
                continue
            if ltype == "note" or "x1" not in ln: continue
            x1,y1 = tx(ln["x1"]), ty(ln["y1"])
            x2,y2 = tx(ln["x2"]), ty(ln["y2"])
            is_g = ltype == "gutter"
            col  = "#2563EB" if is_g else "#DC2626"
            sw   = "4" if is_g else "3"
            els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>')
            # ป้ายความยาว
            mx,my = (x1+x2)/2, (y1+y2)/2
            length = ((ln["x2"]-ln["x1"])**2+(ln["y2"]-ln["y1"])**2)**0.5
            if length > 0.05:
                tc = "#1D4ED8" if is_g else "#B91C1C"
                els.append(f'<text x="{mx:.1f}" y="{my-6:.1f}" font-family="Sarabun,Arial" font-size="11" font-weight="bold" fill="{tc}" text-anchor="middle">{length:.2f}ม.</text>')
            # วงกลมแดงหมายเลขจุดท่อลง
            if ltype == "downpipe":
                els.append(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="10" fill="#DC2626"/>')
                els.append(f'<text x="{x1:.1f}" y="{y1+3.5:.1f}" font-family="Sarabun,Arial" font-size="10" font-weight="bold" fill="white" text-anchor="middle">{dp_n}</text>')
                dp_n += 1

        content = "".join(els)
        return f'<svg viewBox="0 0 {vw:.1f} {vh:.1f}" width="{width_px}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" style="background:#F8FAFF;border:1px solid #CBD5E1;border-radius:4px;display:block;">{content}</svg>'

    def _build_svg_sub_for_report(sub_data: dict,
                                   width_px: int = 340,
                                   height_px: int = 300,
                                   shared_vw: float = 0,
                                   shared_vh: float = 0) -> str:
        """
        SVG หน้าตัดท่อลง 1 จุด
        shared_vw / shared_vh = viewBox ที่ normalize แล้ว (หา max จากทุกจุด)
        → ทุกช่องใช้ viewBox เดียวกัน ขนาดจึงเท่ากันแน่นอน
        """
        import hashlib as _hl
        sub_lines = sub_data.get("lines", []) if isinstance(sub_data, dict) else sub_data

        # empty fallback
        if not sub_lines:
            return (f'<svg width="{width_px}" height="{height_px}" '
                    f'xmlns="http://www.w3.org/2000/svg" '
                    f'style="border:1px solid #CBD5E1;border-radius:3px;display:block;background:#F8FAFC;">'
                    f'<text x="{width_px//2}" y="{height_px//2}" font-family="Sarabun,Arial" '
                    f'font-size="11" fill="#94A3B8" text-anchor="middle">ไม่มีข้อมูล</text></svg>')

        # bounding box
        all_x, all_y = [], []
        for l in sub_lines:
            t = l.get("type", "")
            if t == "elbow" and "pts" in l:
                for pt in l["pts"]:
                    all_x.append(pt["x"]); all_y.append(pt["y"])
            elif "x1" in l:
                all_x += [l["x1"], l["x2"]]; all_y += [l["y1"], l["y2"]]
        if not all_x:
            return (f'<svg width="{width_px}" height="{height_px}" '
                    f'xmlns="http://www.w3.org/2000/svg" '
                    f'style="border:1px solid #CBD5E1;border-radius:3px;display:block;background:#F8FAFC;"></svg>')

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        PAD = 0.8; PPM = 40
        own_vw = max((max_x - min_x + PAD * 2) * PPM, 40)
        own_vh = max((max_y - min_y + PAD * 2) * PPM, 40)

        # ใช้ shared viewBox ถ้ามี ไม่งั้นใช้ของตัวเอง
        vw = shared_vw if shared_vw > 0 else own_vw
        vh = shared_vh if shared_vh > 0 else own_vh

        # offset ให้ content อยู่กึ่งกลาง viewBox ที่ใหญ่กว่า
        off_x = (vw - own_vw) / 2
        off_y = (vh - own_vh) / 2

        def tx(v): return (v - min_x + PAD) * PPM + off_x
        def ty(v): return (v - min_y + PAD) * PPM + off_y

        _pid = _hl.md5(str(sub_lines).encode()).hexdigest()[:6]

        els = [
            f'<defs><pattern id="sg{_pid}" width="{PPM}" height="{PPM}" patternUnits="userSpaceOnUse">'
            f'<path d="M {PPM} 0 L 0 0 0 {PPM}" fill="none" stroke="#E2E8F0" stroke-width="0.6"/>'
            f'</pattern></defs>',
            f'<rect width="{vw:.1f}" height="{vh:.1f}" fill="#FAFCFF"/>',
            f'<rect width="{vw:.1f}" height="{vh:.1f}" fill="url(#sg{_pid})"/>',
        ]

        for ln in sub_lines:
            ltype = ln.get("type", "")
            if ltype == "downpipe" and "x1" in ln:
                x1,y1 = tx(ln["x1"]), ty(ln["y1"])
                x2,y2 = tx(ln["x2"]), ty(ln["y2"])
                els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                            f'stroke="#DC2626" stroke-width="4" stroke-linecap="round"/>')
                length = ((ln["x2"]-ln["x1"])**2+(ln["y2"]-ln["y1"])**2)**0.5
                if length > 0.05:
                    mx,my = (x1+x2)/2, (y1+y2)/2
                    els.append(f'<text x="{mx+14:.1f}" y="{my:.1f}" font-family="Sarabun,Arial" '
                                f'font-size="12" font-weight="bold" fill="#B91C1C">{length:.2f}ม.</text>')
            elif ltype == "arm" and "x1" in ln:
                x1,y1 = tx(ln["x1"]), ty(ln["y1"])
                x2,y2 = tx(ln["x2"]), ty(ln["y2"])
                els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                            f'stroke="#16A34A" stroke-width="3" stroke-linecap="round"/>')
                length = ((ln["x2"]-ln["x1"])**2+(ln["y2"]-ln["y1"])**2)**0.5
                if length > 0.05:
                    mx,my = (x1+x2)/2, (y1+y2)/2
                    els.append(f'<text x="{mx:.1f}" y="{my-8:.1f}" font-family="Sarabun,Arial" '
                                f'font-size="12" font-weight="bold" fill="#15803D" text-anchor="middle">{length:.2f}ม.</text>')
            elif ltype == "elbow" and "pts" in ln:
                pts = ln["pts"]
                if len(pts) >= 4:
                    px2 = [tx(pt["x"]) for pt in pts]
                    py2 = [ty(pt["y"]) for pt in pts]
                    rx=min(px2); ry=min(py2)
                    rw=max(px2)-min(px2); rh=max(py2)-min(py2)
                    els.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{max(rw,6):.1f}" height="{max(rh,6):.1f}" '
                                f'fill="rgba(220,38,38,0.10)" stroke="#DC2626" stroke-width="2" rx="2"/>')
                    for pt in pts:
                        els.append(f'<circle cx="{tx(pt["x"]):.1f}" cy="{ty(pt["y"]):.1f}" '
                                    f'r="3.5" fill="#F59E0B" stroke="#92400E" stroke-width="1"/>')
                    lbl = ln.get("label", ln.get("name", "ข้องอ"))
                    cx2=sum(px2)/len(px2); cy2=sum(py2)/len(py2)
                    els.append(f'<text x="{cx2:.1f}" y="{cy2+4:.1f}" font-family="Sarabun,Arial" '
                                f'font-size="10" font-weight="bold" fill="#991B1B" text-anchor="middle">{lbl}</text>')

        return (f'<svg viewBox="0 0 {vw:.1f} {vh:.1f}" '
                f'width="{width_px}" height="{height_px}" '
                f'preserveAspectRatio="xMidYMid meet" '
                f'xmlns="http://www.w3.org/2000/svg" '
                f'style="border:1px solid #CBD5E1;border-radius:3px;display:block;background:#FAFCFF;">'
                f'{"".join(els)}</svg>')

    # ── สร้าง HTML ส่วนแบบวาด ──
    _cd = p.get("canvas_data", {})
    _main_svg = _build_svg_for_report(_cd)

    # ── เก็บ SVG เพื่อ export เป็น PNG ส่งไป Drive/ประสานงาน (แปลน + หน้าตัด) ──
    _export_svgs = []
    if _main_svg:
        _export_svgs.append(("01_plan_blueprint.png", _main_svg))

    _sub_apps = _cd.get("subApps", [])
    _sub_svg_html = ""
    _SUB_W, _SUB_H = 340, 300   # fixed size ทุกช่อง

    if _sub_apps:
        # ── pass 1: หา max viewBox dimensions จากทุกจุด ──
        PAD_S = 0.8; PPM_S = 40
        _global_vw = 40.0
        _global_vh = 40.0
        for _sub in _sub_apps:
            _sl = _sub.get("lines", []) if isinstance(_sub, dict) else _sub
            _ax, _ay = [], []
            for _l in _sl:
                _t = _l.get("type", "")
                if _t == "elbow" and "pts" in _l:
                    for _pt in _l["pts"]:
                        _ax.append(_pt["x"]); _ay.append(_pt["y"])
                elif "x1" in _l:
                    _ax += [_l["x1"], _l["x2"]]; _ay += [_l["y1"], _l["y2"]]
            if _ax:
                _vw = max((max(_ax) - min(_ax) + PAD_S * 2) * PPM_S, 40)
                _vh = max((max(_ay) - min(_ay) + PAD_S * 2) * PPM_S, 40)
                _global_vw = max(_global_vw, _vw)
                _global_vh = max(_global_vh, _vh)

        # ── pass 2: render ทุกช่องด้วย shared viewBox ──
        _sub_svg_html = '<div style="margin-top:4px;">'
        for _row_start in range(0, len(_sub_apps), 2):
            _sub_svg_html += '<div style="display:flex;gap:16px;margin-bottom:20px;">'
            for _j in range(2):
                _idx = _row_start + _j
                if _idx >= len(_sub_apps):
                    _sub_svg_html += f'<div style="flex:1;width:{_SUB_W}px;height:{_SUB_H}px;"></div>'
                else:
                    _svg = _build_svg_sub_for_report(
                        _sub_apps[_idx],
                        width_px=_SUB_W,
                        height_px=_SUB_H,
                        shared_vw=_global_vw,
                        shared_vh=_global_vh,
                    )
                    _export_svgs.append((f"02_downpipe_{_idx + 1}.png", _svg))
                    _sub_svg_html += f'''
                    <div style="flex:1;text-align:center;min-width:0;">
                        <div style="font-size:0.78rem;font-weight:700;color:#1E3A8A;
                            margin-bottom:6px;background:#EEF3FF;
                            padding:3px 10px;border-radius:4px;display:inline-block;">
                            จุดที่ {_idx + 1}
                        </div>
                        {_svg}
                    </div>'''
            _sub_svg_html += '</div>'
        _sub_svg_html += '</div>'

    _blueprint_section_html = ""
    if _main_svg or _sub_svg_html:
        _blueprint_section_html = f'''
        <div style="margin-top:24px;padding-top:16px;border-top:2px solid #E4EAF8;">
            <div style="font-size:0.78rem;font-weight:700;color:#1A2E6B;background:#EEF3FF;padding:5px 12px;border-radius:4px;margin-bottom:10px;display:inline-block;">
                📐 แบบวาดแปลนรางน้ำและท่อลง
            </div>
            {f'<div style="margin-bottom:6px;">{_main_svg}</div>' if _main_svg else ''}
            {f'''<div style="margin-top:12px;">
                <div style="font-size:0.72rem;font-weight:700;color:#856404;background:#FFF3CD;padding:3px 10px;border-radius:4px;margin-bottom:8px;display:inline-block;">หน้าตัดท่อลงแต่ละจุด</div>
                {_sub_svg_html}
            </div>''' if _sub_svg_html else ''}
        </div>'''

    # ── render HTML รายงาน A4 (3 แผ่น: ใบเสนอราคา / เงื่อนไข / แบบวาด) ──
    boq_date_str      = p.get("boq_date", datetime.date.today().isoformat())
    # วันที่ยืนราคา = boq_date + 30 วัน
    try:
        _bd = datetime.date.fromisoformat(str(boq_date_str))
        _valid_date = (_bd + datetime.timedelta(days=30)).isoformat()
    except Exception:
        _valid_date = ""

    # ── บริษัทผู้ออกใบเสนอราคา (Seller info — hardcoded ตามเอกสารจริง) ──
    SELLER_NAME    = "บริษัท อาควาไลน์ โปรทาร์เก็ต จำกัด"
    SELLER_ADDR    = "638 ถ.ประเสริฐมนูกิจ แขวงลาดพร้าว เขตลาดพร้าว กรุงเทพฯ 10230"
    SELLER_TAXID   = "0105544022991"
    SELLER_TEL     = "02-570-9009"
    SELLER_EMAIL   = "info@aqualineasia.com"

    # ── build ตาราง rows ──
    rows_html = ""
    for idx, r in enumerate(report_rows, 1):
        bg = "#FFFFFF" if idx % 2 != 0 else "#F8FAFC"
        rows_html += f"""
        <tr style="background:{bg};">
            <td style="text-align:center;padding:8px 6px;border-bottom:1px solid #E5E7EB;font-size:0.88rem;">{idx}</td>
            <td style="padding:8px 6px;border-bottom:1px solid #E5E7EB;font-size:0.88rem;">{r['name']}</td>
            <td style="text-align:right;padding:8px 6px;border-bottom:1px solid #E5E7EB;font-size:0.88rem;">{r['qty']:,.2f}</td>
            <td style="text-align:center;padding:8px 6px;border-bottom:1px solid #E5E7EB;font-size:0.88rem;color:#6B7280;">{r['unit']}</td>
        </tr>"""

    # ── grand total in Thai words (simple) ──
    def _thb_words(amount: float) -> str:
        """แปลงตัวเลขเป็นข้อความภาษาไทยแบบย่อ เช่น 104,640.00 → หนึ่งแสนสี่พันหกร้อยสี่สิบบาทถ้วน"""
        try:
            ones = ["","หนึ่ง","สอง","สาม","สี่","ห้า","หก","เจ็ด","แปด","เก้า"]
            tens_th = ["","สิบ","ยี่สิบ","สามสิบ","สี่สิบ","ห้าสิบ","หกสิบ","เจ็ดสิบ","แปดสิบ","เก้าสิบ"]
            def _u(n):
                if n == 0: return ""
                if n < 10: return ones[n]
                if n < 100:
                    t,o = divmod(n,10)
                    ts = tens_th[t]
                    if t==1: ts="สิบ"
                    return ts + (ones[o] if o else "")
                if n < 1000:
                    h,r = divmod(n,100)
                    return ones[h]+"ร้อย"+(_u(r) if r else "")
                if n < 10000:
                    th,r = divmod(n,1000)
                    return ones[th]+"พัน"+(_u(r) if r else "")
                if n < 100000:
                    ht,r = divmod(n,10000)
                    return ones[ht]+"หมื่น"+(_u(r) if r else "")
                if n < 1000000:
                    hh,r = divmod(n,100000)
                    return ones[hh]+"แสน"+(_u(r) if r else "")
                m,r = divmod(n,1000000)
                return _u(m)+"ล้าน"+(_u(r) if r else "")
            cents = round((amount % 1)*100)
            baht  = int(amount)
            result = _u(baht)+"บาท"
            result += (_u(cents)+"สตางค์") if cents else "ถ้วน"
            return f"({result})"
        except Exception:
            return ""

    _grand_words = _thb_words(report_grand)
    _disc_pct_display = _disc_pct_val

    # ── โหลดรูปสำหรับแทรกในรายงาน (saved_photos และ photo_3d ถูกโหลดไว้แล้วข้างบน) ──
    _photos_html = ""
    _photo3d_html = ""
    try:
        import base64
        _photos_list_html = ""
        for photo in saved_photos:
            if photo["suffix"] not in (".jpg", ".jpeg", ".png"):
                continue
            # ข้าม PNG แปลน/หน้าตัดที่ gen เอง (มีเป็น SVG ในส่วนแบบวาดแล้ว)
            if photo["name"].startswith(("01_plan", "02_downpipe")):
                continue
            if photo["name"] == "3D_Model.png":
                # แสดง 3D แยก section
                b64_3d = base64.b64encode(photo["data"]).decode()
                _photo3d_html = f'''
                <div style="text-align:center;background:#fff;padding:10px;border-radius:4px;margin-top:16px;">
                    <img src="data:image/png;base64,{b64_3d}" style="max-width:100%;max-height:600px;object-fit:contain;border:1px solid #CBD5E1;border-radius:4px;" />
                </div>'''
            else:
                b64_data = base64.b64encode(photo["data"]).decode()
                mime = "image/jpeg" if photo["suffix"] in (".jpg", ".jpeg") else "image/png"
                _photos_list_html += f"""
                <div style="flex: 1; min-width: 300px; max-width: 340px; text-align: center; margin-bottom: 20px; display: inline-block;">
                    <img src="data:{mime};base64,{b64_data}" style="width: 100%; max-height: 250px; object-fit: contain; border: 1px solid #CBD5E1; border-radius: 4px; background: #F8FAFC;" />
                    <div style="font-size: 11px; color: #475569; margin-top: 4px; font-weight: bold;">{photo["name"]}</div>
                </div>
                """
        if _photos_list_html:
            _photos_html = f"""
            <div style="display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; margin-top: 10px;">
                {_photos_list_html}
            </div>
            """
        elif not _photo3d_html:
            _photos_html = '<div style="padding:40px;text-align:center;color:#94A3B8;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:4px;">ไม่มีภาพถ่ายสถานที่จริง</div>'
    except Exception as _pe:
        _photos_html = f'<div style="color:red;padding:20px;">เกิดข้อผิดพลาดในการโหลดรูป: {_pe}</div>'

    # ── คำนวณ height ──
    _blueprint_h = 0
    if _blueprint_section_html:
        _blueprint_h = 620
        if _sub_apps:
            import math as _math
            _num_rows = _math.ceil(len(_sub_apps) / 2)
            _blueprint_h += _num_rows * (_SUB_H + 60)

    _photos_h = 100
    if saved_photos:
        import math as _math
        _site_photos_count = len([ph for ph in saved_photos if ph["suffix"] in (".jpg", ".jpeg", ".png") and ph["name"] != "3D_Model.png" and not ph["name"].startswith(("01_plan", "02_downpipe"))])
        _num_photo_rows = _math.ceil(_site_photos_count / 2) if _site_photos_count > 0 else 0
        _photos_h += _num_photo_rows * 320
        # เพิ่ม height สำหรับ 3D image
        if photo_3d:
            _photos_h += 400

    # 4 pages of A4 (4 * 1123px) + margins (4 * 32px) + body padding (40px) + 20px buffer = 4680px
    _iframe_h = 4680

    # ── เตรียม field ต่างๆ ──
    _q_no        = p.get("name","")
    _booking_no  = p.get("booking_no","")
    _po_ref      = p.get("po_ref","")
    _salesperson = p.get("salesperson","")
    _sp_tel      = p.get("salesperson_tel","")
    _sp_email    = p.get("salesperson_email","")
    # บังคับเป็น str ทุกตัว — บางค่า (taxid/phone) อาจมาเป็นตัวเลขจาก JSON ทำให้ + กับ string พัง
    _cust_name   = str(p.get("customer","—") or "—")
    _cust_addr   = str(p.get("address","") or "")
    _cust_taxid  = str(p.get("customer_taxid","") or "")
    _cust_phone  = str(p.get("phone","") or "")
    _cust_contact= str(p.get("customer","") or "")
    _agency      = str(p.get("angency_name","") or "")
    _proj_site   = str(p.get("project_name_site","") or "")
    _install_loc = str(p.get("install_location","") or "")
    _job_type    = p.get("job_type","")
    _payment_method = p.get("payment_method","เงินสด")
    _assessor    = p.get("boq_assessor","")
    _sales_name  = p.get("boq_sales","")
    _color_g     = p.get("boq_color_gutter","")
    _color_d     = p.get("boq_color_dp","")

    report_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,300;0,400;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Sarabun',sans-serif; background:#E8ECF4; padding:20px 12px; font-size:13px; color:#111; }}
.page {{
    background:white; width:794px; min-height:1123px; margin:0 auto 32px auto;
    padding:20px 30px 20px 30px;
    box-shadow:0 2px 16px rgba(0,0,0,0.13);
    position:relative;
}}
/* ── HEADER ── */
.hdr-wrap {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px; }}
.hdr-left {{ display:flex; align-items:flex-start; gap:12px; }}
.hdr-seller {{ font-size:11.5px; line-height:1.55; color:#222; }}
.hdr-seller b {{ font-size:12.5px; }}
.hdr-right {{ text-align:right; font-size:11px; color:#444; line-height:1.6; }}
.stamp-box {{
    border:2px solid #1A2E6B; padding:3px 10px; font-size:11px; font-weight:700;
    color:#1A2E6B; letter-spacing:2px; writing-mode:vertical-rl; text-orientation:upright;
    height:70px; display:flex; align-items:center; justify-content:center; margin-left:12px;
}}
.doc-title {{ font-size:32px; font-weight:800; color:#111; margin:2px 0 6px 0; letter-spacing:1px; }}
/* ── BUYER BLOCK ── */
.buyer-label {{ font-size:11px; font-weight:700; color:#555; margin-bottom:2px; }}
.buyer-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0; margin-bottom:8px; }}
.buyer-left {{ padding-right:16px; }}
.buyer-right {{ border-left:1px solid #DDD; padding-left:14px; font-size:11.5px; line-height:1.65; }}
.info-row {{ display:flex; gap:6px; font-size:11.5px; line-height:1.65; }}
.info-label {{ color:#555; min-width:100px; flex-shrink:0; }}
.info-val {{ color:#111; font-weight:500; }}
/* ── TABLE ── */
table.boq {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:3px; }}
table.boq th {{
    background:#1A2E6B; color:white; padding:6px 7px;
    font-weight:700; font-size:11.5px;
}}
table.boq th.r {{ text-align:right; }}
table.boq th.c {{ text-align:center; }}
table.boq th.l {{ text-align:left; }}
table.boq td {{ padding:5px 7px; border-bottom:1px solid #E5E7EB; vertical-align:top; }}
table.boq td.r {{ text-align:right; }}
table.boq td.c {{ text-align:center; color:#555; }}
table.boq tr.even td {{ background:#F9FAFB; }}
/* sub-item indent */
table.boq td.sub {{ padding-left:20px; color:#444; font-size:11.5px; }}
/* ── TOTALS ── */
.totals-wrap {{ display:flex; justify-content:flex-end; margin-top:8px; }}
.totals-box {{ width:300px; font-size:12px; }}
.tot-row {{ display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #EEE; }}
.tot-grand {{
    display:flex; justify-content:space-between; align-items:center;
    padding:7px 12px; margin-top:5px;
    background:#1A2E6B; border-radius:4px;
    color:white; font-weight:800; font-size:13px;
}}
.tot-grand .amt {{ color:#FFD700; font-size:14px; }}
.grand-words {{ font-size:10.5px; color:#555; text-align:right; margin-top:3px; font-style:italic; }}
/* ── DIVIDER ── */
.divider {{ border:none; border-top:2px solid #1A2E6B; margin:10px 0 8px 0; }}
hr.thin {{ border:none; border-top:1px solid #DDD; margin:7px 0; }}
/* ── PAGE 2: เงื่อนไข ── */
.p2-section {{ margin-bottom:9px; }}
.p2-section h3 {{ font-size:12px; font-weight:700; color:#1A2E6B; margin-bottom:4px; border-bottom:1px solid #DDE5F5; padding-bottom:2px; }}
.p2-section ol, .p2-section ul {{ padding-left:18px; font-size:11px; line-height:1.65; color:#222; margin:0; }}
.p2-section ol li, .p2-section ul li {{ margin-bottom:1px; }}
.p2-section p {{ font-size:11px; line-height:1.5; color:#222; margin-bottom:3px; }}
.bank-box {{ background:#F0F4FF; border:1px solid #C8D5F0; border-radius:4px; padding:5px 10px; font-size:11px; line-height:1.6; margin:3px 0 6px 0; }}
.dist-table {{ width:100%; border-collapse:collapse; font-size:10.5px; margin-top:4px; }}
.dist-table th {{ background:#1A2E6B; color:white; padding:4px 6px; font-size:10.5px; }}
.dist-table td {{ padding:3px 6px; border-bottom:1px solid #EEE; }}
.dist-table tr:nth-child(even) td {{ background:#F9FAFB; }}
/* ── SIG BOX ── */
.sig-grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:0; margin-top:10px; border:1px solid #999; }}
.sig-cell {{ padding:7px 10px 18px 10px; border-right:1px solid #999; font-size:11px; }}
.sig-cell:last-child {{ border-right:none; }}
.sig-cell .sig-title {{ font-weight:700; margin-bottom:2px; }}
.sig-cell .sig-date {{ color:#555; font-size:10.5px; margin-top:2px; }}
/* ── PAGE 3: แบบวาด ── */
.p3-title {{ font-size:15px; font-weight:700; color:#1A2E6B; margin-bottom:12px; padding-bottom:6px; border-bottom:2px solid #1A2E6B; }}
/* ── PAGE NUMBER ── */
.page-num {{ position:absolute; bottom:12px; right:20px; font-size:11px; color:#9CA3AF; }}
/* ── PRINT ── */
@media print {{
    body {{ background:white; padding:0; }}
    .page {{ box-shadow:none; margin:0; width:100%; min-height:297mm; padding:14mm 12mm; page-break-after:always; }}
    .page:last-child {{ page-break-after:auto; }}
    @page {{ size:A4; margin:0; }}
}}

</style>
<script>
function doPrint() {{
    window.print();
}}
</script>
</head><body>

<!-- ══════════════════════════════════════════════
     แผ่น 1 — รายการวัสดุและแบบ
══════════════════════════════════════════════ -->
<div class="page">

    <!-- Header: โลโก้ + ข้อมูลบริษัท -->
    <div class="hdr-wrap">
        <div class="hdr-left">
            {_logo_html}
            <div class="hdr-seller">
                <b>{SELLER_NAME}</b><br>
                {SELLER_ADDR}<br>
                เลขที่ประจำตัวผู้เสียภาษี : {SELLER_TAXID}<br>
                โทรศัพท์ : {SELLER_TEL} &nbsp; E-mail : {SELLER_EMAIL}
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div class="hdr-right">
                {boq_date_str}<br>
                {_q_no}
            </div>
        </div>
    </div>

    <hr class="divider">

    <!-- ผู้ซื้อ + ชื่อเอกสาร -->
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
        <div class="buyer-label" style="font-size:15px;font-weight:700;color:#111;">ผู้ซื้อ</div>
        <div class="doc-title" style="font-size:26px;">รายการวัสดุและแบบ</div>
    </div>

    <!-- Buyer grid -->
    <div class="buyer-grid">
        <!-- ซ้าย: ข้อมูลลูกค้า -->
        <div class="buyer-left">
            <div style="font-size:13.5px;font-weight:700;color:#111;margin-bottom:2px;">{_agency if _agency else _cust_name}</div>
            <div style="font-size:12px;color:#333;line-height:1.7;margin-bottom:4px;">{_cust_addr}</div>
            {'<div class="info-row"><span class="info-label">เลขที่ประจำตัวผู้เสียภาษี :</span><span class="info-val">' + _cust_taxid + '</span></div>' if _cust_taxid else ''}
            {'<div class="info-row"><span class="info-label">ชื่อผู้ติดต่อ</span><span class="info-val">' + _cust_contact + '</span></div>' if _cust_contact else ''}
            {'<div class="info-row"><span class="info-label">โทรศัพท์</span><span class="info-val">' + _cust_phone + '</span></div>' if _cust_phone else ''}
            <div class="info-row"><span class="info-label">E-mail</span><span class="info-val">–</span></div>
            <div class="info-row"><span class="info-label">วิธีจัดส่ง</span><span class="info-val">จัดส่ง</span></div>
            {'<div class="info-row"><span class="info-label">ที่อยู่จัดส่ง</span><span class="info-val">' + _install_loc + '</span></div>' if _install_loc else ''}
            {'<div class="info-row"><span class="info-label">โครงการ</span><span class="info-val">' + _proj_site + '</span></div>' if _proj_site else ''}
        </div>
        <!-- ขวา: เลขเอกสาร + salesperson -->
        <div class="buyer-right">
            <div class="info-row"><span class="info-label">เลขที่</span><span class="info-val">{_q_no}</span></div>
            <div class="info-row"><span class="info-label">วันที่</span><span class="info-val">{boq_date_str}</span></div>
            <div class="info-row"><span class="info-label">พนักงานขาย</span><span class="info-val">{_salesperson}</span></div>
            {'<div class="info-row"><span class="info-label">โทรศัพท์</span><span class="info-val">' + _sp_tel + '</span></div>' if _sp_tel else ''}
            {'<div class="info-row"><span class="info-label">E-mail</span><span class="info-val">' + _sp_email + '</span></div>' if _sp_email else ''}
        </div>
    </div>

    <hr class="thin">

    <!-- ตาราง BOQ -->
    <table class="boq">
        <thead>
            <tr>
                <th class="c" style="width:34px;">ลำดับ</th>
                <th class="l">รายละเอียด</th>
                <th class="r" style="width:100px;">จำนวน</th>
                <th class="c" style="width:100px;">หน่วย</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>

    <br>

    <!-- ลายเซ็น -->
    <div class="sig-grid" style="margin-top:15px;">
        <div class="sig-cell">
            <div class="sig-title">ผู้เสนอราคา</div>
            <div style="margin-top:35px;border-bottom:1px dotted #999;width:140px;"></div>
            <div style="margin-top:4px;font-size:11px;">{_assessor if _assessor else '..........................................'}</div>
            <div class="sig-date">{boq_date_str}</div>
        </div>
        <div class="sig-cell">
            <div class="sig-title">ผู้อนุมัติแบบ</div>
            <div style="margin-top:35px;border-bottom:1px dotted #999;width:140px;"></div>
            <div style="margin-top:4px;font-size:11px;">{_sales_name if _sales_name else '................................'}</div>
            <div class="sig-date">{boq_date_str}</div>
        </div>
        <div class="sig-cell">
            <div class="sig-title">ผู้ยืนยันข้อมูล</div>
            <div style="margin-top:35px;border-bottom:1px dotted #999;width:140px;"></div>
            <div style="margin-top:4px;font-size:11px;">................................</div>
            <div class="sig-date">&nbsp; &nbsp; &nbsp; / &nbsp; &nbsp; &nbsp;</div>
        </div>
    </div>

    <div class="page-num">Page 1/4</div>
</div>

<!-- ══════════════════════════════════════════════
     แผ่น 2 — แบบวาดแปลนรางน้ำและท่อลง
══════════════════════════════════════════════ -->
<div class="page">

    <!-- header ซ้ำ -->
    <div class="hdr-wrap" style="margin-bottom:6px;">
        <div class="hdr-left">
            {_logo_html}
            <div class="hdr-seller">
                <b>{SELLER_NAME}</b><br>
                {SELLER_ADDR}
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div class="hdr-right">{boq_date_str}<br>{_q_no}</div>
        </div>
    </div>
    <hr class="divider">

    <div class="p3-title">📐 แบบวาดแปลนรางน้ำและท่อลง</div>

    <!-- ข้อมูลโครงการย่อ -->
    <div style="display:flex;gap:32px;margin-bottom:14px;font-size:12px;color:#444;">
        <div><span style="color:#888;">โครงการ: </span><b>{_proj_site}</b></div>
        <div><span style="color:#888;">สีราง: </span>{_color_g}</div>
        <div><span style="color:#888;">สีท่อ: </span>{_color_d}</div>
    </div>

    {f'<div style="margin-bottom:12px;">{_main_svg}</div>' if _main_svg else '<div style="padding:32px;text-align:center;color:#94A3B8;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:4px;">ไม่มีข้อมูลแปลน</div>'}

    {f"""<div style="margin-top:16px;">
        <div style="font-size:12px;font-weight:700;color:#856404;background:#FFF3CD;padding:4px 12px;border-radius:4px;margin-bottom:10px;display:inline-block;">หน้าตัดท่อลงแต่ละจุด</div>
        {_sub_svg_html}
    </div>""" if _sub_svg_html else ''}

    <div class="page-num">Page 2/4</div>
</div>

<!-- ══════════════════════════════════════════════
     แผ่น 3 — ภาพถ่ายสถานที่จริง
══════════════════════════════════════════════ -->
<div class="page">

    <!-- header ซ้ำ -->
    <div class="hdr-wrap" style="margin-bottom:6px;">
        <div class="hdr-left">
            {_logo_html}
            <div class="hdr-seller">
                <b>{SELLER_NAME}</b><br>
                {SELLER_ADDR}
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div class="hdr-right">{boq_date_str}<br>{_q_no}</div>
        </div>
    </div>
    <hr class="divider">

    <div class="p3-title">📸 ภาพถ่ายสถานที่จริง</div>

    <!-- ข้อมูลโครงการย่อ -->
    <div style="display:flex;gap:32px;margin-bottom:14px;font-size:12px;color:#444;">
        <div><span style="color:#888;">โครงการ: </span><b>{_proj_site}</b></div>
    </div>

    <div style="margin-top:10px;">
        {_photos_html}
    </div>

    <div class="page-num">Page 3/4</div>
</div>

<!-- ══════════════════════════════════════════════
     แผ่น 4 — แบบ 3D Isometric
══════════════════════════════════════════════ -->
<div class="page">

    <!-- header ซ้ำ -->
    <div class="hdr-wrap" style="margin-bottom:6px;">
        <div class="hdr-left">
            {_logo_html}
            <div class="hdr-seller">
                <b>{SELLER_NAME}</b><br>
                {SELLER_ADDR}
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div class="hdr-right">{boq_date_str}<br>{_q_no}</div>
        </div>
    </div>
    <hr class="divider">

    <div class="p3-title">🏠 แบบ 3D Isometric (สร้างอัตโนมัติจากการวาด)</div>

    <!-- ข้อมูลโครงการย่อ -->
    <div style="display:flex;gap:32px;margin-bottom:14px;font-size:12px;color:#444;">
        <div><span style="color:#888;">โครงการ: </span><b>{_proj_site}</b></div>
    </div>

    <div style="margin-top:10px;">
        {_photo3d_html if _photo3d_html else '<div style="padding:60px;text-align:center;color:#94A3B8;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:4px;">ยังไม่มีภาพ 3D — กรุณากลับหน้าวาดแบบ แล้วกด 💾 บันทึก เพื่อบันทึกภาพ 3D</div>'}
    </div>

    <div class="page-num">Page 4/4</div>
</div>

</body></html>"""

    # ใช้ components.html() — render HTML จริง
    components.html(report_html, height=_iframe_h, scrolling=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # ACTION BUTTONS (Footer Bar)
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="ex01-card" style="padding:12px 18px;">', unsafe_allow_html=True)
    a1, a2, a3, a4, a5 = st.columns(5)

    with a1:
        if st.button("💾 บันทึกและยืนยันข้อมูลถูกต้อง", type="primary", use_container_width=True):
            if not p.get("canvas_boq"):
                toast("กรุณาวาดแปลนและคำนวณ BOQ ก่อนบันทึก", type="warning")
            else:
                save_with_feedback(
                    lambda: save_project(p),
                    success_msg="บันทึกเอกสารสำเร็จ!",
                    error_msg="บันทึกไม่สำเร็จ"
                )
                # Issue 2 (test) — เอาป๊อปอัพ "จัดคิวช่าง InstallQ" ออก; แค่บันทึกสำเร็จก็พอ

    with a2:
        # ══════════════════════════════════════════════════════
        # PDF EXPORT — ใช้ HTTP server ให้ Playwright โหลด Google Fonts ได้
        # + ปุ่ม HTML ดาวน์โหลดแยกเสมอ
        # ══════════════════════════════════════════════════════
        _q_no_safe = p.get("quotation_no", p.get("name", "BOQ")).replace("/", "-").replace(" ", "_")

        if st.button("📥 Save as PDF", use_container_width=True):
            import tempfile, os as _os, threading, time as _time

            _pdf_bytes = None
            _pdf_error = ""

            with st.spinner("⏳ กำลังสร้าง PDF..."):

                # ─── วิธีที่ 1: Playwright + HTTP server (font โหลดได้ 100%) ───
                try:
                    from playwright.sync_api import sync_playwright
                    import http.server, socketserver, socket

                    # เขียน HTML ลง temp file
                    with tempfile.NamedTemporaryFile(
                        suffix=".html", mode="w", encoding="utf-8", delete=False, dir=tempfile.gettempdir()
                    ) as _tf:
                        _tf.write(report_html)
                        _tmp_html = _tf.name
                    _tmp_pdf = _tmp_html.replace(".html", ".pdf")
                    _html_filename = _os.path.basename(_tmp_html)
                    _serve_dir = _os.path.dirname(_tmp_html)

                    # หา port ว่าง
                    with socket.socket() as _s:
                        _s.bind(("", 0))
                        _free_port = _s.getsockname()[1]

                    # เปิด HTTP server ชั่วคราวใน thread แยก
                    class _SilentHandler(http.server.SimpleHTTPRequestHandler):
                        def __init__(self, *a, **kw):
                            super().__init__(*a, directory=_serve_dir, **kw)
                        def log_message(self, *a):
                            pass  # ปิด log

                    _httpd = socketserver.TCPServer(("", _free_port), _SilentHandler)
                    _httpd.allow_reuse_address = True
                    _t = threading.Thread(target=_httpd.serve_forever, daemon=True)
                    _t.start()

                    try:
                        with sync_playwright() as _pw:
                            # auto-install chromium ถ้ายังไม่มี (รองรับ PATH ไม่เจอ playwright)
                            try:
                                _browser = _pw.chromium.launch()
                            except Exception as _le:
                                if "Executable doesn't exist" in str(_le):
                                    import subprocess as _sp
                                    _sp.run(
                                        ["python", "-m", "playwright", "install", "chromium"],
                                        check=True
                                    )
                                    _browser = _pw.chromium.launch()
                                else:
                                    raise
                            _pg = _browser.new_page()
                            # เปิดผ่าน http:// → Playwright โหลด Google Fonts ได้ปกติ
                            _pg.goto(
                                f"http://localhost:{_free_port}/{_html_filename}",
                                wait_until="networkidle",
                                timeout=30000,
                            )
                            # รอ font render
                            _pg.wait_for_timeout(2000)
                            _pg.pdf(
                                path=_tmp_pdf,
                                format="A4",
                                print_background=True,
                                margin={"top": "0mm", "right": "0mm",
                                        "bottom": "0mm", "left": "0mm"},
                            )
                            _browser.close()
                    finally:
                        _httpd.shutdown()

                    with open(_tmp_pdf, "rb") as _pf:
                        _pdf_bytes = _pf.read()

                    _os.unlink(_tmp_html)
                    _os.unlink(_tmp_pdf)

                except ImportError:
                    _pdf_error = "ไม่พบ Playwright"
                except Exception as _e1:
                    _pdf_error = str(_e1)
                    # cleanup ถ้ายังมี temp file ค้างอยู่
                    try:
                        if "_tmp_html" in dir() and _os.path.exists(_tmp_html):
                            _os.unlink(_tmp_html)
                    except Exception:
                        pass

            # ─── แสดงผล ───
            if _pdf_bytes:
                st.download_button(
                    label="💾 คลิกเพื่อดาวน์โหลด PDF",
                    data=_pdf_bytes,
                    file_name=f"{_q_no_safe}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                toast("✅ สร้าง PDF สำเร็จ!", type="success")
            else:
                with st.expander("❌ สร้าง PDF ไม่สำเร็จ — คลิกดูรายละเอียด", expanded=True):
                    st.error(_pdf_error)
                    st.info(
                        "**วิธีแก้:**\n\n"
                        "```\npip install playwright\nplaywright install chromium\n```"
                    )

        # ─── ปุ่ม HTML — แสดงเสมอ เปิดด้วย Chrome แล้ว Ctrl+P ───
        st.download_button(
            label="🌐 ดาวน์โหลด HTML",
            data=report_html.encode("utf-8"),
            file_name=f"{_q_no_safe}.html",
            mime="text/html",
            use_container_width=True,
            help="เปิดด้วย Chrome → Ctrl+P → Save as PDF (font ไทยแสดงครบเพราะมี internet)",
        )
    with a3:
        # ── Print via iframe.contentWindow.print() — ไม่ต้องเปิด tab ใหม่ ไม่ถูก popup block ──
        import base64 as _b64p

        # inject ปุ่มและ style print ลงใน HTML
        _print_inject = (
            '<style>'
            '@media print{'
            'body{background:white!important;padding:0!important;}'
            '.page{box-shadow:none!important;margin:0!important;}'
            '#_pbar{display:none!important;}'
            '}'
            '</style>'
            '<div id="_pbar" style="position:fixed;top:0;left:0;right:0;z-index:9999;'
            'background:#1A2E6B;padding:8px 20px;display:flex;gap:12px;align-items:center;'
            'font-family:Sarabun,sans-serif;">'
            '<span style="color:white;font-size:13px;">กดปุ่มด้านขวาเพื่อ <b>Save as PDF</b></span>'
            '<button onclick="window.print()" '
            'style="background:#22C55E;color:#fff;border:none;padding:7px 22px;'
            'border-radius:6px;font-size:14px;cursor:pointer;font-weight:700;">'
            '🖨️ พิมพ์ / Save as PDF</button>'
            '</div>'
            '<div style="height:52px"></div>'
        )
        _printable_html = report_html.replace("</body>", f"{_print_inject}</body>")
        _html_b64 = _b64p.b64encode(_printable_html.encode("utf-8")).decode()

        # srcdoc ผ่าน data URI — ไม่ต้องเปิด tab ใหม่ ไม่ถูก popup block
        # ปุ่ม "พิมพ์" ข้างใน iframe จะเรียก window.print() ของ iframe เอง = พิมพ์เฉพาะรายงาน
        _iframe_html = f"""
<html><body style="margin:0;padding:0;background:#E8ECF4;">
<iframe id="rpt"
    src="data:text/html;base64,{_html_b64}"
    style="width:100%;height:calc(100vh - 8px);border:none;display:block;">
</iframe>
</body></html>"""

        if st.button("🖨️ พิมพ์ / Save as PDF", use_container_width=True,
                     help="แสดง preview พร้อมปุ่มพิมพ์ — กด 'พิมพ์ / Save as PDF' ในหน้านั้น"):
            components.html(_iframe_html, height=1200, scrolling=False)
            st.info("👆 กดปุ่ม **🖨️ พิมพ์ / Save as PDF** แถบสีเขียวด้านบนรายงาน")
    with a4:
        # ─── ปุ่มส่งงานเข้าฝ่ายประสานงาน ───
        is_sent = p.get("sent_to_coord", False)
        # Issue 5 — ส่งซ้ำได้เพื่ออัปเดตงานเดิม (ล็อกเฉพาะตอนยังไม่มี BOQ)
        btn_label = "🔄 อัปเดตงานให้ประสานงาน" if is_sent else "🚀 ส่งงานให้ประสานงาน"
        disable_send = not p.get("canvas_boq")
        if st.button(btn_label, use_container_width=True, disabled=disable_send, type="secondary" if is_sent else "primary", key="btn_send_coord"):
            coord_url = st.secrets.get("coordinator", {}).get("webapp_url", "")
            if not coord_url:
                st.error("❌ ยังไม่ได้ตั้งค่า webapp_url ใน secrets.toml")
            else:
                with st.spinner("⏳ กำลังส่งข้อมูลไปยังฝ่ายประสานงาน..."):
                    try:
                        import requests as _rq, json as _json
                        items_payload = []
                        for r in report_rows:
                            items_payload.append({
                                "productId": r["code"],
                                "productName": r["name"],
                                "qty": r["qty"],
                                "unit": r["unit"],
                                "unitPrice": 0.0,   # Issue 2 — ราคาคิดที่ฝ่ายประสานงาน (GAS) เท่านั้น; Python ส่งแค่ qty
                                "laborPrice": 0.0,
                                "discount": 0.0,
                                "remarks": ""
                            })
                        
                        # ── render แปลน + หน้าตัดท่อลง เป็น PNG เซฟลง photos/ ก่อนรวม payload ──
                        try:
                            _bp_saved, _bp_err = export_blueprint_images(p, _export_svgs)
                            if _bp_saved:
                                st.caption(f"🖼️ แนบภาพแบบวาด {len(_bp_saved)} รูป")
                            elif _bp_err:
                                st.warning(f"⚠️ แปลงภาพแบบวาดไม่สำเร็จ: {_bp_err} (ส่งข้อมูลอื่นต่อ)")
                        except Exception as _bpe:
                            st.warning(f"⚠️ แปลงภาพแบบวาดไม่สำเร็จ: {_bpe} (ส่งข้อมูลอื่นต่อ)")

                        import base64
                        uploaded_photos = load_photos(p)
                        photos_payload = []
                        for photo in uploaded_photos:
                            photos_payload.append({
                                "name": photo["name"],
                                "content_b64": base64.b64encode(photo["data"]).decode("utf-8"),
                                "suffix": photo["suffix"]
                            })

                        payload = {
                            "quoteId": p.get("id", ""),  # รหัส QO-GUT เดิมจากประสานงาน -> doPost จะอัปเดตแถวเดิม ไม่สร้างซ้ำ
                            "creator": st.session_state.get("user_display", "Python Gutter App"),
                            "projectName": p.get("project_name_site", p.get("name", "โครงการรางน้ำฝน")),
                            "customerName": p.get("customer", "-"),
                            "totalAmount": 0,   # Issue 2 — ไม่ส่งราคา; ฝ่ายประสานงานกดคำนวณราคาเองที่ GAS
                            "specialInstructions": p.get("special_notes", ""),
                            "items": items_payload,
                            "projectJson": _json.dumps(p, ensure_ascii=False),
                            "photos": photos_payload
                        }
                        
                        _resp = _rq.post(
                            coord_url,
                            data=_json.dumps(payload),
                            headers={"Content-Type": "application/json"},
                            timeout=120   # doPost เซฟรูปหลายไฟล์ลง Drive + ตั้งแชร์ + เขียน meta อาจนานเกิน 15 วิ
                        )
                        _res_json = _resp.json()
                        if _res_json.get("ok"):
                            p["sent_to_coord"] = True
                            p["quote_id"] = _res_json.get("quoteId")
                            save_project(p)
                            st.success(f"🚀 ส่งข้อมูลเข้าระบบประสานงานเรียบร้อย! ({_res_json.get('quoteId')})")
                            st.rerun()
                        else:
                            st.error(f"❌ เซิร์ฟเวอร์ตอบกลับผิดพลาด: {_res_json.get('error', 'ไม่ทราบสาเหตุ')}")
                    except Exception as ex:
                        st.error(f"❌ เชื่อมต่อระบบประสานงานไม่ได้: {ex}")

    with a5:
        st.button("✏️ กลับไปแก้ไขแปลน",
                  on_click=lambda: st.session_state.update({"current_page": "canvas"}),
                  use_container_width=True)

    # Issue 4 — ลบปุ่ม "💰 จัดการเรทราคาตั้งต้น" (ราคาคิดที่ GAS Admin เท่านั้น)

    st.markdown('</div>', unsafe_allow_html=True)
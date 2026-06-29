"""
หน้าตั้งราคาอุปกรณ์ — ราคาอ้างอิงจากใบราคา Aqualine Lindab ปัจจุบัน
หน่วย: บาท (ราคาไม่รวม VAT 7%)

แก้ปัญหา widget cache: ใช้ key=f"price_input_{key}_{tier}" 
เพื่อบังคับ Streamlit สร้าง widget ใหม่ทุกครั้งที่ tier เปลี่ยน
"""
import streamlit as st
from pages.page_login import touch_session

DEFAULT_PRICES = {
    # ── รางน้ำฝน ──
    "R":       {"name": "ราง (R)",                             "unit": "เมตร", "price_std": 285,  "price_premium": 385,  "code": "R"},
    "SOK":     {"name": "ท่อเชื่อมรางน้ำ (SOK)",               "unit": "ชิ้น", "price_std": 275,  "price_premium": 360,  "code": "SOK"},
    "RVY":     {"name": "รางน้ำมุมด้านนอก (RVY)",              "unit": "ชิ้น", "price_std": 750,  "price_premium": 990,  "code": "RVY"},
    "RVI":     {"name": "รางน้ำมุมด้านใน (RVI)",               "unit": "ชิ้น", "price_std": 750,  "price_premium": 990,  "code": "RVI"},
    "RSK":     {"name": "ข้อต่อรางน้ำ (RSK)",                  "unit": "ชิ้น", "price_std": 180,  "price_premium": 240,  "code": "RSK"},
    "OSKR_H":  {"name": "แผ่นป้องกันน้ำสันมุมตรง (OSKR-H)",   "unit": "ชิ้น", "price_std": 850,  "price_premium": 1100, "code": "OSKR-H"},
    "OSK_H":   {"name": "แผ่นป้องกันน้ำสันมุมใน (OSK-H)",     "unit": "ชิ้น", "price_std": 1250, "price_premium": 1650, "code": "OSK-H"},
    "RGT":     {"name": "ตัวปิดปลายรางน้ำ (RGT)",              "unit": "ชิ้น", "price_std": 90,   "price_premium": 120,  "code": "RGT"},
    "KFK":     {"name": "ตะขอวางรางน้ำ (KFK)",                 "unit": "ชิ้น", "price_std": 130,  "price_premium": 170,  "code": "KFK"},
    "SSK":     {"name": "ตะขอปรับองศา (SSK)",                  "unit": "ชิ้น", "price_std": 130,  "price_premium": 170,  "code": "SSK"},
    # ── ท่อลง ──
    "SROR":    {"name": "ท่อรางน้ำ (SROR)",                    "unit": "เมตร", "price_std": 285,  "price_premium": 385,  "code": "SROR"},
    "BK":      {"name": "ท่องอ (BK)",                          "unit": "ชิ้น", "price_std": 250,  "price_premium": 330,  "code": "BK"},
    "GROR":    {"name": "ท่อแยกสามทาง (GROR)",                 "unit": "ชิ้น", "price_std": 1100, "price_premium": 1450, "code": "GROR"},
    "UTK":     {"name": "ท่อน้ำทิ้ง (UTK)",                    "unit": "ชิ้น", "price_std": 490,  "price_premium": 650,  "code": "UTK"},
    "SLS":     {"name": "ที่กรองขยะ (SLS)",                    "unit": "ชิ้น", "price_std": 550,  "price_premium": 750,  "code": "SLS"},
    "FUTK":    {"name": "ท่อปรับรับน้ำ (FUTK)",                "unit": "ชิ้น", "price_std": 800,  "price_premium": 1050, "code": "FUTK"},
    "SSVH":    {"name": "ตัวยึดท่อธรรมดา (SSVH)",             "unit": "ชิ้น", "price_std": 110,  "price_premium": 145,  "code": "SSVH"},
    "SSTV":    {"name": "ตัวยึดท่อแบบตะปู (SSTV)",            "unit": "ชิ้น", "price_std": 300,  "price_premium": 390,  "code": "SSTV"},

    # ── อุปกรณ์เพิ่มเติม ──
    "Joint":   {"name": "Joint (เส้นคู่ 2 เส้น) — โซสแตนเลส", "unit": "เมตร", "price_std": 800,  "price_premium": 800,  "code": "Joint",    "color_only": True},
    "PVC_loi":    {"name": "ท่อ PVC เดินลอย",       "unit": "เมตร", "price_std": 0, "price_premium": 0, "code": "PVC-ลอย",   "color_only": True},
    "PVC_din":    {"name": "ท่อ PVC ฝังดิน",        "unit": "เมตร", "price_std": 0, "price_premium": 0, "code": "PVC-ดิน",   "color_only": True},
    "backflow":   {"name": "เสริมปลายน้ำย้อน",       "unit": "ชิ้น", "price_std": 0, "price_premium": 0, "code": "Backflow",  "has_color": True},
    "flashing":   {"name": "แฟลชชิ่งปลาย",           "unit": "ชิ้น", "price_std": 0, "price_premium": 0, "code": "Flashing",  "has_color": True, "has_size": True},
    "leafguard":  {"name": "ตะแกรงกันใบไม้",          "unit": "เมตร", "price_std": 0, "price_premium": 0, "code": "LeafGuard", "color_only": True},
    "support_ul": {"name": "เหล็กซัพพอร์ต U/L",       "unit": "ชิ้น", "price_std": 0, "price_premium": 0, "code": "Support",   "color_only": True},
    "silicone":   {"name": "ซิลิโคน",                 "unit": "หลอด", "price_std": 0, "price_premium": 0, "code": "Silicone",  "has_color": True},
    "screw_fst":  {"name": "สกรู FS-T",               "unit": "ตัว",  "price_std": 0, "price_premium": 0, "code": "FS-T",      "has_color": True},
    "screw_fsbt": {"name": "สกรู FS-BT",              "unit": "ตัว",  "price_std": 0, "price_premium": 0, "code": "FS-BT",     "color_only": True},
    # ── ค่าแรง ──
    "labor":      {"name": "ค่าแรงติดตั้ง (ประมาณ)", "unit": "เมตร", "price_std": 120, "price_premium": 120, "code": "-", "color_only": True},
}

GROUPS = {
    "รางน้ำฝน":         ["R", "SOK", "RVY", "RVI", "RSK", "OSKR_H", "OSK_H", "RGT", "KFK", "SSK"],
    "ท่อลง":            ["SROR", "BK", "GROR", "UTK", "FUTK","SSVH", "SSTV", "SLS"],
    "อุปกรณ์เพิ่มเติม": ["PVC_loi", "PVC_din", "backflow", "flashing",
                          "leafguard", "support_ul", "silicone", "screw_fst", "screw_fsbt", "Joint"],
    "ค่าแรง":           ["labor"],
}


def _tier_price(key: str, tier: str) -> float:
    """ราคา default ของ key ตาม tier"""
    info = DEFAULT_PRICES[key]
    if info.get("color_only"):
        return float(info["price_std"])
    return float(info["price_std"] if tier == "std" else info["price_premium"])


def show():
    touch_session()
    st.markdown('<div class="page-title">💰 ตั้งราคาอุปกรณ์</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">ราคาอ้างอิงจากใบราคา Aqualine Lindab — '
        'ราคา<b>ไม่รวม VAT 7%</b> — แก้ไขได้ตลอดเพราะราคาตลาดเปลี่ยนได้</div>',
        unsafe_allow_html=True,
    )

    # ── init session ──
    if "price_tier" not in st.session_state:
        st.session_state.price_tier = "std"
    # custom_prices เก็บราคาที่ user แก้ไขเอง แยกตาม tier
    # format: {"std": {"R": 300, ...}, "premium": {"R": 400, ...}}
    if "custom_prices" not in st.session_state:
        st.session_state.custom_prices = {"std": {}, "premium": {}}

    # ── เลือก Tier ──
    tier = st.radio(
        "ระดับราคา",
        ["std", "premium"],
        format_func=lambda x: "🎨 สีมาตรฐาน (ขาว/เทา/น้ำตาล)" if x == "std" else "✨ สี Premium (ดำ/เทาเมทาลิก)",
        horizontal=True,
        index=0 if st.session_state.price_tier == "std" else 1,
        key="tier_radio",
    )

    # บันทึก tier ปัจจุบัน
    st.session_state.price_tier = tier

    if tier == "std":
        st.info("🎨 **สีมาตรฐาน** — ขาว / สีเทา / สีน้ำตาล: ราคาคอลัมน์ซ้ายจากใบราคา Aqualine Lindab")
    else:
        st.warning("✨ **สี Premium** — ดำ / สีเทาเมทาลิก / สีอื่นๆ: ราคาคอลัมน์ขวาจากใบราคา Aqualine Lindab")

    st.markdown("---")

    # ── แสดงราคาแบบจัดกลุ่ม ──
    # KEY FIX: ใส่ tier ลงใน widget key ทุกตัว → Streamlit สร้าง widget ใหม่ทุกครั้งที่ tier เปลี่ยน
    # ดังนั้น value= จะถูกอ่านจาก argument จริงๆ ไม่ใช่จาก cache เก่า
    updated = {}

    for group_name, keys in GROUPS.items():
        st.markdown(f'<div class="section-header">{group_name}</div>', unsafe_allow_html=True)
        items = [(k, DEFAULT_PRICES[k]) for k in keys if k in DEFAULT_PRICES]

        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for j, (key, info) in enumerate(items[i: i + 2]):
                with cols[j]:
                    is_color_only = info.get("color_only", False)
                    has_color     = info.get("has_color", False)
                    has_size      = info.get("has_size", False)

                    # ราคา default ของ tier ปัจจุบัน
                    default_p = _tier_price(key, tier)
                    # ถ้า user เคยแก้ไขราคาใน tier นี้ → ใช้ค่านั้น มิฉะนั้นใช้ default
                    current_p = st.session_state.custom_prices[tier].get(key, default_p)

                    # badge แสดง tier
                    if is_color_only:
                        tier_badge = ""
                    elif tier == "std":
                        tier_badge = (
                            '<span style="background:#EFF6FF;color:#1D4ED8;font-size:0.65rem;'
                            'padding:1px 5px;border-radius:3px;margin-left:4px;">สีมาตรฐาน</span>'
                        )
                    else:
                        tier_badge = (
                            '<span style="background:#FFF7ED;color:#C2410C;font-size:0.65rem;'
                            'padding:1px 5px;border-radius:3px;margin-left:4px;">Premium</span>'
                        )

                    st.markdown(
                        f'<div style="font-size:0.78rem;color:#374151;margin-bottom:2px;">'
                        f'<b style="color:#0D2144;">[{info["code"]}]</b> {info["name"]} '
                        f'<span style="color:#3B82F6;font-size:0.72rem;">({info["unit"]})</span>'
                        f'{tier_badge}'
                        f'<span style="color:#9CA3AF;font-size:0.68rem;margin-left:4px;">'
                        f'แนะนำ: ฿{default_p:,.0f}</span></div>',
                        unsafe_allow_html=True,
                    )

                    # widget key รวม tier → บังคับ re-render ใหม่ทุกครั้งที่ tier เปลี่ยน
                    val = st.number_input(
                        f"ราคา {info['name']}",
                        min_value=0.0,
                        value=current_p,
                        step=5.0,
                        key=f"pi_{key}_{tier}",   # ← KEY FIX: รวม tier ใน key
                        label_visibility="collapsed",
                    )
                    updated[key] = val
                    # บันทึกการแก้ไขของ user ลงใน custom_prices ของ tier นี้
                    st.session_state.custom_prices[tier][key] = val

                    # ── ช่องพิมพ์สี ──
                    if has_color:
                        ck = f"extra_color_{key}"
                        if ck not in st.session_state:
                            st.session_state[ck] = ""
                        color_val = st.text_input(
                            f"สี — {info['name']}",
                            value=st.session_state[ck],
                            placeholder="ระบุสี เช่น ขาว / RAL9010 / ดำ",
                            key=f"ci_{key}",
                        )
                        st.session_state[ck] = color_val

                    # ── ช่องพิมขนาด (นิ้ว) ──
                    if has_size:
                        sk = f"extra_size_{key}"
                        if sk not in st.session_state:
                            st.session_state[sk] = ""
                        size_val = st.text_input(
                            f"ขนาด — {info['name']} (นิ้ว)",
                            value=st.session_state[sk],
                            placeholder='เช่น 4", 6", 8"',
                            key=f"si_{key}",
                        )
                        st.session_state[sk] = size_val

    # ── ปุ่มด้านล่าง ──
    st.markdown("---")
    # เก็บ updated เป็น prices (backward compat กับหน้าอื่น)
    st.session_state.prices = updated

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 บันทึกราคา", use_container_width=True, type="primary"):
            st.success("✅ บันทึกราคาเรียบร้อยแล้ว!")
    with col2:
        if st.button("🔄 โหลดราคามาตรฐาน", use_container_width=True):
            # ล้าง custom ของ tier นี้ → กลับไปใช้ default
            st.session_state.custom_prices[tier] = {}
            st.rerun()
    with col3:
        vat = st.checkbox("แสดงราคารวม VAT 7%", value=False)

    # ── ตัวอย่างคำนวณ ──
    st.markdown("---")
    st.markdown('<div class="section-header">ตัวอย่างการคำนวณ (ราง 20 ม.)</div>', unsafe_allow_html=True)

    ex_len  = 20
    r_p     = updated.get("R",     _tier_price("R",     tier))
    rsk_p   = updated.get("RSK",   _tier_price("RSK",   tier))
    kfk_p   = updated.get("KFK",   _tier_price("KFK",   tier))
    labor_p = updated.get("labor", _tier_price("labor", tier))

    joints   = max(0, (ex_len // 5) - 1)
    hooks    = int(ex_len / 0.5) + 1
    subtotal = (ex_len * r_p) + (joints * rsk_p) + (hooks * kfk_p) + (ex_len * labor_p)
    vat_amt  = subtotal * 0.07
    total    = subtotal + vat_amt

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"ราง R  {ex_len} ม.",          f"฿{ex_len * r_p:,.0f}")
    col2.metric(f"ข้อต่อ RSK  {joints} ชิ้น",   f"฿{joints * rsk_p:,.0f}")
    col3.metric(f"ตะขอ KFK  {hooks} ตัว",        f"฿{hooks * kfk_p:,.0f}")
    col4.metric(f"ค่าแรง  {ex_len} ม.",          f"฿{ex_len * labor_p:,.0f}")

    if vat:
        st.markdown(
            f'<div class="ok-box">💰 รวมวัสดุ+แรง <b>฿{subtotal:,.0f}</b> | '
            f'VAT 7% <b>฿{vat_amt:,.0f}</b> | '
            f'<b>รวมสุทธิ ฿{total:,.0f}</b></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ok-box">💰 ราง {ex_len} ม. รวมค่าแรง (ก่อน VAT) ≈ '
            f'<b>฿{subtotal:,.0f}</b> บาท</div>',
            unsafe_allow_html=True,
        )

    st.caption("⚠️ ราคาอ้างอิงจากใบราคา Aqualine Lindab — ราคาจริงอาจแตกต่างตามสี ปริมาณสั่ง และค่าจัดส่ง")

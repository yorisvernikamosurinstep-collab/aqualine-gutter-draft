"""
assess_pdf_export.py  (v2 — 4-page PDF)
หน้า 1: ข้อมูลลูกค้า + จุดที่ 1-8
หน้า 2: BOQ + ลายเซ็น
หน้า 3: แบบแปลนรางน้ำ SVG + หน้าตัดท่อลง
หน้า 4: รูปภาพหน้างาน

วิธีใช้:
    from assess_pdf_export import render_photo_uploader, render_assess_pdf_button
    render_photo_uploader(p)
    render_assess_pdf_button(p)
"""

import base64
import datetime
import math
import streamlit as st
import streamlit.components.v1 as components


def _val(p, *keys, default="—"):
    for k in keys:
        v = p.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _fmt(v, d=2):
    try:
        return f"{float(v):,.{d}f}"
    except Exception:
        return str(v)


def _sides_rows_html(sides):
    if not sides:
        return "<tr><td colspan='4' style='text-align:center;color:#9CA3AF;'>ไม่มีข้อมูลด้าน</td></tr>"
    rows = []
    for s in sides:
        lbl = s.get("label", "?")
        lng = float(s.get("length_m", 0))
        pcs = math.ceil(lng / 4.0)
        hks = math.ceil(lng / 0.5)
        rows.append(
            f"<tr><td class='tc'>ด้าน {lbl}</td>"
            f"<td class='tr'>{lng:.2f} ม.</td>"
            f"<td class='tr'>{pcs} ท่อน</td>"
            f"<td class='tr'>{hks} ตัว</td></tr>"
        )
    return "\n".join(rows)


def _boq_rows_html(boq):
    if not boq:
        return "<tr><td colspan='5' style='text-align:center;color:#9CA3AF;'>ยังไม่มี BOQ</td></tr>"
    rows = []
    for i, item in enumerate(boq, 1):
        name  = item.get("name", item.get("description", ""))
        qty   = _fmt(item.get("qty", 0))
        unit  = item.get("unit", "")
        total = _fmt(item.get("total", item.get("amount", 0)))
        rows.append(
            f"<tr><td class='tc'>{i}</td><td>{name}</td>"
            f"<td class='tr'>{qty}</td><td class='tc'>{unit}</td>"
            f"<td class='tr'>{total}</td></tr>"
        )
    return "\n".join(rows)


def _build_plan_svg(sides, drain_pts, wall_h, g_color="#1D4ED8", p_color="#6B7280"):
    if not sides:
        return ("<svg viewBox='0 0 600 400' xmlns='http://www.w3.org/2000/svg'>"
                "<text x='300' y='200' text-anchor='middle' font-size='14' fill='#9CA3AF'>"
                "ไม่มีข้อมูลด้าน</text></svg>")
    cx, cy = 300, 200
    bw, bh = 220, 150
    bx, by = cx - bw // 2, cy - bh // 2
    edges = [
        dict(gx1=bx,       gy1=by-22,    gx2=bx+bw,    gy2=by-22,    lx=cx,        ly=by-34,    anc="middle", dx=0,  dy=-1),
        dict(gx1=bx+bw+22, gy1=by,       gx2=bx+bw+22, gy2=by+bh,    lx=bx+bw+36,  ly=cy,       anc="start",  dx=1,  dy=0),
        dict(gx1=bx+bw,    gy1=by+bh+22, gx2=bx,       gy2=by+bh+22, lx=cx,        ly=by+bh+36, anc="middle", dx=0,  dy=1),
        dict(gx1=bx-22,    gy1=by+bh,    gx2=bx-22,    gy2=by,       lx=bx-36,     ly=cy,       anc="end",    dx=-1, dy=0),
    ]
    total_len = sum(float(s.get("length_m", 0)) for s in sides)
    drain_dist = []
    rem = drain_pts
    for i, s in enumerate(sides):
        if i == len(sides) - 1:
            drain_dist.append(rem)
        else:
            share = round(drain_pts * float(s.get("length_m", 0)) / total_len) if total_len > 0 else 0
            drain_dist.append(max(0, share))
            rem -= max(0, share)
    gutter_els = []
    pipe_els   = []
    label_els  = []
    for i, s in enumerate(sides[:4]):
        ed  = edges[i]
        lng = float(s.get("length_m", 0))
        lbl = s.get("label", chr(65+i))
        dc  = drain_dist[i] if i < len(drain_dist) else 0
        sw  = 4 if lng > 0 else 1.5
        op  = "1" if lng > 0 else "0.25"
        gutter_els.append(
            f"<line x1='{ed['gx1']}' y1='{ed['gy1']}' x2='{ed['gx2']}' y2='{ed['gy2']}' "
            f"stroke='{g_color}' stroke-width='{sw}' stroke-linecap='round' opacity='{op}'/>"
        )
        label_txt = f"{lng:.1f} ม." if lng > 0 else "?"
        label_els.append(
            f"<text x='{ed['lx']}' y='{ed['ly']}' text-anchor='{ed['anc']}' "
            f"font-size='10' font-weight='700' fill='{g_color}' "
            f"font-family='Sarabun,Arial,sans-serif'>ด้าน {lbl}: {label_txt}</text>"
        )
        if dc > 0 and lng > 0:
            x1e, y1e, x2e, y2e = ed['gx1'], ed['gy1'], ed['gx2'], ed['gy2']
            for j in range(dc):
                t   = (j + 1) / (dc + 1)
                px  = x1e + t * (x2e - x1e)
                py  = y1e + t * (y2e - y1e)
                px2 = px + ed['dx'] * 30
                py2 = py + ed['dy'] * 30
                pipe_els.append(
                    f"<line x1='{px:.1f}' y1='{py:.1f}' x2='{px2:.1f}' y2='{py2:.1f}' "
                    f"stroke='{p_color}' stroke-width='3' stroke-dasharray='4,2'/>"
                    f"<circle cx='{px2:.1f}' cy='{py2:.1f}' r='6' "
                    f"fill='{p_color}' stroke='white' stroke-width='1.5'/>"
                    f"<text x='{px2:.1f}' y='{py2+16:.1f}' text-anchor='middle' "
                    f"font-size='7.5' fill='{p_color}' font-family='Sarabun,Arial,sans-serif'>จ.{j+1}</text>"
                )
    building = (
        f"<rect x='{bx}' y='{by}' width='{bw}' height='{bh}' "
        f"fill='#F1F5F9' stroke='#334155' stroke-width='2.5' rx='3'/>"
        f"<text x='{cx}' y='{cy-6}' text-anchor='middle' font-size='10' "
        f"fill='#64748B' font-family='Sarabun,Arial,sans-serif'>อาคาร</text>"
        f"<text x='{cx}' y='{cy+10}' text-anchor='middle' font-size='8' "
        f"fill='#94A3B8' font-family='Sarabun,Arial,sans-serif'>(ผังมุมบน)</text>"
    )
    corners_svg = ""
    for ccx, ccy in [(bx, by), (bx+bw, by), (bx+bw, by+bh), (bx, by+bh)]:
        corners_svg += (
            f"<rect x='{ccx-4}' y='{ccy-4}' width='8' height='8' "
            f"fill='white' stroke='#334155' stroke-width='1.5'/>"
        )
    legend = (
        f"<rect x='10' y='8' width='14' height='4' rx='2' fill='{g_color}'/>"
        f"<text x='28' y='15' font-size='8' fill='#374151' font-family='Sarabun,Arial,sans-serif'>รางน้ำ</text>"
        f"<circle cx='14' cy='27' r='5' fill='{p_color}'/>"
        f"<text x='28' y='31' font-size='8' fill='#374151' font-family='Sarabun,Arial,sans-serif'>จุดท่อลง</text>"
    )
    north = (
        f"<g transform='translate(568,28)'>"
        f"<circle cx='0' cy='0' r='15' fill='none' stroke='#CBD5E1' stroke-width='1.5'/>"
        f"<polygon points='0,-12 4,4 0,0 -4,4' fill='#0D2144'/>"
        f"<text x='0' y='-16' text-anchor='middle' font-size='8' font-weight='700' "
        f"fill='#0D2144' font-family='Sarabun,Arial,sans-serif'>N</text>"
        f"</g>"
    )
    parts = (
        ["<rect x='0' y='0' width='600' height='400' fill='white'/>",
         "<rect x='4' y='4' width='592' height='392' rx='7' fill='none' stroke='#E2E8F0' stroke-width='1'/>",
         legend, north, building, corners_svg]
        + gutter_els + pipe_els + label_els
    )
    return (
        "<svg viewBox='0 0 600 400' xmlns='http://www.w3.org/2000/svg' "
        "style='width:100%;max-width:600px;'>"
        + "\n".join(parts) + "</svg>"
    )


def _xsec_svg(wall_h, x1_cm, idx):
    W, H = 150, 130
    gx1, gy = 12, 24
    gx2 = 108
    dx = int(gx1 + (gx2 - gx1) * 0.68)
    pipe_h = min(85, max(30, int(wall_h * 14)))
    x2_px  = min(48, max(12, int((x1_cm - 2) * 0.55)))
    er = 9
    return (
        f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' "
        f"style='width:100%;background:#F9FAFB;border-radius:4px;'>"
        f"<line x1='{gx1}' y1='{gy}' x2='{gx2}' y2='{gy}' "
        f"stroke='#1D4ED8' stroke-width='4' stroke-linecap='round'/>"
        f"<text x='{(gx1+gx2)//2}' y='{gy-7}' text-anchor='middle' font-size='7' "
        f"fill='#1D4ED8' font-family='Sarabun,Arial'>ราง</text>"
        f"<path d='M{dx},{gy} Q{dx},{gy+er} {dx+er},{gy+er}' "
        f"fill='none' stroke='#6B7280' stroke-width='3'/>"
        f"<line x1='{dx+er}' y1='{gy+er}' x2='{dx+er+x2_px}' y2='{gy+er}' "
        f"stroke='#6B7280' stroke-width='3' stroke-dasharray='3,2'/>"
        f"<text x='{dx+er+x2_px//2}' y='{gy+er-5}' text-anchor='middle' "
        f"font-size='6.5' fill='#6B7280' font-family='Sarabun,Arial'>"
        f"x2={max(0,x1_cm-2):.0f}ซม.</text>"
        f"<line x1='{dx}' y1='{gy+er}' x2='{dx}' y2='{gy+pipe_h}' "
        f"stroke='#6B7280' stroke-width='3'/>"
        f"<polygon points='{dx-5},{gy+pipe_h} {dx+5},{gy+pipe_h} {dx},{gy+pipe_h+9}' "
        f"fill='#6B7280'/>"
        f"<text x='{dx-13}' y='{gy+er+pipe_h//2}' font-size='7' fill='#6B7280' "
        f"font-family='Sarabun,Arial'>{wall_h:.1f}ม.</text>"
        f"<circle cx='13' cy='13' r='9' fill='#0D2144'/>"
        f"<text x='13' y='17' text-anchor='middle' font-size='8' fill='white' "
        f"font-weight='700' font-family='Sarabun,Arial'>จ{idx}</text>"
        f"</svg>"
    )


def render_photo_uploader(p: dict, max_photos: int = 9):
    st.markdown("### 📸 รูปภาพหน้างานก่อนติดตั้ง")
    st.caption(f"อัปโหลดรูปถ่ายหน้างาน สูงสุด {max_photos} รูป — จะแสดงใน PDF หน้าที่ 4")
    photos: list = p.get("site_photos", [])
    uploaded = st.file_uploader(
        "เลือกรูปภาพ (JPG / PNG)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="site_photo_uploader",
    )
    if uploaded:
        added = 0
        for f in uploaded:
            if len(photos) >= max_photos:
                st.warning(f"⚠️ อัปโหลดได้สูงสุด {max_photos} รูป")
                break
            raw  = f.read()
            b64  = base64.b64encode(raw).decode()
            mime = f.type or "image/jpeg"
            dup  = any(ph.get("data", "")[:32] == b64[:32] for ph in photos)
            if not dup:
                photos.append({"data": b64, "caption": f.name, "mime": mime})
                added += 1
        if added:
            p["site_photos"] = photos
            st.success(f"✅ เพิ่ม {added} รูปแล้ว")
    if photos:
        st.markdown(f"**{len(photos)} รูป** (กรอกคำบรรยาย / กด ❌ เพื่อลบ)")
        cols = st.columns(3)
        del_idx = None
        for i, ph in enumerate(photos):
            with cols[i % 3]:
                src = f"data:{ph['mime']};base64,{ph['data']}"
                st.markdown(
                    f"<img src='{src}' style='width:100%;border-radius:6px;"
                    f"border:1px solid #E2E8F0;margin-bottom:4px;'/>",
                    unsafe_allow_html=True,
                )
                cap = st.text_input(
                    "คำบรรยาย", value=ph.get("caption", ""),
                    key=f"ph_cap_{i}", label_visibility="collapsed",
                    placeholder=f"รูปที่ {i+1}..."
                )
                photos[i]["caption"] = cap
                if st.button("❌ ลบรูปนี้", key=f"del_ph_{i}", use_container_width=True):
                    del_idx = i
        if del_idx is not None:
            photos.pop(del_idx)
            p["site_photos"] = photos
            st.rerun()
        p["site_photos"] = photos
    else:
        st.info("📭 ยังไม่มีรูป — อัปโหลดด้านบน")


_CSS = """<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{font-family:'Sarabun',sans-serif;font-size:11pt;color:#1E293B;background:#fff;}
@page{size:A4 portrait;margin:13mm 13mm 15mm 13mm;}
.page{width:210mm;min-height:297mm;padding:11mm 13mm 13mm 13mm;background:#fff;
  position:relative;page-break-after:always;}
.page:last-child{page-break-after:avoid;}
.dh{display:flex;justify-content:space-between;align-items:flex-start;
  border-bottom:2.5px solid #0D2144;padding-bottom:8px;margin-bottom:11px;}
.logo{width:42px;height:42px;border-radius:7px;background:#0D2144;
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:13pt;font-weight:700;flex-shrink:0;}
.bn{font-size:12pt;font-weight:700;color:#0D2144;line-height:1.2;}
.bs{font-size:7pt;color:#64748B;margin-top:1px;}
.dm{text-align:right;}.dt{font-size:15pt;font-weight:700;color:#0D2144;}
.ds{font-size:8pt;color:#64748B;}.qn{font-size:10pt;font-weight:600;color:#2563EB;margin-top:2px;}
.ig{display:grid;grid-template-columns:1fr 1fr;gap:7px 12px;margin-bottom:11px;
  background:#F8FAFF;border:1px solid #E2E8F0;border-radius:8px;padding:8px 11px;}
.il{font-size:7pt;font-weight:600;color:#64748B;text-transform:uppercase;}
.iv{font-size:9.5pt;font-weight:500;color:#0D2144;}
.sec{margin-bottom:10px;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;}
.st{background:#0D2144;color:#fff;font-size:8.5pt;font-weight:700;padding:4px 11px;}
.sb{padding:8px 11px;}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:7px;}
.kpi{background:#F0F5FF;border-radius:6px;padding:6px 8px;border:1px solid #DBEAFE;text-align:center;}
.kl{font-size:7pt;color:#64748B;font-weight:600;margin-bottom:1px;}
.kv{font-size:13pt;font-weight:700;color:#1D4ED8;line-height:1;}
.ku{font-size:7pt;color:#64748B;margin-top:1px;}
table{width:100%;border-collapse:collapse;font-size:9pt;}
th{background:#1E293B;color:#fff;padding:4px 7px;font-weight:600;font-size:8pt;}
td{padding:3.5px 7px;border-bottom:1px solid #F1F5F9;vertical-align:middle;}
tr:nth-child(even) td{background:#F8FAFF;}
tr:last-child td{border-bottom:none;}
.tc{text-align:center;}.tr{text-align:right;}
tfoot td{background:#E8EEF8!important;font-weight:700;border-top:2px solid #1E293B;}
.ok{background:#D1FAE5;color:#065F46;padding:1px 7px;border-radius:10px;font-size:8pt;font-weight:600;}
.wn{background:#FEF3C7;color:#92400E;padding:1px 7px;border-radius:10px;font-size:8pt;font-weight:600;}
.in{background:#DBEAFE;color:#1E40AF;padding:1px 7px;border-radius:10px;font-size:8pt;font-weight:600;}
.cr{display:flex;align-items:center;gap:5px;margin-bottom:4px;font-size:9.5pt;}
.cv{font-weight:600;color:#0D2144;}
.pb{background:#F8FAFF;border:1.5px solid #DBEAFE;border-radius:9px;padding:12px;text-align:center;}
.pbt{font-size:8pt;font-weight:700;color:#1D4ED8;text-transform:uppercase;letter-spacing:1px;margin-bottom:7px;}
.xg{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px;}
.xi{border:1px solid #E2E8F0;border-radius:6px;overflow:hidden;text-align:center;}
.xl{background:#1E293B;color:#fff;font-size:7pt;font-weight:600;padding:3px 5px;}
.xb{padding:6px;background:#fff;}
.phg{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:7px;}
.phi{break-inside:avoid;}
.phimg{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;border:1px solid #E2E8F0;}
.phc{font-size:7.5pt;color:#64748B;text-align:center;margin-top:2px;line-height:1.3;}
.phn{font-size:7pt;font-weight:700;color:#1D4ED8;margin-bottom:2px;}
.sr{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:14px;}
.sb2{border-top:1.5px solid #CBD5E1;padding-top:4px;text-align:center;font-size:8pt;color:#64748B;}
.sn{font-weight:600;color:#0D2144;font-size:9pt;margin-top:2px;}
.ft{position:fixed;bottom:7mm;left:13mm;right:13mm;display:flex;
  justify-content:space-between;font-size:7pt;color:#94A3B8;
  border-top:1px solid #E2E8F0;padding-top:3px;}
.pbtn{position:fixed;top:10px;right:10px;z-index:999;background:#2563EB;color:#fff;
  border:none;padding:8px 18px;border-radius:8px;font-size:10pt;
  font-family:'Sarabun',sans-serif;cursor:pointer;
  box-shadow:0 2px 10px rgba(37,99,235,.4);}
@media print{
  .pbtn{display:none!important;}
  html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
}
</style>"""


def build_assess_html(p: dict) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    q     = _val(p, "name")
    cust  = _val(p, "customer")
    ag    = _val(p, "angency_name")
    addr  = _val(p, "address")
    ph    = _val(p, "phone")
    tx    = _val(p, "customer_taxid")
    ps    = _val(p, "project_name_site")
    ins   = _val(p, "install_location")
    sal   = _val(p, "salesperson")
    jt    = _val(p, "job_type")
    notes = _val(p, "notes", default="")
    rmap  = {"gable": "ทรงจั่ว", "hip": "ทรงปั้นหยา", "shed": "ทรงเพิงหมาแหงน", "complex": "ทรงปั้นหยาตัวแอล"}
    rshp  = rmap.get(p.get("roof_shape", ""), p.get("roof_shape", "—"))
    fasc  = {"flat": "เชิงตรง (Flat)", "bevel": "เชิงเอียง (Bevel)"}.get(p.get("fascia_type", ""), "—")
    ptch  = p.get("pitch_deg", "—")
    crn   = p.get("corners", {})
    oc, ic = crn.get("outer", 0), crn.get("inner", 0)
    x1    = float(p.get("x1_cm", 0))
    x2    = max(0.0, x1 - 2)
    wh    = float(p.get("wall_height_m", 3.0))
    dp    = int(p.get("drain_points", 1))
    dt    = {"round": "ท่อกลม", "square": "ท่อเหลี่ยม"}.get(p.get("drain_type", ""), "—")
    lad   = p.get("ladder_clearance_cm", "—")
    lok   = float(lad) >= 180 if str(lad).replace(".", "").isdigit() else None
    sides  = [s for s in p.get("sides", []) if s.get("length_m", 0) > 0]
    tlen   = sum(float(s.get("length_m", 0)) for s in sides)
    thk    = math.ceil(tlen / 0.5) if tlen > 0 else 0
    boq    = p.get("boq", [])
    photos = p.get("site_photos", [])
    gc     = p.get("gutter_color", "#1D4ED8")
    pc     = p.get("pipe_color", "#6B7280")
    lb_str = "<span class='ok'>✅ ผ่าน</span>" if lok is True else ("<span class='wn'>⚠️ ไม่ผ่าน</span>" if lok is False else "")
    plan_svg = _build_plan_svg(sides, dp, wh, gc, pc)
    xsec_html = ""
    for i in range(dp):
        svg = _xsec_svg(wh, x1, i+1)
        xsec_html += (f"<div class='xi'><div class='xl'>จุดที่ {i+1}</div>"
                      f"<div class='xb'>{svg}</div></div>")
    if photos:
        ph_items = ""
        for i, photo in enumerate(photos):
            src = f"data:{photo.get('mime','image/jpeg')};base64,{photo.get('data','')}"
            cap = photo.get("caption", "")
            ph_items += (f"<div class='phi'><div class='phn'>รูปที่ {i+1}</div>"
                         f"<img class='phimg' src='{src}' alt='site {i+1}'/>"
                         f"<div class='phc'>{cap}</div></div>")
        page4_body = f"<div class='phg'>{ph_items}</div>"
    else:
        page4_body = ("<div style='text-align:center;padding:50px 20px;color:#9CA3AF;'>"
                      "<div style='font-size:40pt;'>📷</div>"
                      "<div style='font-size:11pt;margin-top:10px;'>ยังไม่มีรูปหน้างาน</div>"
                      "<div style='font-size:9pt;margin-top:4px;'>อัปโหลดผ่านปุ่ม 📸 ในหน้าประเมิน</div>"
                      "</div>")
    notes_html = ""
    if notes and notes != "—":
        notes_html = (f"<div style='margin-top:8px;padding:6px 11px;background:#FFFBEB;"
                      f"border:1px solid #FCD34D;border-radius:6px;font-size:8.5pt;'>"
                      f"<b>📝 หมายเหตุ:</b> {notes}</div>")

    def hdr(title, sub):
        return (f"<div class='dh'><div style='display:flex;align-items:center;gap:9px;'>"
                f"<div class='logo'>AQ</div>"
                f"<div><div class='bn'>AQUALINE</div>"
                f"<div class='bs'>บริษัท อาควาไลน์ โปรทาร์เก็ต จำกัด</div>"
                f"<div class='bs'>638 ถ.ประเสริฐมนูกิจ แขวงลาดพร้าว กรุงเทพฯ 10230</div></div></div>"
                f"<div class='dm'><div class='dt'>{title}</div>"
                f"<div class='ds'>{sub}</div><div class='qn'>{q}</div>"
                f"<div class='ds' style='margin-top:2px;'>วันที่: {today} | {sal}</div></div></div>")

    def ftr(pg, tot):
        return (f"<div class='ft'>"
                f"<span>บริษัท อาควาไลน์ โปรทาร์เก็ต จำกัด — info@aqualineasia.com — 02-570-9009</span>"
                f"<span>หน้า {pg}/{tot} | {q}</span></div>")

    TP = 4
    return f"""<!DOCTYPE html>
<html lang="th">
<head><meta charset="UTF-8"/><title>ใบประเมินหน้างาน — {q}</title>
{_CSS}
</head>
<body>
<button class="pbtn" onclick="window.print()">🖨️ พิมพ์ / บันทึก PDF</button>

<div class="page">
{hdr("ใบประเมินหน้างาน","Site Assessment Report")}
<div class="ig">
  <div><div class="il">ผู้ติดต่อ</div><div class="iv">{cust}</div></div>
  <div><div class="il">บริษัท/หน่วยงาน</div><div class="iv">{ag}</div></div>
  <div><div class="il">โทรศัพท์</div><div class="iv">{ph}</div></div>
  <div><div class="il">เลขผู้เสียภาษี</div><div class="iv">{tx}</div></div>
  <div style="grid-column:1/-1;"><div class="il">ที่อยู่</div><div class="iv">{addr}</div></div>
  <div><div class="il">ชื่อโครงการ</div><div class="iv">{ps}</div></div>
  <div><div class="il">สถานที่ / ประเภทงาน</div><div class="iv">{ins} | {jt}</div></div>
</div>
<div class="sec"><div class="st">จุดที่ 1 — ทรงหลังคา</div>
<div class="sb"><div class="cr"><span>🏠</span><span>ทรงหลังคา:</span>
<span class="cv">{rshp}</span><span class="in">{p.get("roof_shape","—")}</span>
</div></div></div>
<div class="sec"><div class="st">จุดที่ 2 — ความยาวรางน้ำรายด้าน</div>
<div class="sb" style="padding:0;"><table>
<thead><tr><th class="tc" style="width:60px;">ด้าน</th>
<th>ความยาว</th><th class="tr">ราง (ท่อน)</th><th class="tr">ตะขอ (ตัว)</th></tr></thead>
<tbody>{_sides_rows_html(sides)}</tbody>
<tfoot><tr><td class="tc"><b>รวม</b></td>
<td><b>{tlen:.2f} ม.</b></td>
<td class="tr"><b>{math.ceil(tlen/4) if tlen>0 else 0} ท่อน</b></td>
<td class="tr"><b>{thk} ตัว</b></td>
</tr></tfoot>
</table></div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;">
<div class="sec"><div class="st">จุดที่ 3 — เชิงชาย</div><div class="sb">
<div class="cr"><span>📐</span><span>ประเภท:</span><span class="cv">{fasc}</span></div>
<div class="cr"><span>📏</span><span>ความชัน:</span><span class="cv">{ptch}°</span></div>
<div class="cr"><span>🔩</span><span>ระยะตะขอ:</span>
<span class="cv">{"50 ซม." if p.get("fascia_type","flat")=="flat" else "60 ซม."}</span></div>
</div></div>
<div class="sec"><div class="st">จุดที่ 4 — มุมหลังคา</div><div class="sb">
<div class="g2">
<div class="kpi"><div class="kl">มุมนอก (RVY)</div><div class="kv">{oc}</div><div class="ku">ชิ้น</div></div>
<div class="kpi"><div class="kl">มุมใน (RVI)</div><div class="kv">{ic}</div><div class="ku">ชิ้น</div></div>
</div>
<div style="margin-top:5px;font-size:8pt;color:#64748B;">รวม: <b>{oc+ic} จุด</b></div>
</div></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:9px;">
<div class="sec"><div class="st">จุดที่ 5 — ระยะปลายหลังคา-ผนัง</div><div class="sb">
<div class="g2">
<div class="kpi"><div class="kl">X1 (วัดได้)</div><div class="kv">{x1:.0f}</div><div class="ku">ซม.</div></div>
<div class="kpi"><div class="kl">X2 (ท่อแนวราบ)</div><div class="kv">{x2:.0f}</div><div class="ku">ซม.</div></div>
</div></div></div>
<div class="sec"><div class="st">จุดที่ 6 — ความสูงผนัง</div><div class="sb">
<div class="kpi" style="display:inline-block;min-width:100px;">
<div class="kl">ความสูงผนัง</div><div class="kv">{wh:.1f}</div><div class="ku">เมตร</div>
</div></div></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:9px;">
<div class="sec"><div class="st">จุดที่ 7 — จุดระบายน้ำ</div><div class="sb">
<div class="cr"><span>🔵</span><span>ประเภท:</span><span class="cv">{dt}</span></div>
<div class="cr"><span>📍</span><span>จำนวน:</span><span class="cv">{dp} จุด</span></div>
</div></div>
<div class="sec"><div class="st">จุดที่ 8 — ระยะวางบันได</div><div class="sb">
<div class="cr"><span>🪜</span><span>ระยะ:</span>
<span class="cv">{lad} ซม.</span>{lb_str}</div>
<div style="font-size:7.5pt;color:#64748B;">เกณฑ์: ≥ 180 ซม.</div>
</div></div>
</div>
{notes_html}
{ftr(1,TP)}
</div>

<div class="page">
{hdr("สรุป BOQ / วัสดุ","Bill of Quantities")}
<div style="margin-bottom:8px;font-size:8.5pt;color:#64748B;">
โครงการ: <b style="color:#0D2144;">{ps}</b> | สถานที่: <b style="color:#0D2144;">{ins}</b> | ลูกค้า: <b style="color:#0D2144;">{cust}</b>
</div>
<div class="sec"><div class="st">รายการวัสดุและปริมาณ</div>
<div class="sb" style="padding:0;"><table>
<thead><tr><th class="tc" style="width:28px;">#</th><th>รายการ</th>
<th class="tr" style="width:58px;">จำนวน</th>
<th class="tc" style="width:38px;">หน่วย</th>
<th class="tr" style="width:65px;">มูลค่า</th></tr></thead>
<tbody>{_boq_rows_html(boq)}</tbody>
</table></div></div>
<div class="g4" style="margin-top:9px;">
<div class="kpi"><div class="kl">รางน้ำรวม</div><div class="kv">{tlen:.1f}</div><div class="ku">เมตร</div></div>
<div class="kpi"><div class="kl">จุดท่อลง</div><div class="kv">{dp}</div><div class="ku">จุด</div></div>
<div class="kpi"><div class="kl">มุมทั้งหมด</div><div class="kv">{oc+ic}</div><div class="ku">จุด</div></div>
<div class="kpi"><div class="kl">ตะขอทั้งหมด</div><div class="kv">{thk}</div><div class="ku">ตัว</div></div>
</div>
<div class="sr">
<div class="sb2"><div style="height:32px;"></div>
<div class="sn">{sal}</div><div>ผู้ประเมิน</div><div style="margin-top:2px;">วันที่: {today}</div></div>
<div class="sb2"><div style="height:32px;"></div>
<div class="sn">.....................................</div><div>ผู้อนุมัติ</div><div style="margin-top:2px;">วันที่: ................</div></div>
<div class="sb2"><div style="height:32px;"></div>
<div class="sn">.....................................</div><div>ลูกค้ายืนยัน</div><div style="margin-top:2px;">วันที่: ................</div></div>
</div>
{ftr(2,TP)}
</div>

<div class="page">
{hdr("📐 แบบวาดแปลนรางน้ำและท่อลง","Gutter &amp; Downpipe Layout Plan")}
<div style="margin-bottom:7px;font-size:8.5pt;color:#64748B;">
โครงการ: <b style="color:#0D2144;">{ps}</b>
&nbsp;|&nbsp; สีราง: <span style="color:{gc};font-weight:700;">■</span> {p.get("gutter_color_name","ตามมาตรฐาน")}
&nbsp;|&nbsp; สีท่อ: <span style="color:{pc};font-weight:700;">■</span> {p.get("pipe_color_name","ตามมาตรฐาน")}
</div>
<div class="pb">
<div class="pbt">ผังมุมบน (Top View) — สเกลสัดส่วน</div>
{plan_svg}
</div>
<div class="sec" style="margin-top:10px;"><div class="st">หน้าตัดท่อลงแต่ละจุด (Cross Section)</div>
<div class="sb"><div class="xg">
{xsec_html if xsec_html else "<div style='color:#9CA3AF;font-size:9pt;'>ไม่มีข้อมูลจุดท่อลง</div>"}
</div></div></div>
<div class="sec" style="margin-top:9px;"><div class="st">ตารางสรุประยะ</div>
<div class="sb" style="padding:0;"><table>
<thead><tr><th>ด้าน</th><th class="tr">ยาว (ม.)</th>
<th class="tr">ราง</th><th class="tr">ตะขอ</th><th class="tc">ท่อลง</th></tr></thead>
<tbody>{"".join(f"<tr><td>ด้าน {s.get('label','')}</td><td class='tr'>{float(s.get('length_m',0)):.2f}</td><td class='tr'>{math.ceil(float(s.get('length_m',0))/4)}</td><td class='tr'>{math.ceil(float(s.get('length_m',0))/0.5)}</td><td class='tc'>—</td></tr>" for s in sides) if sides else "<tr><td colspan='5' class='tc' style='color:#9CA3AF;'>ไม่มีข้อมูล</td></tr>"}</tbody>
<tfoot><tr><td><b>รวม</b></td><td class="tr"><b>{tlen:.2f} ม.</b></td>
<td class="tr"><b>{math.ceil(tlen/4) if tlen>0 else 0}</b></td>
<td class="tr"><b>{thk}</b></td><td class="tc"><b>{dp} จุด</b></td>
</tr></tfoot>
</table></div></div>
{ftr(3,TP)}
</div>

<div class="page">
{hdr("📸 รูปภาพหน้างานก่อนติดตั้ง","Site Photos — Before Installation")}
<div style="margin-bottom:7px;font-size:8.5pt;color:#64748B;">
โครงการ: <b style="color:#0D2144;">{ps}</b> | สถานที่: <b style="color:#0D2144;">{ins}</b> | จำนวน: <b>{len(photos)} รูป</b>
</div>
{page4_body}
{ftr(4,TP)}
</div>

</body></html>"""


def render_assess_pdf_button(p: dict, label: str = "🖨️ Export ใบประเมิน PDF (4 หน้า)"):
    col1, col2 = st.columns([2, 1])
    with col1:
        show = st.button(label, use_container_width=True, type="primary")
    with col2:
        qname = p.get("name", "assess").replace("/", "_").replace("#", "")
        st.download_button(
            "⬇️ ดาวน์โหลด HTML",
            data=get_assess_html_bytes(p),
            file_name=f"{qname}_assess.html",
            mime="text/html",
            use_container_width=True,
        )
    if show:
        st.info("💡 กดปุ่ม **🖨️ พิมพ์ / บันทึก PDF** ในหน้าตัวอย่าง → Save as PDF → A4 Portrait")
        components.html(build_assess_html(p), height=960, scrolling=True)


def get_assess_html_bytes(p: dict) -> bytes:
    return build_assess_html(p).encode("utf-8")

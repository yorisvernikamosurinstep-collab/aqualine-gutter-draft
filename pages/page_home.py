"""
หน้า 1 — จัดการโปรเจกต์
สร้างงานใหม่ / เลือกงานเก่า / แก้ไข / ลบ / บันทึก
[NEW] Search/Filter + Duplicate project
"""
import streamlit as st
from pages.page_login import touch_session
import datetime
from utils.state import (
    init_session, new_project, project_list, get_project,
    save_current_project, delete_current_project, reload_from_disk,
    duplicate_project,
)
from utils.storage import save_project


import json
import os
import requests
import datetime

SEEN_JOBS_FILE = "seen_jobs.json"

def _load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def _save_seen_jobs(seen_set):
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f)
    except Exception:
        pass

def fetch_gutter_projects_api():
    coord_url = st.secrets.get("coordinator", {}).get("webapp_url", "")
    if not coord_url:
        return []
    try:
        resp = requests.post(coord_url, json={"action": "get_gutter_projects"}, timeout=10)
        res_json = resp.json()
        if res_json.get("ok"):
            return res_json.get("jobs", [])
    except Exception as e:
        st.sidebar.error(f"⚠️ ไม่สามารถเชื่อมต่อฐานข้อมูลระบบประสานงาน: {e}")
    return []

def start_drafting_job(job):
    pid = job["quotationId"]
    if pid in st.session_state.projects:
        st.session_state.current_project_id = pid
        st.session_state.current_page = "canvas"
        st.rerun()
        return
        
    p = {
        "id": pid,
        "name": job["quotationId"],
        "customer": job["customerName"],
        "customer_code": job["customerCode"],
        "angency_name": job["projectName"],
        "customer_taxid": job["taxId"],
        "phone": job["phone"],
        "address": job["address"],
        "project_name_site": job["projectName"],
        "install_location": job["installLocation"],
        "po_ref": job["poRef"],
        "salesperson": job["salesperson"],
        "job_type": job["jobType"] or "ติดตั้งใหม่",
        "created": job["timestamp"] or datetime.datetime.now().isoformat(),
        "created_by": st.session_state.get("current_user", "Draftsman"),
        "last_saved": None,
        "sides": [],
        "corners": {"outer": 0, "inner": 0},
        "fascia_type": "flat",
        "pitch_deg": 30,
        "wall_height_m": 3.0,
        "x1_cm": 0.0,
        "drain_points": 1,
        "drain_type": "round",
        "ladder_ok": None,
        "roof_shape": "rectangle",
        "roof_dims": {},
        "boq": None,
        "canvas_data": None,
        "notes": job["notes"] or "",
        "status": "draft",
        "sent_to_coord": False
    }
    
    from utils.storage import save_project, _coerce_str_fields
    _coerce_str_fields(p)  # บังคับ po_ref/taxid/phone ฯลฯ เป็น str กัน TypeError ตอน render
    st.session_state.projects[pid] = p
    st.session_state.current_project_id = pid
    user = st.session_state.get("current_user", "")
    save_project(p, user=user, skip_validation=True)
    
    st.session_state.current_page = "canvas"
    st.rerun()

def show():
    touch_session()
    st.markdown('<div class="page-title">🏗️ จัดการโปรเจกต์เขียนแบบ</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">เลือกงานรางน้ำฝนที่ประสานงานส่งมาเพื่อเขียนแบบ หรือจัดการงานที่กำลังดำเนินการอยู่</div>', unsafe_allow_html=True)

    # ── แถบสถานะ unsaved ──
    if st.session_state.get("unsaved_changes"):
        st.warning("⚠️ มีการเปลี่ยนแปลงที่ยังไม่ได้บันทึก — กด **💾 บันทึก** หรือไปหน้าอื่นเพื่อบันทึกอัตโนมัติ")

    col_left, col_right = st.columns([1, 1], gap="large")

    # ══════════════════════════════════════════
    # ฝั่งซ้าย — งานลูกค้ารางน้ำฝนรอการทำแบบ
    # ══════════════════════════════════════════
    with col_left:
        st.markdown('<div class="section-header">📥 งานลูกค้ารางน้ำฝนรอการทำแบบ (จากประสานงาน)</div>', unsafe_allow_html=True)
        
        # Load Gutter jobs from API
        api_jobs = fetch_gutter_projects_api()
        # Filter for jobs waiting for drawing (status == 'รอวาดแบบ')
        pending_jobs = [j for j in api_jobs if j.get("crmStatus") == "รอวาดแบบ"]
        
        seen_set = _load_seen_jobs()
        new_jobs = [j for j in pending_jobs if j["quotationId"] not in seen_set]
        
        if new_jobs:
            st.warning(f"🔔 มีงานใหม่ได้รับมอบหมาย {len(new_jobs)} งาน!")
            
        if not pending_jobs:
            st.info("ไม่มีงานรางน้ำฝนที่รอการวาดแบบในขณะนี้")
        else:
            for job in pending_jobs:
                is_new = job["quotationId"] not in seen_set
                red_dot = "🔴 " if is_new else ""
                
                # Card
                st.markdown(f"""
<div style="background:#FFFFFF;border-radius:10px;padding:0.9rem 1rem;
            border:1px solid #C8D5F0;margin-bottom:0.6rem;
            box-shadow:0 2px 8px rgba(13,33,68,0.07);">
    <div>
        <div style="font-size:0.68rem;color:#6B7A99;">
            📅 {job.get('timestamp','')[:10]} &nbsp;|&nbsp; 👤 เซลส์: {job.get('salesperson','')}
        </div>
        <div style="font-size:1.05rem;font-weight:700;color:#0C2142;margin:2px 0;">
            {red_dot}เลขใบเสนอราคา: {job['quotationId']}
        </div>
        <div style="font-size:0.85rem;color:#2E7D32;font-weight:600;">
            🏢 โครงการ/บริษัท: {job['projectName']}
        </div>
        <div style="font-size:0.78rem;color:#6B7A99;">
            👤 ผู้ติดต่อ: {job.get('customerName','')} (รหัส: {job.get('customerCode','')})
            <br>📞 เบอร์โทร: {job.get('phone','')}
            <br>📍 สถานที่ติดตั้ง: {job.get('installLocation','')}
        </div>
        {f'<div style="font-size:0.72rem;color:#D32F2F;margin-top:2px;font-weight:600;">📝 หมายเหตุประสานงาน: {job.get("specialInstructions","")}</div>' if job.get('specialInstructions') else ''}
    </div>
</div>
""", unsafe_allow_html=True)
                
                c1, c2 = st.columns([2, 3])
                with c1:
                    if st.button("เริ่มเขียนแบบ", key=f"start_job_{job['quotationId']}", use_container_width=True, type="primary"):
                        seen_set.add(job["quotationId"])
                        _save_seen_jobs(seen_set)
                        start_drafting_job(job)
                with c2:
                    if job.get("cadFileUrls"):
                        st.markdown(f'<div style="font-size:0.72rem;padding:6px;background:#F1F5F9;border-radius:6px;border:1px solid #E2E8F0;word-break:break-all;"><b>📎 ไฟล์แนบแบบ:</b><br>{job["cadFileUrls"].replace("\n", "<br>")}</div>', unsafe_allow_html=True)
                    else:
                        st.caption("ไม่มีไฟล์แนบส่งมาด้วย")

        # ── Issue 6a — สร้างงานใหม่เอง (ไม่ผ่านประสานงาน) ──
        st.markdown("---")
        if st.button("➕ สร้างงานใหม่ (ไม่ผ่านประสานงาน)", use_container_width=True,
                     key="btn_new_local_job"):
            st.session_state["show_new_local_form"] = not st.session_state.get("show_new_local_form", False)
        if st.session_state.get("show_new_local_form"):
            with st.form("new_local_job_form"):
                nl_cust  = st.text_input("ชื่อลูกค้า / ผู้ติดต่อ")
                nl_proj  = st.text_input("ชื่อโครงการ / บริษัท")
                nl_phone = st.text_input("เบอร์โทร")
                nl_loc   = st.text_input("สถานที่ติดตั้ง")
                if st.form_submit_button("สร้าง", type="primary", use_container_width=True):
                    if not (nl_cust.strip() or nl_proj.strip()):
                        st.warning("กรุณากรอกชื่อลูกค้าหรือชื่อโครงการอย่างน้อย 1 ช่อง")
                    else:
                        import random
                        _today = datetime.datetime.now().strftime("%Y%m%d")
                        _pid = f"QO-GUT-LOCAL-{_today}-{random.randint(1000,9999)}"
                        _p = {
                            "id": _pid, "name": _pid,
                            "customer": nl_cust.strip(), "customer_code": "",
                            "angency_name": nl_proj.strip(), "customer_taxid": "",
                            "phone": nl_phone.strip(), "address": "",
                            "project_name_site": nl_proj.strip(), "install_location": nl_loc.strip(),
                            "po_ref": "", "salesperson": "",
                            "job_type": "ติดตั้งใหม่",
                            "created": datetime.datetime.now().isoformat(),
                            "created_by": st.session_state.get("current_user", "Draftsman"),
                            "last_saved": None, "notes": "",
                            "canvas_data": None, "boq": None,
                            "status": "draft", "sent_to_coord": False,
                        }
                        from utils.storage import save_project as _sp, _coerce_str_fields
                        _coerce_str_fields(_p)
                        st.session_state.projects[_pid] = _p
                        st.session_state.current_project_id = _pid
                        _sp(_p, user=st.session_state.get("current_user", ""), skip_validation=True)
                        st.session_state["show_new_local_form"] = False
                        st.session_state.current_page = "canvas"
                        st.rerun()

    # ══════════════════════════════════════════
    # ฝั่งขวา — รายการโปรเจกต์ที่ยังไม่ได้ส่ง
    # ══════════════════════════════════════════
    with col_right:
        st.markdown('<div class="section-header">📁 งานที่มีอยู่</div>', unsafe_allow_html=True)

        # ── ปุ่มรีโหลด ──
        rcol1, rcol2 = st.columns([3, 1])
        with rcol2:
            if st.button("🔄 รีโหลด", help="โหลดข้อมูลใหม่จากไฟล์", use_container_width=True):
                reload_from_disk()
                st.rerun()

        projects_all = sorted(
            project_list(),
            key=lambda x: x.get("last_saved") or x["created"],
            reverse=True,
        )

        # ══════════════════════════════════════
        # [NEW] SEARCH / FILTER
        # ══════════════════════════════════════
        if projects_all:
            with st.expander("🔍 ค้นหา / กรอง", expanded=False):
                sc1, sc2, sc3 = st.columns(3)

                search_text = sc1.text_input(
                    "ค้นหาชื่อ / ลูกค้า / PO",
                    placeholder="พิมพ์เพื่อค้นหา...",
                    key="home_search",
                )
                filter_status = sc2.selectbox(
                    "กรองสถานะ",
                    ["ทั้งหมด", "draft", "sent", "approved"],
                    format_func=lambda x: {
                        "ทั้งหมด": "📋 ทั้งหมด",
                        "draft":    "📝 Draft",
                        "sent":     "📤 Sent",
                        "approved": "✅ Approved",
                    }.get(x, x),
                    key="home_filter_status",
                )
                filter_type = sc3.selectbox(
                    "ประเภทงาน",
                    ["ทั้งหมด", "ติดตั้งใหม่", "ซ่อม/เปลี่ยน", "ต่อเติม"],
                    key="home_filter_type",
                )

            # Apply filters (Issue 6 — ไม่ตัดงานที่ส่งแล้วทิ้ง; แยกเป็น Tab ทีหลัง)
            projects = list(projects_all)
            if search_text.strip():
                q = search_text.strip().lower()
                projects = [
                    p for p in projects
                    if q in p.get("name", "").lower()
                    or q in p.get("customer", "").lower()
                    or q in p.get("angency_name", "").lower()
                    or q in p.get("po_ref", "").lower()
                    or q in p.get("install_location", "").lower()
                ]
            if filter_status != "ทั้งหมด":
                projects = [p for p in projects if p.get("status") == filter_status]
            if filter_type != "ทั้งหมด":
                projects = [p for p in projects if p.get("job_type") == filter_type]

            # แสดงผลลัพธ์
            if search_text or filter_status != "ทั้งหมด" or filter_type != "ทั้งหมด":
                st.caption(f"🔍 พบ {len(projects)} รายการ จากทั้งหมด {len(projects_all)} งาน")
        else:
            projects = projects_all

        # ── Issue 6b — แยก 2 แท็บ: งานในมือ (ยังไม่ส่ง) / ส่งแล้ว ──
        in_hand = [p for p in projects if not p.get("sent_to_coord")]
        sent    = [p for p in projects if p.get("sent_to_coord")]

        tab_hand, tab_sent = st.tabs([f"📝 งานในมือ ({len(in_hand)})", f"📤 ส่งแล้ว ({len(sent)})"])
        with tab_hand:
            if not in_hand:
                st.info("ไม่พบงานที่ตรงเงื่อนไข" if projects_all else "ยังไม่มีงาน — สร้างงานใหม่ทางซ้ายได้เลยครับ")
            else:
                for p in in_hand:
                    _render_project_card(p)
        with tab_sent:
            if not sent:
                st.info("ยังไม่มีงานที่ส่งให้ประสานงาน")
            else:
                for p in sent:
                    _render_project_card(p)

        if projects_all:
            st.markdown("---")
            from utils.storage import _drive_storage_on
            _loc = "Google Drive (_drafts)" if _drive_storage_on() else "aqualine_projects/"
            st.caption(f"📂 งานทั้งหมด: **{len(projects_all)} งาน** — บันทึกใน `{_loc}`")


def _render_project_card(p: dict):
    """แสดงการ์ดโปรเจกต์พร้อมปุ่มเปิด/แก้ไข/ลบ/duplicate"""
    _status = p.get("status", "draft")
    _status_cfg = {
        "draft":    ("📝 Draft",    "#EFF6FF", "#1D4ED8"),
        "sent":     ("📤 Sent",     "#F0FDF4", "#15803D"),
        "approved": ("✅ Approved", "#FEF9C3", "#A16207"),
    }.get(_status, ("📝 Draft", "#EFF6FF", "#1D4ED8"))

    is_current = st.session_state.get("current_project_id") == p["id"]
    border_color = "#2563EB" if is_current else "#E4EAF8"
    border_width = "2px" if is_current else "1px"

    created_dt = datetime.datetime.fromisoformat(p["created"])
    saved_str  = ""
    if p.get("last_saved"):
        saved_dt  = datetime.datetime.fromisoformat(p["last_saved"])
        saved_str = f" | 💾 {saved_dt.strftime('%d/%m %H:%M')}"

    # escape ทุกค่าที่ยัดลง HTML กัน field ที่มี <, >, " (เช่น notes ที่เป็น meta-JSON จาก GAS) ทำการ์ดพัง
    import html as _html
    _name    = _html.escape(str(p.get('name', '')))
    _jobtype = _html.escape(str(p.get('job_type', '')))
    _cust    = _html.escape(str(p.get('customer', '')))
    _agency  = _html.escape(str(p.get('angency_name', '')))
    _loc_raw = (p.get('install_location') or p.get('address', '') or '')
    _loc     = _html.escape(_loc_raw[:40]) + ('...' if len(_loc_raw) > 40 else '')
    _po      = _html.escape(str(p.get('po_ref', '')))
    _notes_raw = str(p.get('notes', '') or '').strip()
    # ซ่อน notes ถ้าเป็น meta-JSON ({...}) — เป็นข้อมูลภายในของ GAS ไม่ใช่หมายเหตุจริง
    _notes_html = '' if (not _notes_raw or _notes_raw.startswith('{')) else \
        f'<div style="font-size:0.72rem;color:#6B7A99;margin-top:2px;">📝 {_html.escape(_notes_raw[:60])}</div>'

    # สร้างเป็น HTML บรรทัดเดียว (ตัด newline) — กัน "บรรทัดว่าง" จาก conditional ที่ว่าง (PO/notes)
    # ทำให้ Streamlit markdown ตีว่า HTML block จบกลางคัน แล้วโชว์ส่วนที่เหลือเป็น code block
    _po_html = f'  •  PO: {_po}' if _po else ''
    _card_html = (
        f'<div style="background:#FFFFFF;border-radius:10px;padding:0.9rem 1rem;'
        f'border:{border_width} solid {border_color};margin-bottom:0.6rem;'
        f'box-shadow:0 2px 8px rgba(13,33,68,0.07);">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;"><div>'
        f'<div style="font-size:0.68rem;color:#6B7A99;">📅 {created_dt.strftime("%d/%m/%Y %H:%M")}'
        f'&nbsp;|&nbsp; {_jobtype}{saved_str}'
        f'&nbsp;<span style="background:{_status_cfg[1]};color:{_status_cfg[2]};padding:1px 8px;border-radius:10px;font-weight:600;">{_status_cfg[0]}</span></div>'
        f'<div style="font-size:1.05rem;font-weight:700;color:#0D2144;margin:2px 0;">{"🔵 " if is_current else ""}{_name}</div>'
        f'<div style="font-size:0.78rem;color:#6B7A99;">👤 {_cust}{"  •  " + _agency if _agency else ""}</div>'
        f'<div style="font-size:0.75rem;color:#6B7A99;">📍 {_loc}{_po_html}</div>'
        f'{_notes_html}'
        f'</div></div></div>'
    )
    st.markdown(_card_html, unsafe_allow_html=True)

    # ── ปุ่มแถวล่าง (5 ปุ่ม) ──
    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if st.button("📂 เปิด", key=f"open_{p['id']}", use_container_width=True,
                     type="primary" if is_current else "secondary"):
            st.session_state.current_project_id = p["id"]
            st.session_state.current_page = "canvas"
            st.rerun()
    with b2:
        if st.button("✏️ แก้ไข", key=f"edit_{p['id']}", use_container_width=True):
            st.session_state.current_project_id = p["id"]
            st.session_state[f"editing_{p['id']}"] = True
            st.rerun()
    with b3:
        if st.button("💾 บันทึก", key=f"save_{p['id']}", use_container_width=True):
            user = st.session_state.get("current_user", "")
            ok, err = save_project(p, user=user)
            if ok:
                st.success(f"บันทึก '{p['name']}' แล้ว")
            else:
                st.error(f"❌ {err}")
    with b4:
        # [NEW] Duplicate
        if st.button("📋 Copy", key=f"dup_{p['id']}", use_container_width=True,
                     help="Duplicate โปรเจกต์นี้"):
            new_pid = duplicate_project(p["id"])
            if new_pid:
                st.success(f"✅ Duplicate แล้ว → COPY_{p['name']}")
                st.rerun()
    with b5:
        if st.button("🗑️ ลบ", key=f"del_{p['id']}", use_container_width=True):
            st.session_state[f"confirm_del_{p['id']}"] = True
            st.rerun()

    # Confirm ลบ
    if st.session_state.get(f"confirm_del_{p['id']}"):
        st.error(f"⚠️ ยืนยันลบ **{p['name']}** ? ไม่สามารถกู้คืนได้!")
        ca, cb = st.columns(2)
        with ca:
            if st.button("✅ ยืนยันลบ", key=f"yes_del_{p['id']}", use_container_width=True):
                delete_current_project(p["id"])
                del st.session_state[f"confirm_del_{p['id']}"]
                st.rerun()
        with cb:
            if st.button("❌ ยกเลิก", key=f"no_del_{p['id']}", use_container_width=True):
                del st.session_state[f"confirm_del_{p['id']}"]
                st.rerun()

    # โหมดแก้ไขข้อมูลพื้นฐาน
    if st.session_state.get(f"editing_{p['id']}"):
        with st.expander(f"✏️ แก้ไขข้อมูล — {p['name']}", expanded=True):
            with st.form(f"edit_form_{p['id']}"):

                e1c1, e1c2 = st.columns([3, 2])
                new_name          = e1c1.text_input("เลขที่ใบเสนอราคา", value=p.get("name",""))
                new_customer_code = e1c2.text_input("รหัสลูกค้า", value=p.get("customer_code",""))

                e2c1, e2c2 = st.columns(2)
                new_customer      = e2c1.text_input("ชื่อผู้ติดต่อ", value=p.get("customer",""))
                new_angency       = e2c2.text_input("บริษัท / หน่วยงาน", value=p.get("angency_name",""))

                e3c1, e3c2 = st.columns(2)
                new_taxid         = e3c1.text_input("เลขประจำตัวผู้เสียภาษี", value=p.get("customer_taxid",""))
                new_phone         = e3c2.text_input("เบอร์โทร", value=p.get("phone",""))

                new_address       = st.text_area("ที่อยู่บริษัท / ลูกค้า", value=p.get("address",""), height=60)

                e4c1, e4c2 = st.columns(2)
                new_proj_site     = e4c1.text_input("ชื่อโครงการ", value=p.get("project_name_site",""))
                new_install_loc   = e4c2.text_input("สถานที่ติดตั้ง", value=p.get("install_location",""))

                e5c1, e5c2, e5c3 = st.columns(3)
                new_po_ref        = e5c1.text_input("เลขที่อ้างอิง PO", value=p.get("po_ref",""))
                new_salesperson   = e5c2.text_input("พนักงานขาย", value=p.get("salesperson",""))
                new_job           = e5c3.selectbox("ประเภทงาน", ["ติดตั้งใหม่","ซ่อม/เปลี่ยน","ต่อเติม"],
                                                   index=["ติดตั้งใหม่","ซ่อม/เปลี่ยน","ต่อเติม"].index(p.get("job_type","ติดตั้งใหม่")))

                new_notes         = st.text_area("หมายเหตุ", value=p.get("notes",""), height=68)

                _status_opts   = ["draft", "sent", "approved"]
                _status_labels = {"draft":"📝 Draft","sent":"📤 Sent","approved":"✅ Approved"}
                new_status = st.selectbox("สถานะงาน", _status_opts,
                                          index=_status_opts.index(p.get("status","draft")),
                                          format_func=lambda x: _status_labels[x])

                sc1, sc2 = st.columns(2)
                with sc1:
                    if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True, type="primary"):
                        p["name"]              = new_name
                        p["customer_code"]     = new_customer_code
                        p["customer"]          = new_customer
                        p["angency_name"]      = new_angency
                        p["customer_taxid"]    = new_taxid
                        p["phone"]             = new_phone
                        p["address"]           = new_address
                        p["project_name_site"] = new_proj_site
                        p["install_location"]  = new_install_loc
                        p["po_ref"]            = new_po_ref
                        p["salesperson"]       = new_salesperson
                        p["job_type"]          = new_job
                        p["notes"]             = new_notes
                        p["status"]            = new_status
                        user = st.session_state.get("current_user", "")
                        ok, err = save_project(p, user=user)
                        if ok:
                            del st.session_state[f"editing_{p['id']}"]
                            st.success("✅ บันทึกแล้ว!")
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")
                with sc2:
                    if st.form_submit_button("❌ ยกเลิก", use_container_width=True):
                        del st.session_state[f"editing_{p['id']}"]
                        st.rerun()

"""
Aqualine — Admin Dashboard (page_admin.py)
แดชบอร์ดผู้บริหาร: KPI, กราฟยอดขาย, ผลงานพนักงาน, ตารางโปรเจกต์
[NEW] User Management + Activity Log
วางไว้ที่: pages/page_admin.py
"""
import streamlit as st
from pages.page_login import touch_session
import pandas as pd
from datetime import datetime

# ──────────────────────────────────────────
# DATA LAYER
# ──────────────────────────────────────────

def _load_projects() -> dict:
    try:
        from utils.storage import load_all_projects
        projects, _ = load_all_projects()
        return projects
    except Exception:
        return st.session_state.get("projects", {})


@st.cache_data(ttl=60)
def get_analytics_data(_projects_snapshot: str) -> pd.DataFrame:
    import json
    projects = json.loads(_projects_snapshot)
    rows = []

    for pid, p in projects.items():
        boq    = p.get("boq", {})
        canvas = p.get("canvas_boq", {})
        total  = 0
        if isinstance(boq, dict):
            total = boq.get("grand_total", boq.get("total", 0)) or 0

        rows.append({
            "id":              pid,
            "วันที่สร้าง":     p.get("created", "")[:10] if p.get("created") else "",
            "ชื่องาน":         p.get("name", "ไม่มีชื่อ"),
            "ลูกค้า":          p.get("customer", p.get("address", "")),
            "พนักงาน":         p.get("created_by", "ไม่ระบุ"),
            "ความยาวราง (ม.)": float(canvas.get("gutter_length", 0) or 0),
            "มูลค่า (฿)":      float(total),
            "สถานะ":           p.get("status", "draft"),
        })

    df = pd.DataFrame(rows)
    if not df.empty and "วันที่สร้าง" in df.columns:
        df["วันที่สร้าง"] = pd.to_datetime(df["วันที่สร้าง"], errors="coerce")
        df = df.sort_values("วันที่สร้าง", ascending=False)
    return df


# ──────────────────────────────────────────
# CSS
# ──────────────────────────────────────────

ADMIN_CSS = """
<style>
.adm-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 1.4rem;
}
.adm-kpi {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    border-top: 3px solid #1E3A8A;
    box-shadow: 0 2px 8px rgba(13,33,68,0.07);
}
.adm-kpi .kpi-label {
    font-size: 0.70rem;
    color: #6B7A99;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.adm-kpi .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #0D2144;
    line-height: 1.1;
}
.adm-kpi .kpi-sub {
    font-size: 0.72rem;
    color: #8898B3;
    margin-top: 3px;
}
.adm-kpi.accent { border-top-color: #22C55E; }
.adm-kpi.warn   { border-top-color: #F59E0B; }
.adm-kpi.info   { border-top-color: #3B82F6; }

.adm-section {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    border: 1px solid #E4EAF8;
    box-shadow: 0 2px 12px rgba(13,33,68,0.05);
    margin-bottom: 1.2rem;
}
.adm-section-title {
    font-size: 0.78rem;
    font-weight: 700;
    color: #0D2144;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-left: 3px solid #1E3A8A;
    padding-left: 10px;
    margin-bottom: 1rem;
}
.adm-badge {
    display: inline-block;
    font-size: 0.68rem;
    padding: 2px 10px;
    border-radius: 20px;
    font-weight: 600;
}
.adm-badge.draft    { background:#EFF6FF; color:#1D4ED8; }
.adm-badge.sent     { background:#F0FDF4; color:#15803D; }
.adm-badge.approved { background:#FEF9C3; color:#A16207; }
.adm-empty {
    text-align: center;
    padding: 3rem 1rem;
    color: #8898B3;
    font-size: 0.88rem;
}
.adm-refresh-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}
.adm-ts { font-size: 0.70rem; color: #8898B3; }

/* User management table */
.usr-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 8px;
    background: #F8FAFF;
    border: 1px solid #E4EAF8;
    margin-bottom: 8px;
}
.usr-name { font-weight: 600; color: #0D2144; font-size: 0.9rem; }
.usr-role-admin { background:#FEF9C3; color:#A16207; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }
.usr-role-user  { background:#EFF6FF; color:#1D4ED8; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }

/* Activity log */
.log-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid #F0F4FF;
    font-size: 0.82rem;
}
.log-ts   { color: #8898B3; white-space: nowrap; min-width: 120px; }
.log-icon { min-width: 22px; text-align: center; }
.log-body { color: #0D2144; }
.log-user { color: #6B7A99; font-size: 0.75rem; }
</style>
"""

# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────

def _fmt_thb(val: float) -> str:
    if val >= 1_000_000:
        return f"฿ {val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"฿ {val:,.0f}"
    return f"฿ {val:.0f}"


def _get_users_db() -> dict:
    try:
        users = st.secrets.get("users", {})
        if users:
            return {u: dict(cfg) for u, cfg in users.items()}
    except Exception:
        pass
    # fallback
    from pages.page_login import _FALLBACK_USERS
    return _FALLBACK_USERS


def _save_users_db(users: dict):
    """
    บันทึก users ลง .streamlit/secrets.toml
    (Streamlit Cloud ไม่รองรับ write secrets — ใช้วิธี local file แทน)
    """
    import toml
    from pathlib import Path
    secrets_path = Path(".streamlit/secrets.toml")
    try:
        if secrets_path.exists():
            with open(secrets_path, "r", encoding="utf-8") as f:
                data = toml.load(f)
        else:
            data = {}
        data["users"] = users
        with open(secrets_path, "w", encoding="utf-8") as f:
            toml.dump(data, f)
        return True, ""
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════
# USER MANAGEMENT SECTION [NEW]
# ══════════════════════════════════════════

def _show_user_management():
    st.markdown('<div class="adm-section-title">👥 จัดการผู้ใช้งาน</div>', unsafe_allow_html=True)

    ACTION_ICONS = {"create": "➕", "save": "💾", "delete": "🗑️",
                    "duplicate": "📋", "edit": "✏️", "backup": "🔒"}

    users = _get_users_db()

    # ── แสดงรายชื่อผู้ใช้ปัจจุบัน ──
    st.markdown("**รายชื่อผู้ใช้งานทั้งหมด**")
    for username, cfg in users.items():
        role_class = "usr-role-admin" if cfg.get("role") == "admin" else "usr-role-user"
        role_label = "👑 Admin" if cfg.get("role") == "admin" else "👤 User"
        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div class="usr-row">
                <div>
                    <div class="usr-name">@{username} — {cfg.get('name','')}</div>
                    <span class="{role_class}">{role_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            # ไม่ให้ลบ admin คนสุดท้าย หรือตัวเอง
            is_self = username == st.session_state.get("current_user")
            admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
            can_delete = not is_self and not (cfg.get("role") == "admin" and admin_count <= 1)
            if can_delete:
                if st.button("🗑️", key=f"del_user_{username}", help=f"ลบผู้ใช้ {username}"):
                    st.session_state[f"confirm_del_user_{username}"] = True
                    st.rerun()
            else:
                st.markdown(
                    '<span style="font-size:0.7rem;color:#8898B3">ลบไม่ได้</span>',
                    unsafe_allow_html=True,
                )

        # Confirm ลบ user
        if st.session_state.get(f"confirm_del_user_{username}"):
            st.warning(f"⚠️ ยืนยันลบผู้ใช้ **@{username}** ?")
            ya, na = st.columns(2)
            with ya:
                if st.button("✅ ยืนยันลบ", key=f"yes_del_user_{username}", use_container_width=True):
                    new_users = {k: v for k, v in users.items() if k != username}
                    ok, err = _save_users_db(new_users)
                    del st.session_state[f"confirm_del_user_{username}"]
                    if ok:
                        st.success(f"ลบผู้ใช้ @{username} แล้ว — รีสตาร์ทแอปเพื่อให้มีผล")
                        from utils.storage import log_activity
                        log_activity("delete", project_name="",
                                     user=st.session_state.get("current_user",""),
                                     detail=f"deleted user: {username}")
                    else:
                        st.error(f"❌ {err}")
                    st.rerun()
            with na:
                if st.button("❌ ยกเลิก", key=f"no_del_user_{username}", use_container_width=True):
                    del st.session_state[f"confirm_del_user_{username}"]
                    st.rerun()

    st.markdown("---")

    # ── ฟอร์มเพิ่ม user ใหม่ ──
    st.markdown("**เพิ่มผู้ใช้งานใหม่**")
    with st.form("add_user_form"):
        nc1, nc2 = st.columns(2)
        new_username = nc1.text_input("Username", placeholder="เช่น sales3", max_chars=30)
        new_display  = nc2.text_input("ชื่อแสดง", placeholder="เช่น เซลส์ ซี")

        pc1, pc2, pc3 = st.columns(3)
        new_pass  = pc1.text_input("รหัสผ่าน", placeholder="อย่างน้อย 4 ตัว", type="password")
        new_pass2 = pc2.text_input("ยืนยันรหัสผ่าน", type="password")
        new_role  = pc3.selectbox("สิทธิ์", ["user", "admin"],
                                  format_func=lambda x: "👤 User" if x == "user" else "👑 Admin")

        if st.form_submit_button("➕ เพิ่มผู้ใช้", use_container_width=True, type="primary"):
            err_msgs = []
            if not new_username.strip():
                err_msgs.append("กรุณาใส่ Username")
            elif new_username in users:
                err_msgs.append(f"Username '{new_username}' มีอยู่แล้ว")
            if len(new_pass) < 4:
                err_msgs.append("รหัสผ่านต้องมีอย่างน้อย 4 ตัวอักษร")
            if new_pass != new_pass2:
                err_msgs.append("รหัสผ่านไม่ตรงกัน")

            if err_msgs:
                for msg in err_msgs:
                    st.error(msg)
            else:
                users[new_username] = {
                    "pass": new_pass,
                    "role": new_role,
                    "name": new_display or new_username,
                }
                ok, err = _save_users_db(users)
                if ok:
                    st.success(f"✅ เพิ่มผู้ใช้ @{new_username} แล้ว — รีสตาร์ทแอปเพื่อให้มีผล")
                    from utils.storage import log_activity
                    log_activity("create", project_name="",
                                 user=st.session_state.get("current_user",""),
                                 detail=f"added user: {new_username} ({new_role})")
                else:
                    st.error(f"❌ บันทึกไม่สำเร็จ: {err}")
                    st.info("💡 หากรัน Streamlit Cloud ให้เพิ่ม user ใน secrets.toml โดยตรงครับ")

    # ── เปลี่ยนรหัสผ่าน ──
    st.markdown("---")
    st.markdown("**เปลี่ยนรหัสผ่าน**")
    with st.form("change_pass_form"):
        cp1, cp2, cp3 = st.columns(3)
        cp_user  = cp1.selectbox("เลือกผู้ใช้", list(users.keys()))
        cp_pass  = cp2.text_input("รหัสผ่านใหม่", type="password", placeholder="อย่างน้อย 4 ตัว")
        cp_pass2 = cp3.text_input("ยืนยัน", type="password")

        if st.form_submit_button("🔑 เปลี่ยนรหัสผ่าน", use_container_width=True):
            if len(cp_pass) < 4:
                st.error("รหัสผ่านต้องมีอย่างน้อย 4 ตัวอักษร")
            elif cp_pass != cp_pass2:
                st.error("รหัสผ่านไม่ตรงกัน")
            else:
                users[cp_user]["pass"] = cp_pass
                ok, err = _save_users_db(users)
                if ok:
                    st.success(f"✅ เปลี่ยนรหัสผ่านของ @{cp_user} แล้ว")
                else:
                    st.error(f"❌ {err}")
                    st.info("💡 หากรัน Streamlit Cloud ให้แก้ใน secrets.toml โดยตรงครับ")


# ══════════════════════════════════════════
# ACTIVITY LOG SECTION [NEW]
# ══════════════════════════════════════════

def _show_activity_log():
    from utils.storage import load_activity_log
    st.markdown('<div class="adm-section-title">📜 ประวัติการแก้ไข (Activity Log)</div>',
                unsafe_allow_html=True)

    ACTION_ICONS = {
        "create":    ("➕", "#22C55E"),
        "save":      ("💾", "#3B82F6"),
        "delete":    ("🗑️", "#EF4444"),
        "duplicate": ("📋", "#8B5CF6"),
        "edit":      ("✏️", "#F59E0B"),
        "backup":    ("🔒", "#6B7A99"),
    }
    ACTION_LABELS = {
        "create":    "สร้างโปรเจกต์",
        "save":      "บันทึกโปรเจกต์",
        "delete":    "ลบโปรเจกต์",
        "duplicate": "Duplicate โปรเจกต์",
        "edit":      "แก้ไข",
        "backup":    "Backup",
    }

    lc1, lc2 = st.columns([3, 1])
    with lc2:
        log_limit = st.selectbox("แสดง", [50, 100, 200, 500], key="log_limit_sel",
                                 format_func=lambda x: f"{x} รายการล่าสุด")
    with lc1:
        log_filter = st.selectbox("กรองประเภท",
                                  ["ทั้งหมด", "create", "save", "delete", "duplicate", "edit"],
                                  format_func=lambda x: "ทั้งหมด" if x == "ทั้งหมด" else ACTION_LABELS.get(x, x),
                                  key="log_filter_sel")

    logs = load_activity_log(limit=log_limit)

    if log_filter != "ทั้งหมด":
        logs = [l for l in logs if l.get("action") == log_filter]

    if not logs:
        st.markdown('<div class="adm-empty">📭 ยังไม่มีประวัติในระบบ</div>',
                    unsafe_allow_html=True)
        return

    for entry in logs:
        action = entry.get("action", "")
        icon, color = ACTION_ICONS.get(action, ("📌", "#6B7A99"))
        label = ACTION_LABELS.get(action, action)
        ts_raw = entry.get("timestamp", "")
        try:
            ts_dt = datetime.fromisoformat(ts_raw)
            ts_str = ts_dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            ts_str = ts_raw[:16]

        proj  = entry.get("project_name", "")
        user  = entry.get("user", "")
        detail = entry.get("detail", "")
        body  = f"{label}{' — ' + proj if proj else ''}{' · ' + detail if detail else ''}"

        # ⚠️ จุดที่แก้ไข: ดันแท็ก HTML ชิดซ้ายทั้งหมดเพื่อไม่ให้เกิดกล่องสีเทา
        st.markdown(f"""<div class="log-row">
<div class="log-ts">{ts_str}</div>
<div class="log-icon" style="color:{color}">{icon}</div>
<div>
<div class="log-body">{body}</div>
{f'<div class="log-user">👤 {user}</div>' if user else ''}
</div>
</div>""", unsafe_allow_html=True)

    # Export log
    st.markdown("<div style='margin-top:1rem'>", unsafe_allow_html=True)
    import json
    import pandas as pd
    log_csv = pd.DataFrame(load_activity_log(limit=500))
    if not log_csv.empty:
        csv_data = log_csv.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 Export Activity Log (.csv)",
            data=csv_data,
            file_name=f"activity_log_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════

def show():
    if st.session_state.get("user_role") != "admin":
        st.error("⛔ คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return

    st.markdown(ADMIN_CSS, unsafe_allow_html=True)
    touch_session()

    st.markdown('<div class="page-title">📊 Admin Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">ภาพรวมยอดประเมิน · ผลงานพนักงาน · จัดการผู้ใช้ · ประวัติการแก้ไข</div>',
        unsafe_allow_html=True,
    )

    # ── Tabs หลัก ──
    tab_dash, tab_users, tab_log = st.tabs(["📊 Dashboard", "👥 จัดการผู้ใช้", "📜 Activity Log"])

    # ════════════════════════
    # TAB 1: DASHBOARD (เดิม)
    # ════════════════════════
    with tab_dash:
        import json
        raw = _load_projects()
        snapshot = json.dumps(raw, ensure_ascii=False, default=str)
        df = get_analytics_data(snapshot)

        # Refresh bar
        col_ts, col_btn = st.columns([4, 1])
        with col_ts:
            ts = datetime.now().strftime("%d/%m/%Y %H:%M")
            st.markdown(f'<div class="adm-ts">อัปเดตล่าสุด: {ts}</div>', unsafe_allow_html=True)
        with col_btn:
            if st.button("🔄 รีเฟรช", key="adm_refresh", use_container_width=True):
                get_analytics_data.clear()
                st.rerun()

        if df.empty:
            st.markdown(
                '<div class="adm-empty">📂 ยังไม่มีโปรเจกต์ในระบบ<br/>'
                '<span style="font-size:0.78rem">เมื่อทีมเริ่มสร้างงาน ข้อมูลจะปรากฏที่นี่</span></div>',
                unsafe_allow_html=True,
            )
        else:
            # KPI
            total_proj   = len(df)
            total_rev    = df["มูลค่า (฿)"].sum()
            total_len    = df["ความยาวราง (ม.)"].sum()
            active_staff = df["พนักงาน"].nunique()
            avg_rev      = total_rev / total_proj if total_proj else 0

            st.markdown(f"""
            <div class="adm-kpi-grid">
                <div class="adm-kpi">
                    <div class="kpi-label">จำนวนงานทั้งหมด</div>
                    <div class="kpi-value">{total_proj}</div>
                    <div class="kpi-sub">โปรเจกต์</div>
                </div>
                <div class="adm-kpi accent">
                    <div class="kpi-label">มูลค่าประเมินรวม</div>
                    <div class="kpi-value">{_fmt_thb(total_rev)}</div>
                    <div class="kpi-sub">เฉลี่ย {_fmt_thb(avg_rev)} / งาน</div>
                </div>
                <div class="adm-kpi info">
                    <div class="kpi-label">ความยาวรางรวม</div>
                    <div class="kpi-value">{total_len:,.1f}</div>
                    <div class="kpi-sub">เมตร</div>
                </div>
                <div class="adm-kpi warn">
                    <div class="kpi-label">พนักงานที่ใช้งาน</div>
                    <div class="kpi-value">{active_staff}</div>
                    <div class="kpi-sub">คน</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Charts
            col_l, col_r = st.columns(2, gap="medium")
            with col_l:
                st.markdown('<div class="adm-section">', unsafe_allow_html=True)
                st.markdown('<div class="adm-section-title">ผลงานรายบุคคล (จำนวนงาน)</div>',
                            unsafe_allow_html=True)
                emp_cnt = (df.groupby("พนักงาน").size().reset_index(name="จำนวนงาน")
                           .sort_values("จำนวนงาน", ascending=False))
                st.bar_chart(emp_cnt, x="พนักงาน", y="จำนวนงาน", use_container_width=True, height=260)
                st.markdown("</div>", unsafe_allow_html=True)

            with col_r:
                st.markdown('<div class="adm-section">', unsafe_allow_html=True)
                st.markdown('<div class="adm-section-title">มูลค่าเสนอราคารายบุคคล (฿)</div>',
                            unsafe_allow_html=True)
                emp_rev = (df.groupby("พนักงาน")["มูลค่า (฿)"].sum().reset_index()
                           .sort_values("มูลค่า (฿)", ascending=False))
                emp_rev["มูลค่า (฿)"] = emp_rev["มูลค่า (฿)"].round(0)
                st.bar_chart(emp_rev, x="พนักงาน", y="มูลค่า (฿)", use_container_width=True, height=260)
                st.markdown("</div>", unsafe_allow_html=True)

            # Monthly trend
            df_dated = df.dropna(subset=["วันที่สร้าง"])
            if not df_dated.empty:
                st.markdown('<div class="adm-section">', unsafe_allow_html=True)
                st.markdown('<div class="adm-section-title">แนวโน้มงานรายเดือน</div>',
                            unsafe_allow_html=True)
                monthly = (
                    df_dated
                    .assign(เดือน=df_dated["วันที่สร้าง"].dt.to_period("M").astype(str))
                    .groupby("เดือน")
                    .agg(**{"จำนวนงาน": ("id", "count"), "มูลค่ารวม": ("มูลค่า (฿)", "sum")})
                    .reset_index()
                    .sort_values("เดือน")
                )
                monthly["มูลค่ารวม"] = monthly["มูลค่ารวม"].round(0)
                t1, t2 = st.tabs(["จำนวนงาน", "มูลค่ารวม (฿)"])
                with t1:
                    st.bar_chart(monthly, x="เดือน", y="จำนวนงาน", use_container_width=True, height=220)
                with t2:
                    st.bar_chart(monthly, x="เดือน", y="มูลค่ารวม", use_container_width=True, height=220)
                st.markdown("</div>", unsafe_allow_html=True)

            # Data table
            st.markdown('<div class="adm-section">', unsafe_allow_html=True)
            st.markdown('<div class="adm-section-title">รายการโปรเจกต์ทั้งหมด</div>',
                        unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                staff_opts = ["ทั้งหมด"] + sorted(df["พนักงาน"].unique().tolist())
                sel_staff  = st.selectbox("กรองตามพนักงาน", staff_opts, key="adm_staff_filter")
            with fc2:
                status_opts = ["ทั้งหมด"] + sorted(df["สถานะ"].unique().tolist())
                sel_status  = st.selectbox("กรองตามสถานะ", status_opts, key="adm_status_filter")
            with fc3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                show_all = st.checkbox("แสดงทั้งหมด", key="adm_show_all")

            dft = df.copy()
            if sel_staff  != "ทั้งหมด": dft = dft[dft["พนักงาน"] == sel_staff]
            if sel_status != "ทั้งหมด": dft = dft[dft["สถานะ"] == sel_status]
            if not show_all: dft = dft.head(50)

            display_df = dft[["วันที่สร้าง","ชื่องาน","ลูกค้า","พนักงาน","ความยาวราง (ม.)","มูลค่า (฿)","สถานะ"]].copy()
            display_df["วันที่สร้าง"]    = display_df["วันที่สร้าง"].dt.strftime("%d/%m/%Y").fillna("-")
            display_df["มูลค่า (฿)"]     = display_df["มูลค่า (฿)"].apply(lambda x: f"{x:,.0f}")
            display_df["ความยาวราง (ม.)"] = display_df["ความยาวราง (ม.)"].apply(lambda x: f"{x:,.1f}")
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=380)
            st.markdown("</div>", unsafe_allow_html=True)

            # Download
            export_df = df.copy()
            export_df["วันที่สร้าง"] = export_df["วันที่สร้าง"].dt.strftime("%d/%m/%Y").fillna("")
            csv = export_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Export ข้อมูลทั้งหมด (.csv)",
                data=csv,
                file_name=f"aqualine_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

    # ════════════════════════
    # TAB 2: USER MANAGEMENT [NEW]
    # ════════════════════════
    with tab_users:
        st.markdown('<div class="adm-section">', unsafe_allow_html=True)
        _show_user_management()
        st.markdown("</div>", unsafe_allow_html=True)

        st.info(
            "💡 **หมายเหตุ:** การเปลี่ยนแปลงจะมีผลหลังรีสตาร์ทแอป "
            "หากรันบน Streamlit Cloud ต้องแก้ไข `secrets.toml` ใน dashboard โดยตรงครับ",
            icon="ℹ️",
        )

    # ════════════════════════
    # TAB 3: ACTIVITY LOG [NEW]
    # ════════════════════════
    with tab_log:
        st.markdown('<div class="adm-section">', unsafe_allow_html=True)
        _show_activity_log()
        st.markdown("</div>", unsafe_allow_html=True)

"""
Aqualine Site Assessment App v2.0
โทนสี: ขาว / ฟ้า / น้ำเงินนาวี — Luxury
บันทึกข้อมูลลง disk อัตโนมัติ
"""
import streamlit as st
import subprocess, sys, os

# ── ติดตั้ง Chromium binary ให้ Playwright (Streamlit Cloud ต้องการขั้นตอนนี้) ──
# รันครั้งเดียวต่อ container lifetime; ถ้ามีแล้วจะเสร็จเร็วมาก
_pw_flag = os.path.join(os.path.expanduser("~"), ".pw_chromium_installed")
if not os.path.exists(_pw_flag):
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False, capture_output=True
    )
    open(_pw_flag, "w").close()

st.set_page_config(
    page_title="Aqualine Site Assessment",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.state import init_session, save_current_project
from pages.page_login import init_auth, require_login

# ── Auth gate: ต้อง login ก่อนเข้าแอปทุกครั้ง ──
init_auth()
require_login()

# ── โหลด session + disk ──
init_session()

cur = st.session_state.get("current_page", "home")

# ── auto-save เมื่อเปลี่ยนหน้า ──
if st.session_state.get("unsaved_changes"):
    save_current_project()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&family=Kanit:wght@400;600;700&display=swap');

#MainMenu {visibility: hidden;}
footer    {visibility: hidden;}
header    {background-color: transparent !important;}
[data-testid="stHeaderActionElements"] {display: none !important;}
[data-testid="stSidebarNav"] {display: none !important;}

html, body, [class*="css"] {
    font-family: 'Sarabun', sans-serif;
    background-color: #F0F4FF;
}

/* ════════════════════════════
   SIDEBAR
════════════════════════════ */
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #071020 0%, #0A1628 30%, #0D2144 70%, #102A56 100%) !important;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #071020 0%, #0A1628 30%, #0D2144 70%, #102A56 100%) !important;
}
[data-testid="stSidebar"] { border-right: 1px solid rgba(100,149,237,0.25) !important; }
[data-testid="stSidebar"] * { color: #D0DCFA !important; }

.sidebar-logo {
    text-align: center;
    padding: 1.4rem 0 1rem 0;
    border-bottom: 1px solid rgba(100,149,237,0.2);
    margin-bottom: 0.8rem;
}
.sidebar-logo .logo-drop { font-size: 2.4rem; line-height:1; }
.sidebar-logo h2 {
    font-family: 'Kanit', sans-serif;
    font-size: 1.2rem; font-weight: 700;
    color: #FFFFFF !important;
    letter-spacing: 3px; margin: 0.3rem 0 0 0;
}
.sidebar-logo p { font-size: 0.65rem; color: #5A7AA8 !important; letter-spacing: 2px; margin:0; text-transform:uppercase; }

.project-badge {
    background: rgba(100,149,237,0.10);
    border: 1px solid rgba(100,149,237,0.28);
    border-radius: 8px;
    padding: 0.5rem 0.8rem;
    margin: 0 0 0.9rem 0;
}
.project-badge .pb-label { font-size:0.63rem; color:#6A8AAC !important; text-transform:uppercase; letter-spacing:1px; }
.project-badge .pb-name  { font-size:0.92rem; font-weight:700; color:#FFFFFF !important; margin-top:2px; }

.nav-label {
    font-size: 0.63rem; color: #3A5878 !important;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 0 0.5rem; margin-bottom: 0.25rem;
}

/* Sidebar nav buttons */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #8AAAD4 !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 10px 10px 0 !important;
    width: 100% !important;
    text-align: left !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    transition: all 0.15s ease;
    margin-bottom: 2px !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(100,149,237,0.12) !important;
    color: #E0EAFF !important;
}
/* ลดระยะห่างแนวตั้งใน Sidebar ให้กระชับขึ้น */
[data-testid="stSidebar"] [data-testid="element-container"] {
    margin-top: 0px !important;
    margin-bottom: -10px !important;
    padding: 0px !important;
}
/* ซ่อน container ของ active marker เพื่อไม่ให้มีช่องว่างแนวตั้ง */
[data-testid="stSidebar"] [data-testid="element-container"]:has(.active-nav-marker) {
    display: none !important;
}
/* ไฮไลท์ปุ่มที่เป็น Active (เป็น sibling ถัดจาก marker) */
[data-testid="stSidebar"] [data-testid="element-container"]:has(.active-nav-marker) + [data-testid="element-container"] button {
    background: rgba(100,149,237,0.22) !important;
    color: #FFFFFF !important;
    border-left: 3px solid #6495ED !important;
    font-weight: 700 !important;
}

/* Save indicator */
.save-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
}
.save-dot.saved   { background: #22C55E; }
.save-dot.unsaved { background: #F59E0B; animation: pulse 1.2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ════════════════════════════
   TOP NAV BAR
════════════════════════════ */
.topnav-bar {
    background: linear-gradient(90deg, #071020 0%, #0D2144 55%, #1A3570 100%);
    border-radius: 10px;
    padding: 7px 10px;
    margin-bottom: 1.1rem;
    box-shadow: 0 4px 24px rgba(7,16,32,0.25);
    border: 1px solid rgba(100,149,237,0.18);
}

/* active / inactive wrapper classes */
.tnav-active   > div > div > div.stButton > button,
.tnav-active   > div > div > div > .stButton > button {
    background: rgba(255,255,255,0.15) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(100,149,237,0.55) !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    box-shadow: inset 0 0 8px rgba(100,149,237,0.15) !important;
}
.tnav-inactive > div > div > div.stButton > button,
.tnav-inactive > div > div > div > .stButton > button {
    background: transparent !important;
    color: #7A9AC4 !important;
    border: 1px solid transparent !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
}
.tnav-inactive > div > div > div.stButton > button:hover,
.tnav-inactive > div > div > div > .stButton > button:hover {
    background: rgba(100,149,237,0.15) !important;
    color: #D8E8FF !important;
    border: 1px solid rgba(100,149,237,0.3) !important;
}

/* ════════════════════════════
   MAIN CONTENT
════════════════════════════ */
.block-container { padding-top: 0.8rem !important; padding-bottom: 2rem; }

.page-title {
    font-family: 'Kanit', sans-serif;
    font-size: 1.5rem; font-weight: 700;
    color: #0D2144; margin-bottom: 0.1rem;
}
.page-subtitle { font-size: 0.85rem; color: #6B7A99; margin-bottom: 1rem; }

.section-header {
    background: linear-gradient(90deg, #0D2144, #1E3A8A);
    color: white !important;
    padding: 0.5rem 1rem; border-radius: 8px;
    font-weight: 600; font-size: 0.92rem;
    margin: 1rem 0 0.7rem 0;
}

.metric-card {
    background: #FFFFFF; border-radius: 10px;
    padding: 0.85rem 1rem;
    box-shadow: 0 2px 8px rgba(13,33,68,0.07);
    border-top: 3px solid #1E3A8A; margin-bottom: 0.7rem;
}
.metric-card .label  { font-size: 0.73rem; color: #6B7A99; margin-bottom: 0.2rem; }
.metric-card .value  { font-size: 1.4rem; font-weight: 700; color: #0D2144; }
.metric-card .unit   { font-size: 0.78rem; color: #6B7A99; margin-left: 0.2rem; }

.ok-box {
    background: #EFF6FF; border-left: 4px solid #3B82F6;
    padding: 0.65rem 1rem; border-radius: 0 8px 8px 0;
    font-size: 0.86rem; margin: 0.5rem 0; color: #1E3A8A;
}
.warn-box {
    background: #FEF9C3; border-left: 4px solid #EAB308;
    padding: 0.65rem 1rem; border-radius: 0 8px 8px 0;
    font-size: 0.86rem; margin: 0.5rem 0; color: #713F12;
}
.card {
    background: #FFFFFF; border-radius: 12px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 2px 12px rgba(13,33,68,0.07);
    border: 1px solid #E4EAF8; margin-bottom: 0.9rem;
}

.stNumberInput input, .stTextInput input, .stTextArea textarea {
    border-radius: 8px !important;
    border: 1px solid #C8D5F0 !important;
    background: #FAFBFF !important;
}
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1px solid #C8D5F0 !important;
    background: #FAFBFF !important;
}

hr { border-color: #E4EAF8; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════
with st.sidebar:
    # Logo + Brand
    import os
    logo_path = "assets/Logo-gray.png"
    if os.path.exists(logo_path):
        import base64
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="text-align:center;padding:1.4rem 0 0.5rem;">'
            f'<img src="data:image/png;base64,{b64}" style="height:76px;width:auto;" alt="logo">'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<div style="text-align:center;font-size:2.4rem;padding:1rem 0 0.5rem">💧</div>',
                    unsafe_allow_html=True)

    st.markdown("""
    <div class="sidebar-logo" style="padding-top:0.1rem;margin-top:-0.5rem;">
        <h2>AQUALINE</h2>
        <p>Site Assessment v3.0</p>
    </div>
    """, unsafe_allow_html=True)

    # ── ชื่อผู้ใช้ + ปุ่ม logout ──
    user_display = st.session_state.get("user_display", "")
    user_role    = st.session_state.get("user_role", "user")
    role_badge   = "👑 Admin" if user_role == "admin" else "👤 User"
    st.markdown(f"""
    <div class="project-badge" style="margin-bottom:0.5rem">
        <div class="pb-label">{role_badge}</div>
        <div class="pb-name">{user_display}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 ออกจากระบบ", key="sb_logout", use_container_width=True):
        from pages.page_login import logout
        logout()

    # Project badge
    proj_id = st.session_state.get("current_project_id")
    if proj_id and proj_id in st.session_state.projects:
        p = st.session_state.projects[proj_id]
        unsaved = st.session_state.get("unsaved_changes", False)
        dot_class = "unsaved" if unsaved else "saved"
        dot_label = "ยังไม่บันทึก" if unsaved else "บันทึกแล้ว"
        st.markdown(f"""
        <div class="project-badge">
            <div class="pb-label">📁 โปรเจกต์ปัจจุบัน</div>
            <div class="pb-name">{p['name']}</div>
            <div style="font-size:0.65rem;color:#5A7AA8 !important;margin-top:3px;">
                <span class="save-dot {dot_class}"></span>{dot_label}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ปุ่ม save ใน sidebar
        if st.button("💾 บันทึกโปรเจกต์", key="sb_save", use_container_width=True):
            from utils.state import save_current_project
            save_current_project()
            st.success("บันทึกแล้ว!")
    else:
        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.75rem;color:#3A5878;text-align:center;padding:0.5rem;">'
            'ยังไม่มีโปรเจกต์ที่เลือก</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Nav items
    st.markdown('<div class="nav-label">เมนูหลัก</div>', unsafe_allow_html=True)

    nav_items = [
        ("home",   "🏗️", "จัดการโปรเจกต์"),
        ("canvas", "✏️", "วาดแบบหน้าตัด"),
        # ("assess", "📋", "ประเมินหน้างาน"),
        ("boq",    "📦", "BOQ / รายการวัสดุ"),
    ]
    # Issue 4 — เอาเมนู "ตั้งราคาอุปกรณ์" ออก (ราคาคิดที่ GAS Admin "จัดตารางราคาขาย" ที่เดียว)

    # เมนู Admin — เห็นเฉพาะ role admin
    if st.session_state.get("user_role") == "admin":
        st.markdown('<div class="nav-label" style="margin-top:0.6rem">Admin</div>',
                    unsafe_allow_html=True)
        nav_items_admin = [("admin", "📊", "แดชบอร์ดผู้บริหาร")]
    else:
        nav_items_admin = []

    for key, icon, label in nav_items + nav_items_admin:
        is_active = (cur == key)
        if is_active:
            st.markdown('<div class="active-nav-marker"></div>', unsafe_allow_html=True)
        if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True):
            st.session_state.current_page = key
            st.rerun()

    st.markdown("---")

    # Stats
    n = len(st.session_state.get("projects", {}))
    st.markdown(
        f'<div style="font-size:0.68rem;color:#2A4060;text-align:center;">'
        f'📂 {n} โปรเจกต์ในเครื่อง<br/>'
        f'<span style="color:#1E3060;">aqualine_projects/</span></div>',
        unsafe_allow_html=True,
    )

# ════════════════════════════════════════════
# PAGE ROUTING
# ════════════════════════════════════════════
page = st.session_state.get("current_page", "home")

if page == "home":
    from pages import page_home;   page_home.show()
elif page == "canvas":
    from pages import page_canvas; page_canvas.show()
elif page == "assess":
    from pages import page_assess; page_assess.show()
elif page == "boq":
    from pages import page_boq;   page_boq.show()
elif page == "prices":
    from pages import page_prices; page_prices.show()
elif page == "admin" and st.session_state.get("user_role") == "admin":
    from pages import page_admin;  page_admin.show()

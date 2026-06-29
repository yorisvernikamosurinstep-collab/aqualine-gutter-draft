"""
Aqualine Login Page v3.3
- ทุก element อยู่ใน max-width เดียวกัน
- โลโก้ใหญ่ขึ้น อ่านออก
- card ครอบทั้งหมดรวม input
- [v3.2] Login attempt limit (5 ครั้ง / บล็อก 5 นาที)
- [v3.2] Session timeout (ไม่ใช้งาน 30 นาที → logout อัตโนมัติ)
- [v3.3] SSO via Apps Script API — ตรวจสอบ credentials ผ่าน Google Sheets (AQC_USERS)
         ถ้าไม่มี network หรือยังไม่ได้ตั้งค่า WEBAPP_URL จะ fallback ไปใช้ local secrets/fallback
"""
import streamlit as st
import os, base64, time, json
from datetime import datetime
try:
    import requests as _requests
except ImportError:
    _requests = None

# ──────────────────────────────────────────
# CONFIG
MAX_LOGIN_ATTEMPTS = 5          # ผิดได้กี่ครั้ง
LOCKOUT_SECONDS    = 5 * 60     # บล็อกกี่วินาที (5 นาที)
SESSION_TIMEOUT    = 30 * 60    # timeout กี่วินาที (30 นาที)

# ──────────────────────────────────────────
# Fallback สำหรับ dev — ถ้าไม่มี secrets.toml จะใช้ค่านี้แทน
_FALLBACK_USERS = {
    "NIKAMO":  {"pass": "aql638", "role": "admin", "name": "NIKAMO"},
    "sales1": {"pass": "1111",      "role": "user",  "name": "เซลส์ เอก"},
    "sales2": {"pass": "2222",      "role": "user",  "name": "เซลส์ บี"},
    "tech1":  {"pass": "3333",      "role": "user",  "name": "ช่าง ชัย"},
}

def _get_webapp_url() -> str:
    """อ่าน Apps Script Web App URL จาก secrets หรือ env variable"""
    try:
        url = st.secrets.get("webapp_url", "")
        if url:
            return url
    except Exception:
        pass
    return os.environ.get("WEBAPP_URL", "")


def _login_via_api(username: str, password: str) -> dict | None:
    """
    ส่ง POST ไปยัง Apps Script Web App เพื่อตรวจสอบ credentials
    คืน dict {ok, role, name, ...} ถ้าสำเร็จ หรือ None ถ้า network error / ไม่ได้ตั้งค่า URL
    """
    if _requests is None:
        _write_api_log("requests library not installed")
        return None
    webapp_url = _get_webapp_url()
    if not webapp_url:
        _write_api_log("webapp_url is empty")
        return None
    try:
        # GAS มักทำ 302 redirect → ต้องใช้ session เพื่อ handle ได้ถูกต้อง
        session = _requests.Session()
        resp = session.post(
            webapp_url,
            json={"action": "login", "username": username, "password": password},
            timeout=10,
            allow_redirects=True,
        )
        _write_api_log(f"status={resp.status_code} | url={resp.url} | body={resp.text[:400]}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                return data
            except Exception:
                _write_api_log("response is not JSON — likely HTML auth redirect")
                return None
    except Exception as ex:
        _write_api_log(f"exception: {ex}")
    return None


# ── LOG PATH (absolute) ──
_LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_LOG  = os.path.join(_LOG_DIR, "api_debug.txt")

def _write_api_log(msg: str):
    try:
        with open(_API_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {msg}\n")
    except Exception:
        pass


def _get_users_db() -> dict:
    """อ่าน users จาก .streamlit/secrets.toml ถ้าไม่มีให้ fallback (แปลง key เป็นตัวเล็กทั้งหมดเพื่อเทียบเคียงแบบ Case-insensitive)"""
    try:
        users = st.secrets.get("users", {})
        if users:
            return {u.lower(): dict(cfg) for u, cfg in users.items()}
    except Exception:
        pass
    return {u.lower(): dict(cfg) for u, cfg in _FALLBACK_USERS.items()}

def init_auth():
    defaults = {
        "logged_in":       False,
        "current_user":    None,
        "user_role":       None,
        "user_display":    None,
        # --- login attempt ---
        "login_attempts":  0,
        "lockout_until":   0,
        # --- session timeout ---
        "last_active":     0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# ──────────────────────────────────────────
# SESSION TIMEOUT — เรียกทุกครั้งที่ render หน้า
def check_session_timeout():
    """ถ้า login อยู่ และไม่มีการใช้งานนาน SESSION_TIMEOUT วินาที → logout"""
    if not st.session_state.get("logged_in"):
        return
    last = st.session_state.get("last_active", 0)
    if last and (time.time() - last) > SESSION_TIMEOUT:
        _do_logout(reason="timeout")

def touch_session():
    """อัปเดตเวลา last_active — เรียกในทุกหน้าที่ผู้ใช้ interact"""
    st.session_state["last_active"] = time.time()

# ──────────────────────────────────────────
LOGO_PATH = "assets/Logo-gray.png"

def _logo_b64() -> str:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="height:56px;width:auto;" alt="logo">'
    return """<svg width="56" height="52" viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polygon points="60,5 110,90 10,90" fill="none" stroke="rgba(255,255,255,0.85)" stroke-width="7"/>
      <polygon points="60,28 88,80 32,80" fill="rgba(200,50,40,0.85)"/>
      <rect x="42" y="62" width="36" height="18" fill="rgba(255,255,255,0.85)"/>
    </svg>"""

# ──────────────────────────────────────────
LOGIN_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #2a2a2a, #151515);
    min-height:100vh;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] { display: none !important; }
#MainMenu, footer, [data-testid="stToolbar"] { visibility:hidden; }

[data-testid="stMain"] > div > div > div.block-container {
    max-width: 100% !important;
    padding: 80px 16px 40px 16px !important;
    margin: 0 auto !important;
}

.lc-outer {
    max-width: 440px;
    margin: 0 auto;
    width: 100%;
}

/* จำกัดความกว้าง Streamlit widgets ให้ตรงกับ card */
[data-testid="stTextInput"],
[data-testid="stButton"],
[data-testid="stAlert"],
[data-testid="stWarning"] {
    max-width: 440px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

.lc-card {
    background: #ffffff !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    border-radius: 18px;
    padding: 36px 36px 32px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.5) !important;
}

.lc-logo-row {
    display:flex; align-items:center;
    justify-content:center; gap:18px;
    margin-bottom:10px;
}
.lc-vline {
    width:1px; height:52px;
    background: rgba(0, 0, 0, 0.12) !important;
    flex-shrink:0;
}
.lc-brand { display:flex; flex-direction:column; gap:5px; }
.lc-brand-top {
    display:flex; gap:12px; align-items:baseline;
}
.lc-brand-top span {
    font-size:20px; font-weight:700;
    color: #2c2c2c !important;
    letter-spacing:0.22em;
    font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
    line-height:1;
}
.lc-brand-sub {
    font-size:10px; font-weight:500;
    color: #5f6368 !important;
    font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
    white-space:nowrap;
    display:block;
}

.lc-divider {
    height:1px;
    background: rgba(232, 36, 39, 0.25) !important;
    margin:16px 0 10px;
}
.lc-tagline {
    text-align:center;
    font-size:13px;
    color: #5f6368 !important;
    letter-spacing:0.12em;
    text-transform:uppercase;
    font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
    margin-bottom:28px;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}

label[data-testid="stWidgetLabel"] p {
    color: #5f6368 !important;
    font-size: 11px !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    font-family:'Helvetica Neue',Helvetica,Arial,sans-serif !important;
}

input[type="text"],
input[type="password"],
[data-testid="stTextInput"] input,
[data-baseweb="input"] input,
[data-baseweb="base-input"] input {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #202124 !important;
    font-size: 14px !important;
    caret-color: #202124 !important;
}
[data-baseweb="base-input"],
[data-baseweb="input"] {
    background: #ffffff !important;
    border-radius: 8px !important;
}
input[type="text"]:focus,
input[type="password"]:focus,
[data-testid="stTextInput"] input:focus {
    border-color: #e82427 !important;
    background: #ffffff !important;
    box-shadow: 0 0 0 2px rgba(232,36,39,0.20) !important;
}
input::placeholder,
[data-testid="stTextInput"] input::placeholder {
    color: #94a3b8 !important;
}

[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #e82427 0%, #b71c1c 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0.10em !important;
    height: 46px !important;
    box-shadow: 0 4px 12px rgba(232, 36, 39, 0.25) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stButton"] > button:hover {
    opacity: 0.95 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(232, 36, 39, 0.35) !important;
}

[data-testid="stAlert"] {
    background: rgba(232,36,39,0.08) !important;
    border: 1px solid rgba(232,36,39,0.2) !important;
    border-radius: 8px !important;
    color: #b71c1c !important;
}

.lc-footer {
    text-align:center; font-size:11px;
    color:rgba(255,255,255,0.4) !important;
    margin-top:24px; letter-spacing:0.06em;
    font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
}

/* lockout warning box */
.lc-lockout {
    background: rgba(255,165,0,0.12);
    border: 1px solid rgba(255,165,0,0.35);
    border-radius: 8px;
    padding: 10px 14px;
    color: rgba(255,200,80,0.90);
    font-size: 13px;
    text-align: center;
    margin-bottom: 8px;
}
</style>

<script>
(function(){
  function run(){
    var top = document.getElementById('lcBrandTop');
    var sub = document.getElementById('lcBrandSub');
    if(!top||!sub){setTimeout(run,100);return;}
    var W = top.getBoundingClientRect().width;
    var txt = sub.textContent; var n = txt.length;
    var c = document.createElement('canvas');
    var ctx = c.getContext('2d');
    ctx.font = '500 10px Helvetica Neue,Helvetica,Arial,sans-serif';
    var bw = ctx.measureText(txt).width;
    if(bw<=0||n<=1){setTimeout(run,100);return;}
    sub.style.letterSpacing = Math.max(0,(W-bw)/(n-1)).toFixed(2)+'px';
  }
  document.readyState==='loading'
    ? document.addEventListener('DOMContentLoaded',function(){setTimeout(run,120);})
    : setTimeout(run,120);
})();
</script>
"""

# ──────────────────────────────────────────
def _remaining_lockout() -> int:
    """คืนวินาทีที่เหลือจนกว่าจะปลดล็อก (0 = ไม่ได้ถูกบล็อก)"""
    until = st.session_state.get("lockout_until", 0)
    remaining = int(until - time.time())
    return max(0, remaining)

def _reset_attempts():
    st.session_state["login_attempts"] = 0
    st.session_state["lockout_until"]  = 0

# ──────────────────────────────────────────
def show_login():
    init_auth()
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    logo = _logo_b64()

    st.markdown(f"""
    <div class="lc-outer">
      <div class="lc-card">
        <div class="lc-logo-row">
          {logo}
          <div class="lc-vline"></div>
          <div class="lc-brand">
            <div class="lc-brand-top" id="lcBrandTop">
              <span>AQUALINE</span><span>LINDAB</span>
            </div>
            <span class="lc-brand-sub" id="lcBrandSub">RAIN GUTTER SYSTEMS</span>
          </div>
        </div>
        <div class="lc-divider"></div>
        <div class="lc-tagline">Installation &amp; Estimation Management</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # spacer + inputs ใน container เดียวกัน (จำกัดความกว้างด้วย CSS)
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── ตรวจสอบ lockout ──
    remaining = _remaining_lockout()
    if remaining > 0:
        mins = remaining // 60
        secs = remaining % 60
        st.markdown(
            f'<div class="lc-outer"><div class="lc-lockout">🔒 บัญชีถูกล็อคชั่วคราว<br>'
            f'กรุณารอ <b>{mins:02d}:{secs:02d}</b> นาที แล้วลองใหม่</div></div>',
            unsafe_allow_html=True,
        )
        st.text_input("Username", disabled=True, key="login_user_locked")
        st.text_input("Password", disabled=True, type="password", key="login_pass_locked")
        st.button("Sign In", use_container_width=True, disabled=True, key="login_btn_locked")

    else:
        username = st.text_input("Username", placeholder="Enter your username",
                                 key="login_user")
        password = st.text_input("Password", placeholder="Enter your password",
                                 type="password", key="login_pass")

        if 0 < st.session_state.get("login_attempts", 0) < MAX_LOGIN_ATTEMPTS:
            attempts_left = MAX_LOGIN_ATTEMPTS - st.session_state.get("login_attempts", 0)
            st.warning(f"⚠️ รหัสผ่านไม่ถูกต้อง — เหลืออีก {attempts_left} ครั้ง")

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        if st.button("Sign In", use_container_width=True, key="login_btn"):
            login_ok   = False
            user_role  = "user"
            user_name  = username

            # ── ลองผ่าน Apps Script API ก่อน (Google Sheets AQC_USERS) ──
            api_result = _login_via_api(username, password)
            if api_result is not None and api_result.get("ok"):
                login_ok  = True
                user_role = api_result.get("role", "user")
                user_name = api_result.get("name", username)
            else:
                # ── Fallback: ตรวจสอบจาก local secrets / _FALLBACK_USERS (Case-insensitive) ──
                local_user = _get_users_db().get(username.lower())
                if local_user and local_user["pass"] == password:
                    login_ok  = True
                    user_role = local_user["role"]
                    user_name = local_user["name"]

            if login_ok:
                _reset_attempts()
                st.session_state.update({
                    "logged_in":    True,
                    "current_user": username,
                    "user_role":    user_role,
                    "user_display": user_name,
                    "last_active":  time.time(),
                })
                # คงสถานะล็อกอินไว้ใน URL → รีเฟรชแล้ว require_login กู้ session กลับได้ ไม่เด้งล็อกอินซ้ำ
                try:
                    st.query_params["user"] = username
                    st.query_params["role"] = user_role
                    st.query_params["name"] = user_name
                except Exception:
                    pass
                st.rerun()
            else:
                st.session_state["login_attempts"] += 1
                if st.session_state["login_attempts"] >= MAX_LOGIN_ATTEMPTS:
                    st.session_state["lockout_until"] = time.time() + LOCKOUT_SECONDS
                    st.error(f"🔒 กรอกผิดครบ {MAX_LOGIN_ATTEMPTS} ครั้ง — บัญชีถูกล็อค 5 นาที")
                else:
                    left = MAX_LOGIN_ATTEMPTS - st.session_state["login_attempts"]
                    st.error(f"ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง (เหลืออีก {left} ครั้ง)")

    st.markdown('<div class="lc-footer">Aqualine Site Assessment System v3.0</div>',
                unsafe_allow_html=True)

# ──────────────────────────────────────────
def _do_logout(reason: str = "manual"):
    st.session_state.update({
        "logged_in":    False,
        "current_user": None,
        "user_role":    None,
        "user_display": None,
        "last_active":  0,
    })
    try:
        st.query_params.clear()
    except Exception:
        pass
    if reason == "timeout":
        st.session_state["_logout_reason"] = "timeout"
    st.rerun()

def logout():
    _do_logout(reason="manual")

def require_login():
    init_auth()
    # ตรวจ session timeout ก่อนเสมอ
    check_session_timeout()

    # ── SSO Auto-login จาก Apps Script Web App ──
    if not st.session_state["logged_in"]:
        try:
            qp = st.query_params
            with open("sso_debug.txt", "a", encoding="utf-8") as debug_file:
                debug_file.write(f"[{datetime.now()}] qp keys: {list(qp.keys())}, qp dict: {dict(qp)}\n")
            if "user" in qp:
                username = qp["user"]
                role     = qp.get("role", "user")
                name     = qp.get("name", username)
                st.session_state.update({
                    "logged_in":    True,
                    "current_user": username,
                    "user_role":    role,
                    "user_display": name,
                    "last_active":  time.time(),
                })
                # ล้าง query parameters เพื่อทำความสะอาด URL
                # st.query_params.clear()
                st.rerun()
        except Exception as e:
            try:
                with open("sso_error.txt", "a", encoding="utf-8") as error_file:
                    import traceback
                    error_file.write(f"[{datetime.now()}] Error: {str(e)}\n{traceback.format_exc()}\n")
            except Exception:
                pass

    if not st.session_state["logged_in"]:
        # แสดงข้อความถ้า timeout
        if st.session_state.pop("_logout_reason", None) == "timeout":
            st.warning("⏱️ ระบบออกจากระบบอัตโนมัติ เนื่องจากไม่มีการใช้งานนาน 30 นาที")
        show_login()
        st.stop()

    # อัปเดตเวลาทุกครั้งที่ render หน้า
    touch_session()

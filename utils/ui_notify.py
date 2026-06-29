"""
Aqualine — UI Components (utils/ui_notify.py)
Component กลางที่ทุกหน้าเรียกใช้ได้:
- toast()         แจ้งเตือนสำเร็จ / ผิดพลาด / เตือน
- show_spinner()  loading ขณะบันทึก
- confirm_dialog() ยืนยันก่อนลบ
"""
import streamlit as st

# ──────────────────────────────────────────
# TOAST CSS (ใส่ครั้งเดียวต่อ session)
# ──────────────────────────────────────────
def _inject_toast_css():
    if st.session_state.get("_toast_css_injected"):
        return
    st.markdown("""
    <style>
    .aq-toast {
        position: fixed;
        bottom: 32px;
        right: 32px;
        z-index: 99999;
        min-width: 260px;
        max-width: 380px;
        padding: 14px 20px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 4px 20px rgba(0,0,0,0.18);
        display: flex;
        align-items: center;
        gap: 10px;
        animation: aq-slide-in 0.3s ease;
    }
    .aq-toast.success {
        background: #F0FDF4;
        border: 1px solid #86EFAC;
        color: #166534;
    }
    .aq-toast.error {
        background: #FFF1F2;
        border: 1px solid #FDA4AF;
        color: #9F1239;
    }
    .aq-toast.warning {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        color: #92400E;
    }
    .aq-toast.info {
        background: #EFF6FF;
        border: 1px solid #93C5FD;
        color: #1E40AF;
    }
    @keyframes aq-slide-in {
        from { opacity: 0; transform: translateX(40px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    </style>
    """, unsafe_allow_html=True)
    st.session_state["_toast_css_injected"] = True


# ──────────────────────────────────────────
# TOAST NOTIFICATION
# ──────────────────────────────────────────
def toast(message: str, type: str = "success", duration: int = 3):
    """
    แสดง toast notification มุมล่างขวา

    Parameters:
        message  : ข้อความที่จะแสดง
        type     : "success" | "error" | "warning" | "info"
        duration : วินาทีที่จะแสดง (default 3)

    ตัวอย่าง:
        toast("บันทึกสำเร็จ!")
        toast("เกิดข้อผิดพลาด", type="error")
        toast("กรุณากรอกข้อมูลให้ครบ", type="warning")
    """
    _inject_toast_css()

    icons = {
        "success": "✅",
        "error":   "❌",
        "warning": "⚠️",
        "info":    "ℹ️",
    }
    icon = icons.get(type, "✅")

    st.markdown(f"""
    <div class="aq-toast {type}" id="aq-toast-{id(message)}">
        <span>{icon}</span>
        <span>{message}</span>
    </div>
    <script>
    (function() {{
        var el = document.getElementById("aq-toast-{id(message)}");
        if (!el) return;
        setTimeout(function() {{
            el.style.transition = "opacity 0.4s ease";
            el.style.opacity = "0";
            setTimeout(function() {{ el.remove(); }}, 400);
        }}, {duration * 1000});
    }})();
    </script>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────
# SAVE WITH SPINNER
# ──────────────────────────────────────────
def save_with_feedback(save_fn, success_msg: str = "บันทึกสำเร็จ!", error_msg: str = "บันทึกไม่สำเร็จ"):
    """
    รัน save_fn พร้อม spinner และแสดง toast ผลลัพธ์

    Parameters:
        save_fn     : function ที่จะรัน เช่น lambda: save_project(p)
        success_msg : ข้อความเมื่อสำเร็จ
        error_msg   : ข้อความเมื่อผิดพลาด

    ตัวอย่าง:
        save_with_feedback(lambda: save_project(p), "บันทึกโปรเจกต์แล้ว!")
    """
    try:
        with st.spinner("กำลังบันทึก..."):
            result = save_fn()
            if isinstance(result, tuple) and not result[0]:
                raise Exception(result[1])
        toast(success_msg, type="success")
        return True
    except Exception as e:
        toast(f"{error_msg}: {e}", type="error")
        return False


# ──────────────────────────────────────────
# CONFIRM DIALOG (ก่อนลบ)
# ──────────────────────────────────────────
def confirm_dialog(key: str, label: str, message: str, on_confirm) -> None:
    """
    ปุ่มลบพร้อม dialog ยืนยัน 2 ขั้น

    Parameters:
        key        : unique key สำหรับปุ่มนี้
        label      : ชื่อปุ่ม เช่น "🗑️ ลบโปรเจกต์"
        message    : ข้อความยืนยัน เช่น "ต้องการลบโปรเจกต์นี้ใช่ไหม?"
        on_confirm : function ที่รันเมื่อกด "ยืนยัน"

    ตัวอย่าง:
        confirm_dialog(
            key="del_proj",
            label="🗑️ ลบโปรเจกต์",
            message="ต้องการลบโปรเจกต์นี้ใช่ไหม? ไม่สามารถกู้คืนได้",
            on_confirm=lambda: delete_project(pid)
        )
    """
    confirm_key = f"_confirm_{key}"

    if not st.session_state.get(confirm_key):
        if st.button(label, key=f"btn_{key}", use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        st.warning(f"⚠️ {message}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ ยืนยัน", key=f"yes_{key}", use_container_width=True, type="primary"):
                st.session_state[confirm_key] = False
                on_confirm()
                st.rerun()
        with col2:
            if st.button("❌ ยกเลิก", key=f"no_{key}", use_container_width=True):
                st.session_state[confirm_key] = False
                st.rerun()

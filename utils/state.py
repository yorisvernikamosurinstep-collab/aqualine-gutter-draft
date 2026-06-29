"""
state.py — Session state helpers + disk persistence
[NEW] เพิ่ม duplicate_project() + log_activity wrapper
"""
import streamlit as st
import datetime
from utils.storage import save_project, load_all_projects, delete_project, log_activity


def init_session():
    """Initialize session state + โหลดโปรเจกต์จาก disk ครั้งแรก"""
    if "projects" not in st.session_state:
        projects, errors = load_all_projects()
        st.session_state.projects = projects
        if errors:
            for e in errors:
                st.warning(f"⚠️ {e}")

    defaults = {
        "current_project_id": None,
        "current_page": "home",
        "unsaved_changes": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def new_project(name: str, address: str = "") -> str:
    pid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    project = {
        "id": pid,
        "name": name,
        "address": address,
        "created": datetime.datetime.now().isoformat(),
        "created_by": st.session_state.get("current_user", ""),
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
        "notes": "",
        "status": "draft",
    }
    st.session_state.projects[pid] = project
    st.session_state.current_project_id = pid
    user = st.session_state.get("current_user", "")
    ok, err = save_project(project, user=user, skip_validation=True)
    if not ok:
        st.error(f"❌ สร้างโปรเจกต์ไม่สำเร็จ: {err}")
    else:
        log_activity("create", project_name=name, user=user)
    return pid


def get_project() -> dict | None:
    pid = st.session_state.get("current_project_id")
    if pid and pid in st.session_state.projects:
        return st.session_state.projects[pid]
    return None


def save_current_project() -> bool:
    """บันทึกโปรเจกต์ปัจจุบันลง disk"""
    p = get_project()
    if p is None:
        return False
    user = st.session_state.get("current_user", "")
    ok, err = save_project(p, user=user)
    if ok:
        st.session_state.unsaved_changes = False
    else:
        st.error(f"❌ บันทึกไม่สำเร็จ: {err}")
    return ok


def delete_current_project(pid: str) -> bool:
    """ลบโปรเจกต์ออกจาก session + disk"""
    p = st.session_state.projects.get(pid, {})
    pname = p.get("name", pid)
    user  = st.session_state.get("current_user", "")
    if pid in st.session_state.projects:
        del st.session_state.projects[pid]
    if st.session_state.current_project_id == pid:
        st.session_state.current_project_id = None
    ok, err = delete_project(pid, project_name=pname, user=user)
    if not ok:
        st.error(f"❌ ลบโปรเจกต์ไม่สำเร็จ: {err}")
    return ok


# ══════════════════════════════════════════
# [NEW] DUPLICATE PROJECT
# ══════════════════════════════════════════

def duplicate_project(pid: str) -> str | None:
    """
    Copy โปรเจกต์ที่มีอยู่ → สร้างใหม่พร้อม id ใหม่
    คืน new_pid หรือ None ถ้าผิดพลาด
    """
    src = st.session_state.projects.get(pid)
    if not src:
        st.error("ไม่พบโปรเจกต์ต้นฉบับ")
        return None

    import copy
    new_pid  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"COPY_{src['name']}"
    new_proj  = copy.deepcopy(src)

    new_proj["id"]         = new_pid
    new_proj["name"]       = new_name
    new_proj["created"]    = datetime.datetime.now().isoformat()
    new_proj["created_by"] = st.session_state.get("current_user", "")
    new_proj["last_saved"] = None
    new_proj["status"]     = "draft"
    # ไม่ copy canvas_data และ boq (ให้เริ่มใหม่)
    new_proj["canvas_data"] = None
    new_proj["boq"]         = None

    st.session_state.projects[new_pid] = new_proj
    user = st.session_state.get("current_user", "")
    ok, err = save_project(new_proj, user=user, skip_validation=True)
    if ok:
        log_activity("duplicate",
                     project_name=new_name,
                     user=user,
                     detail=f"copied from {src['name']}")
        return new_pid
    else:
        st.error(f"❌ Duplicate ไม่สำเร็จ: {err}")
        return None


def save_field(key: str, value):
    p = get_project()
    if p is not None:
        p[key] = value
        st.session_state.unsaved_changes = True


def project_list() -> list:
    return list(st.session_state.projects.values())


def reload_from_disk():
    """โหลดข้อมูลใหม่จาก disk (รีเฟรช)"""
    projects, errors = load_all_projects()
    st.session_state.projects = projects
    if errors:
        for e in errors:
            st.warning(f"⚠️ {e}")

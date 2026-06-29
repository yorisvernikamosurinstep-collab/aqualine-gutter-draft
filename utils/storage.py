"""
storage.py — บันทึก/โหลดข้อมูลโปรเจกต์ลง disk (JSON + Photos)
โครงสร้าง:
    aqualine_projects/
    └── <project_name>/
        ├── project.json
        ├── project.backup.json   ← [NEW] auto backup
        └── photos/

[NEW] Features:
- Auto backup: ทุกครั้งที่ save จะสำรอง project.backup.json
- Data validation: ตรวจสอบ field สำคัญก่อนบันทึก
- Activity log: บันทึกประวัติการแก้ไขใน activity_log.json
"""
import json
import os
import re
import shutil
import datetime
from pathlib import Path

# ฟิลด์ข้อความที่อาจมาเป็นตัวเลขจากประสานงาน (po_ref/taxid/phone ฯลฯ) → บังคับเป็น str
# กัน TypeError: can only concatenate str (not "int") to str เวลา render ทุกหน้า
_STR_FIELDS = ["customer","customer_code","customer_taxid","phone","address",
               "angency_name","project_name_site","install_location","po_ref",
               "salesperson","notes","name","job_type"]
def _coerce_str_fields(p):
    if isinstance(p, dict):
        for k in _STR_FIELDS:
            v = p.get(k)
            if v is not None and not isinstance(v, str):
                p[k] = str(v)
    return p

PROJECTS_DIR   = Path("aqualine_projects")
ACTIVITY_LOG   = PROJECTS_DIR / "activity_log.json"
MAX_LOG_ENTRIES = 500   # เก็บล็าสุดกี่รายการ


# ════════════════════════════════════════════
# DRIVE-BACKED DRAFT STORAGE (สำหรับรันบน Streamlit Cloud — ไฟล์ในเครื่องหายเมื่อ restart)
# เปิดใช้โดยตั้ง secrets.toml: storage_mode = "drive"  (default = "local" → ใช้ไฟล์ในเครื่องเหมือนเดิม)
# งานร่างจะถูกเซฟ/โหลดผ่าน GAS → Google Drive folder "_drafts"
# ════════════════════════════════════════════
def _drive_storage_on() -> bool:
    try:
        import streamlit as st
        return str(st.secrets.get("storage_mode", "local")).strip().lower() == "drive"
    except Exception:
        return False

def _coord_url() -> str:
    try:
        import streamlit as st
        return (st.secrets.get("coordinator", {}).get("webapp_url", "")
                or st.secrets.get("webapp_url", ""))
    except Exception:
        return ""

def _gas_draft_post(action: str, payload: dict) -> dict:
    import requests, json as _j
    url = _coord_url()
    if not url:
        raise RuntimeError("ยังไม่ได้ตั้ง coordinator webapp_url ใน secrets.toml")
    body = {"action": action}
    body.update(payload or {})
    r = requests.post(url, data=_j.dumps(body), headers={"Content-Type": "application/json"}, timeout=60)
    return r.json()


# ── helpers ──────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    s = name.strip()
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    s = re.sub(r'\s+', "_", s)
    return s or "unnamed"


def _project_dir(project: dict) -> Path:
    folder = _safe_name(project.get("name", project["id"]))
    d = PROJECTS_DIR / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "photos").mkdir(exist_ok=True)
    return d


def _find_project_dir(project_id: str, project_name: str = "") -> Path | None:
    if not PROJECTS_DIR.exists():
        return None
    if project_name:
        d = PROJECTS_DIR / _safe_name(project_name)
        if d.exists():
            return d
    d = PROJECTS_DIR / project_id
    if d.exists():
        return d
    return None


def ensure_dir():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = PROJECTS_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()


# ══════════════════════════════════════════
# [NEW] DATA VALIDATION
# ══════════════════════════════════════════

REQUIRED_FIELDS = ["id", "name", "created"]

FIELD_VALIDATORS = {
    "name":  lambda v: bool(str(v).strip()),
    "phone": lambda v: not v or re.match(r"^[\d\-+()\s]{0,20}$", str(v)),
    "customer_taxid": lambda v: not v or re.match(r"^\d{0,13}$", str(v).replace("-", "")),
}

def validate_project(project: dict) -> tuple[bool, list[str]]:
    """
    ตรวจสอบข้อมูลโปรเจกต์ก่อนบันทึก
    คืน (is_valid: bool, errors: list[str])
    """
    errors = []

    # ตรวจ required fields
    for field in REQUIRED_FIELDS:
        if not project.get(field):
            errors.append(f"ข้อมูล '{field}' จำเป็นต้องมี")

    # ตรวจ format validators
    for field, validator in FIELD_VALIDATORS.items():
        val = project.get(field, "")
        try:
            if not validator(val):
                labels = {
                    "name": "เลขที่ใบเสนอราคา",
                    "phone": "เบอร์โทรศัพท์ (ตัวเลขเท่านั้น)",
                    "customer_taxid": "เลขประจำตัวผู้เสียภาษี (13 หลัก)",
                }
                errors.append(f"รูปแบบ '{labels.get(field, field)}' ไม่ถูกต้อง")
        except Exception:
            pass

    return (len(errors) == 0), errors


# ══════════════════════════════════════════
# [NEW] ACTIVITY LOG
# ══════════════════════════════════════════

def log_activity(action: str, project_name: str = "", user: str = "", detail: str = ""):
    """
    บันทึก activity log ลงไฟล์ activity_log.json
    action: "create" | "save" | "delete" | "duplicate" | "edit" | "backup"
    """
    ensure_dir()
    try:
        # โหลด log เดิม
        if ACTIVITY_LOG.exists():
            with open(ACTIVITY_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # เพิ่ม entry ใหม่
        entry = {
            "timestamp":    datetime.datetime.now().isoformat(),
            "action":       action,
            "project_name": project_name,
            "user":         user,
            "detail":       detail,
        }
        logs.insert(0, entry)

        # ตัดทิ้งถ้าเกิน MAX_LOG_ENTRIES
        logs = logs[:MAX_LOG_ENTRIES]

        with open(ACTIVITY_LOG, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[storage] activity log error: {e}")


def load_activity_log(limit: int = 100) -> list:
    """โหลด activity log ล่าสุด คืน list of dict"""
    if not ACTIVITY_LOG.exists():
        return []
    try:
        with open(ACTIVITY_LOG, "r", encoding="utf-8") as f:
            logs = json.load(f)
        return logs[:limit]
    except Exception:
        return []


# ══════════════════════════════════════════
# [NEW] AUTO BACKUP
# ══════════════════════════════════════════

def _backup_project(project: dict, d: Path):
    """
    สร้าง backup ก่อน save (project.backup.json)
    และ backup รายวัน (backups/YYYY-MM-DD_project.json)
    """
    try:
        src = d / "project.json"
        if not src.exists():
            return

        # 1) backup ล่าสุด (เขียนทับทุกครั้ง)
        shutil.copy2(src, d / "project.backup.json")

        # 2) backup รายวัน
        today = datetime.date.today().isoformat()
        backup_dir = d / "backups"
        backup_dir.mkdir(exist_ok=True)
        daily = backup_dir / f"{today}_project.json"
        if not daily.exists():
            shutil.copy2(src, daily)

    except Exception as e:
        print(f"[storage] backup error: {e}")


def restore_from_backup(project_id: str, project_name: str = "") -> tuple:
    """
    กู้คืนจาก project.backup.json
    คืน (True, project_dict) หรือ (False, error_msg)
    """
    try:
        d = _find_project_dir(project_id, project_name)
        if not d:
            return False, "ไม่พบโฟลเดอร์โปรเจกต์"
        backup_file = d / "project.backup.json"
        if not backup_file.exists():
            return False, "ไม่มีไฟล์ backup"
        with open(backup_file, "r", encoding="utf-8") as f:
            p = json.load(f)
        return True, p
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════
# PROJECT CRUD
# ══════════════════════════════════════════

def save_project(project: dict, user: str = "", skip_validation: bool = False) -> tuple:
    """
    บันทึกโปรเจกต์ลงโฟลเดอร์ <project_name>/project.json
    [NEW] validate ก่อนบันทึก + auto backup + log activity
    คืน (True, "") เมื่อสำเร็จ หรือ (False, error_message) เมื่อล้มเหลว
    """
    # [NEW] Validate ก่อน save
    if not skip_validation:
        is_valid, errors = validate_project(project)
        if not is_valid:
            msg = " | ".join(errors)
            return False, f"ข้อมูลไม่ถูกต้อง: {msg}"

    # โหมด Drive (คลาวด์): เซฟงานร่างผ่าน GAS → Google Drive (_drafts)
    if _drive_storage_on():
        try:
            project["last_saved"] = datetime.datetime.now().isoformat()
            res = _gas_draft_post("save_draft", {
                "draftId": project.get("id") or project.get("name"),
                "projectJson": json.dumps(project, ensure_ascii=False),
            })
            if res.get("ok"):
                log_activity("save", project_name=project.get("name", ""), user=user)
                return True, ""
            return False, res.get("error", "บันทึกงานร่างไม่สำเร็จ")
        except Exception as e:
            return False, f"บันทึกงานร่าง (Drive) ไม่สำเร็จ: {e}"

    try:
        d = _project_dir(project)

        # [NEW] Auto backup ก่อนเขียนทับ
        _backup_project(project, d)

        project["last_saved"] = datetime.datetime.now().isoformat()
        project["_folder"]    = d.name
        filepath = d / "project.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)

        # [NEW] Log activity
        log_activity("save", project_name=project.get("name", ""), user=user)

        return True, ""

    except PermissionError:
        msg = "ไม่มีสิทธิ์บันทึกไฟล์ กรุณาตรวจสอบสิทธิ์โฟลเดอร์"
        print(f"[storage] save error: {msg}")
        return False, msg
    except OSError as e:
        msg = f"บันทึกไฟล์ไม่สำเร็จ: {e.strerror}"
        print(f"[storage] save error: {e}")
        return False, msg
    except Exception as e:
        msg = f"เกิดข้อผิดพลาดในการบันทึก: {e}"
        print(f"[storage] save error: {e}")
        return False, msg


def load_all_projects() -> tuple:
    """
    โหลดโปรเจกต์ทั้งหมด
    คืน (projects_dict, errors_list)
    """
    # โหมด Drive (คลาวด์): ดึงงานร่างจาก GAS → Google Drive (_drafts)
    if _drive_storage_on():
        try:
            res = _gas_draft_post("load_drafts", {})
            projects = {}
            for p in res.get("drafts", []):
                if isinstance(p, dict) and p.get("id"):
                    projects[p["id"]] = _coerce_str_fields(p)
            return projects, ([] if res.get("ok") else [res.get("error", "โหลดงานร่างไม่สำเร็จ")])
        except Exception as e:
            return {}, [f"โหลดงานร่าง (Drive) ไม่สำเร็จ: {e}"]

    ensure_dir()
    projects = {}
    errors = []

    # ไฟล์ที่ไม่ใช่ project.json ให้ข้ามทั้งหมด
    _SKIP_FILES = {"activity_log.json", ".gitkeep"}

    # ── โครงสร้างใหม่: โฟลเดอร์ย่อย ──
    for folder in sorted(PROJECTS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        pfile = folder / "project.json"
        if not pfile.exists():
            continue
        try:
            with open(pfile, "r", encoding="utf-8") as f:
                p = json.load(f)
            # ตรวจว่ามี field "id" จริงๆ (ป้องกัน JSON ที่ไม่ใช่ project)
            if not p.get("id"):
                continue
            projects[p["id"]] = _coerce_str_fields(p)
        except json.JSONDecodeError:
            msg = f"ไฟล์เสียหาย: {pfile.name}"
            errors.append(msg)
            print(f"[storage] load error {pfile}: ไฟล์ JSON เสียหาย")
        except Exception as e:
            msg = f"โหลดไม่สำเร็จ: {pfile.name}"
            errors.append(msg)
            print(f"[storage] load error {pfile}: {e}")

    # ── โครงสร้างเก่า: flat .json ──
    for filepath in sorted(PROJECTS_DIR.glob("*.json")):
        # ข้ามไฟล์ที่รู้ว่าไม่ใช่ project (activity_log, .gitkeep ฯลฯ)
        if filepath.name in _SKIP_FILES:
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                p = json.load(f)
            # ตรวจว่ามี field "id" จริงๆ
            if not p.get("id"):
                continue
            if p["id"] not in projects:
                projects[p["id"]] = _coerce_str_fields(p)
        except Exception as e:
            msg = f"โหลดไม่สำเร็จ: {filepath.name}"
            errors.append(msg)
            print(f"[storage] load error {filepath}: {e}")

    return projects, errors


def delete_project(project_id: str, project_name: str = "", user: str = "") -> tuple:
    """
    ลบโฟลเดอร์โปรเจกต์ทั้งหมด
    [NEW] log activity ก่อนลบ
    คืน (True, "") หรือ (False, error_message)
    """
    # โหมด Drive (คลาวด์): ลบงานร่างผ่าน GAS
    if _drive_storage_on():
        try:
            log_activity("delete", project_name=project_name or project_id, user=user)
            res = _gas_draft_post("delete_draft", {"draftId": project_id})
            return (True, "") if res.get("ok") else (False, res.get("error", "ลบงานร่างไม่สำเร็จ"))
        except Exception as e:
            return False, f"ลบงานร่าง (Drive) ไม่สำเร็จ: {e}"

    try:
        # [NEW] Log ก่อนลบ
        log_activity("delete", project_name=project_name or project_id, user=user)

        d = _find_project_dir(project_id, project_name)
        if d and d.exists():
            shutil.rmtree(d)
        old = PROJECTS_DIR / f"{project_id}.json"
        if old.exists():
            old.unlink()
        return True, ""
    except PermissionError:
        msg = "ไม่มีสิทธิ์ลบไฟล์ กรุณาตรวจสอบสิทธิ์โฟลเดอร์"
        print(f"[storage] delete error: {msg}")
        return False, msg
    except Exception as e:
        msg = f"ลบโปรเจกต์ไม่สำเร็จ: {e}"
        print(f"[storage] delete error: {e}")
        return False, msg


# ── photo helpers ─────────────────────────────────────────────

def save_photos(project: dict, uploaded_files: list) -> tuple:
    d = _project_dir(project)
    photos_dir = d / "photos"
    saved = []
    errors = []
    for uf in uploaded_files:
        try:
            dest = photos_dir / uf.name
            with open(dest, "wb") as f:
                f.write(uf.getbuffer())
            saved.append(uf.name)
        except Exception as e:
            errors.append(f"อัปโหลด {uf.name} ไม่สำเร็จ: {e}")
            print(f"[storage] save photo error {uf.name}: {e}")
    return saved, errors


def save_photo_bytes(project: dict, filename: str, data: bytes) -> tuple:
    """บันทึกรูป (bytes) ลงโฟลเดอร์ photos/ ของโปรเจกต์ — ใช้กับภาพที่ render เอง (แปลน/หน้าตัด)"""
    try:
        d = _project_dir(project)
        dest = d / "photos" / filename
        with open(dest, "wb") as f:
            f.write(data)
        return True, ""
    except Exception as e:
        print(f"[storage] save_photo_bytes error {filename}: {e}")
        return False, str(e)


def load_photos(project: dict) -> list:
    d = _find_project_dir(project["id"], project.get("name", ""))
    if not d:
        return []
    photos_dir = d / "photos"
    if not photos_dir.exists():
        return []
    result = []
    exts = {".jpg", ".jpeg", ".png", ".pdf"}
    for f in sorted(photos_dir.iterdir()):
        if f.suffix.lower() in exts:
            try:
                result.append({
                    "name":   f.name,
                    "data":   f.read_bytes(),
                    "suffix": f.suffix.lower(),
                })
            except Exception as e:
                print(f"[storage] photo load error {f}: {e}")
    return result


def delete_photo(project: dict, filename: str) -> tuple:
    try:
        d = _find_project_dir(project["id"], project.get("name", ""))
        if not d:
            return False, "ไม่พบโฟลเดอร์โปรเจกต์"
        f = d / "photos" / filename
        if f.exists():
            f.unlink()
        return True, ""
    except Exception as e:
        msg = f"ลบรูป {filename} ไม่สำเร็จ: {e}"
        print(f"[storage] delete photo error: {e}")
        return False, msg


def list_project_files() -> list:
    ensure_dir()
    return sorted(PROJECTS_DIR.glob("*.json"))

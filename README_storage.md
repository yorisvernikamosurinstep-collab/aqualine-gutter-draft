# ระบบบันทึกข้อมูลโปรเจกต์ Aqualine

## โครงสร้างโฟลเดอร์

```
your_project/
├── app.py                    ← ไฟล์หลัก (แก้ไขแล้ว)
├── aqualine_projects/        ← โฟลเดอร์เก็บข้อมูล (สร้างอัตโนมัติ)
│   ├── 20240526_143022.json  ← ข้อมูลโปรเจกต์แต่ละงาน
│   ├── 20240526_150011.json
│   └── ...
├── utils/
│   ├── state.py              ← Session + disk sync (แก้ไขแล้ว)
│   ├── storage.py            ← อ่าน/เขียน JSON ใหม่
│   └── calculations.py       ← คงเดิม
└── pages/
    ├── page_home.py          ← จัดการโปรเจกต์ (แก้ไขแล้ว)
    ├── page_canvas.py        ← คงเดิม
    ├── page_assess.py        ← คงเดิม
    ├── page_boq.py           ← คงเดิม
    └── page_prices.py        ← คงเดิม
```

## ไฟล์ที่ต้องเปลี่ยน (copy ไปแทนของเดิม)

| ไฟล์ | Action |
|------|--------|
| `app.py` | แทนของเดิม |
| `utils/state.py` | แทนของเดิม |
| `utils/storage.py` | **ไฟล์ใหม่** — วางใน utils/ |
| `pages/page_home.py` | แทนของเดิม |

## การทำงาน

- **Auto-load**: เปิดแอปครั้งแรก → โหลดโปรเจกต์ทั้งหมดจาก `aqualine_projects/` อัตโนมัติ
- **Auto-save**: เปลี่ยนหน้า → บันทึกอัตโนมัติ
- **Manual save**: กดปุ่ม 💾 ใน sidebar หรือในการ์ดโปรเจกต์
- **Edit**: กด ✏️ แก้ไข → แก้ข้อมูลพื้นฐาน → บันทึก
- **Delete**: กด 🗑️ → ยืนยัน → ลบทั้ง session และไฟล์

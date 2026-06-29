import streamlit as st
import pandas as pd
import altair as alt

# --- กำหนดข้อมูลจุด (Data Points) สำหรับรูปแบบหลังคาแบบต่างๆ ---
# อ้างอิงสเปกจากคู่มือ 'รวมข้อมูลรางน้ำฝน.pdf' หน้า 2 และ 3
ROOF_TYPE_POINTS = {
    "หลังคาเพิงหมาแหงน (Lean-to)": {
        'pts': [(0, 0), (1, 2)], 
        'label': 'Lean-to', 
        'manual_ref': 'หน้า 2 (1.5-3°)'
    },
    "หลังคาทรงจั่ว (Gable)": {
        'pts': [(0, 0), (1, 2), (2, 0)], 
        'label': 'Gable', 
        'manual_ref': 'หน้า 2 (15-30°)'
    },
    "หลังคาทรงปั้นหยา (Hip)": {
        'pts': [(0, 0), (1, 1), (3, 1), (4, 0)], 
        'label': 'Hip', 
        'manual_ref': 'หน้า 2 (25-45°)'
    },
    "หลังคาทรงผีเสื้อ (Butterfly)": {
        'pts': [(0, 2), (1, 0), (2, 2)], 
        'label': 'Butterfly', 
        'manual_ref': 'หน้า 3'
    },
}

def render_visual_roof_selector(session_state_key: str):
    """
    สร้าง Visual Selector สำหรับรูปแบบหลังคาแบบคลิกได้
    อ้างอิงสไตล์จาก image_6d102c.png
    """
    st.markdown("---")
    st.markdown("### <i class='fa fa-home'></i> กำหนดรูปแบบหลังคา", unsafe_allow_html=True)
    st.write(f"คลิกเลือกรูปภาพหลังคาที่ต้องการ (ค่าปัจจุบัน: **{st.session_state[session_state_key]}**)")

    # วาง Layout แบบคอลัมน์เพื่อให้เห็นภาพรวม
    num_types = len(ROOF_TYPE_POINTS)
    cols = st.columns(num_types)

    for i, (name, config) in enumerate(ROOF_TYPE_POINTS.items()):
        
        # 1. จัดเตรียมข้อมูลเป็น DataFrame
        df = pd.DataFrame(config['pts'], columns=['x', 'y'])

        # 2. สร้างการเลือก (Selection Interaction) สำหรับ Altair
        selection = alt.selection_point(on='click', value=st.session_state[session_state_key] == name)

        # 3. สร้าง Base Chart (เส้นและจุด)
        base = alt.Chart(df).encode(
            x=alt.X('x', axis=None), # ซ่อนแกน X
            y=alt.Y('y', axis=None, scale=alt.Scale(zero=False)), # ซ่อนแกน Y, เริ่มต้นไม่ใช่ 0
        )

        # 4. วาดเส้น (mark_line) สไตล์สเก็ตช์สะอาดตา
        line = base.mark_line(
            color='#555555', # สีเทาเข้ม
            strokeWidth=2.5,
            strokeJoin='round',
            strokeCap='round'
        )

        # 5. วาดจุด (mark_point) เพื่อเน้นมุม
        points = base.mark_point(filled=True, size=80).encode(
            color=alt.condition(selection, alt.value('#007BFF'), alt.value('lightgrey')) # สีจุด
        )

        # 6. รวมส่วนประกอบและกำหนด Title
        chart = alt.layer(line, points).properties(
            title=alt.TitleParams(
                text=[config['label'], f"({config['manual_ref']})"], 
                subtitle=f"{name}",
                offset=10
            )
        ).add_params(
            selection
        ).configure_title(
            fontSize=16,
            fontWeight='bold',
            subtitleFontSize=12,
            subtitleFontWeight='lighter',
            anchor='start',
            orient='top'
        )

        # 7. แสดงผลแผนภาพที่คลิกได้
        with cols[i]:
            # สร้าง container เพื่อให้คลิกได้ทั้งพื้นที่
            with st.container():
                st.altair_chart(chart, use_container_width=True)
                # เมื่อคลิกที่แผนภาพ ให้ Update Session State ของ Dropdown จริง
                if st.button(f"เลือก {config['label']}", key=f"btn_{config['label']}"):
                    st.session_state[session_state_key] = name
                    st.rerun()

    st.markdown("---")
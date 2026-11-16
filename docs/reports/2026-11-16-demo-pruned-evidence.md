# demo_v2: ตาราง Evidence per keyword นับ keyword ที่ถูก prune ให้ถูกต้อง

วันที่ 16 พ.ย. 2026 · branch `fix/demo-pruned-evidence`

## ปัญหา

เมื่อรัน demo โดยเปิด AND pruning (`AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ./demo_v2/run_demo.sh`)
แล้วค้นหา AND ที่มี keyword ที่เจอน้อยกับ keyword ที่เจอบ่อย เช่น `"intriguing open question" AND "algorithm"`
ตาราง "Evidence per keyword" (ส่วน What was proven) และตารางในแผง Cloud Server แสดง `algorithm` เป็น 0 partition / 0 entry
ทั้งที่ผลยังเป็น VERIFIED

สาเหตุ: keyword ที่ถูก prune ส่ง evidence แบบ focus (`amtp/server.py` `_focus_evidence`) ซึ่งมี
`mode: "focus"`, `segs` (`[position, PID, component]` เฉพาะ partition ใน focus set), `nb` (γ leaf ข้างเคียงที่พิสูจน์ว่า
keyword ไม่อยู่ใน partition อื่นของ focus set) และ `n_sel` (จำนวน partition ทั้งหมดของ keyword) ไม่มี `L`
แต่ `client_app.py` และ `server_app.py` นับจาก `e.get("L", [])` อย่างเดียว จึงได้ 0

ปัญหานี้อยู่ที่การแสดงผลเท่านั้น การตรวจ (`DataUser.verify`) ถูกต้องอยู่แล้ว

## แก้อะไร

แก้เฉพาะ `demo_v2/` ไม่แตะ `amtp_code/` หรือ `baselines/`

1. `demo_v2/common.py`: เพิ่ม `ev_counts(e)` นับจาก `segs` / `nb` / `n_sel` เมื่อเป็น focus evidence และจาก `L` เมื่อเป็นแบบเต็ม
   คืน `partitions`, `entries`, `pruned`, `neighbours`, `of`
2. `demo_v2/client_app.py` (แผง What was proven) และ `demo_v2/server_app.py` (event ของแผง Cloud Server) ใช้ `ev_counts`
3. `demo_v2/static/index.html` และ `index_old.html`: แถวของ keyword ที่ถูก prune แสดงป้าย `pruned` และ
   "1 of 8 · pruned · 0 neighbour γ" แทน 0 (แก้ทั้งหน้าใหม่และหน้าเก่า)
4. `demo_v2/tests/test_demo_v2.py`: เพิ่ม `test_evidence_counts_cover_pruned_keywords` ค้นหา Rare AND Frequent แล้วตรวจว่า
   ทุกแถว present มี partition หรือ neighbour อย่างน้อย 1 ค่าจากฝั่ง client กับ server ตรงกัน เปิด flag ต้องมีแถว pruned
   ปิด flag ต้องไม่มี

## ผล

ค้นหา `"intriguing open question" AND "algorithm"` (D1, 300 ไฟล์, เปิด flag ทั้งสาม):

| Keyword | Status | Partitions | Entries |
|---|---|---|---|
| algorithm | present `pruned` | 1 of 8 · 0 neighbour γ | 2 |
| intriguing open question | present | 1 | 1 |

(ก่อนแก้: algorithm = 0 / 0)

## วิธีทำซ้ำ

```bash
.venv/bin/python -m pytest demo_v2/tests -q
AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 .venv/bin/python -m pytest demo_v2/tests -q
```

ผล: ปิด flag 34 passed, เปิด flag 34 passed (เดิม 33 + test ใหม่ 1)
ตรวจในเบราว์เซอร์ (Chromium) ทั้ง `/` และ `/static/index_old.html` ไม่มี error ใน console

## สถานะ

- เสร็จ รอ review
- ยังไม่ได้ทดสอบใน Safari (หน้าใหม่มีปัญหาวาดหน้าจอใน Safari อยู่แล้ว แยกจากงานนี้)

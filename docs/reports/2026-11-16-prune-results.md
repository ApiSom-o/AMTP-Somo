# ผลรอบ cloud "prune" — เครื่อง 1 (AMTP ex1, ex2, tamper, ex5)

วันที่ 16 พ.ย. 2026 · branch `results/prune`

## ทำอะไร

1. **ผลจาก cloud:** เครื่อง 1 ของแผน `PLAN=prune` (`docs/reports/2026-11-16-fill-default.md`) รันเสร็จ 15:34 ตัวเฝ้าบน Mac ดึงผลมาไว้ที่ `baselines/results/runs/cloud/prune_w1/` ครบ 7 ชุด: search1, verify1, tamper, xsearch, xverify, xdomains, exp5
   - ตรวจแล้ว: ทุก manifest เป็น commit `767289c`, `git_dirty: false`, `amtp_placement: fill`, flag ทั้ง 3 เป็น true · log ไม่มี FAIL
2. **กราฟ:** `baselines/results/new_purn/graphs/` (paper 25 รูป, story 5 รูป) ดูว่ารูปไหนใช้ผลจากรอบไหนใน `new_purn/README.md`
3. **ทดสอบ overhead ของ flag บน Mac:** `baselines/results/runs/mac_and_prune/flag_overhead/` (xsearch ทุกรูปแบบ + verify1 D1, ปิด → เปิด → ปิด → เปิด, reps 15, commit `767289c`)
4. **HANDOFF:** เพิ่มสถานะรอบ prune และที่มาของผล · งานค้างข้อ 3 (C_Kd hex): บันทึกว่าตัดสินใจไม่แก้

ex4 ของรอบ prune (เครื่อง 2–5) ยังรันอยู่ จะตามมาใน PR ถัดไป

## ผล (ค่ามัธยฐานบน cloud, ms · baseline จาก `gamma_with_v`)

**tamper:** แก้ไฟล์, ซ่อนไฟล์, แทรกไฟล์ และส่งฉบับเก่า จับได้ครบทุกแบบ (แบบละ 360/360) และไม่ฟ้องผิด (0/60) การเปิด flag ไม่กระทบความปลอดภัย

**search1 (N = 100k, AND, vary kQ):**

| kQ | AMTP fill | AMTP prune | SE-COLLAB | Chen | Du |
|---|---|---|---|---|---|
| server 20 | 11.45 | **0.96** | 4.98 | 0.12 | 1.36 |
| ตรวจ 20 | 36.3 | **1.06** | 0.93 | 10.4 | 0.11 |
| end-to-end 20 | 47.5 | **2.37** | 9.39 | 11.54 | 1.71 |
| proof 20 | 581 KB | **20 KB** | 561 B | 640 B | 3.5 KB |

- end-to-end ชนะ SE-COLLAB ทุก kQ และชนะ Chen ที่ kQ ≥ 2
- **แพ้ Du ทุก kQ:** Du ส่ง query ไปหลาย cloud พร้อมกัน แล้วนับเฉพาะ cloud ที่ช้าที่สุด ถ้านับงานทุก cloud รวมกัน (`server_sum`) Du ใช้มากกว่า ~5×

**xsearch (4 domain, end-to-end kQ 16):**

| รูป query | fill | prune | SE-COLLAB |
|---|---|---|---|
| AND | 85.7 | **6.5** | 10.5 |
| AND_of_OR | 178 | **8.4** | 10.8 |
| OR_of_AND | 159 | 19.3 | **11.2** |
| OR | 292 | 302 | **155** |

- OR_of_AND ชนะที่ kQ ≤ 8
- ขนาด proof ของ OR เล็กกว่า SE-COLLAB ประมาณครึ่ง (1.95 เทียบกับ 4.54 MB ที่ kQ 16)

**verify1 / xverify (keyword เดียว):** เกือบเท่ารอบ fill เพราะไม่มีอะไรให้ AND pruning ตัด
- ชนะเรื่องเวลาที่ rQ ≤ 100
- proof เล็กกว่า SE-COLLAB และ Du ที่ rQ ≥ 100

**xdomains (400k ไฟล์ แบ่ง D domain, AND kQ 4, end-to-end):**

| domain | 1 | 4 | 16 | 32 |
|---|---|---|---|---|
| AMTP prune | **0.85** | **2.18** | **7.27** | 14.0 |
| SE-COLLAB | 10.2 | 9.6 | 9.7 | **10.4** |

ฝั่ง server ชนะทุกจุด แต่ end-to-end แพ้ที่ 32 domain

**ex5 (ค้น domain เดียว ขณะที่มี 1–32 domain):**
- end-to-end **1.3 ms คงที่** (fill 3.4) เทียบกับ SE-COLLAB 8.9 ms
- update ส่วน server **37–42 ms เทียบกับรอบ fill 30–33 ms (ช้าลง ~20%)** น่าจะเป็นต้นทุนของ AND pruning ที่เก็บ R^post tree ไว้ตอนสร้าง snapshot ex3 และ ex4 ไม่โดน เพราะไม่นับเวลาสร้าง snapshot

## overhead ของ flag (Mac เครื่องเดียวกัน, server ms, เฉลี่ย 2 รอบ)

| query | ปิด | เปิด | ต่าง |
|---|---|---|---|
| OR kQ 2 / 4 / 8 / 16 | 2.52 / 16.8 / 33.5 / 55.8 | 2.34 / 18.1 / 36.0 / 59.5 | −7% / +7% / +8% / +7% |
| verify1 rQ 10 / 100 / 1,000 / 10,000 | 0.11 / 0.76 / 7.05 / 14.0 | 0.12 / 0.79 / 7.97 / 14.6 | +9% / +4% / +13% / +4% |

- ส่วนที่เพิ่มอยู่ในขั้น lookup คือขั้นวางแผนของ AND pruning ที่ยังทำงานกับ query ที่ไม่มีอะไรให้ตัด
- ฝั่ง user ตรวจไม่เปลี่ยน
- บน cloud ระหว่างรอบ fill กับรอบ prune ต่างกันมากกว่านี้ (OR kQ 2 +42%, verify1 rQ 1,000 +38%) ส่วนที่เกินน่าจะมาจากความต่างระหว่างเครื่อง cloud สองรอบ
- **ตัดสินใจ:** ไม่แก้โค้ด ให้รายงานใน paper ว่า flag เพิ่มเวลา server ของ query ที่ไม่มี AND 4–13% แลกกับ AND ที่เร็วขึ้น 5–21×

## ทำซ้ำ

- รันบน cloud: `PLAN=prune RUN_NAME=paper_prune bash scripts/cloud_worker.sh 1`
- กราฟ: ดู `baselines/results/new_purn/README.md`
- ทดสอบ overhead: `bench.experiments xsearch` และ `verify1 --s-domains D1` ที่ `--reps 15 --warmup 3` สลับ `AMTP_AND_PRUNE=AMTP_PART_RESULTS=AMTP_AND_GREEDY=1` กับไม่ตั้ง flag

## สถานะ

- เพิ่มแค่ผลและเอกสาร ไม่มีโค้ดเปลี่ยน
- ex4 ของรอบ prune (เครื่อง 2–5) ยังรันอยู่ จะตามมาใน PR ถัดไป พร้อมกราฟ ex4 และ story ที่เหลือ

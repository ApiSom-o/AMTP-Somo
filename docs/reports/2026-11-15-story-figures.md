# รายงาน: กราฟเล่าเรื่องสำหรับ paper (graph_op) และ ex3 หลังแก้ Validator — 15 พ.ย. 2026

## สรุปสั้น

1. เพิ่มสคริปต์ `baselines/plot_story.py` วาดกราฟเส้น 11 รูปลง `baselines/results/new_amtp_result/graph_op/` ไม่มีรูปแบบตารางหรือแท่ง
2. ใส่ผล ex3 (update) ของ AMTP ที่รันใหม่หลังแก้ Validator ลงใน `gamma_with_v` แล้ว plot รูป ex3 ใหม่

ทุกรูปใช้ผลชุด **γ มี v ที่รันบน cloud** ไม่ได้แก้ตัวเลขใดๆ ตัวเลขทุกจุดในรูป graph_op อยู่ใน `graph_op/figure_points.csv`

## 1. graph_op

รันใหม่ได้ด้วยคำสั่ง `.venv/bin/python baselines/plot_story.py` ถ้าจะใช้ข้อมูลชุดอื่นหรือเขียนไปโฟลเดอร์อื่น ให้ใส่ `--run` / `--out`

วิธีคำนวณเหมือน `plot_paper.py`:
- ค่าของแต่ละ query คือ median ของรอบที่จับเวลา (15 รอบ หลัง warm-up 3 รอบ)
- แต่ละจุดในกราฟคือ median ข้ามทุก query ของจุดนั้น
- 1 KB = 1000 B

### graph_op/main/ — เรื่องหลักของ paper

| รูป | เทียบกับ | ผล |
|---|---|---|
| detection_vs_tampered | ทุก scheme | AMTP จับได้ 4/4 ประเภทการโจมตี ทุกจำนวนไฟล์ที่ถูกแก้ (t = 5–1,000) · Du 3/4 (จับการเพิ่มผลไม่ได้) · SE-COLLAB 2/4 (จับการซ่อนผลและการเพิ่มผลไม่ได้) · Chen 2 จาก 2 ประเภทที่ทดสอบได้ · ไม่มี scheme ไหนฟ้องผิดกับ response ที่ถูกต้อง |
| proof_size_vs_rq | SE-COLLAB, Du | ที่ rQ = 2,550: AMTP 573 KB, SE-COLLAB 1,431 KB (2.5×), Du 8,711 KB (15×) · แต่ที่ rQ = 10 SE-COLLAB เล็กกว่าเล็กน้อย (5.6 เทียบ 6.2 KB) |
| proof_size_vs_rq_4domains | SE-COLLAB | ที่ rQ = 9,448: AMTP 2,184 KB เทียบ 5,300 KB (2.4×) · แต่ที่ rQ = 10 SE-COLLAB เล็กกว่า (5.6 เทียบ 9.1 KB) |
| query_vs_domains | SE-COLLAB | จาก 1 ถึง 32 domain: AMTP 4.0–4.1 ms, SE-COLLAB 8.9 ms (domain ละ 5,000 ไฟล์) |
| update_vs_domains | — | AMTP update หนึ่ง domain ใช้ 106–112 ms ไม่ว่าจะมีกี่ domain |
| max_partition_vs_batch | Static-MT | θ_max = 64: partition ที่ใหญ่สุดของ AMTP อยู่ที่ 64 ตลอด ส่วน Static-MT โตถึง 629 |
| update_vs_batch | Static-MT | median ของเวลา update ต่อ batch: AMTP เร็วกว่า 4.9× (คิดจากทั้ง 1,674 batch) |

### graph_op/limits/ — ช่วงที่ baseline เร็วกว่า (ไว้ใช้ใน discussion)

ปลายเส้นทุกเส้นมีป้ายบอกว่า scheme นั้นจับการโจมตีอะไรไม่ได้ ป้ายนี้สร้างจากผล tamper detection อัตโนมัติ

| รูป | ผล |
|---|---|
| e2e_vs_rq | ที่ rQ = 10 AMTP เร็วกว่า SE-COLLAB 11× · เส้นตัดกันที่ประมาณ 322 ไฟล์ · AMTP เร็วกว่า Du ทุกจุด · Chen เร็วที่สุด |
| e2e_vs_files | kQ = 5: AMTP เร็วกว่า SE-COLLAB จนถึงประมาณ 76k ไฟล์ |
| server_vs_files | server ของ AMTP เร็วกว่า SE-COLLAB 2.1–12× · Chen และ Du ใช้เวลา server น้อยกว่า AMTP |
| e2e_vs_kq | N = 100k: ที่ kQ = 2 AMTP เร็วกว่า SE-COLLAB 2.4× · เส้นตัดกันที่ kQ ≈ 4.5 |

จุดตัด (322 ไฟล์, 76k ไฟล์, kQ ≈ 4.5) ได้จากการลากเส้นระหว่างจุดที่วัดจริง ใน paper ควรเขียนว่า "ประมาณ"

### ข้อจำกัดที่เขียนไว้ในรูปแล้ว

- Chen ไม่มี proof แยก (0 B) จึงไม่อยู่ในรูปขนาด proof
- Chen ไม่ส่งไฟล์กลับ จึงทดสอบการโจมตีแบบแก้ไฟล์และส่งไฟล์เวอร์ชันเก่ากับ Chen ไม่ได้
- รูป split/merge ไม่มี Global-MT เพราะผลที่มีเป็นแบบไม่มี v จึงเทียบกับ AMTP และ Static-MT ไม่ยุติธรรม ตอนนี้กำลังรัน Global-MT(v) บน w3 เสร็จแล้วจะเพิ่มเป็นเส้นที่สาม

## 2. ex3 หลังแก้ Validator

- ผลใหม่รันบน w4 จาก commit a131032 (branch `validator-imt-speed`, `git_dirty: false`) ใช้คำสั่งและพารามิเตอร์เดียวกับรอบเดิม
- ไฟล์ใหม่: `gamma_with_v/amtp/amtp_exp3_dynamic_update.csv` (+ manifest)
- ไฟล์เดิมที่ช้าผิดปกติ ย้ายไปไว้ที่ `gamma_with_v/amtp/old_before_validator_fix/` ไม่ได้ลบ
- Chen ใช้ผลเดิม เพราะไม่ได้ใช้ Validator ตัวที่แก้
- รูปที่เปลี่ยน: `gamma_with_v/figures/ex3_update/update_vs_b_{insert,delete}.png` และ `figures/figure_points.csv` (re-plot ด้วย `plot_paper.py` แล้ว รูปอื่นไม่เปลี่ยน)

### ผล AMTP ต่อ epoch (median, insert)

| b | Validator ก่อนแก้ → หลังแก้ | update ทั้งหมด ก่อนแก้ → หลังแก้ | Chen |
|---|---|---|---|
| 1 | 60 → 60 ms | 142 → 141 ms | 1.35 ms |
| 10 | 589 → 551 ms | 1.30 → 1.25 s | 13 ms |
| 100 | 7.6 → 4.2 s | 12.8 → 9.4 s | 131 ms |
| 1000 | 597 → 42 s | 632 → 76 s | 1.37 s |

- ที่ b = 1000 แบบ delete: Validator 421 → 23 s, update 462 → 64 s
- เวลา server เกือบเท่ารอบเดิมทุกจุด แสดงว่าเครื่องเร็วพอกัน เทียบกันได้
- หลังแก้ เวลา update ของ AMTP โตตาม b แบบเส้นตรงแล้ว แต่ยังช้ากว่า Chen 56–104× เพราะ AMTP ต้องทำ proof ใหม่และให้ Validator ตรวจทุก epoch

## ไม่ได้แตะ

โค้ด scheme, ผลการทดลองอื่น, `plot_paper.py`, `plot_results.py`, ข้อความใน paper

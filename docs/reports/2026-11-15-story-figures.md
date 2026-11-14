# รายงาน: กราฟเล่าเรื่องสำหรับ paper (graph_op) — 15 พ.ย. 2026

## ทำอะไร

- เพิ่มสคริปต์ `baselines/plot_story.py` สำหรับวาดกราฟชุดใหม่ 10 รูป แต่ละรูปตั้งหัวเป็นประโยคที่บอกผลหลักของรูปนั้น
- ใช้ผลชุด **γ มี v ที่รันบน cloud แล้ว** (`baselines/results/new_amtp_result/gamma_with_v`) **ไม่ได้รันการทดลองใหม่ และไม่ได้แก้ข้อมูล**
- รูปทั้งหมดและ `figure_points.csv` (ตัวเลขทุกจุดในรูป รวม 199 จุด) อยู่ที่ `baselines/results/new_amtp_result/graph_op/`
- รันใหม่ด้วยคำสั่ง `.venv/bin/python baselines/plot_story.py` (ใส่ `--run` / `--out` เพื่อเปลี่ยนโฟลเดอร์ที่อ่านหรือเขียน)

## วิธีคำนวณ (เหมือน plot_paper.py)

- ค่าของแต่ละ query คือ median ของรอบที่จับเวลา (15 รอบ หลัง warm-up 3 รอบ) แต่ละจุดในกราฟคือ median ข้ามทุก query ในกลุ่มนั้น
- 1 KB = 1000 B
- สีและสัญลักษณ์ของแต่ละ scheme ใช้ชุดเดียวกับ `plot_results.py`

## รูปทั้ง 10

| ไฟล์ | ข้อมูล | ผลที่รูปแสดง |
|---|---|---|
| attack_detection.png | tamper_detection | AMTP จับได้ทั้ง 4 การโจมตี SE-COLLAB จับการซ่อนผลและการเพิ่มผลไม่ได้ Du จับการเพิ่มผลไม่ได้ Chen เป็น N/A 2 ช่อง ไม่มี scheme ไหนฟ้องผิดกับ response ที่ถูกต้อง (0/60) |
| proof_size_vs_rq.png | verify_single | ที่ rQ = 2,550 proof ของ AMTP ขนาด 573 KB, SE-COLLAB 1,431 KB (2.5×), Du 8,711 KB (15×) |
| e2e_breakdown.png | search_single (kQ = 5, N = 100k, AND) | เวลา query ของ AMTP 79% อยู่ที่การตรวจผล ฝั่ง server ของ AMTP (2.1 ms) เร็วกว่า SE-COLLAB (4.8 ms) |
| amtp_verify_checks.png | จุดเดียวกับรูปบน | เวลาตรวจผลของ AMTP: part 76%, papc 20%, idx 3%, ct และ comp ไม่ถึง 1% |
| proof_size_vs_rq_4domains.png | verify_multi (4 domain) | ที่ rQ = 9,448 proof ของ AMTP ขนาด 2,184 KB ส่วน SE-COLLAB 5,300 KB (2.4×) |
| e2e_vs_rq.png | verify_single | ที่ rQ = 10 AMTP เร็วกว่า SE-COLLAB 11× เส้นตัดกันที่ประมาณ 322 ไฟล์ AMTP เร็วกว่า Du ทุกจุด (2.8× ที่ rQ = 2,550) |
| query_vs_domains.png | exp5_domains (query) | เมื่อมี 1 ถึง 32 domain เวลา query ของ AMTP อยู่ที่ 4.0–4.1 ms ส่วน SE-COLLAB 8.9 ms |
| update_vs_domains.png | exp5_domains (update) | update หนึ่ง domain ใช้ 106–112 ms ไม่ว่าจะมีกี่ domain |
| max_partition_vs_batch.png | splitmerge θ = 64 (layout) | partition ที่ใหญ่สุดของ AMTP อยู่ที่ 64 ตลอด ส่วน Static-MT โตไปถึง 629 |
| update_vs_batch.png | splitmerge θ = 64 (updates) | median ของเวลา update ต่อ batch: AMTP เร็วกว่า Static-MT 4.9× (คิดจากทั้ง 1,674 batch) |

## ข้อจำกัดที่เขียนไว้ในรูปแล้ว

- **ตอนผลลัพธ์น้อย proof ของ AMTP ใหญ่กว่า SE-COLLAB เล็กน้อย** (rQ = 10: 6.2 KB เทียบ 5.6 KB) หัวกราฟจึงระบุจุดที่ใช้วัด เช่น "At 2,550 results"
- **SE-COLLAB เร็วกว่า AMTP เมื่อผลลัพธ์เกินประมาณ 322 ไฟล์** รูป e2e_vs_rq ขีดเส้นจุดตัดนี้ไว้
- **Chen** มี proof 0 B (ไม่มี proof แยก) จึงไม่อยู่ในรูปขนาด proof ในรูปเวลา Chen เร็วที่สุด แต่ตรวจไม่ได้ว่าไฟล์ถูกแก้หรือเป็นเวอร์ชันเก่า
- **Global-MT ไม่อยู่ในรูป split/merge** เพราะผลที่มีเป็นแบบไม่มี v จึงเทียบกับ AMTP และ Static-MT ไม่ยุติธรรม ตอนนี้กำลังรัน Global-MT(v) อยู่ เสร็จแล้วจะเพิ่มเป็นเส้นที่สาม
- ตัวเลข ex5 ใช้ได้เลย ไม่ต้องรันใหม่หลังแก้ Validator เพราะ ex5 ใช้ b = 1 จึงแทบไม่ผ่านส่วนที่แก้ (ดู `2026-11-15-validator-imt-speed.md`)

## ไม่ได้แตะ

ข้อมูลผลการทดลอง, โค้ด scheme, `plot_paper.py`, `plot_results.py`, รูปเดิมใน `gamma_with_v/figures/` และข้อความใน paper

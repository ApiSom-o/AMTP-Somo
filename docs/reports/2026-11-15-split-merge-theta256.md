# รายงาน: ผล split/merge ที่ θ_max = 256 (γ มี v) — 15 พ.ย. 2026

ต่อจาก `2026-11-15-split-merge-theta128.md` ตอนนี้ ex4 แบบมี v ครบ 3 ค่า θ_max แล้ว (64, 128, 256)

## ทำอะไร

- ดึงผลจากเครื่อง w10 มาไว้ที่ `baselines/results/runs/cloud/w10/` ทั้งผลดิบ, calibration และ log
- คัดลอก `splitmerge_n100000_t256/` ไปไว้ที่ `baselines/results/new_amtp_result/gamma_with_v/amtp/`
- plot ใหม่ด้วย `baselines/plot_paper.py`
  - เพิ่ม `figures/ex4_split_merge/theta_256/` (4 รูป)
  - รูปเทียบข้าม θ_max (`update_vs_theta.png`, `query_server_vs_theta.png`) ตอนนี้มีครบ 3 จุด
  - อัปเดต `figure_points.csv`
  - รูปอื่นไม่เปลี่ยน

## ตรวจผลก่อนใช้

- รันจาก commit 7485556 (`git_dirty: false`) ซึ่งเป็น commit เดียวกับ θ_max = 64 และ 128 พารามิเตอร์อื่นเท่ากันทุกตัว
- ทุก variant รันครบ 1,674 batch และวัด query ครบ 850 ครั้ง
- ใน log ไม่มี FAIL หรือ Traceback

## ผล (median ต่อ batch)

| θ_max | AMTP update | Static-MT update | AMTP เร็วกว่า | partition ใหญ่สุดของ AMTP | partition ใหญ่สุดของ Static-MT |
|---|---|---|---|---|---|
| 64 | 4.9 s | 24.2 s | 4.9× | 64 | 629 |
| 128 | 8.9 s | 37.3 s | 4.2× | 128 | 1,027 |
| 256 | 13.7 s | 37.5 s | 2.7× | 256 | 1,621 |

คอลัมน์ partition ใหญ่สุดคือค่าสูงสุดตลอดการรัน

- ทุกค่า θ_max: AMTP คุมทุก partition ไว้ไม่เกิน θ_max และ update เร็วกว่า Static-MT
- **θ_max ยิ่งเล็ก AMTP ยิ่งได้เปรียบ** เพราะเมื่อเวอร์ชันของ partition เปลี่ยน AMTP ต้อง refresh key ทั้ง partition เมื่อ partition ใหญ่ขึ้น ต้นทุนส่วนนี้จึงโตตาม ในงานนี้ θ_max = 64 ดีที่สุด

## ข้อควรรู้

- **Global-MT ในรูป ex4 เป็นแบบไม่มี v** จึงเร็วกว่ามาก (~0.4 s) แต่เทียบกับ AMTP และ Static-MT ซึ่งมี v ไม่ยุติธรรม
- ผล Global-MT(v) ที่ θ_max = 64 กำลังรันอยู่บน w3

## ไม่ได้แตะ

โค้ด, ผลการทดลองอื่น, graph_op

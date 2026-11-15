# รายงาน: ผล split/merge ที่ θ_max = 128 (γ มี v) — 15 พ.ย. 2026

## ทำอะไร

- ดึงผล ex4 split/merge ที่ θ_max = 128 จากเครื่อง w2 มาไว้ที่ `baselines/results/runs/cloud/w2/` (ผลดิบ, calibration และ log)
- คัดลอก `splitmerge_n100000_t128/` ไปไว้ใน `baselines/results/new_amtp_result/gamma_with_v/amtp/` ข้างชุด θ_max = 64 เดิม
- plot ใหม่ด้วย `baselines/plot_paper.py`
  - เพิ่มโฟลเดอร์ `figures/ex4_split_merge/theta_128/` (4 รูป)
  - เพิ่มรูปเทียบข้าม θ_max: `update_vs_theta.png`, `query_server_vs_theta.png`
  - `figure_points.csv` อัปเดตตาม
  - รูปอื่นไม่เปลี่ยน

## ตรวจผลก่อนใช้

- รันจาก commit 7485556 (`git_dirty: false`) เหมือน θ_max = 64 พารามิเตอร์เท่ากันหมด: เริ่ม 100,000 ไฟล์, b = 100, skew 0.95, θ_min = θ_max / 4, ลบ 0.65 ของกลุ่ม hot
- ทุก variant (AMTP, Static-MT, Global-MT) รันครบ 1,674 batch และวัด query ครบ 850 ครั้ง
- ใน log ไม่มี FAIL หรือ Traceback
- รันบนเครื่อง r7i.4xlarge รุ่นเดียวกับ θ_max = 64 (w1)

## ผล (median ต่อ batch)

| θ_max | variant | update | partition ใหญ่สุด (สูงสุดตลอดการรัน) |
|---|---|---|---|
| 64 | AMTP | 4.9 s | 64 |
| 64 | Static-MT | 24.2 s | 629 |
| 128 | AMTP | 8.9 s | 128 |
| 128 | Static-MT | 37.3 s | 1,027 |

- ทั้งสองค่า θ_max: AMTP คุมทุก partition ไว้ไม่เกิน θ_max ตลอดการรัน
- AMTP update เร็วกว่า Static-MT 4.9× ที่ θ_max = 64 และ 4.2× ที่ θ_max = 128
- เพิ่ม θ_max จาก 64 เป็น 128 ทำให้ update ของ AMTP ช้าลง (4.9 → 8.9 s) เพราะ partition ใหญ่ขึ้น ต้อง refresh key มากขึ้นต่อการเปลี่ยนเวอร์ชันหนึ่งครั้ง

## ข้อควรรู้

- **Global-MT ในรูป ex4 ของ plot_paper เป็นแบบไม่มี v** จึงเร็วกว่ามาก (~0.45 s) แต่เทียบกับ AMTP และ Static-MT ไม่ยุติธรรม (สองตัวนี้มี v) เครื่อง w3 กำลังรัน Global-MT(v) ที่ θ_max = 64 อยู่
- **θ_max = 256 (w10) ยังรันอยู่** เสร็จแล้วจะเพิ่มเป็นจุดที่สามในรูปเทียบข้าม θ_max

## ไม่ได้แตะ

โค้ด, ผลการทดลองอื่น, graph_op

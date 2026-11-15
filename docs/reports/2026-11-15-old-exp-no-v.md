# รายงาน: ย้ายผลแบบ γ ไม่มี v ทั้งหมดไปไว้ที่ old/exp_no_v — 15 พ.ย. 2026

ทีมตัดสินใจใช้ **γ มี v** (γ = H(PID ‖ v ‖ H(Enc(L)))) เท่านั้น ผลแบบไม่มี v จึงย้ายไปเก็บแยก ไม่ได้ลบทิ้ง

## ย้ายอะไร (`git mv` 240 ไฟล์ ประวัติไฟล์ยังอยู่ครบ โครงสร้างโฟลเดอร์เดิมเก็บไว้ข้างใน)

| เดิม | ตอนนี้ |
|---|---|
| `baselines/results/new_amtp_result/gamma_without_v/` | `baselines/results/old/exp_no_v/new_amtp_result/gamma_without_v/` |
| `baselines/results/runs/new_amtp_result/gamma_without_v/` | `baselines/results/old/exp_no_v/runs/new_amtp_result/gamma_without_v/` |
| `baselines/results/runs/cloud/preview_nov/` | `baselines/results/old/exp_no_v/runs/cloud/preview_nov/` |
| `runs/cloud/w3,w4,w5,w6,w8/` ทั้ง `paper_nov`, `paper_calib_nov` และ `paper_nov_q` | `old/exp_no_v/runs/cloud/<เครื่อง>/...` |
| `runs/cloud/w3,w5,w6/novq_w*.log` | `old/exp_no_v/runs/cloud/<เครื่อง>/` |

## ไม่ได้ย้าย

- **Global-MT (ไม่มี v) ในผล split/merge แบบมี v:** เป็น variant หนึ่งในไฟล์ CSV เดียวกับ AMTP และ Static-MT
- **`real_w*.log` / `calib_w*.log`:** ในไฟล์เดียวมีทั้งงานแบบมี v และไม่มี v
- **โค้ด:** ตัวเลือก `AMTP_GAMMA_V=0` และ test ของมันยังอยู่
- **รายงานเก่า:** ยังอ้าง path เดิม

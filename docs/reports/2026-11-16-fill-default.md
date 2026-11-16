# placement fill เป็นค่าเริ่มต้น และแผน cloud "prune"

วันที่ 16 พ.ย. 2026 · branch `feat/fill-default`

## ทำอะไร

1. **เปลี่ยนค่าเริ่มต้นของ placement เป็น fill:** เจ้าของงานตัดสินใจให้ fill เป็นวิธีหลักใน paper
   - `bench/experiments.py` และ `bench/ablation.py`: `--placement` มีค่าเริ่มต้น `fill` (เดิม `least`) ยังเลือก `least` ได้ด้วย `--placement least` หรือ `AMTP_PLACEMENT=least`
   - `baselines/amtp_dataset.py`: ค่า `amtp_placement` ใน manifest เมื่อไม่ได้ตั้ง env เป็น `fill` ให้ตรงกับค่าเริ่มต้นใหม่
   - `scripts/cloud_worker.sh`: แก้คำอธิบาย
   - **ไม่เปลี่ยน:** class `AdaptivePolicy` / `StaticPolicy` (`amtp/variants.py`) ยังมีค่าเริ่มต้น `least` เพราะ test (`test_fill_placement.py`) และ demo ใช้อยู่ การทดลองทุกชุดส่ง placement จาก `--placement` อยู่แล้ว
2. **เพิ่มแผน cloud `PLAN=prune`:** 5 เครื่อง เปิดทุก query flag (`AMTP_AND_PRUNE`, `AMTP_PART_RESULTS`, `AMTP_AND_GREEDY` = 1) placement fill, reps 15 / warmup 3 เหมือนเดิม

   | เครื่อง | job | งาน | เวลา (จากรอบ fill) |
   |---|---|---|---|
   | 1 | `prune-amtp` | AMTP: search1, verify1, tamper, xsearch, xverify, xdomains, exp5 | ≤ 4.3 ชม. |
   | 2 | `prune-sm64` | ex4 AMTP + Static-MT, θ = 64 | ~8 ชม. |
   | 3 | `prune-sm128` | ex4 AMTP + Static-MT, θ = 128 | ~8.5 ชม. |
   | 4 | `prune-sm256` | ex4 AMTP + Static-MT, θ = 256 | ~9.5 ชม. |
   | 5 | `prune-gmtv` | ex4 Global-MT(v), θ = 64 | ~13 ชม. |

3. **ex4 บันทึก query flag ใน manifest:** `bench/ablation.py` เพิ่ม `and_prune`, `part_results`, `and_greedy` ใน `manifest.json` (เดิมไม่บันทึก)

## ทำไม

- **fill:** รอบ fill บน cloud ได้ ex4 AMTP เร็วกว่า Static-MT 13.4× / 11.7× / 9.9× (θ 64 / 128 / 256) เทียบกับ least 4.9× / 4.2× / 2.7× (`docs/reports/2026-11-16-cloud-gmtv-fill.md`) ถ้าค่าเริ่มต้นยังเป็น least คนที่ลืมตั้ง env จะได้ผลที่ไม่ใช่วิธีของ paper
- **ไม่รัน ex3 ใหม่ แต่รัน ex4 ใหม่:** ตั้งแต่รอบ fill (`869cf73`) โค้ดที่เปลี่ยนอยู่ฝั่ง query ทั้งหมด (AND pruning, part-results, planner, γ แบบเร็ว) ส่วน snapshot เปลี่ยนแค่การหยุด GC ระหว่างสร้าง ซึ่ง ex3 / ex4 ไม่นับ (`finalize_update(..., snapshot=False)`) ผล update (ex3 และส่วน update ของ ex4) จึงเท่าเดิม baseline ก็ไม่เปลี่ยน
  - **ex4 ต้องรันใหม่:** ex4 วัด query (server / verify) ทุก batch ด้วย (`bench/ablation.py` `run_queries`) ซึ่งอ่าน query flag จาก env รอบ fill ปิด flag ไว้ ตอนนั้น AMTP query ช้ากว่า Global-MT(v) ~1.7× เพราะมีหลาย partition ซึ่งเป็นจุดที่ AND pruning ลดได้ จึงรัน ex4 ใหม่ทุก variant โดยเปิด flag เหมือนกันทุก variant (โค้ด server / user ชุดเดียวกัน)
  - **ตรวจแล้ว:** ex4 ขนาดเล็ก (n = 3,000, 6 batch, ทั้ง 3 variant) เปิดทุก flag ผ่าน correctness gate (query ทุกตัวถูกยอมรับ) และ manifest บันทึก flag ครบ

## ผลกระทบกับผลที่มีอยู่

- ผลบน Mac ใน `baselines/results/runs/mac_and_prune/` รันด้วย least ใช้เทียบได้ว่า flag ช่วยเท่าไรที่ placement เดียวกัน แต่ไม่ใช่ตัวเลขของ paper ตัวเลข paper ของ query flag จะมาจากรอบ cloud "prune"
- ผล cloud รอบ fill (`new_new/data/fill/`) รันด้วย `AMTP_PLACEMENT=fill` อยู่แล้ว ไม่กระทบ

## วิธีรัน

```
# ตรวจคำสั่งก่อน
PLAN=prune DRY_RUN=1 RUN_NAME=paper_prune bash scripts/cloud_worker.sh 1
# บนเครื่อง cloud (~/NewAMTP ที่ commit ของ main หลัง merge)
PLAN=prune RUN_NAME=paper_prune bash scripts/cloud_worker.sh <1..5>   # เครื่องละหมายเลข · ผลอยู่ใน runs/paper_prune_v/
```

## สถานะ

- pytest: 513 passed, 1 skipped · เปิดทุก flag 511 passed, 3 skipped (ที่ skip คือ test ที่ต้องใช้ dataset จริงซึ่งไม่ได้ unpack ใน worktree)
- แผน cloud "prune" ยังไม่ได้รัน ต้องมีคนเปิดเครื่องให้

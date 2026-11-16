# placement fill เป็นค่าเริ่มต้น และแผน cloud "prune"

วันที่ 16 พ.ย. 2026 · branch `feat/fill-default`

## ทำอะไร

1. **เปลี่ยนค่าเริ่มต้นของ placement เป็น fill:** เจ้าของงานตัดสินใจให้ fill เป็นวิธีหลักใน paper
   - `bench/experiments.py` และ `bench/ablation.py`: `--placement` มีค่าเริ่มต้น `fill` (เดิม `least`) ยังเลือก `least` ได้ด้วย `--placement least` หรือ `AMTP_PLACEMENT=least`
   - `baselines/amtp_dataset.py`: ค่า `amtp_placement` ใน manifest เมื่อไม่ได้ตั้ง env เป็น `fill` ให้ตรงกับค่าเริ่มต้นใหม่
   - `scripts/cloud_worker.sh`: แก้คำอธิบาย
   - **ไม่เปลี่ยน:** class `AdaptivePolicy` / `StaticPolicy` (`amtp/variants.py`) ยังมีค่าเริ่มต้น `least` เพราะ test (`test_fill_placement.py`) และ demo ใช้อยู่ การทดลองทุกชุดส่ง placement จาก `--placement` อยู่แล้ว
2. **เพิ่มแผน cloud `PLAN=prune`:** 1 เครื่อง job `prune-amtp` รัน AMTP แบบเปิดทุก query flag (`AMTP_AND_PRUNE`, `AMTP_PART_RESULTS`, `AMTP_AND_GREEDY` = 1) placement fill ใน search1, verify1, tamper, xsearch, xverify, xdomains และ exp5

## ทำไม

- **fill:** รอบ fill บน cloud ได้ ex4 AMTP เร็วกว่า Static-MT 13.4× / 11.7× / 9.9× (θ 64 / 128 / 256) เทียบกับ least 4.9× / 4.2× / 2.7× (`docs/reports/2026-11-16-cloud-gmtv-fill.md`) ถ้าค่าเริ่มต้นยังเป็น least คนที่ลืมตั้ง env จะได้ผลที่ไม่ใช่วิธีของ paper
- **ไม่รัน ex3 / ex4 ใหม่:** ตั้งแต่รอบ fill (`869cf73`) โค้ดที่เปลี่ยนอยู่ฝั่ง query ทั้งหมด (AND pruning, part-results, planner, γ แบบเร็ว) ส่วน snapshot เปลี่ยนแค่การหยุด GC ระหว่างสร้าง ซึ่ง ex3 / ex4 ไม่นับ (`finalize_update(..., snapshot=False)`) ผล update จึงใช้ของรอบ fill ได้ baseline และ Global-MT(v) ก็ไม่เปลี่ยน
  - **ข้อยกเว้นที่ต้องรู้:** ex4 วัด query (server / verify) ทุก batch ด้วย (`bench/ablation.py` `run_queries`) โดยไม่เปิด query flag แต่ γ แบบเร็ว (`gamma_wire`) ใช้เสมอ verify ของ AMTP ใน ex4 บนโค้ดปัจจุบันจึงน่าจะเร็วขึ้นราว 5–11% ของขั้น papc (วัดบน Mac) ตัวเลข query ของ ex4 รอบ fill จึงเป็นของโค้ดก่อน `gamma_wire` ไม่ได้รันใหม่เพราะ ex4 ใช้เวลานาน ถ้าจะใช้ตัวเลข query ของ ex4 ใน paper ให้ระบุ commit `869cf73`

## ผลกระทบกับผลที่มีอยู่

- ผลบน Mac ใน `baselines/results/runs/mac_and_prune/` รันด้วย least ใช้เทียบได้ว่า flag ช่วยเท่าไรที่ placement เดียวกัน แต่ไม่ใช่ตัวเลขของ paper ตัวเลข paper ของ query flag จะมาจากรอบ cloud "prune"
- ผล cloud รอบ fill (`new_new/data/fill/`) รันด้วย `AMTP_PLACEMENT=fill` อยู่แล้ว ไม่กระทบ

## วิธีรัน

```
# ตรวจคำสั่งก่อน
PLAN=prune DRY_RUN=1 RUN_NAME=paper_prune bash scripts/cloud_worker.sh 1
# บนเครื่อง cloud (~/NewAMTP ที่ commit ของ main หลัง merge)
PLAN=prune RUN_NAME=paper_prune bash scripts/cloud_worker.sh 1      # ผลอยู่ใน runs/paper_prune_v/
```

## สถานะ

- pytest: ดูใน PR
- แผน cloud "prune" ยังไม่ได้รัน ต้องมีคนเปิดเครื่องให้

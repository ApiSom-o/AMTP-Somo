# รายงาน: กติกาการวางไฟล์ "เติมให้เต็มก่อน" (fill) — 15 พ.ย. 2026

## สรุป

- เพิ่มกติกาการวางไฟล์ใหม่ `fill` ทางเลือกของกติกาเดิม `least` (ค่า default ยังเป็น `least` ผลเก่าทุกชุดยังรันซ้ำได้เหมือนเดิม)
- **ไม่เปลี่ยน protocol, การตรวจของผู้ใช้, Validator, ความปลอดภัย และ baseline** เปลี่ยนแค่ว่า server เลือกวางไฟล์ใหม่ไว้ partition ไหน
- วัดบน Mac (ขนาดเล็ก): **update ของ ex3 เร็วขึ้น 1.7–2.9×** และ **insert ของ AMTP ใน ex4 เร็วขึ้น 5.3×** ส่วนเวลา query และขนาด proof เท่าเดิม
- ต้องรันบน cloud ใหม่ จึงจะใช้ตัวเลขใน paper ได้ (ดูหัวข้อสถานะ)

## ทำไมต้องเปลี่ยน

ต้นทุนหลักของ update **ไม่ใช่ split แต่เป็นจำนวน partition ที่ถูกแตะต่อ epoch** เพราะ γ มี v:
partition ที่ถูกแก้แม้ไฟล์เดียวจะได้ v ใหม่ แล้วต้องคำนวณ γ ใหม่ทุก keyword ของทุกไฟล์ใน partition นั้น
(`amtp/engine.py` commit, `amtp/validator.py` `_index_root`)

กติกาเดิม `least` วางไฟล์ใน partition ที่ว่างที่สุดของกลุ่ม ไฟล์ b ไฟล์ใน epoch เดียวจึงไปคนละ partition เกือบทั้งหมด
ผล ex4 บน cloud (θ = 64, b = 100) แตะ **100 partition ต่อ batch** และต้องคำนวณ posting component ใหม่ ~83,000 ตัว

## กติกาใหม่ (ตกลงกับเจ้าของงานแล้ว)

| เหตุการณ์ | กติกา | เปลี่ยนไหม |
|---|---|---|
| วางไฟล์ใหม่ (`fill`) | partition ของกลุ่มที่มีไฟล์มากที่สุดแต่ยัง **น้อยกว่า θ_max** (เท่ากันเลือก PID น้อยกว่า) ถ้าเต็มหมด วางต่อใน partition ที่มีไฟล์มากที่สุด แล้วให้ split แก้ตอนจบ epoch | เปลี่ยน (paper ไม่ได้กำหนดกติกาการวาง) |
| split (> θ_max) | แบ่งครึ่ง PID ใหม่ v = 0 | ไม่เปลี่ยน |
| merge (< θ_min) | รวมกับ partition ที่เล็กที่สุดที่รวมแล้วไม่เกิน θ_max (paper สมการ 34) | ไม่เปลี่ยน |
| Static-MT | ใช้กติกาการวางเดียวกับ AMTP ต่างกันแค่ไม่มี split / merge | — |
| ex3, theta | ฟรีซ partition (StaticPolicy) เหมือนใน paper: วัดต้นทุน update อย่างเดียว | ไม่เปลี่ยน |
| ex5 | ใช้ policy ของ AMTP เหมือนเดิม แต่ update ทีละ 1 ไฟล์ จึงไม่เกิด split / merge จริง | ไม่เปลี่ยน |

state ที่ commit และ anchor ยังอยู่ใน [θ_min, θ_max] เสมอ ใน AMTP ตอนวาง อาจเกิน θ_max ได้แค่ระหว่าง epoch เท่านั้น

**ทำไมความปลอดภัยไม่เปลี่ยน:** Validator รับตำแหน่งที่ server เสนออยู่แล้ว (`validator.py` `_apply_requests`) แล้วตรวจทุกอย่างที่ตามมา
การตรวจของผู้ใช้ทั้ง 7 ข้อไม่ขึ้นกับว่าไฟล์อยู่ partition ไหน test ของ Validator และ tamper ผ่านทั้งสองกติกา (ดูหัวข้อ test)

## แก้อะไร

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `amtp_code/amtp/variants.py` | `AdaptivePolicy(..., placement="least")` และ `place()` รองรับ `least` / `fill` ไล่ partition ของกลุ่มรอบเดียว (O(partition ในกลุ่ม) เท่าเดิม ไม่มีลูปซ้อน) StaticPolicy ได้กติกาเดียวกันอัตโนมัติ GlobalPolicy ไม่เปลี่ยน |
| `amtp_code/bench/ablation.py`, `bench/experiments.py` | flag `--placement least\|fill` (ค่า default อ่านจาก env `AMTP_PLACEMENT` ถ้าไม่ตั้งเป็น `least`) ส่งให้ทุกที่ที่สร้าง AdaptivePolicy / StaticPolicy |
| `baselines/amtp_dataset.py` `write_manifest` | บันทึก `amtp_placement` ในทุก manifest (ablation บันทึก `placement` ด้วย) |
| `scripts/cloud_worker.sh` | หัวไฟล์อธิบาย `AMTP_PLACEMENT=fill` |
| `amtp_code/tests/test_fill_placement.py` (ใหม่) | กติกาเลือกถูก partition ทุกกรณี, root incremental = full rebuild, θ_min ≤ n ≤ θ_max หลังทุก commit, Static-MT ไม่ปรับโครงสร้างและบวมแค่อันเดียวต่อกลุ่ม, fill แตะ partition น้อยกว่า, query ผ่านการตรวจ |
| `amtp_code/tests/test_update_protocol.py` | test protocol / Validator / tamper (targeted + random) รันทั้ง `least` และ `fill` · เพิ่มรอบใน test honest จาก 60/b+20 เป็น 60/b+40 เพราะ fill ทำให้ partition เต็มกว่า merge แรกจึงมาช้ากว่า (epoch 27 ที่ b = 10) |
| `amtp_code/tests/test_gamma_flag.py` | ส่ง `"least"` ให้ฟังก์ชัน test ที่เรียกตรง |
| `CLAUDE.md`, `docs/HANDOFF.md` | pytest รันแบบมี v อย่างเดียว · commit ในชื่อ ApiSom-O ถามก่อน commit / branch / push / PR และเจ้าของงานกด merge เอง |

**ลูปซ้อน:** `scripts/cloud_helpers/scan_in.py amtp_code/amtp/variants.py` เจอจุดเดียว (`merged` ใน `adapt` ซึ่งเป็น set อยู่แล้ว และเป็นโค้ดเดิมที่ไม่ได้แก้)

**test:** `cd amtp_code && ../.venv/bin/python -m pytest -q` → **363 passed** (เดิม 333 + ใหม่ 30)

## ผลวัดบน Mac (ใช้ตัดสินใจเท่านั้น ไม่ใช่ตัวเลขของ paper)

### ex3 (update, partition ฟรีซ, N = 10,000, reps 3 warm-up 1, median)

| b | update least → fill | partition ที่ถูกแตะ | hash_calls |
|---|---|---|---|
| 1 | 54 → 53 ms | 1 → 1 | 19,230 → 20,498 |
| 10 | 482 → 279 ms (**1.7×**) | 10 → 7 | 192,793 → 145,232 |
| 100 | 3,321 → 1,155 ms (**2.9×**) | 93 → 22 | 1,385,101 → 459,674 |
| 1,000 | 7,999 → 4,036 ms (**2.0×**) | 232 → 65 | 3,086,863 → 1,477,680 |

delete ได้ผลใกล้เคียงกัน · split = merge = 0 ทุกจุด

ที่ b = 1,000 ได้แค่ 2× เพราะ N = 10,000 มีแค่ 232 partition (least แตะครบทุกอันแล้ว)
ที่ N = 100,000 (~1,600 partition) least น่าจะแตะเกือบ 1,000 ส่วน fill ~65 จึงคาดว่าจะได้มากกว่านี้ **ต้องยืนยันบน cloud**

### ex4 (split / merge, N = 10,000, θ = 64/16, skew 0.95, 100 insert batch × 100 แล้ว hot delete 63 batch, median ต่อ batch)

| | least | fill |
|---|---|---|
| AMTP insert: update | 1,535 ms | **291 ms (5.3×)** |
| AMTP insert: hash_calls | 1,274,729 | 251,557 |
| AMTP insert: partition ที่ถูกแตะ | 75 | 8 |
| AMTP split ทั้งหมด / merge ทั้งหมด | 162 / 16 | 147 / 3 |
| AMTP hot_delete: update | 1,321 ms | 1,406 ms (การลบไม่ขึ้นกับกติกาการวาง) |
| AMTP partition ใหญ่สุดตลอดการรัน | 64 | 64 |
| AMTP query ตอนจบ: verify / proof | 3.18 ms / 56.3 KB | 3.19 ms / 55.8 KB |
| Static-MT insert: update | 1,845 ms | 1,738 ms |
| Static-MT partition ใหญ่สุดตลอดการรัน | 2,415 | 9,465 |
| AMTP เร็วกว่า Static-MT (insert) | 1.2× | **6.0×** |

**ข้อสังเกต:**
- query ไม่แย่ลง (verify, proof และจำนวน partition ที่ query แตะใกล้เคียงเดิม)
- Static-MT ใช้กติกาเดียวกัน ไฟล์ใหม่จึงกองที่ partition เดียวต่อกลุ่มจนบวมมาก ใน paper ต้องเขียนให้ชัดว่า Static-MT ใช้กติกาการวางเดียวกันทุกอย่าง ต่างกันแค่ไม่มี split / merge
- ใช้ Mac ขนาดเล็ก รันครั้งเดียว ex3 กับ ex4 รันพร้อมกัน เวลาจึงคลาดได้ ส่วน `hash_calls` และจำนวน partition ไม่ขึ้นกับเครื่อง

## รันซ้ำ

```
cd amtp_code
../.venv/bin/python -m bench.experiments exp3 --reps 3 --warmup 1 --sizes 10000 --batches 1 10 100 1000 \
  --placement fill --out <dir>
../.venv/bin/python -m bench.ablation --source arxiv --n 10000 --theta-max 64 --theta-min 16 --batches 100 \
  --batch-size 100 --delete-frac 0 --fresh-source initial --skews 0.95 --runs 1 --hot-delete-frac 0.65 \
  --query-every 50 --variants "AMTP,Static-MT" --placement fill --out <dir>
```
(ใช้ `--placement least` เพื่อเทียบ · บน cloud ตั้ง `AMTP_PLACEMENT=fill` แทน flag)

## สถานะ / งานต่อ

- โค้ดและ test เสร็จ ยังไม่ได้รันบน cloud
- รอบรันบน cloud ครั้งหน้า (ทุก job ใช้ `AMTP_PLACEMENT=fill` และโค้ดหลัง PR #16):
  AMTP ex1, ex2, ex3, ex5, tamper · ex4: AMTP + Static-MT ที่ θ = 64, 128, 256 · **Global-MT(v) θ = 64 รันใหม่**
  (ผลของ w3 รันด้วย commit `089726d` ก่อน PR #16 เวลาจึงเทียบกับรอบใหม่ไม่ได้ เก็บไว้ใช้เช็กเท่านั้น) · baseline ไม่ต้องรันใหม่
- paper: เพิ่มประโยคอธิบายกติกาการวางไฟล์ และบอกว่า Static-MT ใช้กติกาเดียวกัน (ข้อความ ex3 ไม่ต้องแก้)

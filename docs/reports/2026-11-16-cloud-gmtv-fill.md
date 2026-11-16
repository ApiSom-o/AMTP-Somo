# ผล cloud: Global-MT(v) ครบ (w3) และรอบ fill ครบ (ยกเว้น Global-MT(v) ของรอบ fill)

วันที่ 16 พ.ย. 2026 · branch `results/gmtv-fill`

## ทำอะไร

1. **Global-MT(v), θ = 64 จากเครื่อง w3:** ครบ 1,674 batch แล้ว นำมาใส่เป็นเส้นที่สามในกราฟ split/merge ของผลหลักตาม HANDOFF ข้อ 7 โดยเก็บแยกไว้ใน `new_new/`
2. **รอบ fill:** เพิ่มผลที่เหลือของเครื่อง w1–w4 ได้แก่ ex4 θ = 64/128/256, ex3, ex5 และ xdomains แล้ว plot ใหม่ทั้งชุด
3. **แก้ `plot_paper.py`:** ให้รวมโฟลเดอร์ split/merge ที่มี θ เดียวกัน (เช่น `..._t64` กับ `..._t64_gmtv`) เดิมโฟลเดอร์หลังจะเขียนทับโฟลเดอร์แรก ทำให้กราฟ θ = 64 หายไปเหลือแค่ Global-MT(v)
4. **ใช้การแก้ `plot_story.py` และ `plot_paper.py` ที่มีคนทำค้างไว้:** เพิ่มเส้น Global-MT(v), ใช้ log scale ในกราฟ partition ใหญ่สุด และแก้คำอธิบาย workload ให้ตรงโค้ด ผมตรวจแล้วว่าคำอธิบายถูก: `skew = 0.95` คือ 95% ของไฟล์ใหม่ถูกบังคับลงกลุ่ม hot (`bench/workload.py`) ไม่ใช่ Zipf s = 0.95 ตามคำอธิบายเดิม

## ตรวจความถูกต้องของผลก่อนใช้

| ผล | commit | git_dirty | สถานะ |
|---|---|---|---|
| w3 Global-MT(v) | `089726d` | false | ครบ 1,674 batch · log ไม่มี FAIL · `done gmtv_t64` |
| fill w1 / w2 / w3 (ex4 θ 64 / 128 / 256) | `869cf73` | false | `worker done` · ไม่มี FAIL · placement fill |
| fill w4 (search1, verify1, tamper, xsearch, xverify, xdomains, ex3, ex5) | `869cf73` | false | `worker done` · ไม่มี FAIL · ผล 5 ชุดแรกเหมือนที่ commit ไปแล้วทุก byte |

- **ความเร็วของ w3 เทียบ w1** (HANDOFF 7.4): Global-MT แบบไม่มี v ซึ่งรันทั้งสองเครื่อง ใช้ 5.88 µs ต่อ hash บน w3 และ 6.04 µs บน w1 ต่างกัน 2.7% จึงเทียบเวลาของ Global-MT(v) กับ AMTP ในรอบหลักได้
- **workload เหมือนกันทุกโฟลเดอร์:** n = 100k, b = 100, skew 0.95, ลบ 65% ของกลุ่ม hot, seed 1, θ_min = θ_max / 4
- **คัดเฉพาะแถวที่ใช้:** w3 รันทั้ง Global-MT(v) และ Global-MT ส่วนรอบหลักมี Global-MT อยู่แล้ว จึงคัดเฉพาะแถว Global-MT(v) ไปไว้ใน `new_new/data/global_mt_v_t64/` ผลดิบอยู่ที่ `runs/cloud/w3/paper_v_gmtv/` ไม่ได้แก้

## ผล

**ex4 split/merge** (median ต่อ batch):

| ชุด | θ_max | AMTP | Static-MT | AMTP เร็วกว่า | partition ใหญ่สุด AMTP / Static |
|---|---|---|---|---|---|
| ผลหลัก (`gamma_with_v`) | 64 | 4.90 s | 24.25 s | 4.9× | 64 / 629 |
| | 128 | 8.88 s | 37.32 s | 4.2× | 128 / 1,027 |
| | 256 | 13.68 s | 37.52 s | 2.7× | 256 / 1,621 |
| fill (`fill_v`) | 64 | 1.11 s | 14.85 s | **13.4×** | 64 / 93,197 |
| | 128 | 1.25 s | 14.58 s | 11.7× | 128 / 90,893 |
| | 256 | 1.56 s | 15.55 s | 9.9× | 256 / 87,565 |

**Global-MT(v), θ = 64** (ผลหลัก, ครบ 1,674 batch):
- **update:** 66.2 s ต่อ batch ช้ากว่า AMTP (4.90 s) **13.5×**
- **query:** เร็วกว่า AMTP เพราะมี partition เดียว: verify 27.3 เทียบ 44.6 ms และ server 10.2 เทียบ 15.0 ms
- **จุดคุ้มทุน:** AMTP คุ้มกว่าจนกว่าจะมี query เกินประมาณ **2,800 ครั้งต่อ epoch** คิดจาก (66.2 − 4.9) s ÷ (59.6 − 37.5) ms ผลบางส่วนก่อนหน้านี้ได้ ~2,600
- **AMTP ไม่ได้ชนะทุกด้าน:** ต้องเขียนใน paper ว่า query ช้ากว่าแบบ partition เดียว

**ex3 update ของรอบ fill:** b = 1,000 insert ใช้ 14.1 s (รอบหลัก 76.5 s) และ delete ใช้ 20.1 s (รอบหลัก 63.6 s) ที่เร็วขึ้นมาจากการแก้ Validator, engine แบบรวม Merkle และ placement fill

## ค่าและกราฟอยู่ไหน

**ทุกอย่างที่ใหม่อยู่ใน `baselines/results/new_new/` แยกจากผลเดิมทั้งหมด** (ดู `new_new/README.md`) โฟลเดอร์เดิม `new_amtp_result/` ไม่ถูกแก้ เหมือน main ทุกไฟล์

| อะไร | ที่อยู่ |
|---|---|
| ข้อมูล Global-MT(v) θ = 64 | `new_new/data/global_mt_v_t64/` |
| ข้อมูลรอบ fill ครบทุกชุด | `new_new/data/fill/` |
| กราฟผลหลัก + Global-MT(v) | `new_new/graphs/main_with_global_mt_v/story/` (11 รูป) และ `.../paper/` (39 รูป) |
| กราฟรอบ fill | `new_new/graphs/fill/story/` (11 รูป) และ `.../paper/` (39 รูป) |
| ผลดิบจาก cloud | `baselines/results/runs/cloud/w3/paper_v_gmtv/`, `runs/cloud/fill_w1..fill_w4/` |

## ยังไม่ครบ

- **Global-MT(v) ของรอบ fill (worker7) — เพิ่ม 16 พ.ย. 10:30:** Global-MT(v) ของรอบ fill (เครื่อง amtp-worker7, commit `869cf73`, placement fill, engine ใหม่) ครบ 1,674 batch แล้ว อยู่ที่ `data/fill/splitmerge_n100000_t64_gmtv/` (ผลดิบ `runs/cloud/fill_w5/`) และอยู่ในกราฟ `graphs/fill/` แล้ว: update median ทั้ง stream AMTP 1.1 s · Static-MT 14.8 s (13.4×) · Global-MT(v) 28.5 s (**25.7×**) · query (server + verify, median ทุกจุดวัด) AMTP 51.7 · Static-MT 46.1 · Global-MT(v) 30.0 ms → AMTP คุ้มกว่า Global-MT(v) จนกว่าจะมี query เกิน ~1,260 ครั้งต่อ epoch (Static-MT ~2,450) · ตรวจแล้ว: manifest `git_dirty: false`, `placement: fill`, `variants: Global-MT(v)` และใช้ seed / workload เดียวกับ AMTP
- **เมื่อดึงผลแล้ว:** ให้วางเฉพาะแถว Global-MT(v) เป็น `new_new/data/fill_global_mt_v_t64/` ลิงก์เข้า run ของ fill เป็น `amtp/splitmerge_n100000_t64_gmtv` แล้วรันคำสั่งด้านล่างซ้ำ

## วิธีทำกราฟซ้ำ

```
R=$PWD/baselines/results/new_amtp_result; N=$PWD/baselines/results/new_new
# ผลหลัก + Global-MT(v): amtp เดิม + โฟลเดอร์ Global-MT(v) เป็น splitmerge_n100000_t64_gmtv
T=$(mktemp -d); mkdir $T/amtp; for e in $R/gamma_with_v/amtp/*; do ln -s $e $T/amtp/; done
ln -s $N/data/global_mt_v_t64 $T/amtp/splitmerge_n100000_t64_gmtv
for s in secollab chen du; do ln -s $R/gamma_with_v/$s $T/$s; done
.venv/bin/python baselines/plot_story.py --run $T --out $N/graphs/main_with_global_mt_v/story
.venv/bin/python baselines/plot_paper.py $T --out $N/graphs/main_with_global_mt_v/paper
# รอบ fill: amtp จาก new_new/data/fill, baseline จาก gamma_with_v (เครื่องรุ่นเดียวกัน)
T=$(mktemp -d); ln -s $N/data/fill $T/amtp; for s in secollab chen du; do ln -s $R/gamma_with_v/$s $T/$s; done
.venv/bin/python baselines/plot_story.py --run $T --out $N/graphs/fill/story
.venv/bin/python baselines/plot_paper.py $T --out $N/graphs/fill/paper
```

## สถานะ

- pytest ผ่าน 408 passed, 1 skipped (branch นี้แตกจาก main ไม่มีโค้ด AND pruning)
- branch นี้แยกจาก `feat/and-pruning`

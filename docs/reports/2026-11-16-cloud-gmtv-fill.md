# ผล cloud: Global-MT(v) ครบ (w3) และรอบ fill ครบ (ยกเว้น Global-MT(v) ของรอบ fill)

วันที่ 16 พ.ย. 2026 · branch `results/gmtv-fill`

## ทำอะไร

1. **Global-MT(v), θ = 64 จากเครื่อง w3:** ครบ 1,674 batch แล้ว นำมาใส่เป็นเส้นที่สามในกราฟ split/merge ของผลหลัก (`gamma_with_v`) ตาม HANDOFF ข้อ 7
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
- **คัดเฉพาะแถวที่ใช้:** w3 รันทั้ง Global-MT(v) และ Global-MT ส่วนรอบหลักมี Global-MT อยู่แล้ว จึงคัดเฉพาะแถว Global-MT(v) ไปไว้ใน `gamma_with_v/amtp/splitmerge_n100000_t64_gmtv/` ผลดิบอยู่ที่ `runs/cloud/w3/paper_v_gmtv/` ไม่ได้แก้

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

## กราฟอยู่ไหน

| กราฟ | ที่อยู่ | มีอะไรใหม่ |
|---|---|---|
| กราฟเล่าเรื่อง ผลหลัก | `baselines/results/new_amtp_result/graph_op/main/` | `update_vs_batch.png` และ `max_partition_vs_batch.png` มีเส้น Global-MT(v) แล้ว |
| กราฟตามแผน paper ผลหลัก | `baselines/results/new_amtp_result/gamma_with_v/figures/ex4_split_merge/` | `theta_64/` ทั้ง 4 รูปมี Global-MT(v) และรูปเทียบตาม θ ถูกอัปเดต |
| กราฟเล่าเรื่อง รอบ fill | `baselines/results/new_amtp_result/graph_fill/main/` | เพิ่ม `update_vs_batch`, `max_partition_vs_batch`, `query_vs_domains`, `update_vs_domains` |
| กราฟตามแผน paper รอบ fill | `baselines/results/new_amtp_result/fill_v/figures/` | ใหม่ทั้งชุด 39 รูป (ex1–ex5) |

กราฟอื่นในผลหลักออกมาเหมือนเดิมทุก byte เปลี่ยนเฉพาะกราฟ split/merge ตัวเลขทุกจุดอยู่ใน `figure_points.csv` ของแต่ละโฟลเดอร์

## ยังไม่ครบ

- **Global-MT(v) ของรอบ fill (worker7):** ยังไม่ได้ดึงผลเข้า repo กราฟ split/merge ของรอบ fill จึงมีแค่ AMTP กับ Static-MT
- **เมื่อดึงผลแล้ว:** ให้วางเป็น `fill_v/amtp/splitmerge_n100000_t64_gmtv/` เฉพาะแถว Global-MT(v) แล้วรันคำสั่งด้านล่างซ้ำ

## วิธีทำกราฟซ้ำ

```
# ผลหลัก
.venv/bin/python baselines/plot_story.py                       # -> graph_op/
.venv/bin/python baselines/plot_paper.py baselines/results/new_amtp_result/gamma_with_v
# รอบ fill: amtp จาก fill_v และ baseline จาก gamma_with_v (รันบนเครื่องรุ่นเดียวกัน)
T=$(mktemp -d); R=$PWD/baselines/results/new_amtp_result
ln -s $R/fill_v/amtp $T/amtp; for s in secollab chen du; do ln -s $R/gamma_with_v/$s $T/$s; done
.venv/bin/python baselines/plot_story.py --run $T --out $R/graph_fill
.venv/bin/python baselines/plot_paper.py $T --out $R/fill_v/figures
```

## สถานะ

- pytest ผ่าน 408 passed, 1 skipped (branch นี้แตกจาก main ไม่มีโค้ด AND pruning)
- branch นี้แยกจาก `feat/and-pruning`

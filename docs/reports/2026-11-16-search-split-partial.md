# ผลวัด search อย่างเดียวบน cloud (ส่วนที่เสร็จแล้ว: search1, xsearch)

วันที่ 16 พ.ย. 2026 · branch `results/search-split-partial`

## ทำอะไร

1. **ผลจาก cloud:** รอบวัด search อย่างเดียว (`amtp_code/bench_split/run_cloud.sh`, แผนใน `2026-11-16-search-split-plan.md`) เสร็จแล้ว 2 ชุด ดึงมาไว้ที่ `baselines/results/runs/cloud/split_w1/paper_split/`
   - **search1** (Search 1.1 / 1.2): 880 แถว, D1–D4, 10k–125k ไฟล์ · เสร็จ 20:56 (69 นาที)
   - **xsearch** (Search 2.1 หลายโดเมน): 320 แถว, 4 โดเมน × 100k ไฟล์, 4 รูปแบบ query · เสร็จ 21:23 (27 นาที)
   - ตรวจแล้ว: ทั้งสองชุดเป็น commit `00f9d42`, `git_dirty: false`, placement fill, flag ทั้ง 3 เป็น true · log ไม่มี FAIL · จุดตรวจผ่านทุก query (ทั้ง 3 แบบได้ไฟล์ตรงกับ response จริง)
   - **ยังรันอยู่:** xdomains และ exp5 คาดว่าเสร็จ ~00:00 จะตามมาใน PR ถัดไป (log ของ xdomains ที่ยังไม่จบไม่ได้ใส่ใน PR นี้)
2. **กราฟ:** `baselines/results/search_split/graphs/` (Search 1.1, 1.2, 2.1 ทั้ง 4 รูปแบบ, AMTP แยกเวลา search กับ search + proof) และ `figure_points.csv` ใช้แบบ partition ก่อน (`server_search_pf_fetch`) ตามที่ตกลงไว้ใน `2026-11-16-summary-all-changes.md`

3. **กราฟ ex4 รอบ prune:** plot ใหม่ใน `baselines/results/new_purn/graphs/paper/ex4_split_merge/` (θ 64 / 128 / 256, AMTP + Static-MT จาก `prune_w2..w4`) และ `story/main/` เพิ่ม 2 รูป · Global-MT(v) ยังรอเครื่อง 5 · `new_purn/README.md` อัปเดตแล้ว
   - update: AMTP 1.05 / 1.20 / 1.48 s ต่อ batch เทียบ Static-MT 13.5 / 13.6 / 14.4 s (**ชนะทุก θ**)
   - query: AMTP ตรวจช้ากว่า Static-MT เล็กน้อยทุก θ (ต้องเขียนใน paper)

## ทั้งหมดอยู่ที่ไหน

| อะไร | โฟลเดอร์ |
|---|---|
| กราฟ search อย่างเดียว (partition ก่อน) | `baselines/results/search_split/graphs/` |
| กราฟรอบ prune ทั้งหมด (ex1–ex5) | `baselines/results/new_purn/graphs/paper/` และ `story/` |
| ผลดิบ search อย่างเดียว | `baselines/results/runs/cloud/split_w1/paper_split/amtp/` |
| ผลดิบรอบ prune | `baselines/results/runs/cloud/prune_w1/` (query) · `prune_w2..w4/` (ex4) |
| baseline (ไม่รันใหม่) | `baselines/results/new_amtp_result/gamma_with_v/{secollab,chen,du}/` |
| ex3 update (รอบ fill) | `baselines/results/new_new/data/fill/` |

## ผล search อย่างเดียว (แบบ partition ก่อน, cloud, ms)

### Search 1.1: N = 100k, AND, vary kQ

| kQ | AMTP | SE-COLLAB | Chen | Du | AMTP server รวม (search + proof) |
|---|---|---|---|---|---|
| 1 | 0.014 | 0.192 | **0.008** | 0.214 | 0.095 |
| 2 | 0.025 | 0.211 | **0.015** | 0.180 | 0.137 |
| 5 | 0.052 | 0.255 | **0.034** | 0.361 | 0.248 |
| 10 | 0.129 | 0.312 | **0.064** | 0.704 | 0.508 |
| 20 | 0.288 | 0.434 | **0.124** | 1.356 | 0.948 |

### Search 1.2: kQ = 5, vary จำนวนไฟล์

AMTP 0.029 → 0.052 · SE-COLLAB 0.074 → 0.300 · Chen 0.021 → 0.037 · Du 0.283 → 0.364 (10k → 125k)

- **ชนะ SE-COLLAB และ Du ทุกจุด** (SE-COLLAB 1.5–13×, Du 4.7–15×) ส่วนต่างกับ SE-COLLAB โตเมื่อไฟล์เพิ่ม (5.8× ที่ 125k)
- **แพ้ Chen ทุกจุด** (Chen เร็วกว่า 1.4–2.3×) ตัด fetch ของ AMTP ออกก็ยังแพ้ (0.279 เทียบ 0.124 ที่ kQ = 20)
- งาน proof เป็น 70–85% ของเวลา server

### Search 2.1: 4 โดเมน × 100k, เทียบกับ SE-COLLAB `search_core` (baseline หลายโดเมนมีตัวเดียว)

| รูปแบบ | kQ 2 | kQ 4 | kQ 8 | kQ 16 | สรุป |
|---|---|---|---|---|---|
| AND | 0.07 / 0.28 | 0.16 / 0.34 | 0.34 / 0.47 | 0.55 / 0.69 | **ชนะทุกจุด** |
| OR-of-AND | 0.08 / 0.29 | 0.15 / 0.50 | 0.61 / 1.01 | 1.18 / 1.23 | **ชนะทุกจุด** (kQ 16 สูสี) |
| AND-of-OR | 0.35 / 0.84 | 0.19 / 0.53 | 0.46 / 0.63 | 1.06 / 0.96 | ชนะ 3/4 แพ้ที่ kQ 16 |
| OR | 0.82 / 0.91 | 6.6 / 1.7 | 15.5 / 2.9 | 27.3 / 4.6 | ชนะ kQ 2 · **แพ้ kQ ≥ 4** |

(ค่าในตาราง: AMTP / SE-COLLAB)

**OR ที่ kQ สูงแพ้เพราะ fetch:** ผลลัพธ์ 2,000–8,000 ไฟล์ และการดึง ciphertext เป็น 83% ของเวลา (kQ 16: fetch 22.7 จาก 27.3 ms ประมาณ 2.8 µs ต่อไฟล์) ส่วน SE-COLLAB `search_core` รวม fetch แล้วใช้ทั้งหมด 4.6 ms ควรตรวจต่อว่า fetch ของสองฝั่งวัดสิ่งเดียวกันหรือไม่ (เช่น DHT ของ AMTP ทำงานเพิ่มต่อไฟล์) ยังไม่ได้แก้

## สถานะ

- เพิ่มแค่ผลและกราฟ ไม่มีโค้ดเปลี่ยน
- งานต่อ:
  1. ดึง xdomains และ exp5 เมื่อเสร็จ แล้ว plot Search 2.2 และ exp5
  2. ตรวจเรื่อง fetch ของ OR
  3. ข้อเสนอที่กำลังคุย (ยังไม่ได้ทำ): เปลี่ยน leaf ของ B+ tree ให้เก็บชุด partition ของ keyword (เซตหรือ bitmap) + map PID → ไฟล์ เพื่อให้ search อย่างเดียวชนะ Chen (ประมาณ 1.3–1.6×) ไม่กระทบความปลอดภัย proof หรือ update

## วิธี plot ซ้ำ

```
cd amtp_code
../.venv/bin/python -m bench_split.plot_search --amtp ../baselines/results/runs/cloud/split_w1/paper_split/amtp \
    --out ../baselines/results/search_split/graphs
```

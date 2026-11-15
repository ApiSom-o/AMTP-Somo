# รายงาน: รอบรันบน cloud "fill" — ผลชุดแรก (ยังไม่ครบ) — 15 พ.ย. 2026

## สรุป

- รอบรันใหม่ของ **AMTP** บน cloud 5 เครื่อง ด้วยโค้ดล่าสุด: PR #16 (ตรวจ Merkle เร็วขึ้น), กติกาการวางไฟล์ **fill** และ engine อัปเดต Merkle แบบรวม
  (รายงาน `2026-11-15-fill-placement.md`, `2026-11-15-engine-batched-merkle.md`)
- เริ่ม 15 พ.ย. 20:59 (เวลาไทย) ที่ commit **`869cf73`** · ทุกเครื่องผ่าน pytest 409 test ก่อนเริ่ม · manifest ทุกไฟล์: `git_dirty: false`, `amtp_placement: fill`, `amtp_gamma_v: true`
- **ผลที่เสร็จแล้ว (ในรายงานนี้):** search1, verify1, tamper, xsearch, xverify
- **ยังรันอยู่:** xdomains, ex3 (update), ex5, ex4 split / merge (Static-MT) และ Global-MT(v) — ใส่ในรายงานถัดไปเมื่อครบ
- baseline (SE-COLLAB, Du, Chen) **ไม่ได้รันใหม่** ใช้ผลเดิมใน `gamma_with_v/` ซึ่งวัดบนเครื่องรุ่นเดียวกัน (r7i.4xlarge, Intel Xeon Platinum 8488C)

## ผลหลัก: query เร็วขึ้น และจุดเท่ากับ SE-COLLAB ขยับมาทางเรา

เวลา end-to-end ของ AMTP เร็วขึ้น **1.2–1.26×** ทุกจุด (มาจาก PR #16) · ขนาด proof และการจับการโจมตีเท่าเดิมทุกจุด (ตามที่ควรเป็น)

| กราฟ | จุดที่ AMTP = SE-COLLAB เดิม | ใหม่ | ผล |
|---|---|---|---|
| ตาม k_Q (N = 100,000, AND) | k_Q ≈ 4.5 | **k_Q ≈ 5.3** | ที่ k_Q = 5 ตอนนี้ AMTP ชนะ (8.5 เทียบ 9.1 ms) |
| ตาม N (k_Q = 5) | ~76,000 ไฟล์ | **~115,000 ไฟล์** | ที่ 100,000 ไฟล์ AMTP ชนะ |
| ตาม r_Q | ~322 ผลลัพธ์ | **~463 ผลลัพธ์** | |

end-to-end ตาม k_Q (ms, median):

| k_Q | AMTP เดิม | AMTP ใหม่ | SE-COLLAB | Chen | Du |
|---|---|---|---|---|---|
| 2 | 3.75 | **3.01** | 9.03 | 0.76 | 0.30 |
| 5 | 10.73 | **8.52** | 9.10 | 2.11 | 0.52 |
| 10 | 30.68 | **23.85** | 9.18 | 5.55 | 0.92 |
| 15 | 42.94 | **34.26** | 9.29 | 8.41 | 1.32 |
| 20 | 59.08 | **47.47** | 9.39 | 11.54 | 1.71 |

end-to-end ตาม N (k_Q = 5, ms): 10k 2.05 → 1.67 · 50k 6.92 → 5.51 · 100k 10.73 → 8.52 · 125k 12.03 → 9.59

**ที่ยังแพ้ (ต้องเขียนใน paper):** k_Q ≥ 10 ยังช้ากว่า SE-COLLAB (SE-COLLAB จับ hidden / injected ไม่ได้) · Chen และ Du เร็วกว่าทุก k_Q
(Chen จับ modified / old-version ไม่ได้เพราะไม่ส่งไฟล์กลับ, Du จับ injected ไม่ได้)

**ไม่เปลี่ยน:** detection 4/4 ทุก t (0 false alarm) · proof size เท่าเดิมทุก byte (layout ตอนโหลดไฟล์ชุดแรกไม่ขึ้นกับกติกาการวาง) · เวลาฝั่ง server เท่าเดิม

## ไฟล์

| ที่อยู่ | อะไร |
|---|---|
| `baselines/results/new_amtp_result/fill_v/amtp/` | CSV + manifest ของ AMTP ที่เสร็จแล้ว (search_single, verify_single, tamper_detection, search_multi, verify_multi) |
| `baselines/results/new_amtp_result/graph_fill/` | กราฟเส้นแบบเดียวกับ `graph_op/` (main: detection, proof size · limits: e2e ตาม k_Q / N / r_Q, server ตาม N) + `figure_points.csv` |
| `scripts/cloud_helpers/start_fill.sh` | เริ่มแผน fill บนเครื่องหนึ่ง (ส่ง git bundle, เช็ก commit / pytest, เริ่มงาน + watch_stop) |
| `scripts/cloud_helpers/watch_fill_local.sh` | watcher ฝั่ง Mac: รายงานความคืบหน้า แล้วดึงผลกลับเมื่อเครื่องจบ |

`graph_op/` และ `gamma_with_v/` เดิม **ไม่ได้แก้** (ยังเป็นผลรอบเก่า) จะแทนเมื่อผลรอบนี้ครบและตรวจแล้ว

## รันซ้ำ / ทำกราฟซ้ำ

```
# บนเครื่อง cloud (ดู scripts/cloud_helpers/start_fill.sh)
PLAN=fill RUN_NAME=paper_fill bash scripts/cloud_worker.sh <1..5>
# กราฟ: ใช้ฟังก์ชันใน baselines/plot_story.py กับโฟลเดอร์ที่มี amtp/ (fill_v) + secollab/ chen/ du/ (gamma_with_v)
```

## สถานะของแต่ละเครื่อง (15 พ.ย. 23:44)

| แผน | เครื่อง | งาน | สถานะ / คาดว่าเสร็จ (เวลาไทย) |
|---|---|---|---|
| 1 | amtp-worker2 | ex4 θ = 64: AMTP + Static-MT | AMTP เสร็จ · Static-MT batch 553 / 1,674 · ~03:00–03:30 |
| 2 | amtp-worker4 | ex4 θ = 128 | AMTP เสร็จ · Static-MT batch 524 · ~03:00–03:30 |
| 3 | amtp-worker5 | ex4 θ = 256 | AMTP เสร็จ · Static-MT batch 252 · ~04:00–05:00 |
| 4 | amtp-worker6 | search1, verify1, tamper, xsearch, xverify, xdomains, ex3, ex5 | เสร็จ 5 / 8 · ~02:00–02:30 |
| 5 | amtp-worker7 | Global-MT(v) θ = 64 | batch 409 / 1,674 · เร็วกว่ารอบเก่า 2.4× · ~11:30–13:30 วันจันทร์ |

ทุกเครื่องดับเองหลังงานจบ 10 นาที (`scripts/watch_stop.sh`) · Global-MT(v) ของ w3 (commit `089726d`, ก่อนแก้ engine) ยังรันอยู่ ใช้เช็กเท่านั้น เทียบเวลากับรอบนี้ไม่ได้

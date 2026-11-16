# ex4 รอบ prune (θ 64, 128) และข้อตกลงเรื่องการวัด search แยกจาก proof

วันที่ 16 พ.ย. 2026 · branch `results/prune-ex4-split-plan`

## ทำอะไร

1. **ผล ex4 รอบ prune ของเครื่อง 2 และ 3:** `baselines/results/runs/cloud/prune_w2/` (θ = 64) และ `prune_w3/` (θ = 128)
   - ตรวจแล้ว: commit `767289c`, `git_dirty: false`, placement fill, flag ทั้ง 3 เป็น true, ไม่มี FAIL, 3,348 แถว (AMTP + Static-MT อย่างละ 1,674 batch)
   - เครื่อง 4 (θ = 256) และเครื่อง 5 (Global-MT(v)) ยังรันอยู่ ยังไม่มีกราฟ ex4 ของรอบนี้
2. **สคริปต์ cloud** ใน `scripts/cloud_helpers/`: `start_prune.sh`, `watch_prune_local.sh` (ที่ใช้รันรอบ prune) และ `start_split.sh`, `watch_split_local.sh` (สำหรับรอบวัด search อย่างเดียว)
3. **บันทึกข้อตกลงของวันนี้** ในรายงานนี้และใน `docs/HANDOFF.md`

## ผล ex4 (ค่ามัธยฐานต่อ batch)

| θ | รอบ | AMTP update | Static-MT update | AMTP เร็วกว่า | AMTP query: server / ตรวจ (ms) | Static-MT query: server / ตรวจ (ms) |
|---|---|---|---|---|---|---|
| 64 | fill | 1.11 s | 14.85 s | 13.4× | 15.9 / 35.7 | 14.8 / 31.4 |
| 64 | **prune** | 1.05 s | 13.5 s | 12.9× | **5.3 / 12.3** | **5.0 / 10.2** |
| 128 | fill | 1.25 s | 14.58 s | 11.7× | 14.9 / 32.7 | 13.8 / 29.2 |
| 128 | **prune** | 1.20 s | 13.6 s | 11.3× | **5.1 / 11.4** | **4.8 / 9.6** |

- **update เท่าเดิม** ตามที่คาด เพราะโค้ด update ไม่เปลี่ยน ส่วนต่างเล็กน้อยระหว่างรอบมาจากเครื่อง
- **query ต่อ batch เร็วขึ้น ~3× ทุก variant** ขนาด proof ลดจาก ~490 KB เหลือ ~175 KB
- **AMTP ยังช้ากว่า Static-MT ตอน query เล็กน้อย** (ตรวจ 12.3 เทียบกับ 10.2 ms ที่ θ = 64) ต้องเขียนใน paper

## ข้อตกลงเรื่องการวัด search แยกจาก proof

**ที่มา:** อาจารย์ให้แยกการทดลองตามขั้น (search อย่างเดียว, proof อย่างเดียว, verify, update, ฝั่ง user กับฝั่ง server) ตัวจับเวลา `lookup` เดิมใน `build_response` รวมงานเตรียม proof ไว้ด้วย (แผน AND pruning, IMT path, การประกอบหลักฐาน) จึงใช้เป็นเวลา search ไม่ได้

**ที่ทำไปแล้ว (PR #25, #27):** `amtp_code/bench_split/` วัด search ของ server อย่างเดียว โดยไม่แก้ไฟล์เดิม มี 3 แบบ

| แบบ | ใช้อะไร | หมายเหตุ |
|---|---|---|
| เต็ม | Cuckoo filter + B+ tree + `boolean.evaluate` ตัวจริง | ไม่มีโครงสร้างเพิ่ม |
| partition ก่อน | เหมือนข้างบน + `boolean.focus` (กฎเดียวกับ AND pruning) | ไม่มีโครงสร้างเพิ่ม |
| fast | ดัชนีค้นหาที่สร้างครั้งเดียวต่อ snapshot | D1, N = 100k: 83k keyword, สร้าง 0.43 วินาที, ~89 MB |

ผลบน Mac (search1, D1, N = 100k, kQ = 20): เต็ม 0.118 ms · partition ก่อน 0.093 ms · fast 0.035 ms · server รวม (search + proof) 0.456 ms

**ความเห็นของเพื่อนที่รับมาพิจารณา:** ใน paper ควรมีตัวเลข search ชุดเดียว · ดัชนีที่สร้างเพิ่มต้องอยู่ใน paper พร้อมต้นทุน · การหา focus set เป็นงาน search · ควรรัน exp5 ด้วย · ต้องระวังความยุติธรรมกับ Chen

**ตกลงกันแล้ว (เจ้าของงาน, 16 พ.ย.):**

1. **คืนนี้:** รัน `bench_split` บน cloud 1 เครื่อง: search1, xsearch, xdomains และ **exp5** เปิด flag เหมือนรอบ prune (fill + AND pruning + part-results + greedy, reps 15, warmup 3) เก็บทั้ง 3 แบบในรอบเดียว
2. **เอาผลให้อาจารย์ดู** โดยเสนอแบบ **fast** เป็นตัวเลขหลัก พร้อมต้นทุนของดัชนี
3. **ถ้าอาจารย์รับดัชนีค้นหาในการออกแบบ:** ใส่ดัชนีใน server จริงเป็น flag `AMTP_SEARCH_INDEX` (ค่าเริ่มต้นปิด ผลเดิมจะไม่เปลี่ยน) พร้อมตัวจับเวลา search / prep ใน `build_response` ตามที่เพื่อนเสนอ แล้วรันชุด search อีกรอบเป็นตัวเลขสุดท้ายของ paper
4. **ถ้าอาจารย์ไม่รับ:** ใช้แบบ partition ก่อนจากรอบคืนนี้ ไม่ต้องรันเพิ่ม
5. **baseline ไม่ปรับและไม่รันใหม่** ใช้นิยามนี้ และเขียนไว้ใน paper:

   | scheme | เวลา search | หมายเหตุ |
   |---|---|---|
   | SE-COLLAB | `search_core` | รวม result fetch · เทียบกับ AMTP search + fetch |
   | Chen | `server_total` | รวม XOR tag ต่อ entry (เล็กมาก) · ไม่มี fetch · วัดหลัง warm-up ซึ่ง chain ถูกยุบแล้ว (กรณีที่ดีที่สุดของ Chen) · เทียบกับ AMTP search ไม่นับ fetch |
   | Du | `server_total` | cloud ที่ช้าที่สุด · tag สร้างไว้ล่วงหน้า |

## สิ่งที่คาดไว้ (ยังไม่ใช่ผล)

ประมาณจากผลบน Mac × 2 เทียบกับ baseline บน cloud ที่ N = 100k:
- **ชนะ SE-COLLAB และ Du ทุก kQ**
- **Chen:** น่าจะชนะที่ kQ ≥ 2 ด้วยแบบ fast (ส่วนต่าง ~1.4–1.6×) · สูสีหรือแพ้ที่ kQ = 1 และที่ไฟล์น้อย (10k–25k) · ถ้าใช้แบบ partition ก่อนจะแพ้ Chen
- **OR ที่ kQ สูงเทียบกับ SE-COLLAB:** ยังไม่มีตัวเลขขนาดเต็ม

การแยก search ไม่ได้เปลี่ยนผลอื่น: end-to-end ของ search1 ยังแพ้ Du · OR ยังแพ้ SE-COLLAB เรื่องเวลา · verify ของ keyword เดียวยังแพ้ที่ rQ ≥ 1,000 · update ยังแพ้ Chen

## วิธีรันรอบวัด search อย่างเดียว

```
git bundle create newamtp_split.bundle 767289c..main          # เครื่อง cloud ไม่มีสิทธิ์เข้า GitHub
CHECK_ONLY=1 WANT=<commit ของ main> BUNDLE=newamtp_split.bundle bash scripts/cloud_helpers/start_split.sh <ip>   # ตรวจเครื่อง
WANT=<commit ของ main> BUNDLE=newamtp_split.bundle bash scripts/cloud_helpers/start_split.sh <ip>                # เริ่มรัน (~4 ชม.)
IP=<ip> REPO=$PWD bash scripts/cloud_helpers/watch_split_local.sh                                                # ตัวเฝ้าบน Mac
```

- งานรันใน `~/split_cloud_worker.sh` บนเครื่อง เพื่อให้ `scripts/watch_stop.sh` (ซึ่งเฝ้าชื่อ `cloud_worker.sh`) ไม่ปิดเครื่องระหว่างรัน และปิดเครื่องเอง 10 นาทีหลังงานจบ
- ผลบนเครื่อง: `~/NewAMTP/baselines/results/runs/paper_split/` · ตัวเฝ้าดึงมาไว้ที่ `baselines/results/runs/cloud/split_w1/`

## สถานะ

- เพิ่มแค่ผล สคริปต์ช่วยรัน และเอกสาร ไม่มีโค้ดของ AMTP หรือ benchmark เปลี่ยน
- pytest: 521 passed บน main `2202aa0`
- exp5 ผ่าน `bench_split.run` ทดสอบบน Mac แล้ว (1 / 2 / 4 domain, 195 query, จุดตรวจผ่าน)
- รอบวัด search อย่างเดียวยังไม่ได้เริ่ม รอเปิดเครื่อง cloud

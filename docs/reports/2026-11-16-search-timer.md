# วัด search ของ server แยกจาก proof (โฟลเดอร์ใหม่ `amtp_code/bench_split/`)

วันที่ 16 พ.ย. 2026 · branch `feat/search-timer`

## ทำไม

อาจารย์ให้แยกการทดลองตามขั้น: search อย่างเดียว, proof อย่างเดียว, verify, update และแยกเวลาฝั่ง user กับฝั่ง server

ปัญหาของตัวจับเวลาเดิม (`build_response` ใน `amtp/server.py`):
- ช่วง "lookup" ครอบงานเตรียม proof ไว้ด้วย ได้แก่ แผน AND pruning, IMT path และรูป posting list ที่จะส่ง
- ใน search1 รอบ prune ที่ kQ = 20 ตัวเลข lookup จึงเป็น 0.83 ms ซึ่งไม่ใช่เวลาค้นหาจริง

เจ้าของงานกำหนดว่า**ห้ามแก้ไฟล์โค้ดเดิม** ให้ทำงานชิ้นนี้ในโฟลเดอร์ใหม่ และผลก็เก็บแยกในโฟลเดอร์ใหม่

## ทำอะไร

ทุกอย่างอยู่ใน `amtp_code/bench_split/` (รายละเอียดใน `amtp_code/bench_split/README_TH.md`) ไม่มีไฟล์เดิมใน `amtp/`, `bench/`, `baselines/` หรือ `scripts/` ถูกแก้

1. **`search_only.py`:** การค้นหาของ server อย่างเดียว (lookup → เซตไฟล์ → AND / OR → ดึง ciphertext) ไม่สร้าง proof มี 3 แบบ
   - **เต็ม:** สร้างเซตไฟล์จาก posting list ทั้งหมด
   - **partition ก่อน:** หา partition ที่ match ได้ด้วย `boolean.focus` ซึ่งเป็นกฎเดียวกับที่ AND pruning และ user ใช้ แล้วสร้างเซตเฉพาะใน partition นั้น
   - **fast:** ใช้ `SearchIndex` ที่สร้างครั้งเดียวต่อ snapshot (keyword ที่อยู่ตั้งแต่ 3 partition → เซตของ partition + ไฟล์ในแต่ละ partition) แล้วค้นแบบ partition ก่อน
2. **`run.py`:** ห่อ `bench.experiments.run_query` (ไม่แก้ไฟล์) ทุก query ที่วัดจะรัน search ทั้ง 3 แบบในรอบเดียวกัน แล้วต่อด้วย query เต็มแบบเดิม
   - คอลัมน์เดิมเหมือนเดิมทุกตัว
   - เพิ่มคอลัมน์ `server_search*`, `pf_*`, `fast_*`
   - มีจุดตรวจ: ทั้ง 3 แบบต้องได้ไฟล์ตรงกับ response จริง
   - เวลาสร้างและขนาดของดัชนีบันทึกใน `search_index_<suite>.json` (ไฟล์ละชุด)
3. **`plot_search.py`:** กราฟเส้น search อย่างเดียว (Search 1.1, 1.2, 2.1, 2.2) เทียบ AMTP (เต็มและ fast) กับ SE-COLLAB `search_core` และ `server_total` ของ Chen และ Du พร้อมกราฟแยกเวลา server ของ AMTP เป็น search กับ search + proof
4. **`run_cloud.sh`:** pytest → search1 → xsearch → xdomains → กราฟ บน cloud 1 เครื่อง เปิด flag เหมือนรอบ prune
5. **`test_search_split.py`:** ทั้ง 3 แบบได้ไฟล์ตรงกับ `build_response` ใน query 11 แบบ (AND, OR, ซ้อน, keyword ที่ไม่มี, keyword ที่ไม่อยู่ในดัชนี) ทั้งตอนเปิดและปิด flag

## ผลบน Mac (search1, D1, N = 100k, เปิดทุก flag, reps 15, ms)

| kQ | เต็ม | partition ก่อน | fast | server รวม (search + proof) |
|---|---|---|---|---|
| 1 | 0.004 | 0.003 | 0.003 | 0.045 |
| 5 | 0.020 | 0.019 | 0.010 | 0.134 |
| 10 | 0.060 | 0.052 | 0.018 | 0.254 |
| 20 | 0.118 | 0.093 | 0.035 | 0.456 |

**ดัชนีของแบบ fast (D1, N = 100k):** 82,995 keyword จากทั้งหมด 1,082,038 · สร้าง 0.43 วินาที · ~89 MB

**ประมาณการบน cloud** (AMTP ช้ากว่า Mac ~2× เหมือนชุดอื่น รวม fetch) เทียบกับตัวเลขจริงของ baseline บน cloud ที่ kQ = 20:

| AMTP fast | SE-COLLAB `search_core` | Chen | Du |
|---|---|---|---|
| ~0.07 | 0.43 | 0.12 | 1.36 |

ส่วนต่างกับ Chen น้อย ต้องรอตัวเลขจริงจาก cloud

## ผลกระทบกับผลที่มีอยู่

- ไม่มีผลกระทบ เพราะไม่ได้แก้โค้ดเดิม และ server จริงทำงานเหมือนเดิม
- ผลรอบ prune ทุกชุดและ ex4 ที่กำลังรันใช้ได้ตามเดิม

## ต้องเขียนใน paper

- นิยามของ "search อย่างเดียว" ของแต่ละ scheme (ตารางใน README)
- ต้นทุนของดัชนีของแบบ fast
- แสดงทั้ง AMTP แบบเต็มและแบบ fast
- แสดงกราฟ server รวมและ end-to-end คู่กันเสมอ
- กราฟนี้วัดต้นทุนการคำนวณ ไม่ได้วัดว่าแต่ละ scheme เปิดเผยข้อมูลอะไรให้ server เห็นบ้าง
- baseline ทำตาม paper ต้นฉบับ ไม่ได้ปรับเพิ่ม

## วิธีรัน

```
cd amtp_code
../.venv/bin/python -m pytest -q bench_split
SMOKE=1 RUN_NAME=smoke_split bash bench_split/run_cloud.sh      # ตรวจทุกขั้น 1 รอบต่อจุด
RUN_NAME=paper_split bash bench_split/run_cloud.sh              # บน cloud: ผลอยู่ใน baselines/results/runs/paper_split/
```

## สถานะ

- pytest: 521 passed (รวม `bench_split` 7 ตัว)
- **ตรวจโค้ดก่อนขึ้น cloud (16 พ.ย. เย็น) แก้ 3 จุดใน `bench_split/`:**
  - `run.py` เก็บ snapshot ทุกตัวไว้ตลอดการรัน (โค้ดเดิมลบ snapshot หลังจบแต่ละขนาด) ทำให้หน่วยความจำสะสม แก้เป็นอ้างแบบ weak reference ดัชนีถูกลบพร้อม snapshot · ตรวจแล้ว: หน่วยความจำสูงสุดเท่ากับ `bench.experiments` (4.0 GB ที่ search1 D1–D2, 10k–50k) และคอลัมน์ที่ไม่ใช่เวลาตรงกันทุกแถว (120 แถว)
  - สลับลำดับการรันของ search 3 แบบทุกรอบ ไม่ให้แบบใดต้องรันเป็นตัวแรก (cache เย็น) ทุกครั้ง
  - `run_cloud.sh`: ถ้า pytest ไม่ผ่านให้หยุดทันที · การ plot ไม่นับเป็นความล้มเหลวของการรัน
- smoke test บน Mac ผ่าน มี 2 ส่วน (เปิดทุก flag, 1 รอบต่อจุด):
  - **ขนาดเต็ม:** search1 ของ D1 (100k และทุกขนาด) 200 query ผ่านจุดตรวจหมด
  - **ขนาดย่อ:** search1 D1 10k / 25k, xsearch 10k ต่อ domain, xdomains 10k × 1 / 2 / 4 domain ทุกชุดผ่าน ไม่มี FAIL ไม่มีจุดตรวจล้ม · คอลัมน์ใหม่ครบ 48 คอลัมน์ในทั้ง 3 ไฟล์ · กราฟ 8 รูป
  - ระหว่าง smoke test เจอว่าไฟล์สถิติของดัชนีถูกชุดหลังเขียนทับ แก้แล้ว: ใช้ไฟล์ละชุด
- ยังไม่ได้รันบน cloud

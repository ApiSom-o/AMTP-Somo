# รายงาน: อัปเดต Merkle tree ของ engine แบบรวมครั้งเดียว และค้น Search Tree ครั้งเดียวต่อ keyword — 15 พ.ย. 2026

## สรุป

- ตอน commit แต่ละ epoch engine ฝั่ง Cloud Server hash node เดิมซ้ำหลายรอบโดยไม่จำเป็น แก้ให้ hash node ที่เปลี่ยน **ครั้งเดียวต่อ node**
- **root, ทุก node ของ tree, proof, layout และผล accept / reject เหมือนเดิมทุกตัว** ไม่เปลี่ยน protocol, Validator, ฝั่งผู้ใช้ และ baseline
- วัดบน Mac (N = 10,000, placement = fill): hash ฝั่ง server ลด **41–71%** · update ของ ex3 เร็วขึ้น **1.2–1.27×** · ex4 เร็วขึ้น AMTP **1.5–1.8×**, Static-MT **1.9–2.0×**, Global-MT(v) **2.1×**
- ทุก variant ใช้ engine ตัวเดียวกัน จึงเร็วขึ้นทั้งหมด **Global-MT(v) ได้ประโยชน์มากที่สุด** ระยะห่างของ AMTP จึงลดลง (ดูตาราง) ตัวเลขเดิมสูงเกินจริงส่วนหนึ่งเพราะงานซ้ำของโค้ด

## ปัญหาที่เจอ

profile ช่วง update ของ AMTP (N = 30,000, b = 100) พบว่าเวลาส่วนใหญ่อยู่ที่ `node_hash` ซึ่งถูกเรียกจาก `MerkleTree.set_leaf`

`Engine._update_imt` เรียก `set_leaf` ทีละ keyword ที่เปลี่ยน แต่ละครั้ง hash จาก leaf ขึ้นไปถึง root (IMT ลึก 19 ชั้น)
batch ที่มี keyword เปลี่ยน k ตัวจึงใช้ k × 19 hash และ hash root ซ้ำ k ครั้ง ทั้งที่ใช้แค่ค่าสุดท้าย
นับจากการรันจริง (ต่อ batch, median): fill ใช้ 327,002 hash ซึ่ง 120,062 ตัว (37%) เป็นงานซ้ำ · least ใช้ 1,101,252 ซึ่ง 588,170 ตัว (53%) เป็นงานซ้ำ

Validator ไม่มีปัญหานี้ เพราะคำนวณ root จาก multiproof (`root_from_proof`) ซึ่ง hash แต่ละ node ครั้งเดียวอยู่แล้ว

## แก้อะไร

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `amtp/core/merkle.py` `MerkleTree.set_leaves` (ใหม่) | รับ `{ตำแหน่ง: ค่า}` หลาย leaf ตั้งค่า leaf ทั้งหมดก่อน แล้ว hash node ที่เปลี่ยนไล่ขึ้นทีละชั้น ชั้นละครั้งต่อ node · รองรับการเติมช่อง padding (ส่ง `n` ใหม่) · undo เป็น action เดียวที่คืนค่าทุก node และ `n` |
| `amtp/engine.py` `_update_imt` | ใช้ `set_leaves` ครั้งเดียวสำหรับ leaf ที่เปลี่ยนและ key ใหม่ทั้งหมด · ถ้า key ใหม่เกินความจุ สร้าง tree ใหม่ขนาดสองเท่าจาก leaf ปัจจุบัน (ผลเท่ากับของเดิม) |
| `amtp/engine.py` `commit` | domain tree (R^part): `set_leaves` ครั้งเดียวสำหรับ partition ที่เปลี่ยน |
| `amtp/engine.py` `_post_root` | tree ของ γ ต่อ keyword: `set_leaves` ครั้งเดียวสำหรับ component ที่เปลี่ยน |
| `amtp/engine.py` `commit`, `_post_root` | ค้น B+ Search Tree **ครั้งเดียวต่อ keyword ที่เปลี่ยน** (เดิมค้น key เดิมซ้ำ 4–5 ครั้ง) แล้วส่งผลต่อให้ `_post_root` |

`set_leaf` และ `try_append` เดิมยังอยู่ (ใช้กับ slot tree ของ partition ซึ่งเปลี่ยนทีละไฟล์)

## หลักฐานว่าผลไม่เปลี่ยน

- `tests/test_merkle_set_leaves.py` (ใหม่ 46 test):
  - ทุก node, root และ `n` ตรงกับวิธีเดิม (`set_leaf` / `try_append` ทีละตำแหน่ง) ใน 30 กรณีสุ่ม รวมการเติม padding
  - จำนวน hash = จำนวน leaf + จำนวน ancestor ที่ไม่ซ้ำ พอดี และไม่เกินวิธีเดิม
  - undo คืนทุก node และ `n` · เรียกเปล่าไม่ทำอะไร · เรียกสองครั้งเท่ากับเรียกครั้งเดียว
  - engine: root = full rebuild ทุก commit ขณะที่ IMT ขยายความจุหลายรอบ (least และ fill) · `rollback` คืน IMT, domain tree และ tree ของทุก keyword เท่าเดิม
- test เดิมทั้งชุดยังผ่าน: root แบบ incremental = full rebuild, Validator ได้ root เดียวกับ server ทุก epoch, abort / tamper
- ex4 ก่อนและหลังแก้: จำนวน partition, partition ใหญ่สุด, split / merge, keys_refreshed และ proof_bytes **เท่ากันทุกตัว**
- `cd amtp_code && ../.venv/bin/python -m pytest -q` → **409 passed**
- `scripts/cloud_helpers/scan_in.py` กับ `merkle.py`, `engine.py`: จุดใหม่ (`sel_of`) เป็น dict ไม่มีลูปซ้อนเพิ่ม

## ผลวัดบน Mac (ใช้ตัดสินใจเท่านั้น ไม่ใช่ตัวเลขของ paper)

ทุกแถวใช้ placement = fill · "ก่อน" = commit `b6205dd` · "หลัง" = รายงานนี้ · ก่อนและหลังรันพร้อมกันบนเครื่องเดียว

### ex3 (N = 10,000, reps 3 warm-up 1, insert)

| b | update ก่อน → หลัง | server | validate | hash_calls (server) |
|---|---|---|---|---|
| 1 | 55 → 47 ms (1.18×) | 29 → 21 | 26 → 25 | 20,498 → 12,110 (−41%) |
| 10 | 284 → 233 ms (1.22×) | 154 → 104 | 128 → 128 | 145,080 → 70,764 (−51%) |
| 100 | 1,159 → 945 ms (1.23×) | 626 → 401 | 505 → 523 | 459,294 → 209,990 (−54%) |
| 1,000 | 4,038 → 3,168 ms (1.27×) | 2,352 → 1,495 | 1,561 → 1,542 | 1,477,072 → 591,094 (−60%) |

delete ได้ผลเท่ากัน (1.22–1.27×) · Validator ไม่เปลี่ยน และตอนนี้เป็นประมาณครึ่งหนึ่งของเวลา update

เทียบกับโค้ดก่อนวันนี้ (least, ไม่แก้ engine): b = 100 จาก 3,321 → 945 ms (3.5×) · b = 1,000 จาก 7,999 → 3,168 ms (2.5×)

### ex4 (N = 10,000, θ = 64/16, skew 0.95, 100 insert batch × 100 แล้ว hot delete 63 batch, median ต่อ batch)

| variant | phase | update ก่อน → หลัง | hash_calls |
|---|---|---|---|
| AMTP | insert | 296 → 199 ms (1.49×) | 251,557 → 143,234 (−43%) |
| AMTP | hot_delete | 1,433 → 799 ms (1.79×) | 1,195,980 → 497,955 (−58%) |
| Static-MT | insert | 1,747 → 909 ms (1.92×) | 1,510,770 → 513,502 (−66%) |
| Static-MT | hot_delete | 2,220 → 1,097 ms (2.02×) | 1,887,056 → 635,826 (−66%) |
| Global-MT(v) | insert | 4,048 → 1,897 ms (2.13×) | 3,687,783 → 1,076,678 (−71%) |
| Global-MT(v) | hot_delete | 4,568 → 2,148 ms (2.13×) | 4,087,384 → 1,212,743 (−70%) |

AMTP เร็วกว่ากี่เท่า (เวลา update ต่อ batch):

| | ก่อน | หลัง |
|---|---|---|
| insert: เทียบ Static-MT | 5.9× | 4.6× |
| insert: เทียบ Global-MT(v) | 13.7× | 9.5× |
| hot_delete: เทียบ Static-MT | 1.5× | 1.4× |
| hot_delete: เทียบ Global-MT(v) | 3.2× | 2.7× |

query ไม่เปลี่ยน (verify AMTP 3.2 ms, Static-MT 2.9 ms, Global-MT(v) 1.9 ms · proof เท่าเดิมทุก byte)

## รันซ้ำ

```
cd amtp_code
../.venv/bin/python -m pytest -q tests/test_merkle_set_leaves.py
../.venv/bin/python -m bench.experiments exp3 --reps 3 --warmup 1 --sizes 10000 --batches 1 10 100 1000 \
  --placement fill --out <dir>
../.venv/bin/python -m bench.ablation --source arxiv --n 10000 --theta-max 64 --theta-min 16 --batches 100 \
  --batch-size 100 --delete-frac 0 --fresh-source initial --skews 0.95 --runs 1 --hot-delete-frac 0.65 \
  --query-every 50 --placement fill --variants "AMTP,Static-MT,Global-MT(v)" --out <dir>
```

## สถานะ / งานต่อ

- โค้ดและ test เสร็จ ยังไม่ได้รันบน cloud
- **ผล update บน cloud ที่มีอยู่ทุกชุด (ex3, ex4, ex5 และ Global-MT(v) ของ w3) รันด้วยโค้ดก่อนการแก้นี้** `hash_calls` และเวลา update จึงเทียบกับรอบใหม่ไม่ได้ ต้องใช้ผลจากรอบรันใหม่ทั้งหมด
- แผนรันบน cloud (5 เครื่อง, `AMTP_PLACEMENT=fill`, ยังไม่เริ่ม): ex4 AMTP + Static-MT ที่ θ = 64 / 128 / 256 เครื่องละ θ ·
  AMTP ที่เหลือ (search1, verify1, tamper, multi-domain, ex3, ex5) หนึ่งเครื่อง · AMTP θ = 64 + Global-MT(v) หนึ่งเครื่อง
- ที่ยังไม่ได้ทำ: รายการ keyword ที่เรียงแล้ว (`imt_sorted`) ยังเป็น list ซึ่งแทรกช้า (~4% ของเวลา update) ผลน้อยและแตะส่วนหา predecessor ของ IMT จึงยังไม่แก้

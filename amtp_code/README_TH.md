# AMTP User Demo: ฝั่ง Data User

Demo นี้แสดงว่าผู้ใช้ (DU) จะเจออะไรบ้างตอนค้นหาไฟล์ที่เข้ารหัสไว้:
พิมพ์ Boolean query → server ค้นหา → **user verify proof เอง 7 ข้อ** → ผ่านแล้วถึงจะถอดรหัส

## วิธีรัน

```bash
pip install -r requirements.txt
python run.py
```

จากนั้นเปิด http://127.0.0.1:5000 ในเบราว์เซอร์

ถ้าจะรันเทส: `python -m pytest -q` (ต้องผ่านทั้ง 17 ข้อ)

## หน้าจอมีอะไรบ้าง

| ส่วน | ใช้ทำอะไร |
|---|---|
| **Signed in as** | เลือก user 4 คน แต่ละคนมี attribute (ใช้ถอดรหัส) กับ query key (ใช้ค้นหา) ไม่เหมือนกัน |
| **Blockchain anchor** | Domain Root (R_D) กับ epoch ล่าสุดของแต่ละ domain และ Global Root (R_G) ซึ่ง user เชื่อแค่ค่าบนนี้ ไม่เชื่อ server |
| ปุ่ม **Owner adds …** | จำลองว่า DO อัปโหลดไฟล์ใหม่ ทำให้ epoch เพิ่มขึ้น 1 (ถ้าไฟล์เกิน θ_max จะเกิด split) |
| **Boolean query** | พิมพ์ query เช่น `(diabetes AND insulin) OR obesity` หรือกดตัวอย่างที่เตรียมไว้ |
| **Domains** | เลือกค้นได้หลาย domain พร้อมกัน แต่ละ domain verify แยกกันด้วย Domain Root ของตัวเอง |
| **Cloud server behaviour** | ปุ่มสำหรับโชว์ในงานนำเสนอ ใช้สั่งให้ server โกงแบบต่างๆ |

ผลของแต่ละ domain จะแสดงเป็น 4 ขั้น: Build trapdoor → Server searches → Verify proof → Decrypt

- **Verified** (สีเขียว): ผ่านครบ 7 ข้อแล้วถอดรหัส ไฟล์ที่ attribute ไม่ผ่าน policy จะขึ้นว่า 🔒 Locked
  (verify ผ่านแล้ว แต่ไม่มีสิทธิ์อ่าน)
- **Rejected** (สีแดง): มีข้อที่ไม่ผ่าน จะบอกว่าข้อไหนและเพราะอะไร แล้วทิ้งผลทั้งหมดโดยไม่ถอดรหัสเลย
- **Storage error**: ไฟล์หายจาก DHT server ต้องแจ้ง error แทนการส่งผลไม่ครบ
- **No query key**: user คนนี้ไม่มีสิทธิ์ค้นใน domain นั้น

## 7 checks ของ Phase 5 (Accept_Q)

| Check | ตรวจอะไร | Attack ที่ check นี้จับได้ |
|---|---|---|
| b_ctx | domain, epoch, B_Q, nonce ตรงกับที่ส่งไป | Replay response เก่า |
| b_anchor | H(i‖e‖R^part‖R^idx) = R_D บน blockchain | ตอบจาก epoch เก่า (rollback) |
| b_idx | ทุก keyword มีหลักฐาน และการอ้างว่า "ไม่มี keyword นี้" ต้องมี proof | อ้างว่า keyword ไม่มีทั้งที่มี |
| b_papc | สร้าง ρ̂ ใหม่จาก posting list แล้วต้องเจอใน IMT | ลบรายการออกจาก posting list |
| b_part | ทุกตำแหน่งอยู่ใน partition และทุก partition อยู่ใน domain (ASPA multiproof) | ปลอมเนื้อหาใน partition |
| b_comp | Eval(B_Q) ที่ user คำนวณเองต้องได้ไฟล์ชุดเดียวกับที่ server ส่งมาเป๊ะ | ซ่อนไฟล์ หรือเพิ่มไฟล์ที่ไม่ตรง |
| b_ct | H(CT) = cid | แก้ไขเนื้อไฟล์ |

ทุก attack ในเดโมเป็นการแก้ response จริงของ server ไม่ได้ fix ผลไว้ล่วงหน้า และมีเทสคอยเช็คว่า
แต่ละ attack ถูกจับโดย check ที่ถูกต้อง (`tests/test_demo.py`)

## อะไรของจริง อะไรเป็นตัวแทน (ต้องบอกกรรมการตรงๆ)

| ส่วน | ในเดโม |
|---|---|
| AES-GCM, AES-SIV (DEnc), HMAC, SHA-256 | **ของจริง** (library `cryptography`) |
| Merkle tree + multiproof, PAPC, IMT, non-membership proof | **ของจริง** เขียนเองทั้งหมด |
| Partition + split ตาม θ (0 < θ_min, 2θ_min < θ_max) | **ของจริง** (θ_min=1, θ_max=4 เพื่อให้เห็น split กับข้อมูลน้อยๆ) |
| CP-ABE | **ตัวแทน**: ห่อ key ด้วย policy tree ถ้า attribute ไม่ผ่านจะถอดไม่ได้จริง แต่ยังไม่ collusion-resistant ใน prototype ต้องเปลี่ยนเป็น Charm (FAME/BSW07) |
| ABS | **ตัวแทน**: ใช้ Ed25519 signature ของ DO |
| Blockchain | **จำลอง** เป็น class RootAnchor ใน Python (ตรวจ signature และ e = e*+1) ใน prototype ต้องเปลี่ยนเป็น Solidity บน local chain |
| DHT | **จำลอง** 6 node, replica 3 ในโปรเซสเดียว |
| ข้อมูล | ข้อความสมมติ 12 ฉบับ ส่วนการทดลองจริงใช้ Enron |
| Index update | สร้าง index ใหม่ทั้งหมดทุก epoch เพื่อให้โค้ดอ่านง่าย ใน prototype ต้องคำนวณใหม่เฉพาะ path ที่เปลี่ยน |
| Merge, AUDC | ยังไม่มีในเดโมนี้ เพราะเป็นฝั่ง owner |

## โครงสร้างไฟล์

```
amtp/
  hashing.py   H(·) และ Enc(·)
  merkle.py    Merkle tree + multiproof (พื้นฐานของ ASPA)
  crypto.py    AES-GCM, AES-SIV, HMAC, Ed25519, CP-ABE stand-in
  boolean.py   parser AND/OR + Eval
  index.py     partition, posting list, PAPC (γ, ρ), IMT, R_D, split
  owner.py     Phase 1–3: เข้ารหัส, สร้าง index, เซ็น, ส่ง root
  anchor.py    Root Anchor (blockchain stand-in) + Global Root
  dht.py       ที่เก็บ ciphertext แบบ DHT
  server.py    Phase 4: รับ query, Eval, ASPA, และโหมดโกงต่างๆ
  user.py      Phase 4 Step 1 (trapdoor) + Phase 5 (7 checks, ถอดรหัส)
  scenario.py  domain, user, เอกสารสมมติ
web/           หน้าเว็บ (Flask)
tests/         เทส correctness gate
```

## ต่อยอดไปเป็น experiment

ตัวเลขเวลาและขนาด proof ที่โชว์ในหน้าเว็บวัดจากการรันจริง แต่**ยังเอาไปใส่ในรายงานไม่ได้**
เพราะข้อมูลน้อยมากและยังใช้ตัวแทนบางส่วน ขั้นต่อไปคือ:

1. เปลี่ยน CP-ABE และ ABS เป็นของจริง
2. โหลด Enron
3. เปลี่ยน index update เป็นแบบ dirty-path
4. เขียน script benchmark ที่รันซ้ำ ≥30 รอบ แล้วบันทึกผลเป็น CSV

---

# Ablation: AMTP vs Static-MT vs Global-MT

ส่วนนี้ใช้ตอบคำถามว่าการแบ่ง partition และ split/merge ช่วยได้จริงไหม

## หลักการ: ทุก variant ใช้โค้ดชุดเดียวกัน

ทั้ง 3 ตัวรันบน `amtp/engine.py` ตัวเดียวกัน สิ่งที่ต่างกันมีแค่ **partition policy** ใน `amtp/variants.py`
ถ้าผลออกมาต่างกัน จึงมาจากการแบ่ง partition จริงๆ ไม่ใช่เพราะเขียนโค้ดคนละแบบ

| Variant | Policy |
|---|---|
| **AMTP** | split เมื่อ n > θ_max และ merge เมื่อ n < θ_min โดยต้องมี partner ที่รวมกันแล้วไม่เกิน θ_max (ตามสมการ 31–36 ในรายงาน) |
| **Static-MT** | เริ่มจาก layout **เดียวกับ AMTP เป๊ะ** แล้วล็อกไว้ ไม่ split ไม่ merge |
| **Global-MT** | มี partition เดียวสำหรับทั้ง domain |
| Global-MT(v) | (ใส่ `--global-versioned` ถ้าต้องการ) partition เดียวแต่ยังเพิ่ม version ทุกครั้ง คือ "AMTP ที่มีแค่ 1 partition" แบบตรงตัว |

**Global-MT ไม่เพิ่ม version:** ถ้ามี partition เดียว การผูก version ไม่ได้ช่วยกันอะไรเพิ่ม เพราะ R_D ผูก root ของ partition นั้นอยู่แล้ว
ถ้าบังคับให้ Global-MT ต้อง refresh ทุก keyword ทุกครั้งที่ update จะกลายเป็น baseline ที่ทำให้อ่อนเกินจริง (strawman) ส่วน Global-MT(v) มีไว้ให้เห็นทั้งสองแบบ

**สิ่งที่ต้องคอนเฟิร์มกับอาจารย์:** รายงานบอกแค่ว่า "places cid in an active partition" ไม่ได้บอกว่าเลือก partition ยังไง
ในโค้ดตอนนี้ไฟล์แต่ละไฟล์มี bucket (เช่น เจ้าของ mailbox) แล้วจะถูกใส่ใน partition ที่ว่างที่สุดในกลุ่มที่ดูแล bucket นั้น
จะใช้กฎไหนก็ได้ แต่ทุก variant ต้องใช้กฎเดียวกัน

## Correctness gate (ถ้าไม่ผ่าน โปรแกรมจะหยุดเอง)

1. R_D ที่ได้จาก update แบบ incremental ต้องเท่ากับ R_D ที่ได้จากการสร้างใหม่ทั้งหมด
2. ทุก query ของทุก variant ต้องผ่านทั้ง 7 checks ของ Phase 5

## วิธีรัน

```bash
# smoke test ด้วยข้อมูลสังเคราะห์ (ใช้แค่เช็คว่า script ทำงาน ห้ามเอาตัวเลขไปใส่รายงาน)
python -m bench.ablation --source synthetic --n 5000 --batches 40 --batch-size 25

# ของจริงด้วย dataset กลาง arXiv (dataset-v4, ชุดเดียวกับทุก baseline) — python3 datasets/arxiv/unpack.py -> <repo>/data/amtp_file_db_v4
#   เอกสารเริ่มต้น = amtp_dataset.sample(N), เอกสารที่ insert = insert pool, keyword = documents.csv (ไม่สกัดซ้ำ)
#   bucket = arXiv primary category (พับเหลือ --buckets กลุ่ม) ; --batches x --batch-size ต้องไม่เกิน 50,000 (insert pool ของ v4)
python -m bench.ablation --source arxiv --n 100000 \
    --theta-max 1024 --theta-min 256 --batches 50 --batch-size 10 --runs 30 --out results_exp4

# ทางเลือก: Enron — โหลด enron_mail_20150507.tar.gz จาก CMU (https://www.cs.cmu.edu/~enron/)
# แตกไฟล์จะได้โฟลเดอร์ maildir/
python -m bench.ablation --source enron --enron ./maildir --n 100000 \
    --theta-max 1024 --theta-min 256 --batches 50 --batch-size 10 --runs 30 --out results_exp4
```

พารามิเตอร์หลัก:

| พารามิเตอร์ | ความหมาย |
|---|---|
| `--skews 0,0.5,0.8,0.95` | สัดส่วนไฟล์ใหม่ที่ถูกบังคับลง hot bucket |
| `--batch-size` | ขนาด batch (ตามรายงานคือ 1/10/100/1000) |
| `--theta-max/--theta-min` | ต้องเลือกจากรอบจูนแยก (ใช้ `--seed` คนละค่า) ก่อนรันจริง |
| `--runs` | จำนวนรอบ แต่ละรอบใช้ seed ต่างกัน แต่ภายในรอบเดียวกันทุก variant ได้ข้อมูลชุดเดียวกัน |

## ไฟล์ผลลัพธ์ (ในโฟลเดอร์ `--out`)

| ไฟล์ | มีอะไร |
|---|---|
| `updates.csv` | ทุก batch: เวลา, จำนวน hash, จำนวน byte ที่ hash, split/merge, จำนวน posting ที่ต้อง refresh |
| `queries.csv` | ทุก query: เวลาฝั่ง server, เวลา verify, ขนาด proof, จำนวน partition ที่ครอบคลุม |
| `layout.csv` | จำนวน partition และ partition ที่ใหญ่สุดหลัง update |
| `manifest.json` | สเปกเครื่อง, เวอร์ชัน Python และพารามิเตอร์ที่ใช้รัน |
| `summary.md` | ค่า median (เอาไว้ดูคร่าวๆ ส่วนกราฟและ CI ให้ทำจาก CSV) |

`hash_calls` กับ `hash_bytes` เป็นตัววัดต้นทุนที่ไม่ขึ้นกับเครื่อง ควรรายงานคู่กับเวลา

## ทำกราฟ

```bash
python -m bench.plot results_exp4
```

กราฟจะอยู่ใน `results_exp4/figures/` แยกกราฟละ 1 metric มีทั้ง `.png` (ไว้ใส่สไลด์) และ `.pdf` (ไว้ใส่ LaTeX)
และมี `overview.png` ที่รวมทั้ง 6 กราฟไว้ในรูปเดียว

- แต่ละจุดในกราฟคือค่า median และ error bar คือ 95% bootstrap CI
- ถ้ารันหลายรอบ (`--runs 30`): ระบบหา median ของแต่ละรอบก่อน แล้วคิด CI ข้ามรอบ แบบนี้คือสิ่งที่ควรใส่ในรายงาน
- ถ้ารันรอบเดียว: กราฟจะเขียนกำกับไว้ว่า "ONE RUN … smoke test only"
- ถ้าใช้ข้อมูลสังเคราะห์: หัวกราฟจะเขียนว่า SYNTHETIC
- ตัวเลขทุกจุดในกราฟอยู่ใน `figures/figure_data.csv` ไว้ทำตารางหรือเช็คย้อนหลังได้


# Dataset กลาง (arXiv) และเวลาสกัด keyword (Phase 1)

- ทุก scheme (AMTP, Chen [40], Du [7], SE-COLLAB [37]) ใช้ **เอกสารและ keyword W(d) ชุดเดียวกัน** จาก `documents.csv`
  ผ่าน `baselines/amtp_dataset.py` ไม่มีใครสกัด keyword เอง → เวลา search / update ที่เทียบกันไม่รวมเวลาสกัด keyword
- keyword ใน dataset-v4 สกัดด้วย `amtp/nlp.py` (RAKE ตาม Phase 1: Θ_doc = 30,000, L_ch = 400, L_ov = 80, κ = 20,
  Norm แบบ idempotent) ส่วน `index.extract_keywords()` เป็นตัวสกัดคำเดี่ยวแบบง่ายที่ใช้เฉพาะหน้าเว็บ demo
- `DataOwner.encrypt()` ใช้ `doc["keywords"]` ถ้ามี (มาจาก documents.csv) ไม่งั้นค่อยสกัดเอง
- query แบบหลายคำใส่เครื่องหมายคำพูด เช่น `"machine learning" AND "neural network"`
- ดูรายละเอียด dataset ที่ `datasets/arxiv/README.md`

## วัดเวลาสกัด keyword แยก (รายงานเป็นตารางของตัวเอง)

```bash
python -m bench.extraction --n 200000 --pool --sizes 10000 50000 100000 200000 --out results_extraction
```

- จับเวลาเฉพาะ `extract_keywords()` (tokenise + Norm + RAKE + chunking) ไม่รวมอ่านไฟล์, ปิด GC, มี warm-up
- `amtp_extraction_summary.csv` ms ต่อเอกสาร (mean / median / std / p95) ต่อ domain + docs/s ;
  `amtp_extraction_by_n.csv` เวลารวมของทั้งชุดที่ N แต่ละค่า ; `amtp_extraction_raw.csv` รายเอกสาร ; `amtp_extraction_meta.json` สเปกเครื่อง
- คอลัมน์ `match_csv` ต้องได้ 100% (สกัดใหม่แล้วตรงกับ documents.csv ทุกไฟล์)
- ข้อความสำหรับ paper: *All schemes index the same documents and keyword sets W(d), extracted once with AMTP's
  Phase 1 procedure (RAKE, κ = 10); search and update costs therefore exclude keyword extraction, which is reported separately.*

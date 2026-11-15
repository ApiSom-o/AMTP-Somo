# AND pruning (study flag `--and-prune`)

วันที่ 16 พ.ย. 2026 · branch `feat/and-pruning`

## ทำอะไร

เพิ่ม AND pruning เป็น flag เสริม **ค่าเริ่มต้นปิด** ถ้าไม่เปิด flag ทุกอย่างทำงานเหมือน ASPA เดิมใน paper ผลเดิมทั้งหมดจึงไม่เปลี่ยน

**ปัญหา:** ตอนนี้เวลา query และขนาด proof โตตาม kQ และ N เพราะ server ส่ง posting list **เต็ม**ของทุก keyword และผู้ใช้ต้องตรวจ partition ทุกอันที่ list เหล่านั้นแตะ ทั้งที่ผลลัพธ์ของ AND มักมีแค่ไม่กี่ไฟล์

**หลักคิด:** ไฟล์ที่ตรงกับ AND ต้องอยู่ใน list ของ keyword ทุกตัว จึงต้องอยู่ใน partition ของ keyword ที่สั้นที่สุด (เรียกว่า focus set F) server จึงส่ง:
1. **list เต็มของ keyword ที่สั้นที่สุด:** ตรวจด้วย γ, ρ และ IMT เหมือนเดิม
2. **keyword อื่นส่งแค่ส่วนใน F (รูปแบบ `focus`):**
   - component ของ keyword นั้นในทุก partition ของ F ที่มี (`segs`)
   - ใน partition ของ F ที่ keyword นั้นไม่มี ให้ส่ง γ leaf สองตัวที่ติดกันซึ่งคร่อม PID นั้น (`nb` ส่งเป็น preimage คือ PID, v, H(Enc(L)))
   - ทั้งหมดเปิดด้วย multiproof เดียวใน R^post ของ keyword นั้น แล้ว ρ = H(h ‖ |Sel| ‖ R^post) ต้องอยู่ใน IMT เหมือนเดิม

**ไม่ต้องเปลี่ยน index, DO หรือ Validator:** ρ ผูก γ ที่เรียงตาม PID ไว้แล้ว และ Validator ตรวจทุกการเพิ่ม component ด้วย neighbour ว่าอยู่ในลำดับ PID (`validator.py` ส่วน `ins` / `pre`) การใช้ leaf สองตัวที่ติดกันพิสูจน์ว่า keyword ไม่มี component ใน partition จึงใช้ได้ HANDOFF §9 ข้อ D เคยเขียนว่าต้องเปลี่ยนโครงสร้าง index แต่จากที่ทำจริงไม่ต้อง

## ทำไมยังปลอดภัย (การจับ tamper ยังเท่าเดิม)

- **ผู้ใช้คำนวณ F เอง:** ใช้กฎ `boolean.focus` กับ keyword ที่ได้มาแบบเต็มและ keyword ที่พิสูจน์แล้วว่าไม่มีในระบบ กฎคือ AND ใช้ intersection และ OR ใช้ union ถ้า OR มีลูกตัวใดที่ไม่รู้ partition ผลคือ "ไม่มีขอบเขต" ในกรณีที่ไม่มีขอบเขต ถ้า server ส่งแบบ `focus` มา ผู้ใช้จะปฏิเสธ (check papc)
- **ตรวจว่าครอบคลุม F ครบ:** keyword แบบ `focus` ต้องมี component ในทุก partition ของ F หรือมี leaf ที่ติดกันคร่อม PID นั้น ถ้าไม่ครบ ผู้ใช้จะปฏิเสธ
- **ผลของ AND ยังถูกต้อง:** ไฟล์ที่ตรง B_Q ทุกไฟล์อยู่ใน F และใน F ผู้ใช้เห็น posting ครบทุก keyword ส่วนนอก F ข้อมูลที่เห็นเป็นเพียงส่วนย่อยของความจริง Eval เป็น monotone จึงสร้างผลเกินมาไม่ได้ ดังนั้น M̂_Q = M_Q
- **ไม่ต้องเชื่อว่า server เลือก keyword ที่สั้นที่สุดจริง:** ถ้า server เลือกผิด proof จะใหญ่ขึ้นเท่านั้น ผลยังถูกต้อง
- **check อื่นไม่เปลี่ยน:** ct, comp, part, anchor และ ctx เหมือนเดิม ทุกการ accept ยังผ่าน hash, Merkle หรือลายเซ็น
- **OR ไม่ถูก prune:** ต้องใช้ทุก list แบบเต็ม จึงได้ proof แบบเดิม

## สิ่งที่แก้

| ไฟล์ | แก้อะไร |
|---|---|
| `amtp/core/boolean.py` | `focus(ast, known)` คือกฎหา F ที่ server กับผู้ใช้ใช้ร่วมกัน |
| `amtp/index.py` | flag `AMTP_AND_PRUNE` / `set_and_prune()` · `DomainState.post_tree(h)` เก็บ R^post tree ไว้ตอน build เมื่อเปิด flag (ถ้าปิดใช้ `merkle_root` เหมือนเดิม) |
| `amtp/server.py` | `_and_plan`: เลือก keyword ที่ส่งแบบเต็ม (AND เลือกลูกที่มี partition น้อยที่สุด, OR ต้องใช้ลูกทุกตัว) · `_focus_evidence`: สร้าง segs, nb และ multiproof · เลือกรูปแบบที่เล็กกว่าให้แต่ละ keyword |
| `amtp/user.py` | `_parse_postings` รับรูปแบบ `focus` · `_check_papc` หา F, ปฏิเสธถ้าไม่มีขอบเขต และตรวจ `_focus_root` (multiproof, ลำดับ PID, การครอบคลุม F) |
| `baselines/wire_sizes.py` | นับขนาดของรูปแบบ `focus` ด้วยกฎเดียวกับส่วนอื่น (HASH 32 B, INT 8 B) |
| `bench/experiments.py` | `--and-prune` · pQ นับ `segs` ด้วย |
| `baselines/amtp_dataset.py` | manifest บันทึก `amtp_and_prune` |
| `tests/test_and_prune.py` | test ใหม่ 29 ตัว |

## ผลวัด (Mac เครื่องเดียวกัน, D1, N = 100k, query ชุด Search 1.1, 20 query ต่อ kQ, reps 10, warmup 2)

ค่าในตารางเป็น median ของแต่ละ kQ ต้นทุนก่อน → หลังเปิด `--and-prune`

| kQ | end-to-end (ms) | server (ms) | verify (ms) | proof (KB) | posting ที่ส่ง (pQ) | partition (sQ) | hash ของผู้ใช้ |
|---|---|---|---|---|---|---|---|
| 1 | 0.16 → 0.16 | 0.04 → 0.04 | 0.10 → 0.09 | 1.6 → 1.6 | 1.5 → 1.5 | 1.5 → 1.5 | 59 → 59 |
| 2 | 0.64 → 0.27 | 0.13 → 0.08 | 0.47 → 0.14 | 10.2 → 2.8 | 18 → 3 | 17 → 2 | 407 → 101 |
| 5 | 2.41 → **0.48** (5.0×) | 0.47 → 0.14 | 1.87 → 0.26 | 41.7 → **5.7** | 94 → 6 | 88 → 2 | 1,752 → 189 |
| 10 | 10.48 → **0.88** (11.9×) | 2.09 → 0.29 | 8.23 → 0.47 | 171.6 → **11.1** | 510 → 13 | 418 → 2.5 | 7,725 → 366 |
| 15 | 8.89 → **1.16** (7.7×) | 1.77 → 0.36 | 7.01 → 0.63 | 149.5 → **15.3** | 417 → 18 | 349 → 2 | 6,651 → 505 |
| 20 | 17.58 → **1.60** (11.0×) | 3.37 → 0.53 | 14.13 → 0.86 | 294.4 → **21.3** | 971 → 27 | 726 → 5 | 13,343 → 716 |

- **ความถูกต้อง:** ทั้ง 120 query ผ่าน correctness gate ของ `suite_search1` คือผลตรงกับ ground truth ที่คำนวณจากข้อความจริง
- **ขนาด proof:** ไม่มี query ไหนที่ proof ใหญ่ขึ้น (อัตราส่วน proof หลัง/ก่อน ของ query ที่แย่ที่สุดในแต่ละ kQ ≤ 1.0)
- **ต้นทุนเหลือประมาณ 1 posting และ 35 hash ต่อ keyword:** ไม่ขึ้นกับ N อีกต่อไป แต่ยังโตตาม kQ แบบเชิงเส้นเล็กน้อย

## Smoke test เทียบกับ baseline (Mac เครื่องเดียวกัน, D1, N = 100k, Search 1.1, reps 10, warmup 2)

baseline ใช้ option เดียวกับรอบหลักบน cloud: SE-COLLAB `--proof-mode paths` · Chen `--scope full --edb memory` · Du ค่าเริ่มต้น ทุก query ผ่าน correctness gate ของแต่ละ scheme (20 query ต่อ kQ)

**เวลา end-to-end (ms, median):**

| kQ | AMTP | AMTP + pruning | SE-COLLAB | Chen | Du |
|---|---|---|---|---|---|
| 1 | 0.16 | 0.16 | 7.43 | 0.09 | 0.20 |
| 2 | 0.64 | 0.27 | 7.39 | 0.48 | 0.22 |
| 5 | 2.41 | 0.48 | 7.42 | 1.27 | 0.41 |
| 10 | 10.48 | 0.88 | 7.51 | 3.04 | 0.71 |
| 15 | 8.89 | 1.16 | 7.56 | 3.75 | 1.02 |
| 20 | 17.58 | 1.60 | 7.61 | 5.55 | 1.34 |

**ขนาด proof (KB, median):**

| kQ | AMTP | AMTP + pruning | SE-COLLAB | Chen | Du |
|---|---|---|---|---|---|
| 1 | 1.6 | 1.6 | 0.8 | 0.0 | 5.1 |
| 5 | 41.7 | 5.7 | 0.5 | 0.2 | 3.4 |
| 10 | 171.6 | 11.1 | 0.5 | 0.3 | 3.4 |
| 20 | 294.4 | 21.3 | 0.5 | 0.6 | 3.4 |

- **เวลา:**
  - AMTP + pruning เร็วกว่า SE-COLLAB ทุก kQ (4.8–46×) และเร็วกว่า Chen ตั้งแต่ kQ = 2 ขึ้นไป (1.8–3.5×)
  - ยังช้ากว่า Du 15–25% (Du จับ inject ไม่ได้)
  - ถ้าไม่เปิด pruning AMTP แพ้ SE-COLLAB ที่ kQ ≥ 10 และแพ้ Chen ทุก kQ ≥ 2
- **ขนาด proof ตอนผลลัพธ์น้อย:** AMTP ยังใหญ่กว่า baseline ทุกตัวเมื่อ kQ ≥ 2 (ประมาณ 1 KB ต่อ keyword) ส่วน baseline อยู่ที่ 0.5–3.4 KB
- **ตัวเลขชุดนี้ใช้ยืนยันแนวโน้มเท่านั้น:** ไม่ได้ใช้แทนผลบน cloud และไม่ได้ใช้ใน paper
- **การติดตั้ง:** ติดตั้ง `charm-crypto-framework` 0.62 ลงใน `.venv` ของ Mac (Python 3.14) ตามขั้นตอนใน `baselines/README.md` เพื่อรัน SE-COLLAB

## Smoke test cross-domain (Search 2.1, 4 domain × 25k ไฟล์, Mac, reps 5, warmup 1)

ใช้ query จาก `queries_boolean_multi` 320 ตัว (4 shape × kQ 2/4/8/16 × 20 query) แต่ละ query ถามทุก domain แล้วตรวจกับ root ของแต่ละ domain เอง ตัวเลขเป็นผลรวมของทั้ง 4 domain ทุก query ผ่าน correctness gate ราย domain baseline ที่เทียบได้มีแค่ SE-COLLAB เพราะ Chen และ Du ไม่มีโหมด cross-domain ใช้ 25k ไฟล์ต่อ domain แทน 100k เพราะ RAM ของ Mac มี 16 GB

**เวลา end-to-end (ms, median), AMTP → AMTP + pruning · SE-COLLAB:**

| shape | kQ = 2 | kQ = 4 | kQ = 8 | kQ = 16 |
|---|---|---|---|---|
| AND | 1.39 → **0.76** · 7.26 | 6.60 → **1.23** · 7.46 | 16.08 → **2.11** · 7.53 | 20.88 → **3.75** · 7.69 |
| OR | 3.49 → 3.47 · 8.38 | 21.81 → 21.91 · **16.82** | 37.24 → 37.48 · **24.08** | 62.17 → 61.83 · **36.21** |
| AND_of_OR | 2.15 → **2.16** · 7.90 | 5.40 → **1.79** · 7.39 | 17.11 → **2.55** · 7.65 | 45.11 → **4.75** · 7.72 |
| OR_of_AND | 2.56 → **0.80** · 7.38 | 4.59 → **1.50** · 7.48 | 24.28 → **4.95** · 8.18 | 40.03 → 9.31 · **8.19** |

**ขนาด proof (KB, median), AMTP → AMTP + pruning · SE-COLLAB:**

| shape | kQ = 2 | kQ = 4 | kQ = 8 | kQ = 16 |
|---|---|---|---|---|
| AND | 19.5 → 7.6 · 0.5 | 107.7 → 13.4 · 0.5 | 258.7 → 25.9 · 0.5 | 327.8 → 51.0 · 0.5 |
| OR | 41.2 → 41.2 · 44.0 | 227.7 → 227.7 · 396.4 | 377.3 → 377.3 · 678.0 | 592.6 → 592.6 · 1,167.6 |
| AND_of_OR | 24.7 → 24.7 · 23.0 | 84.9 → 20.7 · 1.0 | 267.1 → 27.5 · 1.0 | 692.4 → 54.0 · 1.0 |
| OR_of_AND | 40.0 → 8.2 · 0.5 | 70.7 → 16.1 · 1.0 | 377.9 → 67.8 · 2.4 | 612.5 → 126.1 · 4.4 |

- **เวลา:**
  - AND และ AND_of_OR หลัง pruning ชนะ SE-COLLAB ทุก kQ (2–6×)
  - OR_of_AND ชนะที่ kQ ≤ 8 แต่ที่ kQ = 16 แพ้เล็กน้อย (9.31 เทียบ 8.19)
  - OR ไม่เปลี่ยน ตามที่คาดไว้ และยังแพ้ SE-COLLAB ที่ kQ ≥ 4 (1.3–1.7×) ซึ่งไม่ต่างจากก่อน pruning
- **ขนาด proof:**
  - OR: AMTP เล็กกว่า SE-COLLAB ทุก kQ (สูงสุด 2×) เพราะผลลัพธ์เยอะ
  - shape อื่น: proof เล็กลง 3–13× จากเดิม แต่ยังใหญ่กว่า SE-COLLAB
- AND_of_OR ที่ kQ = 2 canonical ออกมาเป็น OR (rQ ≈ 47) จึงไม่ได้ลด

## ข้อจำกัด (ต้องบอกใน paper ถ้าใช้)

1. **ได้ผลดีเพราะลักษณะของ query ชุดนี้:** query สร้างจากไฟล์ต้นทาง keyword ที่หายากที่สุดจึงมีประมาณ 1 ไฟล์ ถ้าทุก keyword มีไฟล์เยอะ ต้นทุนจะโตตาม |L_min| ซึ่งเป็นขอบล่างตามธรรมชาติของการพิสูจน์ AND
2. **OR ไม่ได้ลด:** AND-of-OR และ OR-of-AND ลดได้บางส่วน แต่ยังไม่ได้วัด (Search 2.1)
3. **ตัวเลขเป็นของ Mac ไม่ใช่ cloud:** baseline (SE-COLLAB, Chen, Du) วัดบน cloud จึงยังเทียบตรงๆ ไม่ได้ ต้องรัน baseline บนเครื่องเดียวกัน หรือรัน AMTP `--and-prune` บน cloud
4. **server ใช้ memory เพิ่ม:** เก็บ R^post tree ของทุก keyword ใน snapshot เมื่อเปิด flag (Engine เก็บ tree ชุดนี้อยู่แล้ว ส่วนที่เพิ่มคือสำเนาใน snapshot) ยังไม่ได้วัดว่าเพิ่มเท่าไร
5. **slot multiproof อาจใหญ่ขึ้นเล็กน้อย:** ใน partition ที่เปิด slot น้อยลง ต้องใช้ sibling hash มากขึ้น ใน test เล็กเจอกรณี +80 B แต่ในผลวัดจริงไม่มี query ไหนที่ proof ใหญ่ขึ้น
6. **ต้องแก้ paper และให้อาจารย์อนุมัติ:** ส่วน ASPA (eq. 52–57) และ proof ของ theorem ต้องเพิ่มรูปแบบ focus, ข้ออ้างเรื่องลำดับ PID ที่ Validator รับประกัน และกฎ focus

## ผลอยู่ที่ไหน

`baselines/results/runs/mac_and_prune/`
- `search1/{base,prune,secollab,chen,du}/` ผล Search 1.1 (D1, N = 100k)
- `xsearch/{base,prune,secollab}/` ผล Search 2.1 cross-domain (4 × 25k)

manifest ทุกไฟล์บันทึก `git_commit: 433c781` และ `git_dirty: true` เพราะรันจาก working tree ที่ยังไม่ได้ commit โค้ดที่ใช้รันคือโค้ดใน commit ของรายงานนี้ ส่วน `amtp_and_prune` บอกว่ารอบไหนเปิด flag

## วิธีรันซ้ำ

```
cd amtp_code
../.venv/bin/python -m pytest -q                                   # 438 passed (flag ปิด)
AMTP_AND_PRUNE=1 ../.venv/bin/python -m pytest -q                  # 437 passed, 1 skipped (flag เปิด)
../.venv/bin/python -m bench.experiments search1 --s-domains D1 --fpd 100000 --reps 10 --warmup 2 --out <dir>/base
../.venv/bin/python -m bench.experiments search1 --s-domains D1 --fpd 100000 --reps 10 --warmup 2 --and-prune --out <dir>/prune
../.venv/bin/python -m bench.experiments xsearch --fix 25000 --reps 5 --warmup 1 [--and-prune] --out <dir>/...
cd ../baselines
../.venv/bin/python se_collab_sim.py search1 --s-domains D1 --fpd 100000 --reps 10 --warmup 2 --proof-mode paths --out <dir>/secollab
../.venv/bin/python chen_et_al_sim.py search1 --s-domains D1 --fpd 100000 --reps 10 --warmup 2 --scope full --edb memory --out <dir>/chen
../.venv/bin/python du_et_al_sim.py search1 --s-domains D1 --fpd 100000 --reps 10 --warmup 2 --out <dir>/du
../.venv/bin/python se_collab_sim.py xsearch --fix 25000 --reps 5 --warmup 1 --proof-mode paths --out <dir>/x_secollab
```

## สถานะ

- โค้ดและ test เสร็จแล้ว ค่าเริ่มต้นปิด ผลเดิมและงานบน cloud ไม่กระทบ
- smoke test บน Mac เสร็จแล้ว: Search 1.1 (5 scheme) และ Search 2.1 cross-domain (AMTP กับ SE-COLLAB)
- ยังไม่ได้วัดบน cloud และยังไม่ได้วัด Search 1.2 (ตาม N), Search 2.2 (ตามจำนวน domain), ex2 และ ex5
- ยังไม่ได้แก้ paper รอเจ้าของงานและอาจารย์ตัดสินใจ

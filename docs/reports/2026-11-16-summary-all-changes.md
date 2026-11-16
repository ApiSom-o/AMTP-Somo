# สรุปรวม: แก้อะไรไปบ้าง ตัดสินใจอะไรแล้ว และต้องแก้ส่วนไหนของ paper

วันที่ 16 พ.ย. 2026 · branch `docs/summary-partition-first`

เอกสารนี้เขียนให้คนที่จะเขียน paper (เจ้าของงานและเพื่อน) อ่านไฟล์เดียวแล้วรู้ว่าโค้ดตอนนี้ต่างจาก paper ตรงไหน ตัวเลขชุดไหนใช้ได้ และอะไรยังไม่เสร็จ รายละเอียดของแต่ละเรื่องอยู่ในรายงานที่อ้างไว้ใน `docs/reports/`

## 0. ใน PR นี้มีอะไร

1. **เปลี่ยนการตัดสินใจเรื่องตัวเลข search อย่างเดียว:** ใช้แบบ **partition ก่อน** แทนแบบ fast (หัวข้อ 3)
   - `amtp_code/bench_split/plot_search.py`: เส้น AMTP ใช้คอลัมน์ `server_search_pf_fetch` ไม่มีเส้น fast แล้ว
2. **ผล ex4 รอบ prune เครื่อง 4 (θ = 256):** `baselines/results/runs/cloud/prune_w4/`
3. **เอกสาร:** รายงานนี้ และแก้ `docs/HANDOFF.md` ให้ตรงกับการตัดสินใจใหม่

---

## 1. สรุปสั้นที่สุด

| | สถานะ |
|---|---|
| **สมการที่ต้องแก้ใน paper** | ส่วน ASPA (eq. 52–57) และ proof ของ theorem เพราะใช้ AND pruning, part-results และ greedy ในรอบ prune |
| **สมการที่ไม่เปลี่ยน** | γ (eq. 17), merge (eq. 34), การ update, Validator, การนับขนาด |
| **ข้อความที่ต้องแก้ (ไม่ใช่สมการ)** | กติกาการวางไฟล์ (fill), ex3 นับ Validator, เครื่อง AWS, 15 รอบ, dataset 4 × 125k, นิยาม "search อย่างเดียว" |
| **ตัวเลขหลักของ paper** | รอบ prune (`767289c`) สำหรับ query · รอบ fill (`869cf73`) สำหรับ ex3 · ex4 รอบ prune · search อย่างเดียวจากรอบ split (กำลังรัน) |
| **ต้องให้อาจารย์อนุมัติ** | การแก้ ASPA (flag ของรอบ prune) |

---

## 2. ทุกอย่างที่แก้ แยกตามว่ากระทบ paper อย่างไร

### 2.1 เปลี่ยนสมการ / โปรโตคอลใน paper (ต้องแก้ paper และให้อาจารย์อนุมัติ)

ทั้ง 3 flag ค่าเริ่มต้นปิดในโค้ด ถ้าปิดทั้งหมด ระบบทำงานเหมือน ASPA ใน paper ทุก byte แต่**ตัวเลข query ของรอบ prune เปิดทั้ง 3 ตัว** ถ้าใช้ตัวเลขชุดนี้ ต้องแก้ paper

| เรื่อง | ส่วนของ paper ที่ต้องแก้ | เปลี่ยนอะไร | ความปลอดภัย | รายงาน |
|---|---|---|---|---|
| **AND pruning** (`--and-prune`) | ASPA eq. 52–57, proof ของ theorem | server ส่ง posting list เต็มเฉพาะ keyword ที่มี partition น้อยที่สุด keyword อื่นส่งแบบ `focus`: component ใน partition ของ focus set F (`segs`) และ γ leaf สองตัวที่ติดกันคร่อม PID ที่ keyword นั้นไม่มี (`nb`) เปิดด้วย multiproof ใน R^post แล้ว ρ = H(h ‖ \|Sel\| ‖ R^post) ต้องอยู่ใน IMT เหมือนเดิม · ต้องเพิ่ม**กฎ focus** (AND = intersection, OR = union, OR ที่มีลูกไม่รู้ขอบเขต = ไม่มีขอบเขต) และข้ออ้างว่า Validator รับประกันลำดับ PID | ผู้ใช้คำนวณ F เอง ตรวจว่าครอบคลุม F ครบ Eval เป็น monotone จึงได้ M̂_Q = M_Q · OR ไม่ถูก prune | `2026-11-16-and-pruning.md` |
| **ตรวจ part เฉพาะไฟล์ผลลัพธ์** (`--part-results`) | ส่วนที่นิยาม proof ของ partition (check part) ใน ASPA | เปิด slot และ domain leaf เฉพาะ partition ของไฟล์ผลลัพธ์ (M_Q) แทนทุกไฟล์ที่ posting แตะ (M_cov) · partition อื่นส่งแค่ (PID, v) เป็น list ธรรมดา | (cid, PID, ℓ) ถูกผูกด้วย γ → ρ → IMT → anchor อยู่แล้ว · v ผิด γ จะไม่ตรง (ประโยชน์ของการมี v ใน γ) · partition ของผลลัพธ์ต้องครบพอดี | `2026-11-16-and-pruning.md` (หัวข้อ part-results) |
| **greedy planner** (`--and-greedy`) | กฎ focus (ขยายจากข้อแรก) | server ส่ง keyword แบบเต็มได้มากกว่า 1 ตัวถ้าทำให้ F หดจนคุ้ม (F = intersection ของทุกตัวที่ส่งเต็ม) | ผู้ใช้ใช้กฎ focus เดิม ซึ่งรองรับหลายตัวอยู่แล้ว | `2026-11-16-and-pruning.md` (หัวข้อ and-greedy) |

**ต้นทุนที่ต้องเขียน:** snapshot ใช้หน่วยความจำ +23–24% (เก็บ R^post tree และ H(Enc(L))) · server ของ query ที่ไม่มี AND ช้าลง 4–13% (วัดบน Mac ยืนยันแล้ว) · update ใน ex5 ช้าลง ~20%

### 2.2 เปลี่ยนข้อความใน paper แต่ไม่เปลี่ยนสมการ

| เรื่อง | ต้องเขียนอะไร | รายงาน |
|---|---|---|
| **การวางไฟล์ใหม่ = fill** (วิธีหลัก) | paper ไม่ได้กำหนดกติกาการวาง: เพิ่มประโยคว่าไฟล์ใหม่ไปที่ partition ที่มีไฟล์มากที่สุดแต่ยังน้อยกว่า θ_max ถ้าเต็มให้ split แก้ตอนจบ epoch · Static-MT ใช้กติกาเดียวกัน · split / merge (eq. 34) ไม่เปลี่ยน | `2026-11-15-fill-placement.md`, `2026-11-16-fill-default.md` |
| **ex3 นับเวลา Validator** | paper เขียนว่าไม่นับ แต่เราเลือกนับ: update = request + CS + Validator + anchor | HANDOFF §3 |
| **ex4 เทียบกับ Global-MT(v)** | Global-MT ที่ยุติธรรมต้องมี v เหมือน AMTP (Global-MT แบบไม่มี v ใช้เทียบไม่ได้) | `2026-11-15-global-mt-v.md` |
| **การตั้งค่าการทดลอง** | เครื่อง AWS r7i.4xlarge (ไม่ใช่ Mac) · 15 รอบหลัง warm-up 3 รอบ (ไม่ใช่ 30) · dataset arXiv 4 domain × 125k · KB = 1000 B · ค่าต่อจุด = median ข้าม query | HANDOFF §3 |
| **นิยาม "search อย่างเดียว"** | ดูหัวข้อ 3 | `2026-11-16-search-timer.md` |
| **ขนาดไฟล์ที่ส่งกลับ** (ถ้าเทียบ response รวมไฟล์) | ~212 B ต่อไฟล์เป็นต้นทุน access control (C_Kd + aad) ที่ baseline ไม่มี · C_Kd เก็บเป็น hex (ตัดสินใจไม่แก้) · กราฟที่มีใช้ proof_bytes จึงไม่กระทบ | HANDOFF §8 ข้อ 3 |

### 2.3 แก้โค้ดอย่างเดียว ไม่กระทบ paper (ผลลัพธ์และ hash เหมือนเดิมทุก bit หรือแค่เร็วขึ้น)

| เรื่อง | ผล | PR / รายงาน |
|---|---|---|
| Validator ตรวจ next pointer ของ IMT จาก O(n·m) เป็น O((n+m) log n) | update เร็วขึ้นมาก | #11 · `2026-11-15-validator-imt-speed.md` |
| ตรวจ Merkle เร็วขึ้น + แก้ลูปซ้อนที่เหลือใน Validator | query เร็วขึ้น 1.2–1.25× hash เท่าเดิม | #16 · `2026-11-15-verify-speed.md` |
| commit Merkle tree แบบรวมครั้งเดียว + ค้น Search Tree ครั้งเดียวต่อ keyword | hash ฝั่ง server ลด 41–71% ผลเหมือนเดิมทุก bit | `2026-11-15-engine-batched-merkle.md` |
| γ แบบเร็วฝั่งผู้ใช้ (`gamma_wire`) และเก็บ H(Enc(L)) ใน snapshot (`post_inner`) | byte ชุดเดียวกัน จำนวน hash เท่าเดิม | `2026-11-16-and-pruning.md` |
| `bench_split/` วัด search อย่างเดียว | ไม่แก้ไฟล์เดิม ใช้แค่วัด | #25, #27 · `2026-11-16-search-timer.md` |

**ข้อควรระวัง:** ผลเวลาบน cloud ก่อนการแก้เหล่านี้เทียบกับรอบใหม่ไม่ได้ (HANDOFF §6)

### 2.4 พิจารณาแล้วไม่ทำ

| เรื่อง | เหตุผล |
|---|---|
| ดัชนีค้นหาเพิ่ม (แบบ fast, `AMTP_SEARCH_INDEX`) | server จริงไม่มีโครงสร้างนี้ ถ้ารายงานเท่ากับวัดระบบที่ไม่มีอยู่จริง (หัวข้อ 3) |
| cache ฝั่งผู้ใช้ | เจ้าของงานตัดสินใจไม่ทำ (16 พ.ย.) |
| จัดไฟล์ตาม keyword | กลัวผิด design |
| แก้ C_Kd จาก hex เป็น binary | cid ทุกตัวจะเปลี่ยน ได้คืนแค่ 3–5% ของ response และไม่เปลี่ยนว่าใครชนะ |
| แก้ overhead 4–13% ของ flag | รายงานใน paper แทน |
| multiprocessing, accumulator | ขัดกติกาเดิม / แพง |

---

## 3. การตัดสินใจล่าสุด: ตัวเลข search อย่างเดียวใช้แบบ partition ก่อน

**ที่มา:** อาจารย์ให้แยกการทดลองตามขั้น ตัวจับเวลา `lookup` เดิมใน `build_response` รวมงานเตรียม proof ไว้ด้วย จึงวัดใหม่ใน `amtp_code/bench_split/` ซึ่งวัดไว้ 3 แบบในรอบเดียวกัน

| แบบ | ใช้อะไร | ใช้ใน paper |
|---|---|---|
| เต็ม | Cuckoo filter + B+ tree + posting list ทั้งหมด + `boolean.evaluate` | ไม่ (ไว้เทียบ) |
| **partition ก่อน** | เหมือนข้างบน + `boolean.focus` หา partition ที่มีโอกาส match แล้วสร้างเซตไฟล์เฉพาะใน partition นั้น | **ใช่** |
| fast | ดัชนีค้นหาที่สร้างเพิ่มต่อ snapshot (~89 MB ต่อ domain) | **ไม่** |

**ทำไมเลือก partition ก่อน (เจ้าของงานตัดสินใจ 16 พ.ย.):**
- ใช้แค่โครงสร้างที่ AMTP มีอยู่แล้ว และ `boolean.focus` เป็นกฎเดียวกับที่ server จริงใช้ตอนทำ AND pruning ไม่มีหน่วยความจำหรือต้นทุน update เพิ่ม
- แบบ fast ใช้ตารางที่ server จริงไม่มี ถ้ารายงาน ผู้ตรวจจะมองว่าวัดระบบที่ไม่มีอยู่จริง
- ไม่ต้องใส่ `AMTP_SEARCH_INDEX` ใน server จริง และไม่ต้องรันใหม่ เพราะรอบที่รันอยู่เก็บคอลัมน์ `pf_*` แล้ว
- แผนเดิมข้อ 2–3 (เสนอ fast ให้อาจารย์ แล้วใส่ดัชนีใน server จริง) ยกเลิก

**ข้อที่ต้องบอกตรงๆ:** โค้ดแบบ partition ก่อนไม่ใช่โค้ดชุดเดียวกับ `build_response` บรรทัดต่อบรรทัด เพราะใน `build_response` งาน search กับงานเตรียม proof ปนกัน แต่ทุกขั้นเป็นงานที่ server จริงทำด้วยโครงสร้างเดิม และจุดตรวจยืนยันว่าทุก query ได้ไฟล์ตรงกับ server จริง

**นิยามที่ต้องเขียนใน paper:**

| scheme | เวลา search อย่างเดียว | หมายเหตุ |
|---|---|---|
| AMTP | `server_search_pf_fetch` | lookup + focus + เซตไฟล์ใน F + AND/OR + ดึง ciphertext · ไม่รวมงาน proof |
| SE-COLLAB | `search_core` | รวม result fetch |
| Chen | `server_total` | ไม่มี fetch · วัดหลัง warm-up ซึ่ง chain ถูกยุบแล้ว (กรณีที่ดีที่สุดของ Chen) |
| Du | `server_total` | cloud ที่ช้าที่สุด |

- baseline ไม่ปรับและไม่รันใหม่ (มาจากรอบก่อน เครื่องรุ่นเดียวกัน ข้อมูลและ query ชุดเดียวกัน)
- ต้องวางกราฟ search อย่างเดียวคู่กับกราฟ server รวม (search + proof) และ end-to-end เสมอ

**ที่คาดไว้ (ยังไม่ใช่ผล, Mac × 2 ที่ kQ = 20):** AMTP ~0.19 ms · SE-COLLAB 0.43 · Chen 0.12 · Du 1.36 → น่าจะชนะ SE-COLLAB และ Du แต่น่าจะแพ้ Chen ที่ kQ สูง

---

## 4. ผลหลักตอนนี้ (cloud)

### Query (รอบ prune, `767289c`, fill + 3 flag) · `runs/cloud/prune_w1/`, กราฟ `new_purn/`

search1 N = 100k, AND, kQ = 20 (ms):

| | AMTP prune | SE-COLLAB | Chen | Du |
|---|---|---|---|---|
| server | 0.96 | 4.98 | 0.12 | 1.36 |
| ตรวจ | 1.06 | 0.93 | 10.4 | 0.11 |
| end-to-end | 2.37 | 9.39 | 11.54 | **1.71** |
| proof | 20 KB | 561 B | 640 B | 3.5 KB |

- **ชนะ:** end-to-end ชนะ SE-COLLAB ทุก kQ และชนะ Chen ที่ kQ ≥ 2 · AND kQ 16 cross-domain end-to-end 85.7 → 6.5 ms (SE-COLLAB 10.5) · ex5 query 1.3 เทียบ 8.9 ms · xdomains ชนะถึง 16 domain · tamper จับได้ครบ 360/360 ทุกแบบ ไม่ฟ้องผิด 0/60
- **แพ้ (ต้องเขียน):** end-to-end แพ้ Du ทุก kQ (Du นับเฉพาะ cloud ที่ช้าที่สุด ถ้านับรวมทุก cloud Du ใช้มากกว่า ~5×) · OR แพ้ SE-COLLAB ที่ kQ ≥ 4 · ตรวจ keyword เดียวแพ้ที่ rQ ≥ 1,000 · xdomains แพ้ที่ 32 domain · proof ใหญ่กว่า baseline · update แพ้ Chen
- **ต้นทุนรวมทุกฝ่าย** (สร้าง query + server + ตรวจ + ถอดรหัส): ชนะทั้ง 3 baseline ที่ kQ ≥ 2 แพ้ Chen ที่ kQ = 1 (0.40 เทียบ 0.36 ms)

### Update

- **ex3** (รอบ fill, `869cf73`): b = 1,000 insert 14.1 s (เดิม 76.5 s) ยังช้ากว่า Chen
- **ex4 รอบ prune** (median ต่อ batch):

| θ | AMTP update | Static-MT update | AMTP เร็วกว่า | query server / ตรวจ (ms) AMTP | Static-MT |
|---|---|---|---|---|---|
| 64 | 1.05 s | 13.5 s | 12.9× | 5.3 / 12.3 | 5.0 / 10.2 |
| 128 | 1.20 s | 13.6 s | 11.3× | 5.1 / 11.4 | 4.8 / 9.6 |
| 256 | 1.48 s | 14.4 s | 9.7× | 4.8 / 9.6 | 4.5 / 8.1 |

θ = 256 มาจาก `prune_w4` (PR นี้) ตรวจแล้ว: 3,348 แถว, commit `767289c`, `git_dirty: false` · AMTP ยังช้ากว่า Static-MT ตอน query เล็กน้อยทุก θ ต้องเขียนใน paper

- **Global-MT(v)** (รอบ fill): AMTP update เร็วกว่า 25.7× แต่ query ช้ากว่า ~1.7× → คุ้มจนถึง ~1,260 query ต่อ epoch · รอบ prune (เครื่อง 5) ยังรัน

---

## 5. ยังไม่เสร็จ

| งาน | สถานะ |
|---|---|
| รอบวัด search อย่างเดียว (search1, xsearch, xdomains, exp5) | กำลังรันบน cloud ที่ main `00f9d42` คาดว่าเสร็จ ~00:00 · ผลจะอยู่ที่ `runs/cloud/split_w1/` แล้วจะ plot ลง `baselines/results/search_split/` |
| ex4 Global-MT(v) รอบ prune (เครื่อง 5) | คาดว่าเสร็จ ~03:00 · หลังจากนั้นทำกราฟ ex4 ของรอบ prune |
| แก้ paper | ยังไม่ได้เริ่ม · เจ้าของงานเป็นคนเขียน · ส่วน ASPA ต้องให้อาจารย์อนุมัติ |
| demo v2 | ยังไม่ได้ทดสอบเต็ม |

## สถานะของ PR นี้

- แก้แค่ `bench_split/plot_search.py` (เลือกคอลัมน์ที่ plot) ไม่มีโค้ดของ AMTP, benchmark หรือ baseline เปลี่ยน
- ทดลอง plot กับข้อมูล smoke test แล้ววาดได้ปกติ (68 จุด)

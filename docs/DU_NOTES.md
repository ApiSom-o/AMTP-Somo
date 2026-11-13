# Du et al. [7]: paper เทียบกับโค้ดของเรา

ตรวจ `baselines/du_et_al_sim.py` เทียบกับ paper ต้นฉบับ
J. Du, J. Zhou, Y. Lin, W. Zhang, J. Wei, "Secure and Verifiable Keyword Search in Multiple Clouds",
IEEE Systems Journal, vol. 16, no. 2, pp. 2660–2671, 2022.

**สรุป:** โค้ดทำตาม paper ครบทั้ง 3 module (file distribution, secure search, integrity verification) และ
Algorithm 1–4 จุดที่ paper เขียนผิดหรือไม่ได้ระบุติดป้าย `[FIX]` / `[ASSUMPTION]` ไว้ในหัวไฟล์ (ข้อ 1–9)
`demo` จับ cloud ที่โกงได้ทุกกรณีที่ paper บอกว่าจับได้

## 1. ส่วนที่ตรงกับ paper

| Module / Algorithm | ใน paper | ในโค้ด |
|---|---|---|
| File segmentation (IV-A-2) | แบ่งไฟล์เป็น t slice เท่ากัน, pad slice สุดท้าย | ตรง; ใช้เนื้อไฟล์ `.txt` จริงของ dataset |
| Iterative encryption (Eq. 1–2) | (m − 1) รอบตาม secret vector V; t ตัวแรกไม่ซ้ำ, ตัวที่ t+1 = ตัวที่ t ("ผูกปม" ด้วย k_f) | ตรง (`gen_secret_vector`) |
| ความยาว V (Eq. 4) | `m = ⌈1 + t + (T − 1)·log_t t!⌉`, T = 10 | ตรง (`secret_vector_length`) |
| Redundant slices (IV-A-4) | Reed-Solomon (n, t): กู้ได้จาก slice ใดก็ได้ t ชิ้น | ตรง (systematic Cauchy RS ใน GF(256)); demo กู้ไฟล์ได้ถูกทุกไฟล์ |
| Bloom filter (IV-B-2) | r master key, random insertion `c·|W_i|·r` บิต (c = 0.1, r = 7) | ตรง |
| Alg. 1 BF tree | แบ่งครึ่ง top-down, `|BF_l| − |BF_r| ≤ 1`, node = OR ของลูก | ตรง |
| Remapping (IV-B-4) | `u.e` สุ่มต่อ node ต่อ cloud, `u.E = Enc(k_f, u.BF_org)` | ตรง |
| Trapdoor (IV-B-6) | `Q` = ตำแหน่ง `h(w, v_i) % d` ของทุก keyword ใน W_q | ตรง |
| Alg. 2 SecureSearch | DFS, ตัดกิ่งที่ไม่ match | ตรง (+ แก้ `T.pr`) |
| Filtering (IV-B-7) | DU ถอด `u.E` แล้วทิ้งผลที่ `BF_org[x] = 0` | ตรง |
| Alg. 3 File ID encoding | `ID' = (HMAC(k_f‖j, fid) ‖ fid) ⊕ HMAC(k_f‖j, C_ij ‖ BF_i)` | ตรง |
| Alg. 4 + เทียบข้าม cloud | ถอด ID; ผลขาด/ว่างจับได้จากการเทียบกับ cloud อื่น (มี cloud ซื่อสัตย์อย่างน้อย 1 ตัว) | ตรง; demo จับได้ทั้ง empty / drop / tamper / forge / irrelevant |

## 2. ส่วนที่ paper ผิดหรือไม่ได้ระบุ (ข้อ 1–9 ในหัวไฟล์)

| เรื่อง | ปัญหาใน paper | โค้ดทำอย่างไร |
|---|---|---|
| Eq. (1) | เงื่อนไข hash / k_f พิมพ์สลับกับตัวอย่างใน Fig. 2(a) | `[FIX]` ทำตาม Fig. 2(a): `V[k] ≠ V[k+1]` → คีย์ = `H(A[V[k+1]])`, เท่ากัน → `k_f` |
| Alg. 2 บรรทัด 3–4 | เรียก `T.pl` ซ้ำสองครั้ง | `[FIX]` `T.pl` กับ `T.pr` |
| Alg. 4 บรรทัด 10, 15 | จับเป็น malicious เมื่อ `HM' = HM` และ `return V` | `[FIX]` `≠` และ `return L` |
| ความยาว R | HMAC 32 byte แต่ `ID = HMAC ‖ fid` ยาวกว่า XOR ตรง ๆ ไม่ได้ | `[ASSUMPTION]` ขยาย R เป็น `R ‖ H(R)` แล้วตัด |
| Cipher | ไม่ระบุ | AES-CTR (ความยาว ciphertext = plaintext จำเป็นสำหรับ RS) |
| PRF ของ remapping | `h(u.e, x)` ไม่ระบุ | AES_{u.e}(x) (เร็วพอสำหรับ remap ล้านบิต) |
| ความยาว d | สูตร `−r·c·n'/ln(1 − p^{1/r})` ใน IV-B-5 (คูณ c = 0.1 จะทำให้ filter สั้นลง ไม่น่าใช่) | `[ASSUMPTION]` `d = r·(1+c)·z_max / −ln(1 − p^{1/r})` (นับ random insertion เป็น keyword เพิ่ม), p = 10⁻⁶ |
| BF tree | มีแบบ basic (Fig. 3a) และ optimized (Fig. 3b) | ใช้แบบ basic (ทุก node ยาว d) — optimized ลดแค่ storage ไม่เปลี่ยนการค้น |
| Irrelevant result | ให้ "matching ตอน filtering" แต่ cloud ซื่อสัตย์ก็มี remapping collision ได้ | กรองทิ้งแทนการกล่าวหา cloud (PR #4) |
| Domain | Du เป็น multi-cloud ไม่มีแนวคิด domain | เอกสาร N ไฟล์ของทุก domain รวมเป็นชุดเดียว แล้วกระจาย slice ไป n_c cloud (ค่าเริ่มต้น 5, t = 3) |

## 3. เรื่องที่สำคัญกับ paper AMTP

### 3.1 Paper ของ Du ทดลองแค่ keyword เดียว
การทดลองใน Sec. VI ค้น keyword เดียว (`host`) และบทสรุปเขียนว่า multi-keyword เป็นงานอนาคต แต่ trapdoor ใน
IV-B-6 นิยามจากชุด keyword W_q อยู่แล้ว การค้นแบบ AND จึงทำได้โดยตรง (node ต้องมีบิตครบทุกตำแหน่งใน Q)
ใน paper ของเราควรเขียนว่า "Du รองรับ AND ผ่าน Bloom-filter trapdoor ของ W_q" และต้นทุน query generation
ใน Table IV ควรเป็น `r·k_Q·T_H` (paper เขียน `r·T_H` สำหรับ keyword เดียว) คอลัมน์ `hash_qgen` ใน CSV = r·k_Q

### 3.2 Du ช้าเพราะ design ของ paper เอง
Bloom filter tree แบบ basic ใช้ความยาว d เดียวกันทุก node (d ถูกเลือกให้พอดีกับ leaf ที่มี keyword ≤ 10 คำ)
node ด้านบนที่รวม keyword ของเอกสารจำนวนมากจึงเกือบเต็มไปด้วย 1 และตัดกิ่งได้น้อย จำนวน node ที่เดินผ่านจึงโตตาม N:

| N | node ที่เดินผ่าน (รวม 5 cloud) | server_total (cloud ที่ช้าสุด) | server_sum (งานรวม) | verify_total | du_decrypt | end_to_end |
|---|---|---|---|---|---|---|
| 10,000 | 8,133 | 12.6 | 61.8 | 0.10 | 0.13 | 12.8 |
| 200,000 | 160,909 | 258.1 | 1,271 | 0.13 | 0.16 | 258.3 |

(dataset-v3, k_Q = 4, AND, median 30 รอบ, ms, เครื่องทดสอบ) — เวลาเกือบทั้งหมดอยู่ที่การค้นฝั่ง cloud
(re-run on the same machine as AMTP and SE-COLLAB; `end_to_end` excludes `du_decrypt`, see 3.4)

### 3.3 ความครบของผลลัพธ์อาศัย "มี cloud ซื่อสัตย์อย่างน้อย 1 ตัว"
Du ตรวจผลขาดได้โดยเทียบผลข้าม cloud เท่านั้น ถ้าทุก cloud ร่วมกันตัดไฟล์เดียวกันทิ้ง DU จะตรวจไม่เจอ
(demo กรณี `ALL collude drop`: ได้ 206 จาก 207 ไฟล์ และไม่มี cloud ถูกจับ) ต่างจาก AMTP ที่ตรวจความครบได้จาก
Domain Root บน blockchain โดยไม่ต้องพึ่ง server ที่ซื่อสัตย์ ใช้เป็นข้อโต้แย้งใน paper ได้เหมือนจุดอ่อนของ SE-COLLAB

### 3.4 End-to-end definition (resolved)
Du's `end_to_end_ms` used to include `du_decrypt` (RS decode + iterative decryption of the returned files), unlike
the other schemes. It now follows the shared definition in `baselines/README.md`: query_gen + server_total +
verify_total, i.e. until the data user holds the verified result set. `du_decrypt_ms` is still reported as its own
column. Results in `baselines/results/du/` were re-run with this definition.

## 4. ต่างจากการทดลองใน paper ต้นฉบับ
- Paper ใช้ RFC dataset 8,502 ไฟล์ (เฉลี่ย 52 KB, keyword top 5% ต่อไฟล์) บน Python, i7-9750H + Xeon Silver 4110
  และจำลอง cloud ด้วย network port
- ของเราใช้ dataset-v3 สูงสุด 200,000 ไฟล์ (title + abstract, keyword RAKE ≤ 10 คำต่อไฟล์) และจำลอง cloud ใน process เดียว
  เวลา `server_total` คือ cloud ที่ช้าที่สุด (cloud ทำงานขนาน) ไม่รวมเวลาเครือข่าย
- ตัวเลขยังไม่ใช่ผลสุดท้าย ต้องรันซ้ำบนเครื่องที่จะรายงานใน paper

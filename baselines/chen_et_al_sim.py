"""
chen_et_al_sim.py
============================================================================
Simulation ของ baseline Chen et al. [40]
  L. Chen, Y. Wu, H. Zhang, J. Weng, Z. Liu,
  "Verifiable Multi-User Dynamic Searchable Symmetric Encryption With Forward
   and Backward Privacy Feasible for Cloud Storage",
  IEEE Transactions on Information Forensics and Security, vol. 21, 2026.

โค้ดนี้จำลองตามที่ paper อธิบายไว้ใน Section II และ IV:
  A. Bitmap index + homomorphic addition   (Section II-A, II-F)
  B. Setup / Share / Update                 (Algorithm 1, 2, 3 — DO)
  C. Search                                 (Algorithm 4 — DU + CS)
  D. Verify                                 (Algorithm 5 — DU)
คอมเมนต์ [Alg.4 L20] = Algorithm 4 บรรทัดที่ 20 ใน paper (เปิด paper ดูคู่กันได้)

สิ่งที่วัดเพื่อเทียบกับ AMTP ตาม Table IV ของ AMTP:
  - Query Generation : O(n_w) * T_PRF                     (DU สร้าง token)
  - Search           : O(n_w * n_u) * (T_H + T_A + T_X)   (CS เดิน chain + บวก ciphertext)
  - Verification     : O(r_C) * (T_PRF + T_X)             (DU คำนวณ F1(id) ทุกผลลัพธ์)
  - Update           : O(N_u * m) * (T_PRF + T_H + T_Enc) (สร้าง entry ให้ทุกผู้ใช้ที่มีสิทธิ์)
  ตัวนับ OpCounter นับจำนวน T_PRF / T_H / T_A / T_X / T_Enc จริงทุกครั้ง ไว้เช็กกับสูตรข้างบน

จุดที่ paper เขียนไม่ชัด/มีบั๊ก และโค้ดนี้ตัดสินใจเอง (ดูคอมเมนต์ [ASSUMPTION]/[FIX]):
  1. [FIX] Alg.2 บรรทัด 2 สุ่ม K_u ทุกครั้งที่ Share -> สุ่มเฉพาะครั้งแรกของผู้ใช้
     (ถ้าสุ่มใหม่ทุกครั้ง ข้อมูลที่แชร์ไปก่อนหน้าจะค้นไม่เจอ)
  2. [FIX] CntDiffs เก็บแค่ Enc(w, c) แต่ Alg.4 บรรทัด 4 ต้องใช้ ST_c -> เข้ารหัส (w, c, ST_c)
  3. [FIX] Alg.5 return accept หลังเช็ค keyword แรก -> เช็คครบทุก keyword ก่อน accept
     และ reject ถ้า CS ส่ง (Sum_e, proof) มาไม่ครบทุก keyword ใน q (selftest t_reject_dropped_keyword)
  4. [ASSUMPTION] F1 ไม่ระบุคีย์ -> ใช้ K'_u (DU คำนวณ proof ได้ แต่ CS ปลอมไม่ได้)
  5. [ASSUMPTION] ไม่ระบุ primitive -> HMAC-SHA256/512 (PRF), SHA-256 (H1, H2),
     SHAKE-256 (H3 ต้องได้ผลยาว gamma บิต), AES-256-GCM (SE), lambda = 128 บิต
  6. [ASSUMPTION] gamma (ความยาว bitmap) = N (paper: gamma >= N_max) + ที่เผื่อเอกสารใหม่ใน exp3
  7. [ASSUMPTION] Update รองรับทั้งเพิ่ม (+2^id) และลบ (-2^id mod n) ตาม Fig. 1(b)(c)
  8. [ASSUMPTION] share() รับหลายเอกสารในครั้งเดียวได้ (รวม bitmap ของ keyword เดียวกันเป็น entry เดียว)
     ใช้ตอนสร้าง index เริ่มต้นเท่านั้น ส่วน exp3 อัปเดตทีละเอกสารตาม paper (--update-mode per-doc)
  9. [ASSUMPTION] --scope queried: dataset arXiv มี keyword ไม่ซ้ำมาก (N = 200,000 -> ~1.29 ล้านคำ)
     index เต็มของ Chen = keyword x gamma บิต (~32 GB) จึงสร้าง entry เฉพาะคำที่ทดลอง
     (bitmap ของคำนั้นครบทุกเอกสาร เวลาค้น/verify เท่าแบบเต็ม) ขนาด storage ยังรายงานของ index เต็ม

Workload: dataset กลางของ AMTP (dataset-v4, arXiv 4 domain x 125,000 ไฟล์, ไฟล์ใน datasets/arxiv/data_v4/) ผ่าน amtp_dataset.py
  - N เอกสาร = N/4 ไฟล์แรกของแต่ละ domain (ไม่สุ่ม) -> ทุก scheme ได้เอกสารชุดเดียวกัน
  - keyword ใช้ที่สกัดไว้ใน documents.csv ตรง ๆ, exp3 ใช้เอกสารจริงจาก insert_pool
  - exp1 ตรวจผลทุก query กับ ground truth จาก plaintext index (ต้องตรงเป๊ะ)

วิธีรัน (pip install cryptography, แตก dataset ด้วย datasets/arxiv/unpack.py ไว้ที่ <repo>/data/amtp_file_db_v4 หรือใส่ --data):
  python3 chen_et_al_sim.py demo                       # ทีละขั้น + จับ CS ที่โกง
  python3 chen_et_al_sim.py selftest                   # ทดสอบความถูกต้อง 12 ข้อ
  python3 chen_et_al_sim.py exp1                       # replay results/exp1_queries.json (default)
  python3 chen_et_al_sim.py exp2                  # replays results/exp2_layouts.json (N = 200k)
  python3 chen_et_al_sim.py exp3 --sizes 10000 50000 100000 200000 --batches 1 10 100 1000 --users 1
ผลทุก suite เขียนลง results/chen/chen_<suite>.csv (mean, median, std จาก --reps รอบ หลัง warm-up --warmup รอบ)
============================================================================
"""

# ----------------------------------------------------------------------------- imports
import argparse                                   # อ่าน argument จาก command line
import csv                                        # เขียนผลการทดลองเป็นไฟล์ CSV
import gc                                         # ปิด garbage collector ระหว่างจับเวลา
import hashlib                                    # SHA-256 / SHAKE-256
import hmac                                       # HMAC (ใช้ทำ PRF)
import json                                       # อ่าน/เขียนไฟล์ query
import os                                         # os.urandom สุ่มคีย์ + จัดการ path
import sqlite3                                    # EDB บนดิสก์ (เมื่อ N ใหญ่)
import statistics as st                           # mean / median / std
import sys                                        # sys.exit ใน selftest
import tempfile                                   # โฟลเดอร์ชั่วคราวสำหรับ SQLite
import time                                       # perf_counter จับเวลา
from collections import defaultdict               # dict ที่สร้างค่าเริ่มต้นให้อัตโนมัติ
from dataclasses import dataclass                 # โครงสร้างข้อมูลแบบสั้น

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # AES-GCM สำหรับ SE

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wire_sizes as W                            # noqa: E402  กติกานับขนาดเดียวกันทุก scheme


# ============================================================================
# 0) ตัวนับจำนวน operation  -> ใช้เช็กว่าจำนวน T_PRF / T_H / ... ตรงกับสูตรใน Table IV
# ============================================================================
class OpCounter:                                  # คลาสเก็บตัวนับ
    def __init__(self):                           # constructor
        self.reset()                              # เริ่มต้นที่ศูนย์ทั้งหมด

    def reset(self):                              # ล้างตัวนับก่อนวัดแต่ละ phase
        self.prf = 0                              # จำนวนครั้งที่เรียก PRF F / F1 (T_PRF)
        self.hash = 0                             # จำนวนครั้งที่เรียก H1 / H2 / H3 (T_H)
        self.add = 0                              # จำนวน homomorphic addition (T_A)
        self.xor = 0                              # จำนวน XOR (T_X)
        self.enc = 0                              # จำนวนการเข้ารหัส bitmap Enc(sk, bs) (T_Enc)
        self.visited = 0                          # จำนวน EDB entry ที่ CS เดินผ่าน (ความยาว chain รวม)

    def snapshot(self):                           # คืนค่าตัวนับปัจจุบันเป็น dict
        return dict(prf=self.prf, hash=self.hash, add=self.add, xor=self.xor,
                    enc=self.enc, visited=self.visited)


COUNT = OpCounter()                               # ตัวนับ global ใช้ทั้งไฟล์


# ============================================================================
# 1) Cryptographic primitives — PRF, hash, homomorphic addition, bitmap, SE
# ============================================================================

LAMBDA_BYTES = 16  # λ (security parameter) = 128 bit = 16 byte ใช้กับ state ST_c และคีย์ผู้ใช้
PROOF_BYTES = 32  # ขนาดของ vt / proof = 32 byte (เพราะ F1 ใช้ HMAC-SHA256 ซึ่งให้ผล 32 byte)


# ---------------------------------------------------------------------------
# ตัวช่วยเล็ก ๆ
# ---------------------------------------------------------------------------

def random_bytes(nbytes: int = LAMBDA_BYTES) -> bytes:
    """สุ่ม byte แบบปลอดภัย = สัญลักษณ์ {0,1}^λ ใน paper"""
    return os.urandom(nbytes)  # ขอเลขสุ่มจากระบบปฏิบัติการ ยาว nbytes byte


def _enc(*parts) -> bytes:
    """เอาหลาย ๆ ค่ามาต่อกันแบบไม่กำกวม (แทนเครื่องหมาย || ใน paper)

    ทำไมต้องมี: ถ้าต่อ "ab"+"c" กับ "a"+"bc" ตรง ๆ จะได้ "abc" เหมือนกัน
    เลยใส่ "ความยาว" นำหน้าแต่ละชิ้น จะได้ไม่ชนกัน
    """
    out = bytearray()  # กล่องว่างไว้ใส่ผลลัพธ์
    for p in parts:  # วนทีละชิ้นที่ส่งเข้ามา
        if isinstance(p, int):  # ถ้าเป็นตัวเลข (เช่น counter c หรือ id)
            p = str(p).encode()  # แปลงเป็นข้อความแล้วเป็น byte (รองรับเลขติดลบ เช่น -1)
        elif isinstance(p, str):  # ถ้าเป็นข้อความ (เช่น keyword)
            p = p.encode("utf-8")  # แปลงเป็น byte แบบ UTF-8 (รองรับภาษาไทย)
        out += len(p).to_bytes(4, "big")  # ใส่ความยาว 4 byte ไว้ข้างหน้า
        out += p  # แล้วต่อด้วยตัวข้อมูลจริง
    return bytes(out)  # คืนค่าเป็น bytes


def xor(a: bytes, b: bytes) -> bytes:
    """XOR สอง byte string ที่ยาวเท่ากัน (สัญลักษณ์ ⊕ ใน paper)

    แปลงเป็นเลขจำนวนเต็มก่อนแล้วค่อย XOR (เร็วกว่าวนทีละ byte ~10 เท่า)"""
    COUNT.xor += 1  # นับเป็น T_X หนึ่งครั้ง
    x = int.from_bytes(a, "big") ^ int.from_bytes(b, "big")  # XOR ทั้งก้อนในครั้งเดียว
    return x.to_bytes(len(a), "big")  # แปลงกลับเป็น byte ความยาวเท่าเดิม


# ---------------------------------------------------------------------------
# PRF และ hash ทั้งหมดที่ paper ใช้
# ---------------------------------------------------------------------------

def F(K_u: bytes, w: str):
    """F_{K_u}(w) -> (K_w, K'_w)   [Alg.2/3 บรรทัด 5, Alg.4 บรรทัด 11]

    ใช้คีย์ของผู้ใช้ K_u สร้างคีย์เฉพาะของ keyword w ออกมา 2 ตัว:
      K_w  = คีย์สำหรับ state (ใช้กับ H1, H2)
      K'_w = คีย์สำหรับ counter (ใช้กับ H3 สร้างคีย์เข้ารหัส bitmap)
    """
    COUNT.prf += 1  # นับเป็น T_PRF หนึ่งครั้ง
    out = hmac.digest(K_u, _enc("F", w), "sha512")  # HMAC-SHA512 ได้ 64 byte
    return out[:32], out[32:]  # ครึ่งแรก = K_w, ครึ่งหลัง = K'_w


def F1(key: bytes, *parts) -> bytes:
    """F1(...) — PRF ที่ใช้สร้าง validator vt และ proof  [Alg.2/3 บรรทัด 18, Alg.5]

    [ASSUMPTION] paper เขียนแค่ F1(w||c) และ F1(id) โดยไม่บอกคีย์
    เราใช้คีย์ K'_u ของผู้ใช้ เพราะ (1) DU ต้องคำนวณเองได้ตอน Verify
    และ (2) CS ต้องไม่รู้คีย์ ไม่งั้น CS ปลอม proof ได้
    """
    COUNT.prf += 1  # นับเป็น T_PRF หนึ่งครั้ง
    return hmac.digest(key, _enc("F1", *parts), "sha256")  # HMAC-SHA256 แบบเรียกครั้งเดียว (เร็ว) ได้ 32 byte


def H1(K_w: bytes, ST: bytes) -> bytes:
    """UT_c = H1(K_w, ST_c) — "ที่อยู่" ของ entry ในฐานข้อมูล EDB  [บรรทัด 13]"""
    COUNT.hash += 1  # นับเป็น T_H หนึ่งครั้ง
    return hashlib.sha256(_enc("H1", K_w, ST)).digest()  # SHA-256 ได้ 32 byte


def H2(K_w: bytes, ST: bytes) -> bytes:
    """H2(K_w, ST_c) — ใช้ทำ "หน้ากาก" ไปซ่อน state ก่อนหน้า  [บรรทัด 14]

    ต้องยาวเท่า ST (16 byte) เพราะจะเอาไป XOR กับ ST_{c-1}
    """
    COUNT.hash += 1  # นับเป็น T_H หนึ่งครั้ง
    return hashlib.sha256(_enc("H2", K_w, ST)).digest()[:LAMBDA_BYTES]  # ตัดเหลือ 16 byte


def H3(K_prime_w: bytes, c: int, gamma: int) -> int:
    """sk_c = H3(K'_w, c) — คีย์ของการเข้ารหัสแบบบวกได้  [บรรทัด 16, Alg.4 บรรทัด 37]

    คีย์นี้ต้องเป็นเลขสุ่มในช่วง [0, n) โดย n = 2^γ (γ = จำนวนบิตของ bitmap)
    จึงใช้ SHAKE-256 ซึ่งเป็น hash ที่ "ขอความยาวผลลัพธ์ได้ตามต้องการ"
    """
    COUNT.hash += 1  # นับเป็น T_H หนึ่งครั้ง
    nbytes = (gamma + 7) // 8  # จำนวน byte ที่ต้องใช้เก็บ γ บิต (ปัดขึ้น)
    digest = hashlib.shake_256(_enc("H3", K_prime_w, c)).digest(nbytes)  # ขอผลยาว nbytes
    return int.from_bytes(digest, "little") & ((1 << gamma) - 1)  # แปลงเป็นเลข แล้วตัดให้อยู่ใน γ บิต


# ---------------------------------------------------------------------------
# Symmetric encryption with homomorphic addition  (Section II-F)
# ---------------------------------------------------------------------------

class HomAdd:
    """การเข้ารหัสที่ "บวกกันได้" แบบในหัวข้อ II-F ของ paper

        Enc(sk, m) = (sk + m) mod n
        Dec(sk, c) = (c - sk) mod n
        Add(c1, c2) = (c1 + c2) mod n      -> ถอดด้วย sk1 + sk2 ได้ m1 + m2

    n = 2^γ ดังนั้น "mod n" ทำได้เร็วด้วยการ AND กับ (n - 1)
    """

    def __init__(self, gamma: int):
        self.gamma = gamma  # γ = ความยาว bitmap = จำนวนเอกสารสูงสุดที่รองรับ
        self.n = 1 << gamma  # n = 2^γ (public parameter)
        self.mask = self.n - 1  # ตัวช่วยทำ mod n (เพราะ x mod 2^γ = x AND (2^γ - 1))
        self.nbytes = (gamma + 7) // 8  # จำนวน byte ของ ciphertext 1 ตัว (ใช้คำนวณขนาด)

    def enc(self, sk: int, m: int) -> int:
        COUNT.enc += 1  # นับเป็น T_Enc หนึ่งครั้ง
        return (sk + m) & self.mask  # c = (sk + m) mod n

    def dec(self, sk: int, c: int) -> int:
        return (c - sk) & self.mask  # m = (c - sk) mod n  (AND กับ mask จัดการเลขติดลบให้ด้วย)

    def add(self, c1: int, c2: int) -> int:
        COUNT.add += 1  # นับเป็น T_A หนึ่งครั้ง
        return (c1 + c2) & self.mask  # c~ = (c1 + c2) mod n

    def neg(self, m: int) -> int:
        """ค่าติดลบใน mod n — ใช้ตอน "ลบเอกสาร" เช่น -2^3 mod 2^4 = 8  (Fig. 1c)"""
        return (-m) & self.mask  # -m mod n


# ---------------------------------------------------------------------------
# Bitmap index  (Section II-A)
# ---------------------------------------------------------------------------

def bitmap_from_ids(ids, gamma: int) -> int:
    """สร้าง bitmap จากรายการ id เอกสาร: เอกสาร id = i  ->  บิตที่ i เป็น 1 (ค่า 2^i)"""
    buf = bytearray((gamma + 7) // 8)  # สร้างกล่องบิตว่าง (ทุกบิตเป็น 0) ยาว γ บิต
    for i in ids:  # วนทุก id
        if not 0 <= i < gamma:  # ถ้า id เกินความจุของ bitmap
            raise ValueError(f"document id {i} อยู่นอกช่วง bitmap (gamma={gamma})")  # แจ้ง error
        buf[i >> 3] |= 1 << (i & 7)  # ตั้งบิตที่ i ให้เป็น 1 (byte ที่ i//8, บิตที่ i%8)
    return int.from_bytes(buf, "little")  # แปลงกล่องบิตเป็นเลขจำนวนเต็มก้อนเดียว


def ids_from_bitmap(bs: int):
    """อ่าน bitmap กลับเป็นรายการ id เอกสาร (ตำแหน่งที่บิตเป็น 1)"""
    if bs == 0:  # ถ้าไม่มีบิตไหนเป็น 1 เลย
        return []  # ก็ไม่มีเอกสาร
    raw = bs.to_bytes((bs.bit_length() + 7) // 8, "little")  # แปลงเลขเป็น byte
    out = []  # รายการผลลัพธ์
    for byte_index, byte in enumerate(raw):  # วนทีละ byte
        if byte:  # ข้าม byte ที่เป็น 0 ทั้งหมด (เร็วขึ้นมากเมื่อ bitmap โหรง)
            for bit in range(8):  # ดูทีละบิตใน byte นั้น
                if byte >> bit & 1:  # ถ้าบิตนี้เป็น 1
                    out.append(byte_index * 8 + bit)  # ตำแหน่งบิต = id เอกสาร
    return out  # คืนรายการ id


def int_to_bytes(x: int, nbytes: int) -> bytes:
    """แปลงเลขเป็น byte ความยาวคงที่ (ใช้ตอนเก็บลงดิสก์ / วัดขนาด)"""
    return x.to_bytes(nbytes, "little")  # little-endian ให้ตรงกับ bitmap_from_ids


def bytes_to_int(b: bytes) -> int:
    """แปลง byte กลับเป็นเลข"""
    return int.from_bytes(b, "little")  # little-endian


# ---------------------------------------------------------------------------
# SE — symmetric encryption ธรรมดา (ใช้กับ CntDiffs ในคิวของผู้ใช้)
# ---------------------------------------------------------------------------

def se_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """SE.Enc — เข้ารหัสด้วย AES-GCM  (Enc_{K'_u}(w, c) ใน Alg.2/3 บรรทัด 12)"""
    nonce = os.urandom(12)  # สุ่ม nonce 12 byte ใหม่ทุกครั้ง (ห้ามใช้ซ้ำ)
    return nonce + AESGCM(_aes_key(key)).encrypt(nonce, plaintext, None)  # ส่ง nonce ไปพร้อม ciphertext


def se_decrypt(key: bytes, blob: bytes) -> bytes:
    """SE.Dec — ถอดรหัส AES-GCM  (Alg.4/5 บรรทัด 3)"""
    return AESGCM(_aes_key(key)).decrypt(blob[:12], blob[12:], None)  # 12 byte แรกคือ nonce


def _aes_key(key: bytes) -> bytes:
    """ทำให้คีย์ยาว 32 byte พอดีสำหรับ AES-256 (K'_u ยาว 16 byte จึงขยายด้วย SHA-256)"""
    return hashlib.sha256(_enc("SE", key)).digest()  # ได้คีย์ 32 byte


# ============================================================================
# 2) EDB — ที่เก็บฐานข้อมูลเข้ารหัสฝั่ง CS (RAM หรือ SQLite)
# ============================================================================

class MemoryEDB:
    """EDB แบบเก็บใน dict ของ Python"""

    def __init__(self, gamma: int):
        self.nbytes = (gamma + 7) // 8  # ขนาดของ e_c 1 ตัว (byte) ใช้ตอนคำนวณพื้นที่
        self._d = {}  # dict จริง ๆ ที่เก็บข้อมูล: key = UT, value = (e, C, vt)

    def get(self, ut: bytes):
        return self._d.get(ut)  # คืน (e, C, vt) หรือ None ถ้าไม่มี

    def put(self, ut: bytes, e: int, c_st, vt: bytes):
        self._d[ut] = (e, c_st, vt)  # เขียน/เขียนทับ entry ที่ที่อยู่ ut

    def put_many(self, rows):
        for ut, e, c_st, vt in rows:  # วนทุกแถว
            self._d[ut] = (e, c_st, vt)  # เขียนทีละแถว

    def delete(self, ut: bytes):
        self._d.pop(ut, None)  # ลบ entry (ถ้าไม่มีก็ไม่เป็นไร)

    def __len__(self):
        return len(self._d)  # จำนวน entry ทั้งหมด

    def size_bytes(self) -> int:
        """พื้นที่จัดเก็บโดยประมาณ = ผลรวมขนาด UT + e + C + vt ของทุก entry"""
        total = 0  # ตัวนับ
        for ut, (e, c_st, vt) in self._d.items():  # วนทุก entry
            total += len(ut) + self.nbytes + len(vt) + (len(c_st) if c_st else 0)  # บวกขนาดแต่ละส่วน
        return total  # คืนจำนวน byte

    def close(self):
        pass  # แบบ RAM ไม่ต้องปิดอะไร


class SqliteEDB:
    """EDB แบบเก็บลงไฟล์ SQLite — ข้อมูลเหมือนกันทุกอย่าง แค่ไม่กิน RAM"""

    def __init__(self, gamma: int, path: str):
        self.nbytes = (gamma + 7) // 8  # ขนาดของ e_c เป็น byte (ทุกตัวยาวเท่ากันเสมอ)
        self.conn = sqlite3.connect(path)  # เปิด/สร้างไฟล์ฐานข้อมูล
        self.conn.execute("PRAGMA journal_mode=OFF")  # ปิด journal ให้เขียนเร็วขึ้น (ใช้ทดลองเท่านั้น)
        self.conn.execute("PRAGMA synchronous=OFF")  # ไม่ต้องรอดิสก์ทุกครั้ง (เร็วขึ้น)
        self.conn.execute("DROP TABLE IF EXISTS edb")  # เริ่มใหม่ทุกครั้ง ลบตารางเก่าทิ้ง
        self.conn.execute(  # สร้างตาราง: ut เป็น primary key
            "CREATE TABLE edb (ut BLOB PRIMARY KEY, e BLOB, cst BLOB, vt BLOB)"
        )

    def get(self, ut: bytes):
        row = self.conn.execute("SELECT e, cst, vt FROM edb WHERE ut=?", (ut,)).fetchone()  # ค้นตาม ut
        if row is None:  # ไม่เจอ
            return None  # คืน None เหมือน dict.get
        return bytes_to_int(row[0]), row[1], row[2]  # แปลง e จาก byte กลับเป็นเลข

    def put(self, ut: bytes, e: int, c_st, vt: bytes):
        self.conn.execute(  # INSERT OR REPLACE = เขียนทับถ้ามีอยู่แล้ว
            "INSERT OR REPLACE INTO edb VALUES (?,?,?,?)",
            (ut, int_to_bytes(e, self.nbytes), c_st, vt),
        )

    def put_many(self, rows):
        self.conn.executemany(  # เขียนหลายแถวในคำสั่งเดียว (เร็วกว่า)
            "INSERT OR REPLACE INTO edb VALUES (?,?,?,?)",
            ((ut, int_to_bytes(e, self.nbytes), c, vt) for ut, e, c, vt in rows),
        )

    def delete(self, ut: bytes):
        self.conn.execute("DELETE FROM edb WHERE ut=?", (ut,))  # ลบแถว

    def __len__(self):
        return self.conn.execute("SELECT COUNT(*) FROM edb").fetchone()[0]  # นับแถว

    def size_bytes(self) -> int:
        q = "SELECT COALESCE(SUM(LENGTH(ut)+LENGTH(e)+LENGTH(vt)+COALESCE(LENGTH(cst),0)),0) FROM edb"  # รวมขนาด
        return self.conn.execute(q).fetchone()[0]  # คืนจำนวน byte

    def close(self):
        self.conn.close()  # ปิดไฟล์


# ============================================================================
# 3) Scheme — DataOwner / CloudServer / DataUser (Algorithm 1-5)
# ============================================================================

ADD = "add"  # ชนิดการอัปเดต: เพิ่ม keyword-document
DEL = "del"  # ชนิดการอัปเดต: ลบ keyword-document


# ---------------------------------------------------------------------------
# โครงสร้างข้อมูลที่ส่งไปมาระหว่าง DO / CS / DU
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """token_i = (K_w, ST_c, c)  [Alg.4 L12] — ส่งจาก DU ไป CS ตอนค้นหา"""
    K_w: bytes  # คีย์ state ของ keyword (32 byte)
    ST_c: bytes  # state ล่าสุดของ keyword (16 byte)
    c: int  # counter ล่าสุด (นับว่า keyword นี้ถูกอัปเดตกี่ครั้งแล้ว เริ่มที่ 0)

    def size_bytes(self) -> int:
        return len(self.K_w) + len(self.ST_c) + 8  # ขนาดที่ต้องส่งผ่านเครือข่าย (c นับเป็น 8 byte)


@dataclass
class UpdateMessage:
    """ข้อความที่ DO ส่งให้ CS ตอน Share/Update  [Alg.2 L20, Alg.3 L21]"""
    u: str  # ผู้ใช้ที่ entry เหล่านี้เป็นของ
    entries: list  # รายการ (UT_c, e_c, C_STc, vt)
    diffs: list  # CntDiffs = รายการ ciphertext Enc_{K'_u}(w, c, ST_c)
    ids: list  # id เอกสารที่เกี่ยวข้อง (ใช้กับ AccessList ตอน Share)

    def size_bytes(self, nbytes_e: int) -> int:
        """ขนาดข้อความ (ใช้วัด communication overhead ของ update)"""
        s = sum(len(ut) + nbytes_e + len(c) + len(vt) for ut, e, c, vt in self.entries)  # ขนาด entry
        return s + sum(len(d) for d in self.diffs)  # บวกขนาดของ CntDiffs


# ---------------------------------------------------------------------------
# ตัวช่วยแพ็ก/แกะ CntDiffs
# ---------------------------------------------------------------------------

def _pack_diff(w: str, c: int, ST_c: bytes) -> bytes:
    """รวม (w, c, ST_c) เป็น byte ก้อนเดียวก่อนเข้ารหัส"""
    return c.to_bytes(8, "big", signed=True) + ST_c + w.encode("utf-8")  # 8 byte c + 16 byte ST + keyword


def _unpack_diff(b: bytes):
    """แกะ byte กลับเป็น (w, c, ST_c)"""
    c = int.from_bytes(b[:8], "big", signed=True)  # 8 byte แรกคือ counter
    ST_c = b[8:8 + LAMBDA_BYTES]  # 16 byte ถัดมาคือ state
    w = b[8 + LAMBDA_BYTES:].decode("utf-8")  # ที่เหลือคือ keyword
    return w, c, ST_c  # คืนทั้งสามค่า


# ============================================================================
# Cloud Server (CS)
# ============================================================================

class CloudServer:
    """CS: เก็บ EDB, AccessList, Queues และทำงานฝั่ง server ของ Search"""

    def __init__(self, gamma: int, edb=None):
        self.he = HomAdd(gamma)  # ตัวเข้ารหัสแบบบวกได้ (CS ใช้แค่ Add)
        self.EDB = edb if edb is not None else MemoryEDB(gamma)  # ฐานข้อมูลที่เข้ารหัส
        self.AccessList = defaultdict(set)  # AccessList[id] = ผู้ใช้ที่มีสิทธิ์เห็นเอกสาร id
        self.Queues = defaultdict(list)  # Queues[u] = คิว CntDiffs ที่รอ DU u มาดึง

    # ---------------- รับข้อมูลจาก DO (Alg.2 L22-24, Alg.3 L22-23) ----------------
    def receive(self, msg: UpdateMessage, register_access: bool):
        if register_access:  # ถ้าเป็นการ Share (ให้สิทธิ์ใหม่)
            for doc_id in msg.ids:  # วนทุกเอกสาร
                self.AccessList[doc_id].add(msg.u)  # [Alg.2 L22] AccessList[id] ∪= {u}
        self.Queues[msg.u].extend(msg.diffs)  # [L23] ใส่ CntDiffs ทั้งหมดเข้าคิวของ u
        self.EDB.put_many(msg.entries)  # [L24] EDB[UT_c] <- (e_c, C_STc, vt)

    # ---------------- DU มาดึงคิว (Alg.4 L1, Alg.5 L1) ----------------
    def fetch_queue(self, u: str):
        diffs = self.Queues.pop(u, [])  # เอาคิวทั้งหมดของ u ออกมา (แล้วล้างคิว)
        return diffs  # ส่งให้ DU (ข้อมูลเข้ารหัสอยู่ CS อ่านไม่ออก)

    # ---------------- ฝั่ง server ของ Search (Alg.4 L16-33) ----------------
    def search(self, tokens):
        R = []  # [L16] R <- ⊥ (ผลลัพธ์ว่าง)
        for tok in tokens:  # [L17] วนทุก token (1 token ต่อ 1 keyword)
            Sum_e = 0  # [L18] ผลรวม ciphertext เริ่มที่ 0
            proof = bytes(PROOF_BYTES)  # proof เริ่มเป็นศูนย์ทั้งหมด (XOR กับ 0 ไม่เปลี่ยนค่า)
            ST_i = tok.ST_c  # เริ่มเดินจาก state ล่าสุด
            for i in range(tok.c, -1, -1):  # [L19] for i = c down to 0 (เดินย้อนจากใหม่ไปเก่า)
                UT_i = H1(tok.K_w, ST_i)  # [L20] คำนวณที่อยู่ของ entry ครั้งที่ i
                entry = self.EDB.get(UT_i)  # [L21] ดึง (e_i, C_ST{i-1}, vt) ออกมา
                if entry is None:  # ไม่ควรเกิดถ้าทุกฝ่ายทำตามโปรโตคอล
                    break  # หยุดเดิน (DU จะ verify ไม่ผ่านเอง)
                e_i, C_prev, vt = entry  # แยกค่าออกมา
                COUNT.visited += 1  # (ไม่อยู่ใน paper) นับ entry ที่เดินผ่าน ไว้รายงานผล
                Sum_e = self.he.add(Sum_e, e_i)  # [L22] รวม bitmap ที่เข้ารหัสด้วยการบวกแบบ homomorphic
                proof = xor(proof, vt)  # [L23] รวม proof ด้วย XOR
                self.EDB.delete(UT_i)  # [L24] ลบ entry เก่าทิ้ง (จะเขียนผลรวมกลับทีหลัง)
                if C_prev is None:  # [L25] ถ้า C = ⊥ แปลว่านี่คือผลรวมจากการค้นครั้งก่อน
                    break  # [L26] ไม่ต้องเดินต่อแล้ว
                ST_i = xor(H2(tok.K_w, ST_i), C_prev)  # [L28] ถอดหน้ากาก ได้ state ก่อนหน้า ST_{i-1}
            UT_c = H1(tok.K_w, tok.ST_c)  # ที่อยู่ของ state ล่าสุด
            self.EDB.put(UT_c, Sum_e, None, proof)  # [L30] เก็บผลรวมไว้ที่เดียว (C = ⊥) ครั้งหน้าจะเร็วขึ้น
            R.append((Sum_e, proof))  # [L31] ใส่ผลของ keyword นี้ลงใน R
        return R  # [L33] ส่ง R กลับให้ DU


# ============================================================================
# Data Owner (DO)
# ============================================================================

class DataOwner:
    """DO: เจ้าของข้อมูล เชื่อถือได้ 100% — สร้าง index ที่เข้ารหัสแล้วส่งให้ CS"""

    def __init__(self, gamma: int):
        self.setup(gamma)  # เรียก Setup ทันทีที่สร้าง DO

    # ---------------- Setup (Alg.1) ----------------
    def setup(self, gamma: int):
        self.gamma = gamma  # γ = จำนวนเอกสารสูงสุดที่ระบบรองรับ (= ความยาว bitmap)
        self.he = HomAdd(gamma)  # [Alg.1 L1] n <- Setup(1^λ) โดย n = 2^γ
        self.CT = defaultdict(dict)  # [L2] CT[u][w] = (ST_c, c) state ของแต่ละ keyword แยกตามผู้ใช้
        self.UsersKeys = {}  # UsersKeys[u] = (K_u, K'_u) คีย์ของผู้ใช้แต่ละคน
        self.AccessList = defaultdict(set)  # สำเนาฝั่ง DO: เอกสาร id แชร์ให้ใครบ้าง
        self.doc_keywords = {}  # DO รู้ข้อมูลของตัวเอง: เอกสาร id มี keyword อะไรบ้าง (ใช้ตอนลบ)
        return self.he.n  # [L4] public parameter n (EDB ว่างอยู่ใน CS แล้ว)

    # ---------------- แกนกลางของ Share/Update (บรรทัด 4-19) ----------------
    def _gen_entries(self, u: str, docs, op: str) -> UpdateMessage:
        """สร้าง entry ที่เข้ารหัสสำหรับผู้ใช้ u จากรายการเอกสาร docs = [(id, keywords), ...]"""
        K_u, K_prime_u = self.UsersKeys[u]  # ดึงคีย์ของผู้ใช้ u
        by_kw = defaultdict(list)  # จัดกลุ่ม: keyword -> รายการ id
        for doc_id, kws in docs:  # วนทุกเอกสาร
            for w in kws:  # วนทุก keyword ในเอกสาร
                by_kw[w].append(doc_id)  # จดว่า keyword w อยู่ในเอกสาร doc_id
        entries, diffs = [], []  # ที่เก็บผลลัพธ์
        for w, ids in by_kw.items():  # [L4] for w in W(id)
            K_w, K_prime_w = F(K_u, w)  # [L5] K_w || K'_w <- F_{K_u}(w)
            state = self.CT[u].get(w)  # [L6] (ST_c, c) <- CT[u][w]
            if state is None:  # [L7] ถ้ายังไม่เคยมี keyword นี้สำหรับผู้ใช้ u
                c, ST_prev = -1, random_bytes()  # [L8] c <- -1, ST สุ่มขึ้นมาเป็นจุดเริ่ม
            else:  # ถ้าเคยมีแล้ว
                ST_prev, c = state  # เอา state กับ counter ปัจจุบันมาเป็น "ของก่อนหน้า"
            ST_c = random_bytes()  # [L10] สุ่ม state ใหม่ (นี่คือหัวใจของ forward privacy)
            c = c + 1  # [L10] counter + 1
            self.CT[u][w] = (ST_c, c)  # [L11] บันทึก state ใหม่ลง CT
            # [FIX] paper ใส่แค่ (w, c) แต่ DU ต้องใช้ ST_c ทำ token (Alg.4 L4) จึงใส่ ST_c ไปด้วย
            diffs.append(se_encrypt(K_prime_u, _pack_diff(w, c, ST_c)))  # [L12] CntDiffs ∪= Enc_{K'_u}(w,c,ST_c)
            UT_c = H1(K_w, ST_c)  # [L13] ที่อยู่ใหม่ (สุ่มทุกครั้ง CS จึงโยงกับครั้งก่อนไม่ได้)
            C_ST = xor(H2(K_w, ST_c), ST_prev)  # [L14] ซ่อน state ก่อนหน้าไว้ (มีแค่คนรู้ ST_c ถึงเปิดได้)
            bs = bitmap_from_ids(ids, self.gamma)  # [L15] สร้าง bitmap: บิตของเอกสารเหล่านี้เป็น 1
            if op == DEL:  # [ASSUMPTION] ถ้าเป็นการลบ (paper อธิบายใน Fig. 1c แต่ไม่ได้เขียนใน Alg.3)
                bs = self.he.neg(bs)  # ใช้ -bs mod n แทน (Fig. 1c) พอบวกรวมแล้วบิตนั้นจะกลับเป็น 0
            sk_c = H3(K_prime_w, c, self.gamma)  # [L16] คีย์เข้ารหัส bitmap ของครั้งที่ c
            e_c = self.he.enc(sk_c, bs)  # [L17] e_c = (sk_c + bs) mod n
            vt = xor(F1(K_prime_u, w, c - 1), F1(K_prime_u, w, c))  # [L18] F1(w||c-1) ⊕ F1(w||c)
            for doc_id in ids:  # [L18] ... ⊕ F1(id) ของทุกเอกสารในการอัปเดตนี้
                vt = xor(vt, F1(K_prime_u, doc_id))  # XOR สะสม
            entries.append((UT_c, e_c, C_ST, vt))  # เก็บ entry ที่จะส่งให้ CS
        all_ids = [doc_id for doc_id, _ in docs]  # รายการ id ทั้งหมดในข้อความนี้
        return UpdateMessage(u=u, entries=entries, diffs=diffs, ids=all_ids)  # แพ็กเป็นข้อความ

    # ---------------- Share (Alg.2) ----------------
    def register_user(self, u: str):
        """[Alg.2 L2-3] สร้างคีย์ให้ DU u (ครั้งแรกครั้งเดียว) แล้วคืนคีย์ให้ส่งไปที่ DU"""
        if u not in self.UsersKeys:  # [FIX] paper สุ่มทุกครั้งที่ Share -> สุ่มเฉพาะครั้งแรกของผู้ใช้
            self.UsersKeys[u] = (random_bytes(), random_bytes())  # [L2-3] K_u, K'_u <- {0,1}^λ
        return self.UsersKeys[u]  # [L21] ส่ง (K_u, K'_u) ให้ DU u

    def share(self, u: str, docs, cs: CloudServer):
        """Alg.2: ให้สิทธิ์ผู้ใช้ u เห็นเอกสาร docs = [(id, keywords), ...]
        ใช้ทั้งตอนแชร์เอกสารเดิมให้ผู้ใช้ใหม่ และตอนเพิ่มเอกสารใหม่เข้าระบบ"""
        keys = self.register_user(u)  # เตรียมคีย์ของผู้ใช้
        todo = []  # เอกสารที่ต้องสร้าง entry จริง ๆ
        for doc_id, kws in docs:  # วนทุกเอกสาร
            kws = set(kws)  # ตัด keyword ซ้ำในเอกสารเดียวกันออก
            if doc_id in self.doc_keywords and self.doc_keywords[doc_id] != kws:  # id เดิมแต่ keyword ต่าง
                raise ValueError(f"doc {doc_id} มีอยู่แล้ว ให้ใช้ update() เพื่อแก้ keyword")  # ป้องกันข้อมูลเพี้ยน
            if u in self.AccessList[doc_id]:  # ผู้ใช้นี้มีสิทธิ์เอกสารนี้อยู่แล้ว
                continue  # ข้าม (ถ้าบวก bitmap ซ้ำ บิตจะทดเลขเพี้ยน)
            self.AccessList[doc_id].add(u)  # [L1] AccessList[id] ∪= {u}
            self.doc_keywords[doc_id] = kws  # DO จำ keyword ของเอกสารไว้
            todo.append((doc_id, kws))  # รอสร้าง entry
        msg = self._gen_entries(u, todo, ADD)  # [L4-19] สร้าง entry ที่เข้ารหัส
        cs.receive(msg, register_access=True)  # [L20, L22-24] ส่งให้ CS เก็บ
        return keys, msg  # คืนคีย์ (ให้ DU) และข้อความ (ไว้วัดขนาด)

    # ---------------- Update (Alg.3) ----------------
    def update(self, docs, op: str, cs: CloudServer):
        """Alg.3: เพิ่ม (op=ADD) หรือลบ (op=DEL) คู่ keyword-document ของเอกสารที่แชร์ไปแล้ว

        docs = [(id, keywords), ...]   ถ้า op=DEL และ keywords=None จะลบเอกสารทั้งไฟล์
        """
        per_user = defaultdict(list)  # ผู้ใช้แต่ละคน -> เอกสารที่ต้องอัปเดตให้เขา
        for doc_id, kws in docs:  # วนทุกเอกสาร
            current = self.doc_keywords.get(doc_id, set())  # keyword ที่เอกสารนี้มีอยู่ตอนนี้
            if op == ADD:  # กรณีเพิ่ม
                kws = set(kws) - current  # เพิ่มเฉพาะ keyword ที่ยังไม่มี (กันบวกบิตซ้ำ)
                self.doc_keywords[doc_id] = current | kws  # อัปเดตข้อมูลฝั่ง DO
            else:  # กรณีลบ
                kws = current if kws is None else set(kws) & current  # ลบได้เฉพาะ keyword ที่มีอยู่จริง
                self.doc_keywords[doc_id] = current - kws  # อัปเดตข้อมูลฝั่ง DO
                if not self.doc_keywords[doc_id]:  # ถ้าเอกสารไม่เหลือ keyword แล้ว (ลบทั้งไฟล์)
                    del self.doc_keywords[doc_id]  # ลืมเอกสารนี้
            if not kws:  # ไม่มีอะไรต้องทำ
                continue  # ข้ามไป
            for u in self.AccessList.get(doc_id, ()):  # [Alg.3 L1-2] userList <- AccessList[id]
                per_user[u].append((doc_id, kws))  # ทุกผู้ใช้ที่มีสิทธิ์ต้องได้ entry ของตัวเอง
            if op == DEL and doc_id not in self.doc_keywords:  # ลบทั้งไฟล์แล้ว
                self.AccessList.pop(doc_id, None)  # ล้างรายการสิทธิ์ของเอกสารนั้น
        msgs = []  # เก็บข้อความที่ส่ง
        for u, udocs in per_user.items():  # [L2] for u in userList  -> ต้นทุน O(N_u · m)
            msg = self._gen_entries(u, udocs, op)  # [L4-19] สร้าง entry สำหรับผู้ใช้ u
            cs.receive(msg, register_access=False)  # [L21-23] ส่งให้ CS
            msgs.append(msg)  # จดไว้
        return msgs  # คืนรายการข้อความ (ไว้วัดขนาด)


# ============================================================================
# Data User (DU)
# ============================================================================

class DataUser:
    """DU: ผู้ใช้ที่ได้รับสิทธิ์ ค้นหาและตรวจผลลัพธ์"""

    def __init__(self, u: str, keys, gamma: int):
        self.u = u  # ชื่อ/ตัวระบุผู้ใช้
        self.K_u, self.K_prime_u = keys  # คีย์ที่ DO ส่งมาให้ (K_u, K'_u)
        self.he = HomAdd(gamma)  # ตัวเข้ารหัสแบบบวกได้ (DU ใช้ Dec)
        self.gamma = gamma  # γ
        self.CT = {}  # CT[w] = (ST_c, c) สำเนา state ฝั่ง DU (ได้จากคิว)

    # ---------------- ดึงคิว (Alg.4 L1-5, Alg.5 L1-5) ----------------
    def sync(self, cs: CloudServer):
        diffs = cs.fetch_queue(self.u)  # [L1] diffs <- fetch Queues[u] from CS
        for diff in diffs:  # [L2] for diff in diffs
            w, c, ST_c = _unpack_diff(se_decrypt(self.K_prime_u, diff))  # [L3] (w', c) <- SE.Dec(K'_u, diff)
            old = self.CT.get(w)  # state เดิมที่ DU มี
            if old is None or c > old[1]:  # เก็บเฉพาะ state ที่ใหม่กว่า
                self.CT[w] = (ST_c, c)  # [L4] CT[u][w'] <- (ST_c, c)
        return len(diffs)  # จำนวน diff ที่ดึงมา

    # ---------------- สร้าง Token (Alg.4 L6-15) ----------------
    def gen_token(self, q):
        tokens = []  # Token = เซตว่าง
        for w in q:  # [L6] for each w_i in q
            state = self.CT.get(w)  # [L7] (ST_c, c) <- CT[u][w_i]
            if state is None:  # [L8] ถ้า keyword นี้ไม่เคยมีเลย
                return None  # [L9] return ∅ (AND กับเซตว่าง = ว่างแน่นอน)
            ST_c, c = state  # แยกค่า
            K_w, _ = F(self.K_u, w)  # [L11] K_w || K'_w <- F_{K_u}(w) (ใช้แค่ K_w ส่งให้ CS)
            tokens.append(Token(K_w=K_w, ST_c=ST_c, c=c))  # [L12-13] Token ∪= {(K_w, ST_c, c)}
        return tokens  # [L15] ส่ง Token ให้ CS

    # ---------------- ถอดผล + AND (Alg.4 L34-43) ----------------
    def decrypt(self, q, R):
        bitmaps = []  # bitmap ของแต่ละ keyword (เก็บไว้ใช้ตอน Verify)
        for w, (Sum_e, _proof) in zip(q, R):  # [L34] for each (Sum_e, proof) in R
            _, c = self.CT[w]  # counter ล่าสุดของ keyword นี้
            _, K_prime_w = F(self.K_u, w)  # คีย์ counter K'_w
            Sum_sk = 0  # [L35] ผลรวมคีย์เริ่มที่ 0
            for j in range(c, -1, -1):  # [L36] for j = c to 0
                sk_j = H3(K_prime_w, j, self.gamma)  # [L37] คีย์ของการอัปเดตครั้งที่ j
                Sum_sk = (Sum_sk + sk_j) & self.he.mask  # [L38] รวมคีย์ mod n
            bitmaps.append(self.he.dec(Sum_sk, Sum_e))  # [L40] bs_w <- Dec(Sum_sk, Sum_e)
        Bs = bitmaps[0]  # เริ่มจาก bitmap ของ keyword แรก
        for bs in bitmaps[1:]:  # [L42] Bs <- bs_w1 ∧ ... ∧ bs_wq
            Bs &= bs  # AND ทีละตัว = เอกสารที่มี "ทุก" keyword
        return Bs, bitmaps  # [L43] return Bs (และ bitmap ราย keyword ไว้ verify)

    # ---------------- Verify (Alg.5 L6-17) ----------------
    def verify(self, q, bitmaps, R) -> bool:
        if len(R) != len(q) or len(bitmaps) != len(q):  # [L6] ต้องมี (Sum_e, proof) ครบทุก w_i ใน q
            return False  # CS ตัดผลของบาง keyword ทิ้ง -> reject (zip จะตัดส่วนเกินทิ้งเงียบ ๆ)
        for w, bs_w, (_Sum_e, proof) in zip(q, bitmaps, R):  # [L6] for each w_i in q
            _, c = self.CT[w]  # [L7] (ST_c, c) <- CT[u][w_i]
            proof_p = xor(F1(self.K_prime_u, w, -1), F1(self.K_prime_u, w, c))  # [L8] F1(w||-1) ⊕ F1(w||c)
            for doc_id in ids_from_bitmap(bs_w):  # [L9] for each id in bs_w
                proof_p = xor(proof_p, F1(self.K_prime_u, doc_id))  # [L10] proof' ⊕= F1(id)
            if proof_p != proof:  # [L12] ถ้าไม่เท่ากัน  [FIX] paper คืนผลหลัง keyword แรก -> เช็คทุกคำ
                return False  # [L15] reject (CS ส่งผลขาด/เกิน/ปลอม)
        return True  # [L13] ผ่านครบทุก keyword -> accept

    # ---------------- รวมทุกขั้นตอนของการค้น 1 ครั้ง ----------------
    def search(self, q, cs: CloudServer):
        """สะดวกใช้: sync -> token -> CS search -> decrypt -> verify
        คืน (รายการ id ที่ตรงทุก keyword, ผล verify True/False)"""
        self.sync(cs)  # ดึงคิวให้ state เป็นปัจจุบัน
        tokens = self.gen_token(q)  # สร้าง token
        if tokens is None:  # มี keyword ที่ไม่เคยมีเลย
            return [], True  # ผลว่าง (ไม่มีอะไรให้ตรวจ)
        R = cs.search(tokens)  # CS ค้นและส่งผลกลับ
        Bs, bitmaps = self.decrypt(q, R)  # ถอดและ AND
        ok = self.verify(q, bitmaps, R)  # ตรวจความถูกต้อง
        return ids_from_bitmap(Bs), ok  # คืน id เอกสารและผลตรวจ




def supports(shape: str) -> bool:
    """[40] ค้นได้แค่ AND (Alg.4 L42: Bs = bs_w1 ∧ ... ∧ bs_wq) -> รองรับแค่ single และ conjunctive"""
    return shape in ("single", "conjunctive")  # OR / nested = N/A


# ============================================================================
# 4) Workload — dataset กลางของ AMTP (amtp_dataset.py ในโฟลเดอร์เดียวกัน)
# ============================================================================
HERE = os.path.dirname(os.path.abspath(__file__))  # โฟลเดอร์ของไฟล์นี้ (baselines/)
SHARED_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # ไฟล์ query กลาง ใช้ร่วมทุก scheme
sys.path.insert(0, HERE)                          # ให้ import amtp_dataset.py ที่อยู่ข้าง ๆ ได้


def dataset():
    """import amtp_dataset ตอนใช้งานจริง (demo / selftest จะได้รันได้โดยไม่ต้องมี dataset)"""
    import amtp_dataset                           # ตัวโหลด dataset กลาง
    return amtp_dataset                           # คืน module


FILE_LEN = {}                                     # ตำแหน่งบิต -> ขนาด plaintext ของไฟล์ (ใช้นับ response_bytes)


def to_chen(docs, start: int = 0):
    """แปลง Doc ของ dataset -> (ตำแหน่งบิต, set(keywords)) ที่ DataOwner ของ Chen ใช้
    bitmap ต้องใช้เลข 0..gamma-1 แทน id เอกสาร จึงใช้ลำดับในรายการเป็นตำแหน่งบิต
    และจำขนาดไฟล์ของแต่ละตำแหน่งไว้ใน FILE_LEN: [40] คืนแค่ bitmap ไม่ได้คืนไฟล์ จึงคิดขนาด
    ciphertext มาตรฐาน AES-GCM ของไฟล์ผลลัพธ์ตามกติกากลาง (wire_sizes.py)"""
    root = dataset().load()["dir"] if docs and hasattr(docs[0], "file_path") else None
    if start == 0:
        FILE_LEN.clear()
    for i, d in enumerate(docs):
        if root is not None:
            FILE_LEN[start + i] = os.path.getsize(os.path.join(root, d.file_path))
    return [(start + i, set(d.keywords)) for i, d in enumerate(docs)]  # keyword ไม่ซ้ำในไฟล์อยู่แล้ว


def parse_and_query(q: str):
    """แปลง query string แบบ "A AND B AND C" -> ["A", "B", "C"]  (single = keyword เดียว)"""
    return [t.strip() for t in q.split(" AND ")]  # แยกด้วย AND


# ============================================================================
# 5) ตัวช่วยของ benchmark (รูปแบบผลลัพธ์เหมือน SE-COLLAB: <ชื่อ>_ms, _ms_median, _ms_std)
# ============================================================================
class Writer:
    """สะสมผลแต่ละแถว พิมพ์ขึ้นจอ (ไม่แสดง std/median ให้อ่านง่าย) และเขียน CSV ตอน close()"""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # สร้างโฟลเดอร์ผลลัพธ์
        self.path = os.path.join(out_dir, f"chen_{name}.csv")  # ไฟล์ปลายทาง
        self.rows = []                            # แถวที่สะสมไว้

    def add(self, **row):
        self.rows.append(row)                     # เก็บแถว
        show = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()
                if not k.endswith("_std") and not k.endswith("_median")}  # ตัดคอลัมน์ที่ไม่ต้องโชว์
        print("  " + "  ".join(f"{k}={v}" for k, v in show.items()), flush=True)  # พิมพ์ขึ้นจอ

    def close(self):
        if not self.rows:                         # ไม่มีข้อมูล
            return                                # ไม่ต้องเขียน
        keys = list(dict.fromkeys(k for r in self.rows for k in r))  # รวมชื่อคอลัมน์ทุกแถว (คงลำดับ)
        with open(self.path, "w", newline="", encoding="utf-8") as f:  # เปิดไฟล์
            w = csv.DictWriter(f, fieldnames=keys)  # writer
            w.writeheader()                       # หัวตาราง
            w.writerows(self.rows)                # ข้อมูล (แถว N/A ช่องที่ไม่มีจะว่าง)
        print(f"-> {os.path.relpath(self.path)}")  # แจ้งที่อยู่ไฟล์
        dataset().write_manifest(self.path)       # เครื่อง / commit / คำสั่งที่ใช้รัน (<csv>.manifest.json)


def summarize(samples, prefix: str = ""):
    """รวมผลหลายรอบ -> คอลัมน์ <ชื่อ>_ms (mean), <ชื่อ>_ms_median, <ชื่อ>_ms_std  (เหมือน SE-COLLAB)"""
    out = {}                                      # ผลสรุป
    for k in samples[0]:                          # ทุก metric
        v = [s.get(k, 0.0) for s in samples]      # ค่าทุกรอบ
        out[f"{prefix}{k}_ms"] = st.mean(v)       # ค่าเฉลี่ย
        out[f"{prefix}{k}_ms_median"] = st.median(v)  # มัธยฐาน
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)  # ส่วนเบี่ยงเบนมาตรฐาน
    return out                                    # คืนผล


def popcount(x: int) -> int:
    return bin(x).count("1")                      # จำนวนบิตที่เป็น 1 = จำนวนเอกสารใน bitmap


def setup(docs, gamma, args, users=1, needed=None):
    """สร้างระบบมาตรฐานสำหรับการทดลอง: DO 1 ตัว, CS 1 ตัว, DU `users` คน (ทุกคนเห็นทุกเอกสาร)

    ขนาด index ของ Chen = (จำนวน keyword ไม่ซ้ำ) x (gamma บิต) ต่อผู้ใช้ — dataset arXiv มี keyword
    ไม่ซ้ำเยอะมาก (N = 200,000 -> ~1.29 ล้านคำ -> ~32 GB) จึงมี 2 แบบ (--scope):
      full    : สร้าง entry ของทุก keyword (ตรงตาม paper ทุกอย่าง)
      queried : [ASSUMPTION] สร้าง entry เฉพาะ keyword ที่การทดลองใช้ (needed) โดย bitmap ของคำนั้น
                ครบทุกเอกสาร -> เวลาค้น/verify ของคำนั้นเท่ากับแบบ full ทุกประการ
                (search เดินเฉพาะ chain ของคำที่ค้น ไม่ได้แตะ entry ของคำอื่น)
      auto    : full ถ้าขนาดไม่เกิน --max-edb-gb ไม่งั้น queried
    cs_storage_bytes รายงานขนาดของ index เต็มเสมอ (คำนวณตรง ๆ ได้ เพราะทุก entry ยาวเท่ากัน)"""
    nbytes = (gamma + 7) // 8                     # ขนาด ciphertext 1 ก้อน (byte)
    entry = 32 + nbytes + LAMBDA_BYTES + PROOF_BYTES  # 1 entry = UT + e + C_ST + vt
    distinct = len({w for _, kws in docs for w in kws})  # จำนวน keyword ไม่ซ้ำ = จำนวน entry ต่อผู้ใช้
    full_bytes = distinct * entry * users         # ขนาด index เต็ม (byte)
    scope = args.scope                            # แบบที่ผู้ใช้เลือก
    if scope == "auto":                           # เลือกให้อัตโนมัติ
        scope = "full" if full_bytes <= args.max_edb_gb * 1e9 or needed is None else "queried"
    if scope == "queried":                        # สร้างเฉพาะคำที่ใช้
        docs = [(i, kws & needed) for i, kws in docs if kws & needed]  # ตัดคำที่ไม่ใช้ออก (bitmap ของคำที่เหลือครบ)
    used = len({w for _, kws in docs for w in kws}) * entry * users  # ขนาดที่จะสร้างจริง
    tmpdir = None                                 # โฟลเดอร์ชั่วคราวของ SQLite
    if args.edb == "sqlite" or (args.edb == "auto" and used > args.ram_limit_gb * 1e9):  # ใหญ่เกิน RAM
        tmpdir = tempfile.mkdtemp(prefix="chen_edb_")  # สร้างโฟลเดอร์ชั่วคราว
        edb = SqliteEDB(gamma, os.path.join(tmpdir, "edb.sqlite"))  # EDB บนดิสก์
    else:                                         # ไม่งั้นเก็บใน RAM
        edb = MemoryEDB(gamma)                    # EDB ใน dict
    do = DataOwner(gamma)                         # Alg.1 Setup
    cs = CloudServer(gamma, edb)                  # CS ที่ EDB ว่าง
    dus = []                                      # รายชื่อ DU
    t0 = time.perf_counter()                      # จับเวลา outsource
    for k in range(users):                        # ทุกผู้ใช้
        name = f"DU{k + 1}"                       # ชื่อผู้ใช้
        keys = do.register_user(name)             # DO สร้างคีย์ให้
        do.share(name, docs, cs)                  # Alg.2 Share ทุกเอกสาร (แบบ batch, ดู [ASSUMPTION] 8)
        dus.append(DataUser(name, keys, gamma))   # DU ถือคีย์
    t_out = (time.perf_counter() - t0) * 1e3      # เวลา outsource (ms)
    for du in dus:                                # sync ครั้งแรก (ทำครั้งเดียว ไม่นับเป็นต้นทุนต่อ query)
        du.sync(cs)                               # ดึงคิว
    info = dict(index_scope=scope, gamma=gamma, keywords=distinct,  # ข้อมูลของ setup
                edb_entries=distinct * users, cs_storage_bytes=full_bytes,
                outsource_ms=t_out if scope == "full" else "",  # เวลา outsource มีความหมายเฉพาะแบบ full
                edb_backend="sqlite" if tmpdir else "memory")
    return do, cs, dus, info, tmpdir             # คืนทุกอย่าง


def teardown(cs, tmpdir):
    """ปิด EDB และลบไฟล์ SQLite ชั่วคราว"""
    cs.EDB.close()                                # ปิด EDB
    if tmpdir:                                    # ถ้าใช้ SQLite
        for f in os.listdir(tmpdir):              # ลบทุกไฟล์ในโฟลเดอร์
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)                          # ลบโฟลเดอร์
    gc.collect()                                  # คืน RAM ก่อนรอบถัดไป


def print_setup(n, info):
    """แสดงข้อมูลของ setup"""
    t = f"{info['outsource_ms'] / 1e3:.1f}s" if info["outsource_ms"] != "" else "-"  # เวลา outsource
    print(f" N={n}: scope={info['index_scope']} outsource={t} keywords={info['keywords']} "
          f"full EDB={info['cs_storage_bytes'] / 1e9:.2f} GB ({info['edb_backend']})")


def run_query(du, cs, q):
    """query เต็มหนึ่งรอบ: DU สร้าง token -> CS ค้นหา+รวม proof -> DU ถอด+AND -> DU verify
    คืน (เวลาแยกตามขั้น, จำนวน operation แยกตามขั้น, ข้อมูลขนาด/ผลลัพธ์)"""
    COUNT.reset()                                 # ล้างตัวนับ
    t0 = time.perf_counter()                      # เริ่ม
    du.sync(cs)                                   # Alg.4 L1-5 (คิวว่างเพราะ sync ไปตอน setup แล้ว)
    tokens = du.gen_token(q)                      # Alg.4 L6-15
    t1 = time.perf_counter()                      # จบ query generation
    c_q = COUNT.snapshot()                        # นับ T_PRF ตอนสร้าง token (ควร = kQ)
    if tokens is None:                            # มี keyword ที่ไม่อยู่ใน index
        return ({"query_gen": (t1 - t0) * 1e3, "server_total": 0.0, "du_decrypt": 0.0,
                 "verify_total": 0.0, "end_to_end": (t1 - t0) * 1e3}, {}, dict(rQ=0, pQ=0, ids=set()))
    COUNT.reset()                                 # ล้างก่อนวัด search
    R = cs.search(tokens)                         # Alg.4 L16-33
    t2 = time.perf_counter()                      # จบ server search
    c_s = COUNT.snapshot()                        # นับ T_H / T_A / T_X ฝั่ง CS
    Bs, bitmaps = du.decrypt(q, R)                # Alg.4 L34-43
    ids = ids_from_bitmap(Bs)                     # แปลงผลเป็นรายการ id
    t3 = time.perf_counter()                      # จบการถอด
    COUNT.reset()                                 # ล้างก่อนวัด verify
    ok = du.verify(q, bitmaps, R)                 # Alg.5
    t4 = time.perf_counter()                      # จบ verify
    c_v = COUNT.snapshot()                        # นับ T_PRF / T_X ตอน verify
    assert ok                                     # ระหว่าง benchmark ผลต้องผ่านการตรวจเสมอ
    times = {
        "query_gen": (t1 - t0) * 1e3,             # สร้าง token
        "server_total": (t2 - t1) * 1e3,          # ทุกอย่างที่ CS ทำ (เดิน chain + Add + XOR proof)
        "du_decrypt": (t3 - t2) * 1e3,            # DU รวมคีย์ H3 + Dec + AND
        "verify_total": (t4 - t3) * 1e3,          # Alg.5
        "end_to_end": (t4 - t0) * 1e3,            # รวมทุกขั้น (ไม่รวม network)
    }
    ops = dict(prf_qgen=c_q["prf"], hash_search=c_s["hash"], add_search=c_s["add"],  # จำนวน op
               xor_search=c_s["xor"], visited=c_s["visited"], prf_verify=c_v["prf"], xor_verify=c_v["xor"])
    nbytes = cs.he.nbytes                         # ขนาด Sum_e 1 ก้อน
    info = dict(rQ=len(ids), pQ=sum(popcount(b) for b in bitmaps),  # จำนวนผลลัพธ์ / ผลรวม posting
                proof_bytes=len(R) * W.HASH,      # ขนาด proof (vt 32 byte ต่อ keyword)
                token_bytes=sum(t.size_bytes() for t in tokens),  # ขนาด token ที่ DU ส่ง
                # response = (Sum_e + vt) ต่อ keyword + ไฟล์ผลลัพธ์ (id + ciphertext มาตรฐาน) ตาม wire_sizes.py
                response_bytes=len(R) * (nbytes + W.HASH)
                + sum(W.result_entry_bytes(W.std_ct_bytes(FILE_LEN.get(i, 0))) for i in ids),
                ids=set(ids))                     # ผลลัพธ์ (ไว้เทียบกับ ground truth ไม่เขียนลง CSV)
    return times, ops, info                       # คืนผล


def measure(du, cs, q, reps, warmup):
    """warm-up ก่อน แล้ววัดจริง reps รอบ ปิด garbage collector ระหว่างวัด (เหมือน SE-COLLAB)
    หมายเหตุ: search ครั้งแรกรวม entry ของ keyword เป็นก้อนเดียว รอบที่วัดจริงจึงเป็นสถานะหลังรวมแล้ว
    (ตอนเริ่ม chain ยาว 1 อยู่แล้วเพราะ setup ทำ Share ครั้งเดียว ผลจึงเท่ากัน)"""
    for _ in range(warmup):                       # รอบอุ่นเครื่อง
        run_query(du, cs, q)                      # ไม่บันทึก
    samples, ops, info = [], {}, {}               # ที่เก็บผล
    gc.disable()                                  # ปิด GC ไม่ให้กระโดดเข้ามาทำให้เวลาแกว่ง
    try:
        for _ in range(max(1, reps)):             # รอบที่วัดจริง
            m, ops, info = run_query(du, cs, q)   # วัด
            samples.append(m)                     # เก็บเวลา
    finally:
        gc.enable()                               # เปิด GC กลับ
    return summarize(samples), ops, info          # สรุปเวลา + op + ขนาด


# ============================================================================
# 6) Experiments (ตาม AMTP Section V-B)
# ============================================================================
def suite_exp1(args):
    """AMTP Exp.1: วนทุกขนาด N x ทุก k_Q x query 4 รูปแบบ (Chen รองรับแค่ AND -> แบบอื่นเขียน N/A)
    By default it replays the shared results/exp1_queries.json (or the file given with --queries), like Du and
    SE-COLLAB. Only if that file does not exist are queries generated with amtp_dataset.make_queries (same seed =
    same queries) and saved as the shared file, so an existing shared file is never overwritten.
    ทุก query ที่รองรับจะถูกเทียบกับ ground truth จาก plaintext index -> ผลต้องตรงเป๊ะ"""
    D = dataset()                                 # dataset กลาง
    path = args.queries or SHARED_QUERIES         # query file to replay (shared file by default)
    replay = None                                 # query ที่โหลดจากไฟล์
    if os.path.exists(path):                      # replay the shared workload
        with open(path, encoding="utf-8") as f:   # เปิดไฟล์
            replay = json.load(f)                 # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(replay)} queries)")
    elif args.queries:                            # an explicit file that does not exist is an error
        raise SystemExit(f"query file not found: {path}")
    else:
        print("[queries] no shared query file -> generating with amtp_dataset.make_queries (same seed = same queries)")
    sizes = sorted({x["N"] for x in replay}) if replay else args.sizes  # ขนาดที่ต้องรัน
    print(f"[exp1] Boolean search scalability  sizes={sizes}")
    w = Writer("exp1_boolean_scalability", args.out)  # ไฟล์ผล
    exported = []                                 # query ที่จะบันทึกออก
    for n in sizes:                               # ทุกขนาด database
        src = D.sample(n, args.domains, args.data)  # เอกสาร n ไฟล์ (ชุดเดียวกันทุก scheme)
        docs = to_chen(src)                       # แปลงรูปแบบ
        inv = D.inverted_index(src)               # plaintext index ไว้หา ground truth
        if replay:                                # ใช้ query จากไฟล์
            qs = [x for x in replay if x["N"] == n]
        else:                                     # สร้าง query เอง
            qs = [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
            exported += [dict(q, dataset=D.DATASET_TAG, seed=args.seed, domains=args.domains) for q in qs]
        needed = {t for q in qs if supports(q["shape"]) for t in parse_and_query(q["query"])}  # คำที่ต้องค้น
        do, cs, dus, info, tmp = setup(docs, n, args, needed=needed)  # gamma = N  ([ASSUMPTION] 6)
        print_setup(n, info)                      # แสดงข้อมูล
        for q in qs:                              # ทุก query
            base = dict(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""))  # คอลัมน์หลัก
            if not supports(q["shape"]):          # OR / nested
                w.add(**base, status="N/A")       # บันทึกว่าไม่รองรับ
                continue                          # ข้าม
            terms = parse_and_query(q["query"])   # keyword ของ query
            res, ops, qi = measure(dus[0], cs, terms, args.reps, args.warmup)  # วัด
            gt = D.ground_truth(inv, terms)       # คำตอบที่ถูกต้อง
            assert qi.pop("ids") == gt, f"ผลค้นหาไม่ตรง ground truth: {q['query']}"  # ต้องตรงเป๊ะ
            w.add(**base, status="ok", index_scope=info["index_scope"],
                  keywords=info["keywords"], cs_storage_bytes=info["cs_storage_bytes"],  # full index size (computed)
                  **qi, **res, **ops)  # บันทึก
        del do, dus, docs, src, inv               # คืน RAM
        teardown(cs, tmp)                         # ปิด/ลบ EDB
    w.close()                                     # เขียน CSV
    if exported:                                  # บันทึก query ที่สร้าง
        qpath = SHARED_QUERIES                    # ไฟล์ query กลาง (นอกโฟลเดอร์ chen/)
        D.save_queries(qpath, exported)           # เขียน
        print(f"-> {os.path.relpath(qpath)}  (replay the identical workload in AMTP / other baselines)")


def suite_exp2(args):
    """AMTP Exp.2: proof/verification เทียบกับ r_Q บนเอกสารชุดเดียวกับทุก scheme
    (results/exp2_layouts.json: clustered / dispersed / partition_spread ฝัง keyword เดียวกันในไฟล์เดียวกัน)
    Chen ไม่มี partition และ Merkle tree: verify ต้องคำนวณ F1(id) ของทุกผลลัพธ์ จึงขึ้นกับ r_Q อย่างเดียว
    แต่ end-to-end ไม่เท่ากันทุก layout: ids_from_bitmap ไล่ bitmap ถึงบิตสูงสุดที่เป็น 1 (implementation
    ไม่ใช่ตัวอัลกอริทึม) -> layout ที่มีไฟล์อยู่ท้าย ๆ (dispersed) ถอดผลนานกว่า clustered ที่จบแถว N/3"""
    D = dataset()                                 # dataset กลาง
    lay = D.load_exp2_layouts()                   # layout กลาง
    n = lay["N"]                                  # ขนาด database (ตามไฟล์กลาง)
    print(f"[exp2] selective proof / verification  N={n} layouts={list(lay['layouts'])}")
    docs = to_chen(D.sample(n, lay["domains"], args.data))  # เอกสาร n ไฟล์
    for i, words in D.exp2_markers(lay, n).items():  # ฝัง keyword ให้มีผลลัพธ์พอดี r ไฟล์
        docs[i][1].update(words)
    needed = {f"{v['prefix']}{r}" for v in lay["layouts"].values() for r in lay["rq"]}  # คำที่ต้องค้น
    do, cs, dus, info, tmp = setup(docs, n, args, needed=needed)  # สร้างระบบ
    print_setup(n, info)                          # แสดงข้อมูล
    w = Writer("exp2_selective_proof", args.out)  # ไฟล์ผล
    for r in lay["rq"]:                           # ทุก r_Q
        for name, spec in lay["layouts"].items():  # ทุก layout
            res, ops, qi = measure(dus[0], cs, [f"{spec['prefix']}{r}"], args.reps, args.warmup)  # วัด
            qi.pop("ids")                         # ไม่ต้องเขียนรายการ id
            assert qi["rQ"] == r                  # ต้องได้ผลพอดี r ไฟล์
            w.add(N=n, rQ=r, layout=name, proof_bytes=qi["proof_bytes"],
                  response_bytes=qi["response_bytes"], **res, **ops)  # บันทึก
    w.close()                                     # เขียน CSV
    teardown(cs, tmp)                             # ปิด/ลบ EDB


def run_tampered(du, cs, q, kind, ids):
    """query หนึ่งรอบที่ CS โกง แล้วจับเวลาเฉพาะ DU verify (Alg.5) คืน ({verify_total}, {detected})
    hide: ผลที่ DU ได้ขาดเอกสารตำแหน่ง ids; inject: ผลมีเอกสารตำแหน่ง ids ที่ไม่ตรง query เพิ่มเข้ามา
    [ASSUMPTION] [40] บวก ciphertext แบบ homomorphic (Sum_e = bitmap + Sum_sk mod 2^gamma) CS ที่โกงจึงบวก / ลบ 2^id
    กับ Sum_e ได้ ผลที่ DU ถอดได้ = bitmap ที่บิตนั้นเปลี่ยน จำลองโดยแก้บิตหลังถอด (เหมือน t_reject_missing)"""
    du.sync(cs)
    tokens = du.gen_token(q)
    R = cs.search(tokens)
    _, bitmaps = du.decrypt(q, R)
    if ids and kind == "hide":
        for doc_id in ids:
            bitmaps[0] &= ~(1 << doc_id)
    elif ids and kind == "inject":
        for doc_id in ids:
            bitmaps[0] |= 1 << doc_id
    t0 = time.perf_counter()
    ok = du.verify(q, bitmaps, R)
    t1 = time.perf_counter()
    return {"verify_total": (t1 - t0) * 1e3}, {"detected": not ok}


# ---------------- dataset-v4 suites (แผนของอาจารย์; ไฟล์กลางใน datasets/arxiv/data_v4/ ใช้ร่วมกับทุก scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl ทุก domain ทุกขนาด files-per-domain
    (Chen รองรับ single / AND ซึ่งเป็นทุกรูปแบบของไฟล์นี้) ผลต้องเท่ากับ result_size และ ground truth"""
    D = dataset()
    qs = D.search_single_queries()
    plan = D.search1_points(qs, args.fpd, args.fix, args.s1_kq, args.all_points)
    print(f"[search1] domains={args.s_domains} files/domain={args.fpd} queries={len(qs)} "
          f"points={sum(map(len, plan.values()))}")
    w = Writer("search_single", args.out)
    for dname in args.s_domains:
        for n in args.fpd:
            mine = [q for q in plan[n] if q["domain"] == dname]
            if not mine:
                continue
            src = D.domain_docs(dname, n, args.data)
            inv = D.inverted_index(src)
            needed = {k for q in mine for k in q["keywords"]}
            do, cs, dus, info, tmp = setup(to_chen(src), n, args, needed=needed)
            print_setup(n, info)
            for q in mine:
                res, ops, qi = measure(dus[0], cs, q["keywords"], args.reps, args.warmup)
                ids = qi.pop("ids")
                assert len(ids) == q["result_size"][str(n)] and ids == D.ground_truth(inv, q["keywords"]), \
                    f"ผลไม่ตรง: {q['query_id']} n={n}"
                w.add(scheme="Chen[40]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", index_scope=info.get("index_scope", ""), **qi, **res, **ops)
            teardown(cs, tmp)
            del do, cs, dus, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): verify_keywords.csv แถว single_domain ที่ --fix ไฟล์ต่อ domain (ค่าอ้างอิง:
    Chen ไม่มี Merkle proof ตรวจด้วย F1(id) ทุกผลลัพธ์)"""
    D = dataset()
    rows = D.verify_keywords("single_domain", args.fix)
    print(f"[verify1] files/domain={args.fix} keywords={len(rows)}")
    w = Writer("verify_single", args.out)
    for dname in args.s_domains:
        mine = [r for r in rows if r["domain"] == dname]
        do, cs, dus, info, tmp = setup(to_chen(D.domain_docs(dname, args.fix, args.data)), args.fix, args,
                                       needed={r["keyword"] for r in mine})
        print_setup(args.fix, info)
        for r in mine:
            res, ops, qi = measure(dus[0], cs, [r["keyword"]], args.reps, args.warmup)
            qi.pop("ids")
            assert qi["rQ"] == r["result_size"], f"{r['keyword']}: {qi['rQ']} != {r['result_size']}"
            w.add(scheme="Chen[40]", domain=dname, N=args.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", **qi, **res, **ops)
        teardown(cs, tmp)
        del do, cs, dus
        gc.collect()
    w.close()


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl ต่อ domain: keyword (~2,000 ผลลัพธ์) ที่ files_per_domain
    CS ซ่อนเอกสาร t ตัวแรกของ tamper_order (hide) หรือใส่เอกสาร t ตัวแรกของ amtp_dataset.inject_order ที่ไม่ตรง query
    (inject) วัดเวลา verify และนับว่าจับได้กี่รอบ
    modify / old_version = N/A: [40] คืนแค่ bitmap ของ id (Sum_e, proof) ไม่ได้คืนหรือรับรอง ciphertext ของไฟล์
    localized = 0: proof ของ [40] เป็นค่า XOR รวมก้อนเดียวต่อ keyword ตรวจได้แค่ผ่าน / ไม่ผ่าน ชี้ตัวเอกสารไม่ได้
    (full check จึงเท่ากับ verify ปกติ)"""
    D = dataset()
    sets = [r for r in D.tamper_sets() if r["domain"] in args.s_domains]
    w = Writer("tamper_detection", args.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = D.domain_docs(dname, n, args.data)
        pos_of = {d.doc_id: i for i, d in enumerate(src)}
        inj = D.inject_order(ts, args.data)
        q = [ts["query_keyword"]]
        do, cs, dus, info, tmp = setup(to_chen(src), n, args, needed=set(q))
        print_setup(n, info)
        base = dict(scheme="Chen[40]", domain=dname, N=n, keyword=q[0], rQ=ts["result_size"])

        def measure_t(kind, ids):
            for _ in range(args.warmup):
                run_tampered(dus[0], cs, q, kind, ids)
            samples, det = [], 0
            gc.disable()
            try:
                for _ in range(max(1, args.reps)):
                    m, i = run_tampered(dus[0], cs, q, kind, ids)
                    samples.append(m)
                    det += i["detected"]
            finally:
                gc.enable()
            return summarize(samples), det, len(samples)

        res, det, runs = measure_t("none", None)
        assert det == 0, "ผลที่ซื่อสัตย์ไม่ผ่าน verify"
        w.add(**base, tamper="none", tampered=0, status="ok", detected_runs=0, runs=runs, localized=0, **res)
        for kind in args.tamper_kinds:
            for t in ts["tamper_counts"]:
                if kind in ("modify", "old_version"):
                    w.add(**base, tamper=kind, tampered=t, status="N/A")
                    continue
                ids = [pos_of[i] for i in (inj if kind == "inject" else ts["tamper_order"])[:t]]
                res, det, runs = measure_t(kind, ids)
                w.add(**base, tamper=kind, tampered=t, status="ok", detected_runs=det, runs=runs, localized=0, **res)
        teardown(cs, tmp)
        del do, cs, dus, src
        gc.collect()
    w.close()


def compact(dus, cs, keywords):
    """(ไม่จับเวลา) ให้ผู้ใช้ค้น keyword ที่ถูกแตะ เพื่อให้ CS รวม entry เป็นก้อนเดียวตามกลไกของ [40]
    ป้องกัน EDB บวมระหว่างการทดลองที่ทำซ้ำหลายรอบ"""
    for du in dus:                                # ทุกผู้ใช้
        du.sync(cs)                               # ดึงคิว
        toks = [t[0] for t in (du.gen_token([w]) for w in keywords) if t]  # token ราย keyword
        cs.search(toks)                           # CS เดินและรวม entry


def suite_exp3(args):
    """AMTP Exp.3: dynamic update — insert เอกสารจริงจาก insert pool b ไฟล์ แล้ว delete ชุดเดิม
    (ขนาดฐานข้อมูลคงที่ที่ N)  --update-mode per-doc = เรียก Share/Update ทีละเอกสารตาม paper,
    --users = N_u (ต้นทุนโตตาม N_u · m)"""
    D = dataset()                                 # dataset กลาง
    print(f"[exp3] dynamic update  sizes={args.sizes} batches={args.batches} users={args.users} "
          f"mode={args.update_mode}")
    pool = D.insert_pool(args.domains, args.data)  # เอกสารใหม่ที่ไม่อยู่ในชุดเริ่มต้น (v4: 50,000 ไฟล์)
    # ต้นทุน update ของ [40] ไม่ขึ้นกับ entry ที่มีอยู่แล้ว (ทุก keyword-update สร้าง entry ใหม่ O(1) ต่อผู้ใช้)
    # จึงไม่สร้าง index เริ่มต้นเลย (scope=queried, needed ว่าง) และเก็บ EDB ใน RAM ที่ทุก N
    # -> ทุก N วัดด้วยวิธีเดียวกัน (เดิม scope=auto สร้าง index เต็มที่ 10k / 50k แต่ไม่สร้างที่ 100k / 200k)
    args.scope, args.edb = "queried", "memory"    # บังคับเหมือนกันทุก N (ไม่ขึ้นกับ --scope / --edb)
    needed = set()                                # ไม่ต้องมี entry เริ่มต้นสำหรับการวัด update
    w = Writer("exp3_dynamic_update", args.out)   # ไฟล์ผล
    for n in args.sizes:                          # ทุกขนาด database
        docs = to_chen(D.sample(n, args.domains, args.data))  # เอกสารเริ่มต้น n ไฟล์
        gamma = n + max(args.batches)             # เผื่อบิตให้เอกสารใหม่ ([ASSUMPTION] 6)
        do, cs, dus, info, tmp = setup(docs, gamma, args, users=args.users, needed=needed)  # สร้างระบบ
        print_setup(n, info)                      # แสดงข้อมูล
        nbytes = cs.he.nbytes                     # ขนาด e_c
        cursor = 0                                # ตำแหน่งใน insert pool (วนซ้ำเมื่อหมด)
        for b in args.batches:                    # ทุกขนาด batch
            ins, dele = [], []                    # เวลาแต่ละรอบ
            ops_ins = ops_del = {}                # จำนวน op ของรอบสุดท้าย
            pairs_all, bytes_ins, bytes_del = [], [], []  # จำนวนคู่ / ขนาดข้อความ
            for r in range(args.warmup + args.reps):  # warm-up + รอบจริง
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]  # เอกสารจริง b ไฟล์จาก pool
                cursor = (cursor + b) % len(pool)  # เลื่อนตำแหน่ง
                new = to_chen(batch, start=n)     # ตำแหน่งบิต n .. n+b-1 (ว่างอยู่เพราะลบทุกรอบ)
                pairs = sum(len(k) for _, k in new)  # จำนวนคู่ keyword-document
                gc.disable()                      # ปิด GC ระหว่างจับเวลา
                try:
                    COUNT.reset()                 # ล้างตัวนับ
                    mb = 0                        # ขนาดข้อความ DO -> CS
                    t0 = time.perf_counter()      # ---- INSERT (Alg.2 Share ให้ทุกผู้ใช้) ----
                    if args.update_mode == "per-doc":  # ตาม paper: ทีละเอกสาร
                        for d in new:
                            for du in dus:        # ทุกผู้ใช้ที่ได้สิทธิ์ -> O(N_u · m)
                                mb += do.share(du.u, [d], cs)[1].size_bytes(nbytes)
                    else:                         # batch: รวม keyword เดียวกันเป็น entry เดียว
                        for du in dus:
                            mb += do.share(du.u, new, cs)[1].size_bytes(nbytes)
                    t_ins = (time.perf_counter() - t0) * 1e3  # เวลา insert (ms)
                    c_ins, b_ins = COUNT.snapshot(), mb  # op และขนาดของ insert
                    COUNT.reset()                 # ล้างตัวนับ
                    mb = 0                        # รีเซ็ตขนาด
                    t0 = time.perf_counter()      # ---- DELETE (Alg.3 Update, op = DEL) ----
                    if args.update_mode == "per-doc":  # ทีละเอกสาร
                        for doc_id, _ in new:
                            mb += sum(m.size_bytes(nbytes) for m in do.update([(doc_id, None)], DEL, cs))
                    else:                         # batch
                        mb += sum(m.size_bytes(nbytes) for m in do.update([(i, None) for i, _ in new], DEL, cs))
                    t_del = (time.perf_counter() - t0) * 1e3  # เวลา delete (ms)
                    c_del, b_del = COUNT.snapshot(), mb  # op และขนาดของ delete
                finally:
                    gc.enable()                   # เปิด GC กลับ
                compact(dus, cs, {x for _, k in new for x in k})  # รวม entry (ไม่จับเวลา)
                if r < args.warmup:               # รอบอุ่นเครื่อง
                    continue                      # ไม่บันทึก
                ins.append({"update": t_ins})     # เก็บเวลา insert
                dele.append({"update": t_del})    # เก็บเวลา delete
                ops_ins, ops_del = c_ins, c_del   # op ของรอบล่าสุด
                pairs_all.append(pairs)           # จำนวนคู่
                bytes_ins.append(b_ins)           # ขนาดข้อความ insert
                bytes_del.append(b_del)           # ขนาดข้อความ delete
            for op, samples, ops, mbytes in (("insert", ins, ops_ins, bytes_ins),
                                             ("delete", dele, ops_del, bytes_del)):  # บันทึกทั้งสอง op
                res = summarize(samples)          # update_ms / _median / _std
                mean_ms = res["update_ms"]        # เวลาเฉลี่ยทั้ง batch
                w.add(N=n, batch=b, op=op, users=args.users, update_mode=args.update_mode,
                      index_scope=info["index_scope"], edb_backend=info["edb_backend"],
                      pairs=st.mean(pairs_all),
                      message_bytes=st.mean(mbytes), **res,
                      per_doc_ms=mean_ms / b,     # เวลาเฉลี่ยต่อเอกสาร
                      throughput_docs_s=b / (mean_ms / 1e3),  # เอกสารต่อวินาที
                      throughput_pairs_s=st.mean(pairs_all) / (mean_ms / 1e3),  # คู่ keyword-document ต่อวินาที
                      prf=ops["prf"], hash=ops["hash"], enc=ops["enc"], xor=ops["xor"])  # จำนวน op (รอบล่าสุด)
        del do, dus, docs                         # คืน RAM
        teardown(cs, tmp)                         # ปิด/ลบ EDB
    w.close()                                     # เขียน CSV



# ============================================================================
# 7) Demo — ตัวอย่างเล็ก ๆ ให้เห็นทุกขั้นตอน  (python3 chen_et_al_sim.py demo)
# ============================================================================

def run_demo(_args=None):
    g = 8  # bitmap 8 บิต = รองรับเอกสาร id 0-7 (เล็ก ๆ ให้อ่านง่าย)

    def show_bits(x: int) -> str:
        return "".join("1" if x >> i & 1 else "0" for i in range(g))  # บิตของ f0 อยู่ซ้ายสุด (แบบ Fig. 1)

    print("=== 1) Setup ===")  # ขั้นที่ 1
    do = DataOwner(g)  # DO ทำ Setup (n = 2^8)
    cs = CloudServer(g)  # CS เริ่มด้วย EDB ว่าง
    print(f"n = 2^{g} = {do.he.n}")  # แสดง public parameter

    print("\n=== 2) Share: DO แชร์ 4 เอกสารให้ alice ===")  # ขั้นที่ 2
    docs = [(0, ["w1", "w2"]), (1, ["w2"]), (2, ["w1", "w2"]), (3, ["w1"])]  # เอกสารตัวอย่าง
    keys, msg = do.share("alice", docs, cs)  # Alg.2
    for ut, e, c_st, vt in msg.entries:  # โชว์ entry ที่ CS ได้รับ
        print(f"  UT={ut.hex()[:12]}..  e_c={show_bits(e)} (สุ่ม อ่านไม่ออก)  vt={vt.hex()[:12]}..")  # CS เห็นแค่นี้
    print(f"  EDB มี {len(cs.EDB)} entry, คิวของ alice มี {len(cs.Queues['alice'])} diff")  # สถานะ CS

    print("\n=== 3) Search: alice ค้น w1 AND w2 ===")  # ขั้นที่ 3
    du = DataUser("alice", keys, g)  # alice ได้คีย์จาก DO
    du.sync(cs)  # ดึงคิว -> รู้ state ล่าสุดของ w1, w2
    q = ["w1", "w2"]  # query
    tokens = du.gen_token(q)  # สร้าง token
    R = cs.search(tokens)  # CS ค้นและรวมผล
    Bs, bitmaps = du.decrypt(q, R)  # alice ถอด
    for w, bs in zip(q, bitmaps):  # โชว์ bitmap ของแต่ละคำ
        print(f"  bs_{w} = {show_bits(bs)}  -> เอกสาร {ids_from_bitmap(bs)}")  # หลังถอดรหัส
    print(f"  AND    = {show_bits(Bs)}  -> ผลลัพธ์ {ids_from_bitmap(Bs)}")  # ผล AND
    print(f"  verify = {du.verify(q, bitmaps, R)}")  # ผลตรวจ

    print("\n=== 4) Update: เพิ่ม w1 ให้ f1 แล้วลบ f2 ทั้งไฟล์ ===")  # ขั้นที่ 4
    old_ut = H1(tokens[0].K_w, tokens[0].ST_c)  # ที่อยู่ที่ CS รู้จากการค้นครั้งก่อน
    m = do.update([(1, ["w1"])], ADD, cs)[0]  # Alg.3 เพิ่ม
    print(f"  UT ใหม่ = {m.entries[0][0].hex()[:12]}..  (ไม่ใช่ {old_ut.hex()[:12]}.. -> forward privacy)")  # ที่อยู่ใหม่
    do.update([(2, None)], DEL, cs)  # Alg.3 ลบทั้งไฟล์
    ids, ok = du.search(q, cs)  # ค้นใหม่
    print(f"  w1 AND w2 -> {ids}  verify={ok}")  # ควรได้ [0, 1]

    print("\n=== 5) CS โกง: ซ่อนเอกสาร 1 ไฟล์ ===")  # ขั้นที่ 5
    du.sync(cs)  # ดึงคิว (ว่าง)
    R = cs.search(du.gen_token(["w1"]))  # CS ค้นตามปกติ
    Bs, bitmaps = du.decrypt(["w1"], R)  # alice ถอด
    bitmaps[0] &= ~1  # สมมติผลที่ได้ขาดเอกสาร f0
    print(f"  verify = {du.verify(['w1'], bitmaps, R)}  (ต้องเป็น False)")  # ต้องจับได้


# ============================================================================
# 8) Selftest — ทดสอบความถูกต้อง  (python3 chen_et_al_sim.py selftest)
# ============================================================================

def run_selftest(_args=None):
    g = 64  # bitmap 64 บิต พอสำหรับทดสอบ
    base_docs = [(0, ["cancer", "biopsy"]), (1, ["fraud", "bank"]),  # ฐานข้อมูลตัวอย่าง
                 (2, ["cancer", "fraud", "bank"]), (3, ["cancer", "bank"])]

    def make(edb=None):
        """สร้างระบบใหม่: DO + CS + DU 'alice' ที่เห็นทุกเอกสาร"""
        do = DataOwner(g)  # Setup
        cs = CloudServer(g, edb)  # CS
        keys, _ = do.share("alice", base_docs, cs)  # Share ทุกเอกสารให้ alice
        return do, cs, DataUser("alice", keys, g)  # คืนทั้งสามฝ่าย

    def t_fig1():  # ตัวอย่าง Fig. 1(c): ลบ f3 จาก 1100 (mod 2^4) ได้ 0100
        he = HomAdd(4)  # gamma = 4
        assert ids_from_bitmap(he.add(bitmap_from_ids([2, 3], 4), he.neg(bitmap_from_ids([3], 4)))) == [2]

    def t_search():  # ค้นคำเดียวและหลายคำ
        do, cs, du = make()
        assert du.search(["cancer"], cs) == ([0, 2, 3], True)
        assert du.search(["cancer", "bank"], cs) == ([2, 3], True)
        assert du.search(["cancer", "fraud", "bank"], cs) == ([2], True)

    def t_unknown():  # keyword ที่ไม่มี -> ว่าง
        do, cs, du = make()
        assert du.search(["nothing"], cs) == ([], True)

    def t_updates():  # เพิ่ม / ลบ keyword / ลบทั้งไฟล์
        do, cs, du = make()
        do.update([(1, ["cancer"])], ADD, cs)
        assert du.search(["cancer"], cs) == ([0, 1, 2, 3], True)
        do.update([(2, ["cancer"])], DEL, cs)
        assert du.search(["cancer"], cs) == ([0, 1, 3], True)
        do.update([(3, None)], DEL, cs)
        assert du.search(["cancer"], cs) == ([0, 1], True)
        assert du.search(["bank"], cs) == ([1, 2], True)

    def t_aggregation():  # ค้นซ้ำหลัง CS รวม entry (C = ⊥) ต้องได้ผลเดิม
        do, cs, du = make()
        first = du.search(["bank"], cs)
        n = len(cs.EDB)
        assert first == du.search(["bank"], cs) == ([1, 2, 3], True) and len(cs.EDB) == n
        do.update([(0, ["bank"])], ADD, cs)
        assert du.search(["bank"], cs) == ([0, 1, 2, 3], True)

    def t_long_chain():  # เพิ่มทีละไฟล์ 20 ครั้ง (chain ยาว)
        do, cs, du = make()
        for i in range(10, 30):
            do.share("alice", [(i, ["bank", "new"])], cs)
        assert du.search(["bank", "new"], cs) == (list(range(10, 30)), True)

    def t_reject_missing():  # CS ซ่อนเอกสาร -> reject
        do, cs, du = make()
        du.sync(cs)
        R = cs.search(du.gen_token(["cancer"]))
        _, bms = du.decrypt(["cancer"], R)
        bms[0] &= ~(1 << 2)
        assert du.verify(["cancer"], bms, R) is False

    def t_reject_dropped():  # CS ข้าม entry เก่าตอนรวมผล -> reject
        do, cs, du = make()
        do.update([(1, ["cancer"])], ADD, cs)
        du.sync(cs)
        tok = du.gen_token(["cancer"])[0]
        e_new, _, vt_new = cs.EDB.get(H1(tok.K_w, tok.ST_c))
        R = [(e_new, vt_new)]
        _, bms = du.decrypt(["cancer"], R)
        assert du.verify(["cancer"], bms, R) is False

    def t_reject_dropped_keyword():  # CS ส่งผลไม่ครบทุก keyword ใน query (ตัด "bank" ทิ้ง) -> reject
        do, cs, du = make()
        du.sync(cs)
        q = ["cancer", "bank"]
        R = cs.search(du.gen_token(q))[:1]  # เหลือแค่ผลของ "cancer"
        _, bms = du.decrypt(q, R)
        assert du.verify(q, bms, R) is False

    def t_reject_forged():  # CS ปลอม proof -> reject
        do, cs, du = make()
        du.sync(cs)
        Sum_e, proof = cs.search(du.gen_token(["bank"]))[0]
        R = [(Sum_e, bytes(len(proof)))]
        _, bms = du.decrypt(["bank"], R)
        assert du.verify(["bank"], bms, R) is False

    def t_forward():  # update ใหม่ได้ UT ใหม่ที่ token เก่าคำนวณไม่ได้
        do, cs, du = make()
        du.sync(cs)
        old = du.gen_token(["bank"])[0]
        msgs = do.update([(0, ["bank"])], ADD, cs)
        assert msgs[0].entries[0][0] != H1(old.K_w, old.ST_c)

    def t_multi_user():  # bob เห็นแค่บางเอกสาร และลบแล้วต้องหายจากทุกคน
        do, cs, du_a = make()
        keys_b, _ = do.share("bob", base_docs[:2], cs)
        du_b = DataUser("bob", keys_b, g)
        assert du_b.search(["cancer"], cs) == ([0], True)
        assert du_a.search(["cancer"], cs) == ([0, 2, 3], True)
        do.update([(0, None)], DEL, cs)
        assert du_b.search(["cancer"], cs) == ([], True)
        assert du_a.search(["cancer"], cs) == ([2, 3], True)

    def t_sqlite():  # EDB แบบ SQLite ต้องได้ผลเหมือนแบบ RAM
        with tempfile.TemporaryDirectory() as d:
            edb = SqliteEDB(g, os.path.join(d, "edb.sqlite"))
            do, cs, du = make(edb)
            do.update([(1, ["cancer"])], ADD, cs)
            assert du.search(["cancer", "bank"], cs) == ([1, 2, 3], True)
            edb.close()

    tests = [t_fig1, t_search, t_unknown, t_updates, t_aggregation, t_long_chain,  # รายการทดสอบทั้งหมด
             t_reject_missing, t_reject_dropped, t_reject_dropped_keyword, t_reject_forged, t_forward,
             t_multi_user, t_sqlite]
    failed = 0  # นับข้อที่ไม่ผ่าน
    for t in tests:  # รันทีละข้อ
        try:
            t()  # ทดสอบ
            print(f"  PASS  {t.__name__}")  # ผ่าน
        except Exception as ex:  # ไม่ผ่าน
            failed += 1  # นับ
            print(f"  FAIL  {t.__name__}: {ex!r}")  # แสดงสาเหตุ
    print(f"{len(tests) - failed}/{len(tests)} passed")  # สรุป
    sys.exit(1 if failed else 0)  # คืนรหัส error ถ้ามีข้อที่ไม่ผ่าน




# ============================================================================
# 9) main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Chen et al. [40] simulation")  # ตัวอ่าน argument
    ap.add_argument("mode", choices=["demo", "selftest", "exp1", "exp2", "exp3", "all",
                                     "search1", "verify1", "tamper"])  # โหมดที่จะรัน
    # ---- dataset กลาง (amtp_dataset.py) ----
    ap.add_argument("--data", default=None, help="โฟลเดอร์ dataset (ค่าเริ่มต้น <repo>/data/amtp_file_db_v4 หรือ AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domain ที่ใช้")
    ap.add_argument("--seed", type=int, default=42, help="seed ของการสร้าง query (เท่ากับ seed ของ dataset)")
    # ---- ชื่อและค่าเริ่มต้นเหมือนกันทุก baseline (du / se_collab / chen) ----
    ap.add_argument("--reps", type=int, default=30, help="จำนวนรอบที่วัดจริง")
    ap.add_argument("--warmup", type=int, default=3, help="จำนวนรอบ warm-up (ไม่นับ)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="ขนาด N ของ exp1/exp3 (สูงสุด 500,000 = 4 domain x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="จำนวน keyword ต่อ query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="จำนวน query ต่อ k_Q (exp1)")
    # ---- เฉพาะ Chen ----
    ap.add_argument("--queries", default=None,
                    help=f"query JSON to replay (default {os.path.relpath(SHARED_QUERIES)})")
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 10, 100, 1000], help="ขนาด batch ของ exp3")
    ap.add_argument("--users", type=int, default=1, help="จำนวน DU ที่ได้สิทธิ์ N_u (exp3)")
    ap.add_argument("--update-mode", choices=["per-doc", "batch"], default="per-doc",
                    help="exp3: per-doc = ตาม paper, batch = รวม keyword ทั้ง batch")
    ap.add_argument("--scope", choices=["auto", "full", "queried"], default="auto",
                    help="สร้าง index เต็ม หรือเฉพาะ keyword ที่ทดลอง (ดู setup())")
    ap.add_argument("--max-edb-gb", type=float, default=4.0, help="scope=auto: index เต็มใหญ่เกินนี้ -> queried")
    ap.add_argument("--edb", choices=["auto", "memory", "sqlite"], default="auto",
                    help="ที่เก็บ EDB (auto = ลง SQLite เมื่อเกิน --ram-limit-gb)")
    ap.add_argument("--ram-limit-gb", type=float, default=2.0, help="เพดาน RAM ของ EDB ก่อนสลับไป SQLite")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "chen"), help="โฟลเดอร์ผลลัพธ์")
    Dm = dataset()                                # ค่าเริ่มต้นของ v4 suites ใช้ร่วมกับทุก scheme
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: จำนวนไฟล์ต่อ domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1: ไฟล์ต่อ domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    a = ap.parse_args()                           # อ่าน argument
    run = {"demo": run_demo, "selftest": run_selftest,  # ฟังก์ชันของแต่ละโหมด
           "exp1": suite_exp1, "exp2": suite_exp2, "exp3": suite_exp3, "search1": suite_search1,
           "verify1": suite_verify1, "tamper": suite_tamper}
    for name in (["exp1", "exp2", "exp3"] if a.mode == "all" else [a.mode]):  # all = รันทุก experiment
        run[name](a)                              # เรียกใช้


if __name__ == "__main__":
    main()

"""
Field Extractor v2.2 (rule-based, TH/EN)
ดึงฟิลด์หลักจากข้อความเรซูเม่ (plain text):
- name
- last_job_title
- experience_years
- expected_salary
- availability
- location
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Tuple, List
from datetime import datetime

# -------------------------
# Lightweight dataclass-like
# -------------------------
class Extracted:
    def __init__(
        self,
        name: Optional[str] = None,
        last_job_title: Optional[str] = None,
        experience_years: Optional[float] = None,
        expected_salary: Optional[str] = None,
        availability: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.name = name
        self.last_job_title = last_job_title
        self.experience_years = experience_years
        self.expected_salary = expected_salary
        self.availability = availability
        self.location = location

    def asdict(self) -> Dict[str, Optional[str]]:
        return {
            "name": self.name,
            "last_job_title": self.last_job_title,
            "experience_years": self.experience_years,
            "expected_salary": self.expected_salary,
            "availability": self.availability,
            "location": self.location,
        }

# -------------------------
# Normalization helpers
# -------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _first_group(rx: re.Pattern, text: str):
    m = rx.search(text)
    return _norm(m.group(1)) if m else None

def _lines(text: str, n: int = 20) -> List[str]:
    return [(ln or "").strip() for ln in (text or "").splitlines()[:n]]

# -------------------------
# Dictionaries / Patterns
# -------------------------

JOB_TITLES = [
    # EN common
    "software engineer", "backend engineer", "frontend engineer", "full stack developer",
    "data analyst", "data scientist", "data engineer", "ml engineer", "business analyst",
    "product manager", "project manager", "product owner", "scrum master",
    "marketing coordinator", "marketing executive", "marketing manager",
    "performance marketing", "seo specialist", "content writer",
    "customer service", "customer support", "front desk", "receptionist",
    "accountant", "finance officer", "payroll", "hr officer", "hr generalist",
    "operations", "operations analyst", "sales executive", "sales associate",
    "graphic designer", "ui designer", "ux designer", "qa engineer", "qa tester",
    # TH common
    "วิศวกรซอฟต์แวร์", "นักพัฒนา", "นักวิเคราะห์ข้อมูล", "วิศวกรข้อมูล", "นักวิทยาศาสตร์ข้อมูล",
    "ผู้จัดการผลิตภัณฑ์", "ผู้ประสานงานโครงการ", "ผู้จัดการโครงการ", "การตลาด", "บริการลูกค้า",
    "พนักงานต้อนรับ", "นักบัญชี", "เจ้าหน้าที่บุคคล", "เจ้าหน้าที่การเงิน", "นักออกแบบกราฟิก",
]
# allow Senior/Junior/Lead prefixes
JOB_TITLES_RX = re.compile(
    r"\b(?:senior|jr\.?|junior|lead|หัวหน้า|ผู้ช่วย)?\s*(" + "|".join(map(re.escape, JOB_TITLES)) + r")\b",
    re.I,
)

LOCATION_HINTS = [
    # EN cities/provinces (top TH)
    "bangkok", "nonthaburi", "pathum thani", "samut prakan", "chonburi",
    "chiang mai", "phuket", "khon kaen", "nakhon ratchasima",
    # TH
    "กรุงเทพ", "กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ",
    "ชลบุรี", "เชียงใหม่", "ภูเก็ต", "ขอนแก่น", "นครราชสีมา",
]

CURRENCY_RX = r"(?:฿|THB|บาท|baht|\$|USD)"
NUM_RX = r"(?:\d{1,3}(?:[,\s]\d{3})+|\d+)"
RANGE_RX = rf"{NUM_RX}\s*(?:-|to|–|—|ถึง)\s*{NUM_RX}"

MONTHS = {
    # EN
    "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,
    "may":5,"jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"sept":9,"september":9,
    "oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12,
    # TH (short)
    "ม.ค.":1,"ก.พ.":2,"มี.ค.":3,"เม.ย.":4,"พ.ค.":5,"มิ.ย.":6,"ก.ค.":7,"ส.ค.":8,"ก.ย.":9,"ต.ค.":10,"พ.ย.":11,"ธ.ค.":12,
    # TH (long)
    "มกราคม":1,"กุมภาพันธ์":2,"มีนาคม":3,"เมษายน":4,"พฤษภาคม":5,"มิถุนายน":6,"กรกฎาคม":7,
    "สิงหาคม":8,"กันยายน":9,"ตุลาคม":10,"พฤศจิกายน":11,"ธันวาคม":12,
}
PRESENT_WORDS = r"(?:present|current|ปัจจุบัน|ปจบ\.?)"

MONTHS_RE = "|".join(map(re.escape, MONTHS.keys()))

def _date_part_with_prefix(prefix: str) -> str:
    """สร้างพาร์ตวันที่พร้อมตั้งชื่อกรุ๊ปด้วย prefix (หลีกเลี่ยง redefinition)"""
    return rf"""
(?:
   (?P<{prefix}mw>(?:{MONTHS_RE}))\s*(?P<{prefix}yw>\d{{4}})
 |
   (?P<{prefix}y>\d{{4}})(?:[./\- ](?P<{prefix}m>\d{{1,2}}))?
)
"""

DATE_SPAN_RX = re.compile(
    rf"""
    {_date_part_with_prefix('s_')}
    \s*(?:–|-|to|until|through|ถึง|จนถึง|—)\s*
    (?:
        (?P<end_present>{PRESENT_WORDS})
      |
        {_date_part_with_prefix('e_')}
    )
    """,
    re.I | re.X,
)

# -------------------------
# Date helpers
# -------------------------
def _parse_date_tokens(tokens: Dict[str, str]) -> Optional[Tuple[int, int]]:
    """รับ dict ที่อาจมี keys: yw,mw,y,m  → (year, month) ; month=1 ถ้าไม่เจอ"""
    if tokens.get("yw"):
        y = int(tokens["yw"])
        mw = (tokens.get("mw") or "").lower()
        mm = MONTHS.get(mw, 1)
        return (y, mm)
    if tokens.get("y"):
        y = int(tokens["y"])
        mm = int(tokens["m"]) if tokens.get("m") else 1
        return (y, mm)
    return None

def _months_between(a: Tuple[int,int], b: Tuple[int,int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])

def _now_ym() -> Tuple[int,int]:
    dt = datetime.now()
    return (dt.year, dt.month)

def _start_end_from_match(m) -> Optional[Tuple[Tuple[int,int], Tuple[int,int]]]:
    """แปลง match ของ DATE_SPAN_RX ให้เป็น (start_ym, end_ym)"""
    gd = m.groupdict()
    start = _parse_date_tokens({
        "yw": gd.get("s_yw"),
        "mw": gd.get("s_mw"),
        "y" : gd.get("s_y"),
        "m" : gd.get("s_m"),
    })
    if not start:
        return None
    if gd.get("end_present"):
        end = _now_ym()
    else:
        end = _parse_date_tokens({
            "yw": gd.get("e_yw"),
            "mw": gd.get("e_mw"),
            "y" : gd.get("e_y"),
            "m" : gd.get("e_m"),
        })
        if not end:
            return None
    return start, end

# -------------------------
# Extractors
# -------------------------

def extract_name(text: str) -> Optional[str]:
    """หาในบรรทัดต้น ๆ หรือ pattern Name: / ชื่อ: (ข้ามหัวข้ออย่าง 'ประวัติย่อ/Resume')"""
    # explicit label
    m = re.search(r"(?:^|\n)\s*(?:Name|ชื่อ)\s*[:：\-]\s*(.+)$", text, re.I | re.M)
    if m:
        cand = _norm(m.group(1))
        if 2 <= len(cand) <= 80:
            return cand

    skip_pat = re.compile(
        r"(?i)\b("
        r"resume|curriculum vitae|cv|profile|summary|personal information|"
        r"ประวัติย่อ|เรซูเม่|โปรไฟล์|ข้อมูลส่วนตัว|สรุปประวัติ"
        r")\b"
    )

    for ln in _lines(text, n=12):
        if not ln:
            continue
        if skip_pat.search(ln):
            continue
        if "@" in ln:
            continue
        if 2 <= len(ln) <= 80:
            return ln
    return None


def _experience_block(text: str, span_chars: int = 1200) -> str:
    m = re.search(r"(?:^|\n)\s*(experience|work history|employment|ประสบการณ์)\b", text, re.I)
    if not m:
        return text[:span_chars]
    st = m.start()
    return text[st : st + span_chars]


def extract_last_job_title(text: str) -> Optional[str]:
    """เดาจากบล็อกประสบการณ์ + รูปแบบพบบ่อย"""
    block = _experience_block(text)
    hay = block.lower()

    jt = JOB_TITLES_RX.search(hay)
    if jt:
        return _norm(jt.group(0).title())

    for ln in _lines(block, 8):
        ln = re.sub(r"\s{2,}", " ", ln)
        m = re.match(r"(.{2,60})\s+(?:at|@)\s+.{2,80}", ln, re.I)
        if m:
            role = _norm(m.group(1))
            if 2 <= len(role) <= 60:
                return role
        m2 = re.match(r"(.{2,60})\s*-\s*(.{2,60})", ln)
        if m2:
            a, b = _norm(m2.group(1)), _norm(m2.group(2))
            if re.search(r"(engineer|developer|analyst|manager|designer|consultant|officer)", b, re.I):
                return b
            if re.search(r"(engineer|developer|analyst|manager|designer|consultant|officer)", a, re.I):
                return a

    jt2 = JOB_TITLES_RX.search(text.lower())
    return _norm(jt2.group(0).title()) if jt2 else None


def extract_experience_years(text: str) -> Optional[float]:
    """
    คำนวณจากช่วงวันที่ (รองรับ TH/EN เดือนและ 'Present') ถ้าไม่เจอ ค่อย fallback 'X years'
    """
    months_total = 0
    for m in DATE_SPAN_RX.finditer(text or ""):
        se = _start_end_from_match(m)
        if not se:
            continue
        start, end = se
        diff = _months_between(start, end)
        if diff > 0:
            months_total += diff

    if months_total > 0:
        return round(months_total / 12.0, 2)

    rx = re.compile(
        rf"(?:(?:experience|exp|ประสบการณ์)[^\d]{{0,12}})?(({RANGE_RX})|({NUM_RX}))\s*(?:years?|yrs?|ปี)",
        re.I,
    )
    m = rx.search(text or "")
    if not m:
        return None
    val = m.group(1)
    try:
        if re.search(r"-|to|–|—|ถึง", val):
            a, b = re.split(r"\s*(?:-|to|–|—|ถึง)\s*", val)
            return round((float(a.replace(",", "")) + float(b.replace(",", ""))) / 2.0, 2)
        return float(val.replace(",", ""))
    except Exception:
        return None


def extract_expected_salary(text: str) -> Optional[str]:
    """
    ดึงเงินเดือน (range/ตัวเลข + สกุลเงิน) แล้ว normalize เป็นสตริงสั้น ๆ
    """
    rx = re.compile(
        rf"(?:expected salary|salary expectation|เงินเดือนที่คาดหวัง|เงินเดือนที่ต้องการ)\s*[:\-]?\s*((?:{RANGE_RX}|{NUM_RX})\s*(?:{CURRENCY_RX})?)",
        re.I,
    )
    g = _first_group(rx, text)
    if not g:
        rx2 = re.compile(rf"(?:salary|เงินเดือน).{{0,24}}(({RANGE_RX}|{NUM_RX})\s*(?:{CURRENCY_RX})?)", re.I)
        g = _first_group(rx2, text)
    if not g:
        return None

    val = g

    def to_num(x: str) -> Optional[int]:
        x = x.lower().replace(",", "").replace(" ", "")
        x = re.sub(r"[^\d.km]", "", x)
        if not x:
            return None
        mul = 1
        if x.endswith("k"):
            mul = 1000; x = x[:-1]
        elif x.endswith("m"):
            mul = 1000000; x = x[:-1]
        try:
            return int(float(x) * mul)
        except Exception:
            return None

    cur = "THB" if re.search(r"(฿|thb|บาท|baht)", val, re.I) else ("USD" if re.search(r"\$|usd", val, re.I) else "")
    if re.search(r"-|to|–|—|ถึง", val):
        a, b = re.split(r"\s*(?:-|to|–|—|ถึง)\s*", val)
        a_num, b_num = to_num(a), to_num(b)
        if a_num and b_num:
            return f"{a_num:,}-{b_num:,} {cur}".strip()
    n = to_num(val)
    if n:
        return f"{n:,} {cur}".strip()
    return _norm(val)


def extract_availability(text: str) -> Optional[str]:
    """
    จับ availability/notice period แล้วคืนสรุปสั้น ๆ:
    - "immediately", "in 30 days", "notice 45 days", "พร้อมเริ่มทันที"
    """
    pats = [
        r"(?:available|start)\s*(?:immediately|now)",
        r"(?:available|can start)\s*in\s*(\d{1,2})\s*(days?|weeks?)",
        r"(?:notice period)\s*[:\-]?\s*(\d{1,2})\s*(days?|weeks?)",
        r"(?:พร้อมเริ่มงาน|เริ่มงานได้)\s*(ทันที|\d{1,2}\s*วัน|\d{1,2}\s*สัปดาห์)",
        r"(?:แจ้งลา|โนติส)\s*(\d{1,2})\s*(วัน|สัปดาห์)",
    ]
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            raw = _norm(m.group(0))
            if re.search(r"immediately|ทันที", raw, re.I):
                return "immediately"
            m2 = re.search(r"(\d{1,2})\s*(days?|weeks?|วัน|สัปดาห์)", raw, re.I)
            if m2:
                num = m2.group(1)
                unit = m2.group(2).lower()
                if unit in ("วัน",):
                    unit = "days"
                elif unit in ("สัปดาห์",):
                    unit = "weeks"
                if "notice" in raw.lower() or "โนติส" in raw.lower() or "แจ้งลา" in raw.lower():
                    return f"notice {num} {unit}"
                return f"in {num} {unit}"
            return raw
    return None


def extract_location(text: str) -> Optional[str]:
    m = re.search(r"(?:Location|ที่อยู่|จังหวัด|อาศัยอยู่ที่)\s*[:：\-]\s*([^\n,]+)", text, re.I)
    if m:
        return _norm(m.group(1))
    m2 = re.search(r"\b([A-Za-zก-๙\. ]{2,30}),\s*(Thailand|ไทย)\b", text, re.I)
    if m2:
        return _norm(m2.group(1))
    for w in LOCATION_HINTS:
        if re.search(rf"(?<![A-Za-zก-๙]){re.escape(w)}(?![A-Za-zก-๙])", text, re.I):
            return w.title() if w.isalpha() else w
    return None


def extract_all(text: str) -> Extracted:
    t = text or ""
    return Extracted(
        name=extract_name(t),
        last_job_title=extract_last_job_title(t),
        experience_years=extract_experience_years(t),
        expected_salary=extract_expected_salary(t),
        availability=extract_availability(t),
        location=extract_location(t),
    )


__all__ = [
    "Extracted",
    "extract_all",
    "extract_name",
    "extract_last_job_title",
    "extract_experience_years",
    "extract_expected_salary",
    "extract_availability",
    "extract_location",
]
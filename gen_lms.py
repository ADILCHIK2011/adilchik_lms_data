#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LMS datasi generatori (O'zbekiston IT-akademiya konteksti).
Rollar: student / mentor / tutor / curator
Deterministik (seed=7).
"""
import json, random, csv, os
from datetime import date, timedelta, time
from collections import defaultdict

random.seed(7)
OUT = "/home/claude/lms"
os.makedirs(OUT, exist_ok=True)

TERM_START = date(2026, 2, 2)   # semestr boshi (dushanba)
TERM_END   = date(2026, 7, 31)

# ------------------------------------------------------------------ ISMLAR
M_FIRST = ["Bekzod","Javohir","Sardor","Aziz","Doniyor","Otabek","Shohruh","Jasur","Alisher",
           "Ulug'bek","Temur","Nodir","Rustam","Sanjar","Firdavs","Islom","Muhammadali","Diyor",
           "Anvar","Bobur","Xurshid","Ravshan","Sherzod","Akmal","Farrux","Behruz","Asadbek",
           "Amirbek","Umar","Abror","Sarvar","Elyor","Nurbek","Xasan","Husan"]
F_FIRST = ["Malika","Nilufar","Zilola","Dilnoza","Gulnora","Shahzoda","Madina","Sevara","Kamola",
           "Nozima","Feruza","Ozoda","Mohira","Nargiza","Gulbahor","Zarina","Rayhona","Sitora",
           "Muslima","Robiya","Odina","Charos","Munisa","Aziza","Laylo","Nafisa","Yulduz","Dilfuza"]
LAST = ["Karimov","Rahimov","Yusupov","Abdullayev","Toshmatov","Ergashev","Nazarov","Qodirov",
        "Sultonov","Mirzayev","Xolmatov","Sobirov","Umarov","Ismoilov","Jo'rayev","Alimov",
        "Tursunov","Xasanov","Norqulov","Saidov","Nematov","Ochilov","Bekmurodov","Jalilov",
        "Rustamov","Ashurov","Hamidov","Qurbonov","Shodmonov","Tolipov","Egamberdiyev","Yo'ldoshev"]

def full_name(gender):
    fn = random.choice(M_FIRST if gender == "male" else F_FIRST)
    ln = random.choice(LAST) + ("a" if gender == "female" else "")
    return fn, ln

def phone():
    return f"+998{random.choice([90,91,93,94,97,98,99,88,33,77])}{random.randint(1000000,9999999)}"

def translit(s):
    for ch in ("'", "‘", "ʻ", "’", " "):
        s = s.replace(ch, "")
    return s.lower()

DISTRICTS = ["Chilonzor","Yunusobod","Mirzo Ulug'bek","Yashnobod","Shayxontohur","Olmazor",
             "Sergeli","Uchtepa","Mirobod","Bektemir","Yakkasaroy"]

# ----------------------------------------------------------------- KURSLAR
COURSES = [
    # (kod, nom, oy, haftada dars, daraja, oylik to'lov UZS, yosh)
    ("FE-BAS", "Frontend Basics (HTML/CSS)",  4, 3, "Boshlang'ich", 650_000,  "12-16"),
    ("FE-JS",  "JavaScript Fundamentals",     5, 3, "O'rta",        800_000,  "14-18"),
    ("FE-RCT", "React va zamonaviy frontend", 5, 3, "Yuqori",       950_000,  "15-18"),
    ("PY-BAS", "Python dasturlash asoslari",  4, 3, "Boshlang'ich", 700_000,  "12-17"),
    ("SC-KID", "Scratch — kichiklar uchun",   3, 2, "Boshlang'ich", 450_000,  "10-13"),
    ("UX-FIG", "UI/UX dizayn (Figma)",        4, 3, "O'rta",        850_000,  "14-18"),
    ("MB-FLU", "Mobil ilovalar (Flutter)",    5, 3, "Yuqori",       950_000,  "15-18"),
    ("DA-SQL", "Ma'lumotlar bazasi va SQL",   3, 2, "O'rta",        750_000,  "15-18"),
]

# --------------------------------------------------------------- XODIMLAR
def make_staff(role, count, start_id, prefix):
    out = []
    for i in range(count):
        g = random.choice(["male","female"])
        fn, ln = full_name(g)
        exp = random.randint(1, 9) if role != "curator" else random.randint(1, 6)
        salary = {
            "mentor":  random.randint(6, 14) * 1_000_000,
            "tutor":   random.randint(3, 7) * 1_000_000,
            "curator": random.randint(4, 8) * 1_000_000,
        }[role]
        out.append({
            "id": start_id + i,
            "code": f"{prefix}-{start_id+i}",
            "role": role,
            "first_name": fn,
            "last_name": ln,
            "full_name": f"{fn} {ln}",
            "gender": g,
            "phone": phone(),
            "email": f"{translit(fn)}.{translit(ln)}{random.randint(1,99)}@academy.uz",
            "telegram": f"@{translit(fn)}_{translit(ln)[:4]}{random.randint(10,99)}",
            "experience_years": exp,
            "rating": round(min(5.0, max(3.4, random.gauss(4.5, 0.32))), 2),
            "monthly_salary": salary,
            "hired_at": (date(2026,1,1) - timedelta(days=random.randint(60, 1500))).isoformat(),
            "status": "active" if random.random() > 0.06 else "vacation",
        })
    return out

mentors  = make_staff("mentor", 14, 1,   "MNT")   # dars o'tuvchi
tutors   = make_staff("tutor",  18, 101, "TUT")   # qo'shimcha dars o'tuvchi
curators = make_staff("curator", 9, 201, "CUR")   # ota-onalar bilan aloqa

# mentorlarga yo'nalish biriktiramiz
for m in mentors:
    m["specialization"] = random.choice([c[1] for c in COURSES])
for t in tutors:
    t["specialization"] = random.choice([c[1] for c in COURSES])
for c in curators:
    c["max_students"] = random.choice([30, 35, 40, 45])

# ----------------------------------------------------------------- GURUHLAR
ROOMS = ["101-xona","102-xona","103-xona","201-xona","202-xona","203-xona","301-lab","302-lab"]
SLOTS = [("09:00","10:30"), ("11:00","12:30"), ("14:00","15:30"), ("16:00","17:30"), ("18:00","19:30")]
SCHED = {
    3: [("odd", [1,3,5]), ("even", [2,4,6])],       # haftada 3 kun
    2: [("tue_thu", [2,4]), ("mon_wed", [1,3]), ("sat_sun", [6,7])],
}

groups = []
gid = 0
for ci, (code, cname, months, per_week, level, fee, ages) in enumerate(COURSES):
    n_groups = random.choice([2, 3, 3, 4])
    for k in range(n_groups):
        gid += 1
        sch_name, days = random.choice(SCHED[per_week])
        slot = random.choice(SLOTS)
        start_offset = random.choice([0, 0, 7, 14])
        groups.append({
            "id": gid,
            "name": f"{code}-{gid:03d}",
            "course_code": code,
            "course_name": cname,
            "level": level,
            "age_range": ages,
            "mentor_id": random.choice(mentors)["id"],
            "tutor_id": random.choice(tutors)["id"],
            "curator_id": random.choice(curators)["id"],
            "room": random.choice(ROOMS),
            "schedule_type": sch_name,
            "schedule_days": days,          # 1=Dush ... 7=Yak
            "lesson_start": slot[0],
            "lesson_end": slot[1],
            "duration_min": 90,
            "monthly_fee": fee,
            "duration_months": months,
            "started_at": (TERM_START + timedelta(days=start_offset)).isoformat(),
            "status": "active",
        })

# ---------------------------------------------------------------- DARSLAR
TOPICS = {
 "FE-BAS": ["HTML tuzilishi","Teglar va atributlar","Ro'yxatlar va jadvallar","Formalar",
            "CSS selektorlar","Box model","Flexbox","Grid","Pozitsiyalash","Responsive dizayn",
            "Media queries","Animatsiyalar","Bootstrap asoslari","Tailwind kirish","Landing page",
            "Git va GitHub","Deploy (Netlify)","Loyiha himoyasi"],
 "FE-JS":  ["O'zgaruvchilar va tiplar","Operatorlar","Shartlar","Sikllar","Funksiyalar","Massivlar",
            "Obyektlar","DOM manipulyatsiya","Hodisalar (Events)","LocalStorage","Fetch va API",
            "Promise va async/await","ES6+ imkoniyatlari","Modullar","Xatolarni ushlash",
            "To-do ilova","Weather API loyihasi","Yakuniy loyiha"],
 "FE-RCT": ["React kirish va JSX","Komponentlar","Props","useState","useEffect","Ro'yxatlar va key",
            "Formalar boshqaruvi","React Router","Custom hooks","Context API","Redux Toolkit",
            "API bilan ishlash","Tailwind + React","Optimizatsiya","Testlash asoslari",
            "Deploy (Vercel)","Portfolio loyiha","Yakuniy himoya"],
 "PY-BAS": ["Python kirish","O'zgaruvchilar","Shartli operatorlar","Sikllar","Funksiyalar",
            "Ro'yxat va lug'atlar","Fayllar bilan ishlash","Xatolar","OOP asoslari","Modullar",
            "Kutubxonalar (pip)","Requests va API","Telegram bot","Ma'lumotlarni tahlil",
            "Pandas kirish","Kichik loyiha","Loyiha himoyasi"],
 "SC-KID": ["Scratch bilan tanishuv","Spraytlar","Harakatlar","Sikllar","Shartlar","O'zgaruvchilar",
            "Ovoz va musiqa","Animatsiya yaratish","Oddiy o'yin","Labirint o'yini","Platformer",
            "Viktorina","Yakuniy loyiha"],
 "UX-FIG": ["Dizayn asoslari","Rang nazariyasi","Tipografiya","Figma interfeysi","Frame va Auto Layout",
            "Komponentlar","Variantlar","Prototiplash","Wireframe","Mobil UI","Web UI",
            "Dizayn tizimi","Foydalanuvchi tadqiqoti","Portfolio","Himoya"],
 "MB-FLU": ["Dart asoslari","Flutter kirish","Widgetlar","Layout","Navigatsiya","State management",
            "Formalar","HTTP va API","Firebase","Local storage","Animatsiyalar","Publish",
            "Yakuniy loyiha"],
 "DA-SQL": ["Ma'lumotlar bazasi tushunchasi","SELECT","WHERE va filtrlash","JOIN turlari",
            "GROUP BY va agregatlar","Subquery","INSERT/UPDATE/DELETE","Indekslar","Normalizatsiya",
            "Tranzaksiyalar","PostgreSQL amaliyot","Yakuniy loyiha"],
}

def gen_lesson_dates(g):
    start = date.fromisoformat(g["started_at"])
    days = set(g["schedule_days"])
    out, d = [], start
    while d <= TERM_END:
        if d.isoweekday() in days:
            out.append(d)
        d += timedelta(days=1)
    return out

HOLIDAYS = {date(2026,3,21), date(2026,3,22), date(2026,3,23), date(2026,5,9), date(2026,3,20)}

lessons = []
lid = 0
for g in groups:
    topics = TOPICS[g["course_code"]]
    dates = [d for d in gen_lesson_dates(g) if d not in HOLIDAYS]
    for i, d in enumerate(dates):
        lid += 1
        topic = topics[i % len(topics)]
        module = i // 6 + 1
        is_exam = (i + 1) % 12 == 0
        lessons.append({
            "id": lid,
            "group_id": g["id"],
            "lesson_number": i + 1,
            "date": d.isoformat(),
            "weekday": d.isoweekday(),
            "start_time": g["lesson_start"],
            "end_time": g["lesson_end"],
            "topic": topic,
            "module": module,
            "type": "exam" if is_exam else ("practice" if i % 3 == 2 else "lecture"),
            "mentor_id": g["mentor_id"],
            "room": g["room"],
            "has_homework": not is_exam,
            "status": "completed" if d <= date(2026, 7, 31) else "planned",
        })

lessons_by_group = defaultdict(list)
for l in lessons:
    lessons_by_group[l["group_id"]].append(l)

# --------------------------------------------------------------- STUDENTLAR
SCHOOLS = [f"{n}-son maktab" for n in [1,7,12,18,24,33,45,52,64,77,89,101,110,124,153,178,201,233]]
PARENT_REL = ["Ota","Ona","Buvi","Bobo","Aka","Opa"]

students = []
sid = 0
for g in groups:
    n = random.randint(8, 15)
    lo, hi = map(int, g["age_range"].split("-"))
    for _ in range(n):
        sid += 1
        gender = random.choices(["male","female"], [0.62, 0.38])[0]
        fn, ln = full_name(gender)
        age = random.randint(lo, hi)
        birth = date(2026 - age, random.randint(1,12), random.randint(1,28))

        # ota-ona (curator shular bilan ishlaydi)
        p_gender = random.choice(["male","female"])
        pfn, pln = full_name(p_gender)
        parent = {
            "full_name": f"{pfn} {ln if p_gender=='male' else ln+'a'}",
            "relation": "Ota" if p_gender == "male" else "Ona",
            "phone": phone(),
            "telegram": f"@{translit(pfn)}{random.randint(100,999)}",
            "preferred_contact": random.choice(["telegram","phone","telegram","sms"]),
        }

        # o'quvchi profili (davomat/vazifa ehtimolliklariga ta'sir qiladi)
        profile = random.choices(
            ["a'lochi", "yaxshi", "o'rtacha", "zaif", "xavf_ostida"],
            [0.16, 0.30, 0.32, 0.15, 0.07])[0]

        students.append({
            "id": sid,
            "code": f"STU-{10000+sid}",
            "role": "student",
            "first_name": fn,
            "last_name": ln,
            "full_name": f"{fn} {ln}",
            "gender": gender,
            "birth_date": birth.isoformat(),
            "age": age,
            "phone": phone(),
            "telegram": f"@{translit(fn)}_{random.randint(100,9999)}",
            "school": random.choice(SCHOOLS),
            "grade": min(11, max(4, age - 6)),
            "district": random.choice(DISTRICTS),
            "group_id": g["id"],
            "group_name": g["name"],
            "course_code": g["course_code"],
            "mentor_id": g["mentor_id"],
            "tutor_id": g["tutor_id"],
            "curator_id": g["curator_id"],
            "parent": parent,
            "enrolled_at": g["started_at"],
            "monthly_fee": g["monthly_fee"],
            "status": "active",
            "_profile": profile,
        })

# ehtimolliklar profil bo'yicha
P = {
 # profil: (kelish, kechikish, vazifa_topshirish, o'z_vaqtida, bal_avg, bal_sd)
 "a'lochi":     (0.97, 0.03, 0.98, 0.95, 92, 5),
 "yaxshi":      (0.93, 0.07, 0.92, 0.85, 82, 7),
 "o'rtacha":    (0.86, 0.13, 0.80, 0.68, 71, 9),
 "zaif":        (0.75, 0.20, 0.58, 0.45, 58, 11),
 "xavf_ostida": (0.58, 0.25, 0.34, 0.25, 45, 13),
}

def clamp(v, lo, hi): return max(lo, min(hi, v))

# --------------------------------------------- DAVOMAT / VAZIFA / COINS
attendance = []
homework_assignments = []
homework_submissions = []
coin_tx = []
makeups = []          # qoldirilgan darsni yopish
curator_contacts = [] # curator ↔ ota-ona
tutor_sessions = []   # tutor qo'shimcha darslari
payments = []

att_id = ha_id = hs_id = ct_id = mk_id = cc_id = ts_id = pay_id = 0

SHOP = [("Akademiya futbolkasi", 450), ("Stiker to'plami", 80), ("Blokrot + ruchka", 120),
        ("Termokruzhka", 380), ("Ryukzak", 900), ("Powerbank", 1200),
        ("Kinoga chipta", 300), ("Pizza kuponi", 250), ("Sertifikat ramkasi", 200),
        ("Simsiz sichqoncha", 700), ("Quloqchin", 1500), ("Bepul 1 oy kurs", 3000)]

TODAY = date(2026, 7, 31)

# vazifa mavzulari
HW_TASKS = ["Amaliy topshiriq","Mustaqil loyiha","Kod yozish mashqi","Takrorlash testi",
            "Mini-loyiha","Debug topshirig'i","Refaktoring vazifasi","Tahlil topshirig'i"]

# har guruh uchun uy vazifalari
hw_by_lesson = {}
for l in lessons:
    if not l["has_homework"]:
        continue
    ha_id += 1
    due = date.fromisoformat(l["date"]) + timedelta(days=random.choice([2, 2, 3, 4]))
    hw = {
        "id": ha_id,
        "lesson_id": l["id"],
        "group_id": l["group_id"],
        "title": f"{l['topic']} — {random.choice(HW_TASKS)}",
        "assigned_date": l["date"],
        "due_date": due.isoformat(),
        "max_score": 100,
        "coins_reward": random.choice([15, 20, 20, 25, 30]),
        "difficulty": random.choice(["oson","o'rta","o'rta","qiyin"]),
        "created_by_mentor_id": l["mentor_id"],
    }
    homework_assignments.append(hw)
    hw_by_lesson[l["id"]] = hw

students_by_group = defaultdict(list)
for s in students:
    students_by_group[s["group_id"]].append(s)

for g in groups:
    g_lessons = lessons_by_group[g["id"]]
    for s in students_by_group[g["id"]]:
        p_att, p_late, p_hw, p_ontime, sc_mu, sc_sd = P[s["_profile"]]
        balance = 0
        consecutive_absent = 0
        streak = 0
        missed_lessons = []

        for l in g_lessons:
            ldate = date.fromisoformat(l["date"])
            if ldate > TODAY:
                continue
            att_id += 1
            r = random.random()
            if r < p_att:
                status = "late" if random.random() < p_late else "present"
            else:
                status = random.choices(["absent_excused","absent_unexcused"], [0.45, 0.55])[0]

            minutes_late = random.randint(5, 25) if status == "late" else 0
            attendance.append({
                "id": att_id,
                "student_id": s["id"],
                "lesson_id": l["id"],
                "group_id": g["id"],
                "date": l["date"],
                "status": status,          # present | late | absent_excused | absent_unexcused
                "minutes_late": minutes_late,
                "marked_by_mentor_id": l["mentor_id"],
                "note": "Ota-ona xabar berdi" if status == "absent_excused" else
                        ("Sababsiz" if status == "absent_unexcused" else ""),
            })

            # --- coins: davomat
            if status == "present":
                streak += 1
                consecutive_absent = 0
                amt = 10
                ct_id += 1; balance += amt
                coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                    "type":"earn","reason":"attendance","description":"Darsga o'z vaqtida keldi",
                    "amount":amt,"balance_after":balance,"ref_lesson_id":l["id"]})
                if streak > 0 and streak % 10 == 0:
                    ct_id += 1; balance += 50
                    coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                        "type":"earn","reason":"streak_bonus",
                        "description":f"{streak} ta ketma-ket dars — bonus",
                        "amount":50,"balance_after":balance,"ref_lesson_id":l["id"]})
            elif status == "late":
                streak = 0; consecutive_absent = 0
                ct_id += 1; balance += 4
                coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                    "type":"earn","reason":"attendance_late","description":f"Kechikdi ({minutes_late} daq)",
                    "amount":4,"balance_after":balance,"ref_lesson_id":l["id"]})
            else:
                streak = 0; consecutive_absent += 1
                missed_lessons.append(l)
                if status == "absent_unexcused":
                    pen = -5
                    ct_id += 1; balance = max(0, balance + pen)
                    coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                        "type":"penalty","reason":"absent_unexcused","description":"Sababsiz qoldirdi",
                        "amount":pen,"balance_after":balance,"ref_lesson_id":l["id"]})

                # 2 ta ketma-ket qoldirsa — curator ota-onaga qo'ng'iroq
                if consecutive_absent >= 2:
                    cc_id += 1
                    curator_contacts.append({
                        "id": cc_id,"curator_id": g["curator_id"],"student_id": s["id"],
                        "date": l["date"],"channel": s["parent"]["preferred_contact"],
                        "reason":"absence_alert",
                        "subject": f"{consecutive_absent} ta ketma-ket dars qoldirildi",
                        "summary":"Ota-onaga xabar berildi, sabab so'raldi",
                        "parent_response": random.choice(["Kasal bo'lgan","Oilaviy sabab","Javob yo'q",
                                                          "Maktab tadbiri","Ertadan keladi"]),
                        "resolved": random.random() < 0.8,
                        "follow_up_needed": consecutive_absent >= 3,
                    })
                    consecutive_absent = 0

            # --- uy vazifasi
            hw = hw_by_lesson.get(l["id"])
            if hw and status != "absent_unexcused":
                hs_id += 1
                submitted = random.random() < p_hw
                if not submitted:
                    homework_submissions.append({
                        "id": hs_id,"homework_id": hw["id"],"student_id": s["id"],
                        "group_id": g["id"],"assigned_date": hw["assigned_date"],
                        "due_date": hw["due_date"],"submitted_at": None,"status":"not_submitted",
                        "days_late": None,"score": 0,"coins_earned": 0,
                        "mentor_feedback":"Topshirilmadi","checked_by_mentor_id": l["mentor_id"],
                    })
                else:
                    due = date.fromisoformat(hw["due_date"])
                    ontime = random.random() < p_ontime
                    if ontime:
                        sub = due - timedelta(days=random.randint(0, 2))
                        days_late = 0; st = "submitted_on_time"
                    else:
                        days_late = random.randint(1, 5)
                        sub = due + timedelta(days=days_late)
                        st = "submitted_late"
                    score = int(clamp(random.gauss(sc_mu, sc_sd), 20, 100))
                    if days_late: score = int(score * (1 - min(0.3, days_late * 0.07)))
                    coins = int(hw["coins_reward"] * (score / 100) * (1.0 if ontime else 0.6))
                    homework_submissions.append({
                        "id": hs_id,"homework_id": hw["id"],"student_id": s["id"],
                        "group_id": g["id"],"assigned_date": hw["assigned_date"],
                        "due_date": hw["due_date"],"submitted_at": sub.isoformat(),"status": st,
                        "days_late": days_late,"score": score,"coins_earned": coins,
                        "mentor_feedback": random.choice(
                            ["Zo'r ish!","Yaxshi, lekin kodni toza yozing","Talab darajasida",
                             "Ba'zi xatolar bor, tuzating","Ajoyib yechim","Qayta ko'rib chiqing"]),
                        "checked_by_mentor_id": l["mentor_id"],
                    })
                    if coins:
                        ct_id += 1; balance += coins
                        coin_tx.append({"id": ct_id,"student_id": s["id"],"date": sub.isoformat(),
                            "type":"earn","reason":"homework",
                            "description":f"Uy vazifasi ({score} ball)",
                            "amount":coins,"balance_after":balance,"ref_homework_id": hw["id"]})
                    if score >= 95:
                        ct_id += 1; balance += 25
                        coin_tx.append({"id": ct_id,"student_id": s["id"],"date": sub.isoformat(),
                            "type":"earn","reason":"excellent_work","description":"A'lo bajarilgan ish",
                            "amount":25,"balance_after":balance,"ref_homework_id": hw["id"]})

            # --- darsdagi faollik
            if status in ("present","late") and random.random() < 0.22:
                amt = random.choice([5, 5, 10, 15])
                ct_id += 1; balance += amt
                coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                    "type":"earn","reason":"activity","description":"Darsdagi faollik / to'g'ri javob",
                    "amount":amt,"balance_after":balance,"ref_lesson_id":l["id"]})

            # --- coin sarflash (do'kon)
            if balance > 400 and random.random() < 0.05:
                item, cost = random.choice([x for x in SHOP if x[1] <= balance])
                ct_id += 1; balance -= cost
                coin_tx.append({"id": ct_id,"student_id": s["id"],"date": l["date"],
                    "type":"spend","reason":"shop","description":f"Sotib oldi: {item}",
                    "amount":-cost,"balance_after":balance,"ref_item": item})

        # ---- qoldirilgan darslarni yopish (makeup) — "qolib ketmasligi" uchun
        for l in missed_lessons:
            if random.random() < (0.85 if s["_profile"] in ("a'lochi","yaxshi") else
                                  0.55 if s["_profile"] == "o'rtacha" else 0.30):
                mk_id += 1
                md = date.fromisoformat(l["date"]) + timedelta(days=random.randint(2, 9))
                if md > TODAY: md = TODAY
                mode = random.choices(["tutor_session","video_recording","self_study"], [0.55,0.30,0.15])[0]
                makeups.append({
                    "id": mk_id,"student_id": s["id"],"missed_lesson_id": l["id"],
                    "missed_date": l["date"],"makeup_date": md.isoformat(),
                    "mode": mode,
                    "tutor_id": g["tutor_id"] if mode == "tutor_session" else None,
                    "duration_min": 60 if mode == "tutor_session" else 90,
                    "topic": l["topic"],
                    "completed": True,
                    "quiz_score": int(clamp(random.gauss(P[s["_profile"]][4] - 5, 10), 20, 100)),
                })
                ct_id += 1; balance += 10
                coin_tx.append({"id": ct_id,"student_id": s["id"],"date": md.isoformat(),
                    "type":"earn","reason":"makeup_completed",
                    "description":f"Qoldirilgan darsni yopdi: {l['topic']}",
                    "amount":10,"balance_after":balance,"ref_lesson_id":l["id"]})

        # ---- tutor bilan qo'shimcha darslar (zaifroq o'quvchilarga ko'proq)
        n_tut = {"a'lochi":random.randint(0,2),"yaxshi":random.randint(1,3),
                 "o'rtacha":random.randint(2,6),"zaif":random.randint(4,10),
                 "xavf_ostida":random.randint(5,12)}[s["_profile"]]
        for _ in range(n_tut):
            ts_id += 1
            d = TERM_START + timedelta(days=random.randint(10, (TODAY - TERM_START).days))
            tp = random.choice(TOPICS[g["course_code"]])
            tutor_sessions.append({
                "id": ts_id,"student_id": s["id"],"tutor_id": g["tutor_id"],
                "group_id": g["id"],"date": d.isoformat(),
                "start_time": random.choice(["13:00","15:30","17:00","19:30"]),
                "duration_min": random.choice([45, 60, 60, 90]),
                "type": random.choice(["individual","individual","mini_group"]),
                "topic": tp,
                "reason": random.choice(["Mavzuni tushunmadi","Uy vazifasi bo'yicha yordam",
                                         "Qoldirilgan darsni yopish","Imtihonga tayyorgarlik",
                                         "Loyiha bo'yicha maslahat"]),
                "attended": random.random() < 0.9,
                "progress_note": random.choice(["Yaxshilanish bor","Takrorlash kerak",
                                                "Mavzuni o'zlashtirdi","Yana bir sessiya kerak"]),
            })

        # ---- to'lovlar
        for mo in range(2, 8):  # fev..iyul
            pay_id += 1
            due = date(2026, mo, 5)
            late = random.random() < (0.10 if s["_profile"] in ("a'lochi","yaxshi") else 0.28)
            paid = due + timedelta(days=random.randint(1, 14) if late else -random.randint(0, 4))
            unpaid = mo == 7 and random.random() < 0.12
            payments.append({
                "id": pay_id,"student_id": s["id"],"group_id": g["id"],
                "period": f"2026-{mo:02d}","amount": g["monthly_fee"],
                "due_date": due.isoformat(),
                "paid_at": None if unpaid else paid.isoformat(),
                "status": "unpaid" if unpaid else ("late" if late else "paid"),
                "method": random.choice(["Payme","Click","Naqd","Uzcard","Humo"]),
                "discount_pct": random.choice([0,0,0,0,10,15,20]),
            })

        s["coins_balance"] = balance

# ------------------------------------------------- CURATOR: rejali aloqalar
for s in students:
    g = next(x for x in groups if x["id"] == s["group_id"])
    for _ in range(random.randint(2, 6)):
        cc_id += 1
        d = TERM_START + timedelta(days=random.randint(5, (TODAY - TERM_START).days))
        reason = random.choices(
            ["monthly_report","progress_update","payment_reminder","homework_alert",
             "praise","meeting_invite"], [0.30,0.22,0.16,0.14,0.12,0.06])[0]
        curator_contacts.append({
            "id": cc_id,"curator_id": g["curator_id"],"student_id": s["id"],
            "date": d.isoformat(),"channel": s["parent"]["preferred_contact"],
            "reason": reason,
            "subject": {
                "monthly_report":"Oylik natijalar hisoboti",
                "progress_update":"Farzandingiz progressi haqida",
                "payment_reminder":"To'lov muddati eslatmasi",
                "homework_alert":"Uy vazifalari topshirilmayapti",
                "praise":"Farzandingiz a'lo natija ko'rsatdi",
                "meeting_invite":"Ota-onalar yig'ilishiga taklif",
            }[reason],
            "summary": random.choice(["Ota-ona bilan bog'lanildi","Xabar yuborildi, o'qildi",
                                      "Telefon orqali suhbat","Javob olindi"]),
            "parent_response": random.choice(["Rahmat, tushundim","Nazoratga olaman",
                                              "Javob yo'q","Uchrashuvga kelaman","Ok"]),
            "resolved": random.random() < 0.85,
            "follow_up_needed": random.random() < 0.2,
        })

# ------------------------------------------------------ STUDENT STATISTIKA
att_by_student = defaultdict(list)
for a in attendance: att_by_student[a["student_id"]].append(a)
hw_by_student = defaultdict(list)
for h in homework_submissions: hw_by_student[h["student_id"]].append(h)
mk_by_student = defaultdict(list)
for m in makeups: mk_by_student[m["student_id"]].append(m)
tut_by_student = defaultdict(list)
for t in tutor_sessions: tut_by_student[t["student_id"]].append(t)

for s in students:
    A = att_by_student[s["id"]]
    H = hw_by_student[s["id"]]
    total = len(A)
    present = sum(1 for a in A if a["status"] == "present")
    late = sum(1 for a in A if a["status"] == "late")
    absent = total - present - late
    absent_unex = sum(1 for a in A if a["status"] == "absent_unexcused")
    covered = len(mk_by_student[s["id"]])

    done = [h for h in H if h["status"] != "not_submitted"]
    ontime = [h for h in done if h["status"] == "submitted_on_time"]
    scores = [h["score"] for h in done]

    s["attendance"] = {
        "total_lessons": total,
        "present": present,
        "late": late,
        "absent": absent,
        "absent_excused": absent - absent_unex,
        "absent_unexcused": absent_unex,
        "attendance_rate": round((present + late) / total * 100, 1) if total else 0.0,
        "punctuality_rate": round(present / total * 100, 1) if total else 0.0,
        "missed_covered_by_makeup": covered,
        "missed_not_covered": max(0, absent - covered),
        "is_behind": (absent - covered) > 3,
    }
    s["homework"] = {
        "assigned": len(H),
        "submitted": len(done),
        "on_time": len(ontime),
        "late": len(done) - len(ontime),
        "not_submitted": len(H) - len(done),
        "submission_rate": round(len(done) / len(H) * 100, 1) if H else 0.0,
        "on_time_rate": round(len(ontime) / len(H) * 100, 1) if H else 0.0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "best_score": max(scores) if scores else 0,
    }
    s["coins"] = {
        "balance": s.pop("coins_balance"),
        "total_earned": sum(t["amount"] for t in coin_tx if t["student_id"] == s["id"] and t["amount"] > 0),
        "total_spent": abs(sum(t["amount"] for t in coin_tx if t["student_id"] == s["id"] and t["amount"] < 0)),
    }
    s["tutor_sessions_count"] = len(tut_by_student[s["id"]])
    s["makeup_count"] = covered

    # umumiy reyting
    perf = (s["attendance"]["attendance_rate"] * 0.35 +
            s["homework"]["submission_rate"] * 0.30 +
            s["homework"]["avg_score"] * 0.35)
    s["performance_score"] = round(perf, 1)
    s["performance_label"] = ("A'lo" if perf >= 88 else "Yaxshi" if perf >= 75
                              else "Qoniqarli" if perf >= 60 else "Past")
    s["risk_level"] = ("high" if (s["attendance"]["attendance_rate"] < 70 or
                                  s["homework"]["submission_rate"] < 50) else
                       "medium" if (s["attendance"]["attendance_rate"] < 85 or
                                    s["homework"]["submission_rate"] < 70) else "low")
    s.pop("_profile")

# coins bo'yicha reyting
for i, s in enumerate(sorted(students, key=lambda x: -x["coins"]["balance"]), 1):
    s["coins"]["rank_overall"] = i
grp_rank = defaultdict(int)
for s in sorted(students, key=lambda x: (x["group_id"], -x["coins"]["balance"])):
    grp_rank[s["group_id"]] += 1
    s["coins"]["rank_in_group"] = grp_rank[s["group_id"]]

# --------------------------------------------------------- GURUH STATISTIKA
for g in groups:
    ss = students_by_group[g["id"]]
    g["students_count"] = len(ss)
    g["total_lessons"] = len([l for l in lessons_by_group[g["id"]]
                              if date.fromisoformat(l["date"]) <= TODAY])
    g["avg_attendance_rate"] = round(sum(s["attendance"]["attendance_rate"] for s in ss) / len(ss), 1)
    g["avg_homework_rate"]  = round(sum(s["homework"]["submission_rate"] for s in ss) / len(ss), 1)
    g["avg_score"] = round(sum(s["homework"]["avg_score"] for s in ss) / len(ss), 1)
    g["students_at_risk"] = sum(1 for s in ss if s["risk_level"] == "high")
    g["students_behind"] = sum(1 for s in ss if s["attendance"]["is_behind"])
    g["monthly_revenue"] = len(ss) * g["monthly_fee"]

# xodimlar yuklamasi
for m in mentors:
    gs = [g for g in groups if g["mentor_id"] == m["id"]]
    m["groups_count"] = len(gs)
    m["students_count"] = sum(g["students_count"] for g in gs)
    m["lessons_taught"] = sum(g["total_lessons"] for g in gs)
    m["avg_group_attendance"] = round(sum(g["avg_attendance_rate"] for g in gs)/len(gs), 1) if gs else 0
for t in tutors:
    ts = [x for x in tutor_sessions if x["tutor_id"] == t["id"]]
    t["sessions_count"] = len(ts)
    t["students_helped"] = len({x["student_id"] for x in ts})
    t["total_hours"] = round(sum(x["duration_min"] for x in ts) / 60, 1)
for c in curators:
    cs = [x for x in curator_contacts if x["curator_id"] == c["id"]]
    my = [s for s in students if s["curator_id"] == c["id"]]
    c["students_count"] = len(my)
    c["contacts_count"] = len(cs)
    c["unresolved_contacts"] = sum(1 for x in cs if not x["resolved"])
    c["students_at_risk"] = sum(1 for s in my if s["risk_level"] == "high")

# ------------------------------------------------------------- YOZIB QO'YISH
def dump(p, o, ind=None):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=ind)
    return os.path.getsize(p)

def to_csv(p, rows):
    flat = []
    for r in rows:
        fr = {}
        for k, v in r.items():
            if isinstance(v, (dict, list)):
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        fr[f"{k}_{k2}"] = v2
                else:
                    fr[k] = "|".join(map(str, v))
            else:
                fr[k] = v
        flat.append(fr)
    keys = list({k for r in flat for k in r})
    order = list(flat[0].keys()) + [k for k in keys if k not in flat[0]]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=order); w.writeheader(); w.writerows(flat)
    return os.path.getsize(p)

meta = {
    "name": "LMS demo dataset (IT-akademiya, O'zbekiston)",
    "roles": ["student", "mentor", "tutor", "curator"],
    "role_meaning": {
        "student": "Mijoz — o'quvchi. Davomat, coins, uy vazifasi kuzatiladi",
        "mentor": "Asosiy dars o'tuvchi. Dars o'tadi, vazifa beradi va tekshiradi",
        "tutor": "Qo'shimcha dars o'tuvchi. Individual/mini-guruh sessiyalari, qoldirilgan darslarni yopadi",
        "curator": "Ota-onalar bilan bog'lanuvchi. Davomat/to'lov/progress bo'yicha xabar beradi",
    },
    "term_start": TERM_START.isoformat(),
    "term_end": TERM_END.isoformat(),
    "counts": {
        "students": len(students), "mentors": len(mentors), "tutors": len(tutors),
        "curators": len(curators), "groups": len(groups), "courses": len(COURSES),
        "lessons": len(lessons), "attendance_records": len(attendance),
        "homework_assignments": len(homework_assignments),
        "homework_submissions": len(homework_submissions),
        "coin_transactions": len(coin_tx), "makeup_sessions": len(makeups),
        "tutor_sessions": len(tutor_sessions), "curator_contacts": len(curator_contacts),
        "payments": len(payments),
    },
    "coin_rules": {
        "attendance_present": 10, "attendance_late": 4, "absent_unexcused": -5,
        "streak_10_lessons": 50, "homework": "15-30 × (ball/100), kech topshirsa ×0.6",
        "excellent_work_95plus": 25, "activity_in_class": "5-15",
        "makeup_completed": 10, "shop_items": [{"item": i, "cost": c} for i, c in SHOP],
    },
    "currency": "UZS",
}

sizes = {}
sizes["meta.json"] = dump(f"{OUT}/meta.json", meta, 2)
sizes["students.json"] = dump(f"{OUT}/students.json", students, 2)
sizes["mentors.json"] = dump(f"{OUT}/mentors.json", mentors, 2)
sizes["tutors.json"] = dump(f"{OUT}/tutors.json", tutors, 2)
sizes["curators.json"] = dump(f"{OUT}/curators.json", curators, 2)
sizes["groups.json"] = dump(f"{OUT}/groups.json", groups, 2)
sizes["courses.json"] = dump(f"{OUT}/courses.json", [
    {"code":c[0],"name":c[1],"duration_months":c[2],"lessons_per_week":c[3],
     "level":c[4],"monthly_fee":c[5],"age_range":c[6],"topics":TOPICS[c[0]]} for c in COURSES], 2)
sizes["lessons.json"] = dump(f"{OUT}/lessons.json", lessons)
sizes["attendance.json"] = dump(f"{OUT}/attendance.json", attendance)
sizes["homework_assignments.json"] = dump(f"{OUT}/homework_assignments.json", homework_assignments)
sizes["homework_submissions.json"] = dump(f"{OUT}/homework_submissions.json", homework_submissions)
sizes["coin_transactions.json"] = dump(f"{OUT}/coin_transactions.json", coin_tx)
sizes["makeup_sessions.json"] = dump(f"{OUT}/makeup_sessions.json", makeups, 2)
sizes["tutor_sessions.json"] = dump(f"{OUT}/tutor_sessions.json", tutor_sessions, 2)
sizes["curator_contacts.json"] = dump(f"{OUT}/curator_contacts.json", curator_contacts, 2)
sizes["payments.json"] = dump(f"{OUT}/payments.json", payments, 2)

sizes["students.csv"] = to_csv(f"{OUT}/students.csv", students)
sizes["attendance.csv"] = to_csv(f"{OUT}/attendance.csv", attendance)
sizes["homework_submissions.csv"] = to_csv(f"{OUT}/homework_submissions.csv", homework_submissions)
sizes["coin_transactions.csv"] = to_csv(f"{OUT}/coin_transactions.csv", coin_tx)
sizes["groups.csv"] = to_csv(f"{OUT}/groups.csv", groups)
sizes["payments.csv"] = to_csv(f"{OUT}/payments.csv", payments)

dump(f"{OUT}/lms_full.json", {
    "meta": meta, "courses": [c[0] for c in COURSES], "groups": groups,
    "mentors": mentors, "tutors": tutors, "curators": curators, "students": students,
})

print(json.dumps({"counts": meta["counts"],
                  "sizes_kb": {k: round(v/1024,1) for k,v in sizes.items()}},
                 ensure_ascii=False, indent=2))

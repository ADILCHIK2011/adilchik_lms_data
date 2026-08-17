# LMS datasi — student / mentor / tutor / curator

Sintetik (test/demo) LMS datasi. IT-akademiya konteksti, O'zbekiston. Valyuta — **UZS**.
Semestr: **2026-02-02 → 2026-07-31**.

## Rollar

| Rol | Vazifasi | Datada nima bor |
|---|---|---|
| **student** | Mijoz — o'quvchi | Davomat, coins, uy vazifasi, to'lovlar, ota-ona kontakti |
| **mentor** | Asosiy dars o'tuvchi | Guruhlar, o'tilgan darslar, vazifa berish/tekshirish, guruh davomati |
| **tutor** | Qo'shimcha dars o'tuvchi | Individual/mini-guruh sessiyalari, qoldirilgan darsni yopish |
| **curator** | Ota-onalar bilan bog'lanuvchi | Aloqa tarixi (davomat, to'lov, progress, maqtov), javoblar, follow-up |

## Hajm

| | |
|---|---|
| O'quvchilar | **294** |
| Mentorlar / Tutorlar / Curatorlar | 14 / 18 / 9 |
| Guruhlar / Kurslar | 26 / 8 |
| Darslar | 1 731 |
| Davomat yozuvlari | **19 355** |
| Uy vazifalari / topshirishlar | 1 595 / **16 557** |
| Coin tranzaksiyalari | **38 604** |
| Makeup (yopilgan dars) | 1 230 |
| Tutor sessiyalari | 1 030 |
| Curator aloqalari | 1 609 |
| To'lovlar | 1 764 |

## Fayllar

| Fayl | Nima bor |
|---|---|
| `students.json` | 294 o'quvchi — profil + ota-ona + davomat/vazifa/coins statistikasi |
| `mentors.json` / `tutors.json` / `curators.json` | Xodimlar + yuklama ko'rsatkichlari |
| `groups.json` / `courses.json` | Guruhlar (jadval, xona, mentor/tutor/curator) va kurs dasturi |
| `lessons.json` | 1 731 dars — sana, mavzu, modul, turi (lecture/practice/exam) |
| `attendance.json` | Har dars × har o'quvchi davomat yozuvi |
| `homework_assignments.json` | Vazifa: deadline, max ball, coin mukofoti, qiyinlik |
| `homework_submissions.json` | Topshirish: sana, kechikish, ball, coin, mentor izohi |
| `coin_transactions.json` | To'liq coin ledger (`balance_after` bilan) |
| `makeup_sessions.json` | Qoldirilgan darsni yopish yozuvlari |
| `tutor_sessions.json` | Tutor qo'shimcha darslari |
| `curator_contacts.json` | Curator ↔ ota-ona aloqa tarixi |
| `payments.json` | Oylik to'lovlar (Payme/Click/Naqd, chegirma, kechikish) |
| `lms_full.json` | Hammasi bitta faylda |
| CSV'lar | students, attendance, homework_submissions, coin_transactions, groups, payments |
| `types.ts` | TypeScript interfeyslar + helper funksiyalar |
| `schema.prisma` | PostgreSQL uchun tayyor Prisma schema (enum'lar, index'lar, relation'lar) |
| `gen_lms.py` | Generator (seed=7) |

## Coin tizimi

**Ishlab olish:**

| Harakat | Coin |
|---|---|
| Darsga o'z vaqtida kelish | +10 |
| Kechikib kelish | +4 |
| 10 ta ketma-ket dars (streak) | +50 bonus |
| Uy vazifasi | `mukofot × (ball/100)`, kech topshirsa `×0.6` |
| 95+ ball olish | +25 |
| Darsdagi faollik | +5…15 |
| Qoldirilgan darsni yopish | +10 |
| **Sababsiz qoldirish** | **−5** |

**Sarflash (do'kon):** stiker 80 → futbolka 450 → ryukzak 900 → quloqchin 1500 → bepul 1 oy kurs 3000

Har bir tranzaksiyada `balance_after` bor, ya'ni balansni qayta hisoblamasdan tarixni ko'rsatish mumkin.

## "Darslardan qolib ketmaslik" mexanikasi

Bu asosiy mantiq — data shunday qurilgan:

1. O'quvchi darsni qoldiradi → `attendance.status = absent_excused | absent_unexcused`
2. Qoldirilgan dars **makeup** orqali yopiladi (`makeup_sessions.json`):
   - `tutor_session` (55%) — tutor bilan individual
   - `video_recording` (30%) — yozuvni ko'radi + quiz
   - `self_study` (15%) — mustaqil + quiz
3. Har bir o'quvchida hisoblab qo'yilgan:
   - `attendance.missed_covered_by_makeup` — yopilgan
   - `attendance.missed_not_covered` — **yopilmagan** (asosiy signal)
   - `attendance.is_behind` — `true`, agar yopilmagan > 3

Hozirgi datada **294 tadan 108 tasi** `is_behind = true` — dashboardda "ortda qolganlar" bloki uchun yetarli.

**Curator avtomatik ishga tushadi:** o'quvchi **2 ta ketma-ket** dars qoldirsa, `curator_contacts` ga `reason: "absence_alert"` yozuvi tushadi — kanal, ota-ona javobi, `resolved` va `follow_up_needed` bilan.

## O'quvchi profillari

Har bir o'quvchiga yashirin profil berilgan, u davomat va vazifa ehtimolligini boshqaradi:

| Profil | Ulush | Kelish | Vazifa topshirish | O'rtacha ball |
|---|---|---|---|---|
| A'lochi | 16% | 97% | 98% | ~92 |
| Yaxshi | 30% | 93% | 92% | ~82 |
| O'rtacha | 32% | 86% | 80% | ~71 |
| Zaif | 15% | 75% | 58% | ~58 |
| Xavf ostida | 7% | 58% | 34% | ~45 |

Zaif o'quvchilarga tutor sessiyalari ko'proq beriladi (5–12 ta), a'lochilarga 0–2 ta.

**Natijaviy taqsimot:** A'lo 91 · Yaxshi 135 · Qoniqarli 34 · Past 34
**Risk:** low 204 · medium 57 · high 33
**O'rtachalar:** davomat 86.9% · vazifa 80.4% · ball 69.9 · coin balans 891

## Student obyekti

```json
{
  "id": 42,
  "code": "STU-10042",
  "full_name": "Sarvar Ismoilov",
  "age": 16,
  "group_name": "FE-RCT-006",
  "mentor_id": 5, "tutor_id": 112, "curator_id": 204,
  "parent": {
    "full_name": "Anvar Ismoilov",
    "relation": "Ota",
    "phone": "+998901234567",
    "telegram": "@anvar123",
    "preferred_contact": "telegram"
  },
  "attendance": {
    "total_lessons": 72, "present": 68, "late": 2,
    "absent_excused": 1, "absent_unexcused": 1,
    "attendance_rate": 97.2, "punctuality_rate": 94.4,
    "missed_covered_by_makeup": 2, "missed_not_covered": 0,
    "is_behind": false
  },
  "homework": {
    "assigned": 66, "submitted": 65, "on_time": 62, "late": 3,
    "not_submitted": 1, "submission_rate": 98.5,
    "avg_score": 90.6, "best_score": 100
  },
  "coins": { "balance": 2465, "total_earned": 2915, "total_spent": 450,
             "rank_overall": 3, "rank_in_group": 1 },
  "performance_score": 92.8,
  "performance_label": "A'lo",
  "risk_level": "low"
}
```

## Tez boshlash

**Prisma bilan (NestJS):**
```bash
cp schema.prisma prisma/schema.prisma
npx prisma migrate dev --name init
# seed skript yozib JSON'larni to'g'ridan-to'g'ri createMany bilan yuklaysiz
```

**React dashboard uchun:**
```ts
import { STUDENTS, studentsBehind, leaderboard, atRisk } from "./types";

studentsBehind();        // ortda qolganlar, eng ko'p qoldirgani birinchi
atRisk("high");          // curator shoshilinch ishlashi kerak bo'lganlar
leaderboard(10);         // coins reytingi
leaderboard(10, 6);      // guruh ichida
```

**pandas bilan:**
```python
import pandas as pd
att = pd.read_csv("attendance.csv", parse_dates=["date"])

# Guruh davomati vaqt bo'yicha
att.assign(ok=att.status.isin(["present","late"])) \
   .groupby([pd.Grouper(key="date", freq="W"), "group_id"])["ok"].mean()

# Coins taqsimoti
coins = pd.read_csv("coin_transactions.csv")
coins.groupby("reason")["amount"].agg(["sum","count"])
```

## Qayta generatsiya

```bash
python3 gen_lms.py     # seed=7 — aynan shu data qaytadan chiqadi
```

O'zgartirish mumkin: `TERM_START`/`TERM_END`, `COURSES` ro'yxati, `TOPICS` dars mavzulari, `P` (profil ehtimolliklari), `SHOP` (coin do'koni), coin miqdorlari.

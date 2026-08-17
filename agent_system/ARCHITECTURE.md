# LMS Multi-Agent tahlil tizimi — arxitektura

Kod: `agent_system/`. Haqiqiy datasetga (294 o'quvchi, `../students.json` va h.k.)
qarshi ishga tushirilib tekshirilgan. Ishga tushirish:

```bash
python3 -m agent_system.main --source .          # bir marta ishlaydi, reports/latest.json yozadi
python3 -m agent_system.main --source export.zip # ZIP export bilan ham ishlaydi
python3 -m agent_system.main --source . --schedule   # har soatda (APScheduler)
```

## 1. Stek va nima uchun

| Qatlam | Tanlov | Sabab |
|---|---|---|
| Agent orkestratsiyasi | **LangGraph** (CrewAI emas) | Bu workflow — aniq ketma-ketlikka ega DAG, qat'iy data-kontraktlar bilan (Agent 2 Agent 1'ning bayroqlariga muhtoj, Agent 3 ikkalasiga ham). CrewAI erkin "rol o'ynovchi" agentlar uchun mo'ljallangan; LangGraph esa aniq state-machine + shartli edge'lar berib, har bosqichdan keyin state'ni checkpoint qiladi — debugging va observability uchun bepul. |
| Validatsiya | **Pydantic v2** | `types.ts`/`schema.prisma` bilan bir xil maydonlar; noto'g'ri qatorni butun faylni buzmasdan alohida rad etish imkonini beradi. |
| Analitika | Sof Python (pandas'siz) | Hajm (~20k davomat yozuvi) uchun stdlib yetarli, qo'shimcha bog'liqlik shart emas. |
| LLM (ixtiyoriy) | **Claude** (Anthropic SDK) | Shaxsiy tavsiya matni uchun; kalit bo'lmasa yoki xato bo'lsa — shablon matnga avtomatik qaytadi. |
| Bulut DB | **PostgreSQL** (`schema.prisma` allaqachon mavjud) | NestJS/Prisma backend bilan bevosita moslashadi. |
| Xabarnoma | **Telegram Bot API** (to'g'ridan-to'g'ri HTTPS, kutubxonasiz) | Yengil, `httpx` orqali; token bo'lmasa — dry-run rejimda konsolga yozadi. |
| Tashqi integratsiya | **MCP** (JSON-RPC 2.0 / HTTP) | Boshqa agent flotiga/dashboard'ga hisobotni "tool call" sifatida e'lon qilish uchun minimal klient. |
| Scheduler | **APScheduler** | `--schedule` bilan jarayon ichida soatlik cron; prod'da tashqi cron/K8s CronJob bilan ham almashtirilishi mumkin (`main.py` bitta jarayon sifatida chaqiriladi). |

## 2. Agentlar zanjiri

```
      ┌─────────┐   ok    ┌────────────┐    ┌─────────────┐    ┌──────────────┐
START →│ ingest  │────────→│ Agent 1     │───→│ Agent 2      │───→│ Agent 3       │→ END
      │ (ZIP/dir)│         │ Davomat     │    │ O'zlashtirish │    │ Integratsiya │
      └────┬────┘          └────────────┘    └─────────────┘    └──────────────┘
           │ fatal (ZIP o'qilmadi / dataset bo'sh)
           └──────────────────────────────────────────────────────────────→ END
```

- **ingest** (`ingestion.py`) — ZIP yoki katalogni o'qiydi, har qatorni Pydantic bilan
  tekshiradi, xato qatorlarni "karantin"ga oladi, orphan FK'larni tashlab yuboradi.
- **Agent 1** (`attendance_agent.py`) — har o'quvchi tarixini 13 talik oynolarga bo'lib,
  7 tadan kam kelganlarni bayroqlaydi; sabab (`documented_excused` / `homework_avoidance`
  / `unexplained`) ni curator kontaktlari va shu davrdagi uy vazifasi ko'rsatkichlari bilan
  chatishtirib aniqlaydi; 2+ ketma-ket qoldirganlar uchun curator alert generatsiya qiladi.
- **Agent 2** (`performance_agent.py`, `ranking.py`) — davomat/uy vazifa/ball asosida
  `performance_score` hisoblaydi (Agent 1 bayroqlari jarima sifatida qo'shiladi), guruh
  va o'quvchi darajasida qiyin mavzularni topadi, reyting (top/bottom) va shaxsiy
  tavsiya matnini (LLM yoki shablon) tuzadi.
- **Agent 3** (`integration_agent.py`, `storage.py`, `notify.py`, `mcp_client.py`,
  `cli_exec.py`) — avvalgi muvaffaqiyatsiz sinxronizatsiya navbatini bo'shatadi, yangi
  hisobotni bulutga yozadi (yoki fallback navbatga), curator alert'lar uchun ota-onaga
  Telegram xabar yuboradi, hisobotni MCP orqali e'lon qiladi, ixtiyoriy ravishda data
  repo'ning git commit'ini (xavfsiz CLI executor orqali) hisobotga tegga oladi.

## 3. Ma'lumot kontrakti (`models.PipelineState`)

`data_source → bundle → attendance_out → performance_out → integration_out`.
Har bosqich faqat oldingisining Pydantic chiqishiga bog'liq — hech qaysi agent
xom JSON fayllarga bevosita murojaat qilmaydi, faqat `DataBundle` orqali.

## 4. Xatoliklarni boshqarish / fallback jadvali

| Holat | Qaror |
|---|---|
| ZIP fayl buzilgan / umuman ochilmaydi | `IngestionFatalError` → graf `abort` shoxobchasiga o'tadi, `PipelineState.aborted=True`, sabab `errors`da — hech qanday yarim-tayyor hisobot yozilmaydi. |
| `students.json` va `attendance.json` ikkalasi ham yo'q | Tahlil qilib bo'lmaydi → fatal xato (yuqoridagi kabi). |
| Boshqa fayl (masalan `coin_transactions.json`) yo'q | `quality.files_missing`ga yoziladi, o'sha to'plam bo'sh ro'yxat sifatida davom etadi — pipeline to'xtamaydi. |
| Bitta qator noto'g'ri formatda (masalan noto'g'ri enum qiymati) | Faqat o'sha qator `quality.quarantined`ga yoziladi, qolgan qatorlar yuklanadi. |
| Attendance/homework/coin yozuvi noma'lum `student_id`ga ishora qiladi | Qator tashlab yuboriladi, `orphaned_fk_count` oshiriladi — soxta o'quvchi hech qayerda paydo bo'lmaydi. |
| O'quvchining so'nggi oynasi juda qisqa (yangi qo'shilgan) | Baholanmaydi, sababi `notes`ga yoziladi — noto'g'ri "kam kelgan" bayrog'i qo'yilmaydi. |
| `ANTHROPIC_API_KEY` yo'q yoki LLM chaqiruvi xato bersa | `_llm_recommendation` `None` qaytaradi → shablon matnga avtomatik qaytish, `source="template"` deb belgilanadi. |
| `DATABASE_URL` yo'q yoki Postgres yozib bo'lmadi | Hisobot lokal SQLite navbatiga (`reports/fallback_queue.sqlite3`) yoziladi; keyingi ishga tushirishda avval shu navbat bo'shatiladi (`flush_fallback_queue`). |
| Telegram HTTP xatosi / 429 | 3 martagacha eksponensial backoff bilan qayta urinadi; oxirida ham muvaffaqiyatsiz bo'lsa — o'sha bitta xabar `ok=False` deb belgilanadi, boshqa xabarlar davom etadi (bitta noto'g'ri chat_id butun jarayonni to'xtatmaydi). |
| Ota-ona/curator uchun Telegram/chat ID topilmadi | `NotificationResult(ok=False, error=...)`, jarayon davom etadi. |
| `MCP_SERVER_URL` sozlanmagan | `NoOpMCPClient` — `mcp_published=False` sifatida ochiq ko'rsatiladi (jim yutilmaydi). |
| CLI buyrug'i allowlist'da yo'q | `CLIExecutionError` — subprocess umuman ishga tushirilmaydi (`shell=True` hech qachon ishlatilmaydi). |
| Joriy katalog git repo emas (git buyrug'i xato bersa) | Faqat `data_repo_commit` maydoni hisobotga qo'shilmaydi, xato yutiladi — ixtiyoriy metadata. |

## 5. Prodakshnga chiqarish

1. `.env.example` → `.env`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_DEFAULT_CHAT_ID`, `MCP_SERVER_URL`, `ANTHROPIC_API_KEY` to'ldiriladi.
2. Postgres: `schema.prisma`dagi jadvallardan tashqari `storage.py` avtomatik
   `lms_agent_reports` jadvalini yaratadi (append-only audit log sifatida).
3. Scheduler: `python -m agent_system.main --schedule` bitta uzoq muddatli
   jarayon sifatida (systemd/K8s Deployment) yoki tashqi cron orqali soatiga
   bir marta `--source` bilan chaqiriladi.
4. Dashboard uchun API kerak bo'lsa, `reports/latest.json` (yoki Postgres'dagi
   `lms_agent_reports` jadvali) FastAPI/NestJS orqali o'qiladi — bu qatlam
   hozircha kod bazasida yo'q, chunki mavjud `schema.prisma`/NestJS backend
   buni allaqachon qamrab olishi mumkin.

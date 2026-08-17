// ============================================================================
// LMS datasi — TypeScript tiplari
// Rollar: student | mentor | tutor | curator
// ============================================================================

export type Role = "student" | "mentor" | "tutor" | "curator";

export type AttendanceStatus =
  | "present"           // keldi
  | "late"              // kechikdi
  | "absent_excused"    // sababli qoldirdi
  | "absent_unexcused"; // sababsiz qoldirdi

export type HomeworkStatus =
  | "submitted_on_time"
  | "submitted_late"
  | "not_submitted";

export type RiskLevel = "low" | "medium" | "high";
export type PerformanceLabel = "A'lo" | "Yaxshi" | "Qoniqarli" | "Past";
export type MakeupMode = "tutor_session" | "video_recording" | "self_study";
export type PaymentStatus = "paid" | "late" | "unpaid";

// ---------------------------------------------------------------- XODIMLAR

interface StaffBase {
  id: number;
  code: string;              // "MNT-3", "TUT-105", "CUR-203"
  role: Exclude<Role, "student">;
  first_name: string;
  last_name: string;
  full_name: string;
  gender: "male" | "female";
  phone: string;
  email: string;
  telegram: string;
  experience_years: number;
  rating: number;            // 3.4 – 5.0
  monthly_salary: number;    // UZS
  hired_at: string;
  status: "active" | "vacation";
  specialization?: string;
}

/** Dars o'tuvchi — guruhga biriktirilgan, vazifa beradi va tekshiradi */
export interface Mentor extends StaffBase {
  role: "mentor";
  groups_count: number;
  students_count: number;
  lessons_taught: number;
  avg_group_attendance: number;
}

/** Qo'shimcha dars o'tuvchi — individual sessiyalar, qoldirilgan darslarni yopadi */
export interface Tutor extends StaffBase {
  role: "tutor";
  sessions_count: number;
  students_helped: number;
  total_hours: number;
}

/** Ota-onalar bilan bog'lanuvchi */
export interface Curator extends StaffBase {
  role: "curator";
  max_students: number;
  students_count: number;
  contacts_count: number;
  unresolved_contacts: number;
  students_at_risk: number;
}

// ---------------------------------------------------------------- STUDENT

export interface Parent {
  full_name: string;
  relation: "Ota" | "Ona" | "Buvi" | "Bobo" | "Aka" | "Opa";
  phone: string;
  telegram: string;
  preferred_contact: "telegram" | "phone" | "sms";
}

export interface StudentAttendance {
  total_lessons: number;
  present: number;
  late: number;
  absent: number;
  absent_excused: number;
  absent_unexcused: number;
  attendance_rate: number;        // (present + late) / total
  punctuality_rate: number;       // present / total
  /** qoldirilgan darsdan nechtasi makeup bilan yopilgan */
  missed_covered_by_makeup: number;
  /** yopilmagan — shu raqam o'sib ketsa student ortda qoladi */
  missed_not_covered: number;
  /** true = darslardan qolib ketgan (yopilmagan > 3) */
  is_behind: boolean;
}

export interface StudentHomework {
  assigned: number;
  submitted: number;
  on_time: number;
  late: number;
  not_submitted: number;
  submission_rate: number;
  on_time_rate: number;
  avg_score: number;
  best_score: number;
}

export interface StudentCoins {
  balance: number;
  total_earned: number;
  total_spent: number;
  rank_overall: number;
  rank_in_group: number;
}

export interface Student {
  id: number;
  code: string;                  // "STU-10042"
  role: "student";
  first_name: string;
  last_name: string;
  full_name: string;
  gender: "male" | "female";
  birth_date: string;
  age: number;
  phone: string;
  telegram: string;
  school: string;
  grade: number;
  district: string;
  group_id: number;
  group_name: string;
  course_code: string;
  mentor_id: number;
  tutor_id: number;
  curator_id: number;
  parent: Parent;
  enrolled_at: string;
  monthly_fee: number;
  status: "active";
  attendance: StudentAttendance;
  homework: StudentHomework;
  coins: StudentCoins;
  tutor_sessions_count: number;
  makeup_count: number;
  performance_score: number;     // 0–100 (davomat 35% + vazifa 30% + ball 35%)
  performance_label: PerformanceLabel;
  risk_level: RiskLevel;
}

// ------------------------------------------------------------ GURUH / DARS

export interface Group {
  id: number;
  name: string;                  // "FE-RCT-006"
  course_code: string;
  course_name: string;
  level: string;
  age_range: string;
  mentor_id: number;
  tutor_id: number;
  curator_id: number;
  room: string;
  schedule_type: "odd" | "even" | "tue_thu" | "mon_wed" | "sat_sun";
  schedule_days: number[];       // 1 = Dushanba … 7 = Yakshanba
  lesson_start: string;
  lesson_end: string;
  duration_min: number;
  monthly_fee: number;
  duration_months: number;
  started_at: string;
  status: "active";
  students_count: number;
  total_lessons: number;
  avg_attendance_rate: number;
  avg_homework_rate: number;
  avg_score: number;
  students_at_risk: number;
  students_behind: number;
  monthly_revenue: number;
}

export interface Course {
  code: string;
  name: string;
  duration_months: number;
  lessons_per_week: number;
  level: string;
  monthly_fee: number;
  age_range: string;
  topics: string[];
}

export interface Lesson {
  id: number;
  group_id: number;
  lesson_number: number;
  date: string;
  weekday: number;
  start_time: string;
  end_time: string;
  topic: string;
  module: number;
  type: "lecture" | "practice" | "exam";
  mentor_id: number;
  room: string;
  has_homework: boolean;
  status: "completed" | "planned";
}

// -------------------------------------------------------------- YOZUVLAR

export interface AttendanceRecord {
  id: number;
  student_id: number;
  lesson_id: number;
  group_id: number;
  date: string;
  status: AttendanceStatus;
  minutes_late: number;
  marked_by_mentor_id: number;
  note: string;
}

export interface HomeworkAssignment {
  id: number;
  lesson_id: number;
  group_id: number;
  title: string;
  assigned_date: string;
  due_date: string;
  max_score: number;
  coins_reward: number;
  difficulty: "oson" | "o'rta" | "qiyin";
  created_by_mentor_id: number;
}

export interface HomeworkSubmission {
  id: number;
  homework_id: number;
  student_id: number;
  group_id: number;
  assigned_date: string;
  due_date: string;
  submitted_at: string | null;
  status: HomeworkStatus;
  days_late: number | null;
  score: number;
  coins_earned: number;
  mentor_feedback: string;
  checked_by_mentor_id: number;
}

export type CoinReason =
  | "attendance" | "attendance_late" | "streak_bonus" | "homework"
  | "excellent_work" | "activity" | "makeup_completed"
  | "absent_unexcused" | "shop";

export interface CoinTransaction {
  id: number;
  student_id: number;
  date: string;
  type: "earn" | "spend" | "penalty";
  reason: CoinReason;
  description: string;
  amount: number;              // spend/penalty da manfiy
  balance_after: number;
  ref_lesson_id?: number;
  ref_homework_id?: number;
  ref_item?: string;
}

/** Qoldirilgan darsni yopish — "qolib ketmaslik" mexanikasi */
export interface MakeupSession {
  id: number;
  student_id: number;
  missed_lesson_id: number;
  missed_date: string;
  makeup_date: string;
  mode: MakeupMode;
  tutor_id: number | null;
  duration_min: number;
  topic: string;
  completed: boolean;
  quiz_score: number;
}

/** Tutor qo'shimcha darsi */
export interface TutorSession {
  id: number;
  student_id: number;
  tutor_id: number;
  group_id: number;
  date: string;
  start_time: string;
  duration_min: number;
  type: "individual" | "mini_group";
  topic: string;
  reason: string;
  attended: boolean;
  progress_note: string;
}

/** Curator ↔ ota-ona aloqasi */
export interface CuratorContact {
  id: number;
  curator_id: number;
  student_id: number;
  date: string;
  channel: "telegram" | "phone" | "sms";
  reason: "absence_alert" | "monthly_report" | "progress_update"
        | "payment_reminder" | "homework_alert" | "praise" | "meeting_invite";
  subject: string;
  summary: string;
  parent_response: string;
  resolved: boolean;
  follow_up_needed: boolean;
}

export interface Payment {
  id: number;
  student_id: number;
  group_id: number;
  period: string;              // "2026-04"
  amount: number;
  due_date: string;
  paid_at: string | null;
  status: PaymentStatus;
  method: "Payme" | "Click" | "Naqd" | "Uzcard" | "Humo";
  discount_pct: number;
}

// ============================================================================
// Helperlar
// ============================================================================

import studentsJson from "./students.json";
import attendanceJson from "./attendance.json";
import coinsJson from "./coin_transactions.json";
import submissionsJson from "./homework_submissions.json";

export const STUDENTS = studentsJson as Student[];
export const ATTENDANCE = attendanceJson as AttendanceRecord[];
export const COINS = coinsJson as CoinTransaction[];
export const SUBMISSIONS = submissionsJson as HomeworkSubmission[];

/** Darslardan qolib ketganlar — curator ishlashi kerak bo'lganlar */
export const studentsBehind = () =>
  STUDENTS.filter((s) => s.attendance.is_behind).sort(
    (a, b) => b.attendance.missed_not_covered - a.attendance.missed_not_covered
  );

/** Xavf ostidagilar */
export const atRisk = (level: RiskLevel = "high") =>
  STUDENTS.filter((s) => s.risk_level === level);

/** Coins leaderboard */
export const leaderboard = (n = 10, groupId?: number) =>
  STUDENTS.filter((s) => !groupId || s.group_id === groupId)
    .sort((a, b) => b.coins.balance - a.coins.balance)
    .slice(0, n);

/** Bitta o'quvchining coin tarixi */
export const coinHistory = (studentId: number) =>
  COINS.filter((t) => t.student_id === studentId);

/** Vazifa topshirmayotganlar (oxirgi N ta topshiriq bo'yicha) */
export function missingHomework(studentId: number, lastN = 5) {
  return SUBMISSIONS.filter((h) => h.student_id === studentId)
    .slice(-lastN)
    .filter((h) => h.status === "not_submitted");
}

/** Guruh davomati sana kesimida */
export function groupAttendanceByDate(groupId: number) {
  const map: Record<string, { present: number; total: number }> = {};
  for (const a of ATTENDANCE) {
    if (a.group_id !== groupId) continue;
    map[a.date] ??= { present: 0, total: 0 };
    map[a.date].total++;
    if (a.status === "present" || a.status === "late") map[a.date].present++;
  }
  return Object.entries(map).map(([date, v]) => ({
    date,
    rate: Math.round((v.present / v.total) * 1000) / 10,
  }));
}

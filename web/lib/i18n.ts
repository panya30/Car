import { cookies } from "next/headers";

export type Locale = "th" | "en";
export const LOCALES: Locale[] = ["th", "en"];
export const DEFAULT_LOCALE: Locale = "th";

/** Read the user's locale from the `lang` cookie (set by /api/lang/<locale>).
 *  Default Thai — that's the audience for these listings. */
export async function getLocale(): Promise<Locale> {
  const c = await cookies();
  const v = c.get("lang")?.value;
  return v === "en" ? "en" : "th";
}

/** Translation dictionary. Keys grouped by page; missing keys fall back
 *  to English, then to the raw key. */
const dict: Record<Locale, Record<string, string>> = {
  th: {
    // --- nav ---
    brand_subtitle: "/ ตลาดรถ",
    nav_overview: "ภาพรวม",
    nav_listings: "ประกาศ",
    nav_stories: "บทวิเคราะห์",
    nav_matches: "ข้ามแพลตฟอร์ม",
    nav_alerts: "แจ้งเตือน",
    nav_runs: "ประวัติเก็บข้อมูล",
    footer_data: "ข้อมูล: SQLite snapshot · refresh:",

    // --- overview ---
    overview_title: "ภาพรวม",
    overview_latest: "Snapshot ล่าสุด:",
    stat_in_latest: "รถใน snapshot ล่าสุด",
    stat_distinct_ever: "รถที่ไม่ซ้ำทั้งหมด",
    stat_snapshots: "Snapshots",
    stat_total_rows: "Rows ทั้งหมด",
    card_top_makes: "แบรนด์ยอดนิยม (snapshot ล่าสุด)",
    card_year_dist: "การกระจายตามปี",
    card_recent_runs: "การเก็บข้อมูลล่าสุด",
    th_make: "แบรนด์",
    th_n: "จำนวน",
    th_avg_price: "เฉลี่ย ฿",
    th_range: "ช่วง ฿",

    // --- listings ---
    listings_title: "ประกาศรถ",
    listings_count_one: "รถ",
    page_of: "หน้า",
    of: "จาก",
    all_sources: "ทุกแหล่ง",
    all_makes: "ทุกแบรนด์",
    any_fuel: "เชื้อเพลิงทั้งหมด",
    any_transmission: "เกียร์ทั้งหมด",
    any_body: "ตัวถังทั้งหมด",
    any_color: "สีทั้งหมด",
    placeholder_year: "ปี",
    placeholder_min: "ราคาต่ำสุด ฿",
    placeholder_max: "ราคาสูงสุด ฿",
    placeholder_max_km: "ไมล์สูงสุด",
    placeholder_search: "ค้นหาชื่อ…",
    btn_filter: "กรอง",
    sort_year_desc: "ปีล่าสุดก่อน",
    sort_price_desc: "ราคาสูง→ต่ำ",
    sort_price_asc: "ราคาต่ำ→สูง",
    sort_mileage_asc: "ไมล์น้อยสุด",
    sort_views_desc: "ยอดวิวสูงสุด",
    no_matches: "ไม่พบรายการ",
    pagination_prev: "← ก่อนหน้า",
    pagination_next: "ถัดไป →",
    suffix_views: "วิว",

    // --- stories ---
    stories_title: "บทวิเคราะห์ตามกลุ่มรถ",
    stories_intro:
      "รายงาน 6 ส่วนต่อกลุ่มรถ (Cohort-indexed Story Unit). " +
      "ANOMALY = ราคา+ไมล์ตรงกับลายเซ็นกรอเลขไมล์/รถน้ำท่วม — ตรวจสอบให้แน่ใจก่อนวางมัดจำ. " +
      "DEAL = ราคาดีกว่าค่าเฉลี่ยในกลุ่มอย่างชัดเจน. FAIR = ราคาใกล้ค่ากลาง.",
    stories_cached_at: "Cached:",
    stories_regen_with: "regenerate ด้วย",
    stories_empty:
      "ยังไม่มีบทวิเคราะห์ — ต้องการอย่างน้อย 15 รายการต่อกลุ่ม. " +
      "เก็บข้อมูลเพิ่ม แล้วรัน",
    badge_deal: "ดีล",
    badge_anomaly: "ผิดปกติ",
    badge_fair: "ปกติ",
    badge_overpriced: "แพงกว่าตลาด",
    section_drivers: "จุดเด่น",
    section_counterpoints: "ข้อควรตรวจสอบ",
    section_action: "Action",
    label_drivers_empty: "ไม่พบจุดเด่นชัดเจน",
    cohort_summary_prefix: "กลุ่มเปรียบเทียบ:",
    cohort_summary_listings: "รายการจาก",
    cohort_summary_sources_one: "แหล่ง",
    cohort_summary_sources_many: "แหล่ง",
    cohort_summary_top_colors: "สียอดนิยม:",
    pill_anchor: "ราคาที่ควรเสนอ:",
    pill_walkaway: "เกินกว่านี้อย่าซื้อ:",
    pill_headroom: "ส่วนต่างถึงค่ากลาง:",
    pill_upside: "upside ถ้าขายต่อที่ P75",
    inspect_priority:
      "ตรวจสอบ: ใต้ท้องรถ (น้ำท่วม), ห้องเครื่อง, ความถูกต้องของเลขไมล์, การเข้าเกียร์",
    anomaly_action_headline: "ตรวจสอบหรือเดินจากไป — อย่าวางมัดจำโดยไม่รู้",
    anomaly_action_genuine:
      "ถ้าจริง (ประวัติไมล์น้อยตรวจสอบได้): ราคาเสนอ {anchor}, เกิน {walkAway} อย่าซื้อ",
    anomaly_action_required:
      "เอกสารที่ต้องการ: ประวัติเล่มทะเบียน, ตราบริการศูนย์, วันจดทะเบียนเจ้าของแรก",
    anomaly_action_inspection:
      "ตรวจสอบที่ต้องทำ: third-party odometer audit (ECU vs dashboard), หาคราบน้ำท่วมใต้ท้อง, วัดความหนาสีทุกแผ่น",
    anomaly_action_walk:
      "เดินจากไปถ้า: เอกสารไม่ครบ, สีไม่ตรง, ตัวแทนปฏิเสธให้อ่าน ECU",
    anomaly_subline:
      "การที่ราคา+ไมล์ห่างกันมากคือลายเซ็นกรอเลขไมล์/รถน้ำท่วม. ไม่ใช่คำแนะนำให้ซื้อ — เป็นคำแนะนำให้ตรวจสอบหรือเดินจากไป.",
    polish_summary: "✨ บทวิเคราะห์เวอร์ชันภาษาไทย (AI ขัดเกลา)",
    polish_summary_hint: "(คลิกเพื่อขยาย — ตัวเลขเดียวกัน, รูปแบบสนทนา)",
    photo_audit: "📷 ตรวจสอบจากภาพ",
    photo_audit_score: "ความเสี่ยง",
    photo_audit_flagged: "ที่พบ:",

    // --- matches ---
    matches_title: "Cross-source — รถเดียวกันคนละแหล่ง",
    matches_intro:
      "ตรวจจับรถเดียวกันจากหลาย source ผ่าน signature ", // continued below
    matches_intro_continued:
      ". Spread = (max − min) / min × 100. Spread กว้าง + หลายแหล่ง = สัญญาณ arbitrage หรือประกาศตกค้าง.",
    matches_computed_at: "คำนวณเมื่อ",
    matches_rerun_with: "เรียกใหม่ด้วย",
    matches_total_groups: "Groups ทั้งหมด",
    matches_cross_source: "Groups ข้ามแหล่ง",
    matches_listings_matched: "รายการที่จับคู่",
    matches_showing: "แสดง",
    filter_all_groups: "ทั้งหมด (รวม source เดียว)",
    filter_cross_source: "ข้ามแหล่ง (≥2)",
    filter_multi_source: "หลายแหล่ง (≥3)",
    filter_any_spread: "Spread ทุกค่า",
    filter_spread_5: "≥ 5%",
    filter_spread_10: "≥ 10%",
    filter_spread_20: "≥ 20%",
    matches_n_sources_one: "แหล่ง",
    matches_n_sources_many: "แหล่ง",
    matches_no_results: "ไม่มีรายการที่ตรงกับเงื่อนไขนี้.",
    matches_cheapest: "ถูกสุด",

    // --- alerts ---
    alerts_title: "การแจ้งเตือน",
    alerts_intro: "Anomaly และ deal ที่ pipeline หลังเก็บข้อมูลส่งเข้าคิว. ส่งไป LINE ด้วย",
    alerts_intro_after: "หลังตั้งค่า",
    alert_total: "ทั้งหมด",
    alert_unseen: "ยังไม่อ่าน",
    alert_pushed: "ส่ง LINE แล้ว",
    alert_unseen_anomalies: "Anomaly ที่ยังไม่อ่าน",
    alert_pushed_label: "ส่งแล้ว",
    alerts_empty: "ยังไม่มีการแจ้งเตือน — เก็บข้อมูลเสร็จแล้วรัน",
    alerts_to_generate: "เพื่อสร้าง.",

    // --- runs ---
    runs_title: "ประวัติเก็บข้อมูล",
    th_run: "#",
    th_started: "เริ่ม",
    th_finished: "สิ้นสุด",
    th_queries: "Queries",
    th_unique: "รถใหม่",
    th_status: "สถานะ",
    th_note: "หมายเหตุ",
    th_error: "ข้อผิดพลาด",

    // --- empty / db ---
    no_data:
      "ยังไม่มีข้อมูล. รัน python scraper.py แล้วโหลดหน้าใหม่.",
  },
  en: {
    brand_subtitle: "/ taladrod",
    nav_overview: "Overview",
    nav_listings: "Listings",
    nav_stories: "Stories",
    nav_matches: "Matches",
    nav_alerts: "Alerts",
    nav_runs: "Runs",
    footer_data: "data: SQLite snapshot · refresh:",

    overview_title: "Overview",
    overview_latest: "Latest snapshot:",
    stat_in_latest: "Cars in latest",
    stat_distinct_ever: "Distinct cars ever",
    stat_snapshots: "Snapshots",
    stat_total_rows: "Total rows",
    card_top_makes: "Top makes (latest)",
    card_year_dist: "Year distribution",
    card_recent_runs: "Recent scrape runs",
    th_make: "Make",
    th_n: "N",
    th_avg_price: "Avg ฿",
    th_range: "Range ฿",

    listings_title: "Listings",
    listings_count_one: "cars",
    page_of: "page",
    of: "of",
    all_sources: "All sources",
    all_makes: "All makes",
    any_fuel: "Any fuel",
    any_transmission: "Any transmission",
    any_body: "Any body",
    any_color: "Any color",
    placeholder_year: "Year",
    placeholder_min: "Min ฿",
    placeholder_max: "Max ฿",
    placeholder_max_km: "Max km",
    placeholder_search: "Search title…",
    btn_filter: "Filter",
    sort_year_desc: "Newest year",
    sort_price_desc: "Price ↓",
    sort_price_asc: "Price ↑",
    sort_mileage_asc: "Lowest km",
    sort_views_desc: "Most viewed",
    no_matches: "No matches.",
    pagination_prev: "← prev",
    pagination_next: "next →",
    suffix_views: "views",

    stories_title: "Story Units",
    stories_intro:
      "Cohort-indexed 6-section reports. " +
      "ANOMALY = price+km gap fits the rollback / flood-rebrand signature, " +
      "treat as verify or walk away. DEAL = top-quartile cohort value. " +
      "FAIR = priced near median.",
    stories_cached_at: "cached at",
    stories_regen_with: "regenerate with",
    stories_empty:
      "No stories — need at least 15 listings per cohort. " +
      "Run more scrape passes, then",
    badge_deal: "DEAL",
    badge_anomaly: "ANOMALY",
    badge_fair: "FAIR",
    badge_overpriced: "OVERPRICED",
    section_drivers: "Drivers",
    section_counterpoints: "Counterpoints",
    section_action: "Action",
    label_drivers_empty: "no notable drivers",
    cohort_summary_prefix: "Cohort:",
    cohort_summary_listings: "listings across",
    cohort_summary_sources_one: "source",
    cohort_summary_sources_many: "sources",
    cohort_summary_top_colors: "top colors:",
    pill_anchor: "Anchor offer:",
    pill_walkaway: "Walk-away above:",
    pill_headroom: "Headroom to median:",
    pill_upside: "upside if resold at P75",
    inspect_priority:
      "Inspect: undercarriage (flood), engine bay, odometer auth, transmission shift",
    anomaly_action_headline: "Verify or walk away — do not deposit blind.",
    anomaly_action_genuine:
      "If genuine (low-km history confirmed): anchor {anchor}, walk-away above {walkAway}",
    anomaly_action_required:
      "Required: เล่มทะเบียน history, service-book stamps, ECU odometer audit",
    anomaly_action_inspection: "",
    anomaly_action_walk: "Walk away if: any document gap or paint mismatch",
    anomaly_subline:
      "The combination of price gap + km gap is the rollback / flood signature. Not a recommendation to buy — recommendation to inspect or walk away.",
    polish_summary: "✨ AI-polished Thai narrative",
    polish_summary_hint:
      "(click to expand — same numbers, conversational prose)",
    photo_audit: "📷 photo audit",
    photo_audit_score: "risk",
    photo_audit_flagged: "flagged:",

    matches_title: "Cross-source matches",
    matches_intro:
      "Listings detected on multiple sources via signature ",
    matches_intro_continued:
      ". Spread = (max − min) / min × 100. Big spread + multiple sources = arbitrage signal or stale listing.",
    matches_computed_at: "computed",
    matches_rerun_with: "re-run with",
    matches_total_groups: "Total groups",
    matches_cross_source: "Cross-source groups",
    matches_listings_matched: "Listings matched",
    matches_showing: "Showing",
    filter_all_groups: "All groups (incl. single-source)",
    filter_cross_source: "Cross-source (≥2 sources)",
    filter_multi_source: "Multi-source (≥3 sources)",
    filter_any_spread: "Any spread",
    filter_spread_5: "≥ 5% spread",
    filter_spread_10: "≥ 10% spread",
    filter_spread_20: "≥ 20% spread",
    matches_n_sources_one: "source",
    matches_n_sources_many: "sources",
    matches_no_results: "No matches at this filter.",
    matches_cheapest: "cheapest",

    alerts_title: "Alerts",
    alerts_intro:
      "Anomalies and deals queued by the post-scrape pipeline. Push to LINE via",
    alerts_intro_after: "after setting",
    alert_total: "Total",
    alert_unseen: "Unseen",
    alert_pushed: "Pushed (LINE)",
    alert_unseen_anomalies: "Unseen anomalies",
    alert_pushed_label: "pushed",
    alerts_empty: "No alerts yet — run",
    alerts_to_generate: "after a scrape to generate.",

    runs_title: "Scrape runs",
    th_run: "#",
    th_started: "Started",
    th_finished: "Finished",
    th_queries: "Queries",
    th_unique: "Unique",
    th_status: "Status",
    th_note: "Note",
    th_error: "Error",

    no_data:
      "No data yet. Run python scraper.py from the repo root, then refresh.",
  },
};

export function t(loc: Locale, key: string): string {
  return dict[loc]?.[key] ?? dict.en[key] ?? key;
}

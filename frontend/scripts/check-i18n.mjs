// Translation check, run before every build (no dependencies):
//  - uz.json and ru.json have the same keys and the same {{placeholders}};
//  - every key the code uses exists (static t("…") calls plus the dynamic families below);
//  - Uzbek uses the modifier letters ʻ (U+02BB) and ʼ (U+02BC), never a plain apostrophe.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src/", import.meta.url).pathname;
const PLURAL = /_(zero|one|two|few|many|other)$/;
const load = (lang) => JSON.parse(readFileSync(join(root, "i18n", `${lang}.json`), "utf8"));

function flatten(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    if (v && typeof v === "object") flatten(v, `${prefix}${k}.`, out);
    else out[`${prefix}${k}`] = v;
  }
  return out;
}

const langs = { uz: flatten(load("uz")), ru: flatten(load("ru")) };
const base = (key) => key.replace(PLURAL, "");
const bases = Object.fromEntries(Object.entries(langs).map(([l, d]) => [l, new Set(Object.keys(d).map(base))]));
const problems = [];

for (const [a, b] of [["uz", "ru"], ["ru", "uz"]]) {
  for (const key of bases[a]) if (!bases[b].has(key)) problems.push(`${key}: missing in ${b}.json`);
}

const placeholders = (text) => new Set([...String(text).matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((m) => m[1]));
const byBase = (dict) => {
  const out = {};
  for (const [key, text] of Object.entries(dict)) {
    const set = (out[base(key)] ??= new Set());
    for (const name of placeholders(text)) set.add(name);
  }
  return out;
};
const [uzVars, ruVars] = [byBase(langs.uz), byBase(langs.ru)];
for (const key of Object.keys(uzVars)) {
  const u = [...uzVars[key]].sort().join(",");
  const r = [...(ruVars[key] ?? [])].sort().join(",");
  if (ruVars[key] && u !== r) problems.push(`${key}: placeholders differ (uz: ${u || "-"}, ru: ${r || "-"})`);
}

for (const [key, text] of Object.entries(langs.uz)) {
  if (/['`‘’]/.test(text)) problems.push(`${key}: uz text uses an apostrophe instead of ʻ / ʼ`);
}

function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}
const used = new Set();
for (const file of sources(root)) {
  const code = readFileSync(file, "utf8");
  for (const m of code.matchAll(/\bt\(\s*"([a-z0-9_.]+)"/g)) used.add(m[1]);
  for (const m of code.matchAll(/i18nKey="([a-z0-9_.]+)"/g)) used.add(m[1]);
}

// Keys built at runtime (`state.${key}` and the like) and the API error codes learners can get.
const expand = (prefix, names) => names.map((n) => `${prefix}${n}`);
const statuses = ["valid", "recert_required", "superseded", "missing"];
const dynamic = [
  ...expand("state.", ["certified", "in_progress", "not_started", "recert_required", "locked"]),
  ...expand("cert_status.", statuses),
  ...expand("home.cert_", statuses),
  ...expand("verify.status_", statuses),
  ...expand("verify.hint_", statuses),
  ...expand("player.sub_", ["uz", "ru"]),
  ...expand("player.sub_short_", ["uz", "ru"]),
  ...expand("lesson.pdf_", ["uz", "ru"]),
  ...expand("intro.rule_", ["random", "timer", "autosave", "unanswered", "no_answers", "after_fail"]),
  ...expand("reason.", [
    "module_no_test", "prerequisite_core", "lessons_incomplete", "test_not_published",
    "attempt_in_progress", "already_passed", "attempts_exhausted", "cooldown", "remediation_pending",
  ]),
  ...expand("errors.", [
    "network", "request.invalid", "auth.invalid_credentials", "auth.locked", "auth.required",
    "auth.forbidden", "auth.password_change_required", "auth.csrf", "password.current_invalid",
    "password.too_short", "password.too_long", "password.equals_employee_id", "password.same_as_current",
    "module.not_found", "module.locked", "module.no_test", "lesson.not_found", "lesson.version_changed",
    "lesson.not_tracked", "attempt.not_found", "attempt.expired", "attempt.finished", "attempt.in_progress",
    "attempt.answer_invalid", "attempt_question.not_found", "test.not_available", "test.pool_too_small",
    "certificate.not_found",
  ]),
];
for (const key of [...used, ...dynamic]) {
  for (const lang of Object.keys(langs)) {
    if (!bases[lang].has(key)) problems.push(`${key}: used but missing in ${lang}.json`);
  }
}

if (problems.length) {
  console.error(`i18n: ${problems.length} problem(s)\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log(`i18n: ok (${bases.uz.size} keys, ${used.size} used directly, ${dynamic.length} dynamic)`);

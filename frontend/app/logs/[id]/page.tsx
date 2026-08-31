"use client";

import Link from "next/link";
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, FileClock, Printer, RefreshCw, Save, ShieldAlert } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, Field, Notice, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { DailyLog, DailyLogEntry, DailyLogManual, DailyLogVersion, HazardClassification, SiteEvidenceRef } from "@/lib/types";

const CONSTRUCTION_FIELDS: [keyof DailyLogManual, string][] = [
  ["weather", "天气"], ["machinery", "机械作业"], ["production_notes", "生产问题补充"],
  ["technical_quality_safety", "技术质量安全活动"], ["inspection_acceptance", "检查验收"], ["construction_other", "其他事项"],
];
const SAFETY_FIELDS: [keyof DailyLogManual, string][] = [
  ["pre_shift_inspection", "岗前巡查"], ["pre_shift_education", "岗前教育"], ["dangerous_projects", "危大工程"],
  ["high_risk_work", "高风险作业"], ["incident_response", "事故 / 险情处置"], ["personnel_duties", "从业人员履职"],
  ["other_safety_management", "其他安全管理"],
];

export default function DailyLogPage() {
  const { id } = useParams<{ id: string }>();
  const [log, setLog] = useState<DailyLog>();
  const [manual, setManual] = useState<DailyLogManual>();
  const [versions, setVersions] = useState<DailyLogVersion[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const value = await api<DailyLog>(`/api/daily-logs/${id}`);
      setLog(value); setManual(value.manual_content);
      setVersions(await api<DailyLogVersion[]>(`/api/daily-logs/${id}/versions`));
    } catch (reason) { setError((reason as ApiError).message); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!log || !manual || log.status !== "DRAFT") return true;
    setBusy(true); setError("");
    try {
      const value = await api<DailyLog>(`/api/daily-logs/${log.id}`, { method: "PATCH", body: JSON.stringify({ manual_content: manual }) });
      setLog(value); setManual(value.manual_content); return true;
    } catch (reason) { setError((reason as ApiError).message); return false; }
    finally { setBusy(false); }
  };
  const refresh = async () => {
    if (!log) return;
    setBusy(true); setError("");
    try {
      const value = await api<DailyLog>(`/api/daily-logs/${log.id}/refresh`, { method: "POST" });
      window.location.assign(`/logs/${value.id}`);
    } catch (reason) { setError((reason as ApiError).message); setBusy(false); }
  };
  const confirm = async () => {
    if (!log || !window.confirm("确认这是人工核对后的正式日志版本？确认后该版本不能再编辑。")) return;
    if (!(await save())) return;
    setBusy(true); setError("");
    try {
      const value = await api<DailyLog>(`/api/daily-logs/${log.id}/confirm`, { method: "POST" });
      setLog(value); setManual(value.manual_content); await load();
    } catch (reason) { setError((reason as ApiError).message); }
    finally { setBusy(false); }
  };

  if (error && !log) return <Notice tone="error">{error}</Notice>;
  if (!log || !manual) return <p className="py-12 text-center text-slate-500">正在读取日志…</p>;
  const construction = log.log_type === "CONSTRUCTION";
  const editable = log.status === "DRAFT";
  const fields = construction ? CONSTRUCTION_FIELDS : SAFETY_FIELDS;
  const issueCount = log.auto_content.entries.reduce((count, entry) => count + entry.issues.length, 0);
  const unclassified = Object.values(manual.hazard_classifications).filter((value) => value === "UNCLASSIFIED").length;

  return <div className="mx-auto max-w-5xl">
    <Link href="/logs" className="mb-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-site-700"><ArrowLeft size={17}/>返回日志中心</Link>
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm font-semibold text-site-700">{log.date} · 版本 v{log.version}</p><h1 className="mt-1 text-2xl font-bold">{construction ? "施工日志" : "施工安全日志"}</h1><p className="mt-1 text-sm text-slate-600">{log.project_name}</p></div><span className={`rounded-full px-3 py-1 text-sm font-bold ${editable ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-800"}`}>{editable ? "草稿待确认" : "已确认"}</span></div>
    {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
    {log.stale && <Card className="mb-4 border-blue-200 bg-blue-50"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-bold text-blue-900">日志来源已有变化</p><p className="text-sm text-blue-800">新增 {log.new_event_count} 条已确认 Event。系统不会自动覆盖当前版本。</p></div><Button onClick={refresh} disabled={busy}><RefreshCw size={17}/>更新日志</Button></div></Card>}
    <Card className="paper-grid mb-4 border-t-4 border-t-site-600 bg-[#fffdf8] shadow-lift"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold tracking-widest text-site-600">AUTO-FILLED · 可追溯</p><h2 className="mt-1 font-bold">自动带入的现场事实</h2><p className="mt-1 text-sm text-slate-600">逐条展示，不累计人数、不推断综合进度。</p></div><span className="shrink-0 rounded-lg bg-site-50 px-2 py-1 text-xs font-bold text-site-800">{log.auto_content.entries.length} 条事实</span></div>
      {!log.auto_content.entries.length ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-center text-sm text-slate-500">当日暂无已确认 Event，所有事实栏目保持为空。</p> : <div className="mt-4 space-y-3">{log.auto_content.entries.map((entry, index) => <EntryCard key={entry.event_id} entry={entry} index={index}/>)}</div>}
    </Card>
    {!construction && <Card className="mb-4 border-amber-200"><div className="flex items-start gap-2"><ShieldAlert className="mt-0.5 shrink-0 text-amber-700" size={20}/><div><h2 className="font-bold">安全问题专业归类</h2><p className="mt-1 text-sm text-slate-600">系统不自动认定一般或重大事故隐患。必须由人员逐项选择，才能确认日志。</p></div></div>
      {issueCount === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">当天 Event 未记录问题。</p> : <div className="mt-4 space-y-3">{log.auto_content.entries.flatMap((entry) => entry.issues.map((issue) => <div key={issue.key} className="rounded-xl bg-amber-50 p-3"><p className="font-semibold">{issue.description}</p><p className="mt-1 text-xs text-slate-600">原分类：{issue.category} · 来源 Event {entry.event_id}</p><label className="mt-3 block space-y-1"><span className="text-sm font-semibold">专业归类</span><Select aria-label={`问题归类 ${issue.description}`} disabled={!editable} value={manual.hazard_classifications[issue.key] ?? "UNCLASSIFIED"} onChange={(event) => setManual({ ...manual, hazard_classifications: { ...manual.hazard_classifications, [issue.key]: event.target.value as HazardClassification } })}><option value="UNCLASSIFIED">待专业归类</option><option value="GENERAL">一般隐患</option><option value="MAJOR">重大事故隐患（人工认定）</option><option value="NOT_HAZARD">非安全隐患</option></Select></label></div>))}</div>}
      {unclassified > 0 && <p className="mt-3 flex items-center gap-1 text-sm font-semibold text-amber-800"><AlertTriangle size={15}/>仍有 {unclassified} 个问题未归类</p>}
    </Card>}
    <Card className="mb-4 border-l-4 border-l-gold-500"><p className="text-xs font-bold tracking-widest text-gold-700">MANUAL INPUT · 人工责任</p><h2 className="mt-1 font-bold">人工填写栏目</h2><p className="mt-1 text-sm text-slate-600">这些内容不会冒充 AI 或现场原始证据，系统会记录填写人与时间。</p><div className="mt-4 grid gap-4 md:grid-cols-2">{fields.map(([key, label]) => <Field key={key} label={`${label}（人工填写）`}><Textarea aria-label={label} disabled={!editable} value={manual[key] as string} onChange={(event) => setManual({ ...manual, [key]: event.target.value })}/></Field>)}</div></Card>
    <div className="mb-4 grid gap-2 sm:grid-cols-3">{editable && <><Button variant="secondary" onClick={save} disabled={busy}><Save size={17}/>保存草稿</Button><Button onClick={confirm} disabled={busy || log.stale || (!construction && unclassified > 0)}><CheckCircle2 size={17}/>确认日志</Button></>}<Button asChild variant="secondary"><Link href={`/logs/${log.id}/print`} target="_blank"><Printer size={17}/>打印预览</Link></Button></div>
    <Card><details><summary className="flex min-h-11 cursor-pointer items-center gap-2 font-bold"><FileClock size={18}/>版本与审计记录</summary><div className="mt-3 space-y-2">{versions.map((version) => <Link key={version.id} href={`/logs/${version.id}`} className={`flex min-h-12 items-center justify-between rounded-xl px-3 text-sm ${version.id === log.id ? "bg-site-50 text-site-800" : "bg-slate-50"}`}><span>版本 v{version.version} · {version.status === "CONFIRMED" ? "已确认" : "草稿"}</span><span>{version.source_count} 条来源 <ExternalLink className="ml-1 inline" size={13}/></span></Link>)}</div><p className="mt-3 text-xs text-slate-500">当前版本审计操作 {log.audits.length} 条。</p></details></Card>
  </div>;
}

function EntryCard({ entry, index }: { entry: DailyLogEntry; index: number }) {
  const value = entry.construction;
  const facts = [["施工内容", value.activity], ["班组", value.crew], ["人数", value.worker_count == null ? undefined : `${value.worker_count} 人`], ["进度", value.progress == null ? undefined : `${Math.round(value.progress * 10000) / 100}%`]];
  return <div className="rounded-xl border border-slate-200 p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><strong>记录 {index + 1} · {entry.location.building} / {entry.location.floor} / {entry.location.zone}</strong><p className="mt-1 text-xs text-slate-500">{new Date(entry.occurred_at).toLocaleString("zh-CN")} · {entry.recorder_name} {entry.recorder_role}</p></div><Link href={`/records/${entry.record_id}`} className="text-xs font-semibold text-site-700">查看原始记录</Link></div><dl className="mt-3 grid gap-2 sm:grid-cols-2">{facts.map(([label, fact]) => <div key={label as string} className="rounded-lg bg-slate-50 px-3 py-2 text-sm"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 font-semibold">{fact ?? "—（无证据）"}</dd></div>)}</dl>{entry.issues.length > 0 && <div className="mt-3"><p className="text-xs font-semibold text-slate-500">现场问题</p>{entry.issues.map((issue) => <div key={issue.key} className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-sm"><span className="font-semibold">{issue.description}</span>{issue.responsible_person && <span className="text-slate-600"> · 责任人原文：{issue.responsible_person}</span>}<Evidence refs={issue.evidence}/></div>)}</div>}</div>;
}

function Evidence({ refs }: { refs: SiteEvidenceRef[] }) {
  if (!refs.length) return <span className="mt-1 block text-xs text-amber-700">该问题由人员确认，但没有可显示的字段证据引用</span>;
  return <span className="mt-1 block text-xs text-slate-600">证据：{refs.map((ref) => ref.quote || ref.description).filter(Boolean).join("；")}</span>;
}

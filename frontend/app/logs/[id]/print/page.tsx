"use client";

import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { DailyLog, DailyLogManual, HazardClassification } from "@/lib/types";

const SAFETY_LABELS: [keyof DailyLogManual, string][] = [
  ["pre_shift_inspection", "岗前巡查"], ["pre_shift_education", "岗前教育"], ["dangerous_projects", "危大工程"],
  ["high_risk_work", "高风险作业"], ["incident_response", "事故 / 险情处置"], ["personnel_duties", "从业人员履职"],
  ["other_safety_management", "其他安全管理"],
];
const CONSTRUCTION_LABELS: [keyof DailyLogManual, string][] = [
  ["weather", "天气"], ["machinery", "机械作业"], ["production_notes", "生产问题"],
  ["technical_quality_safety", "技术质量安全活动"], ["inspection_acceptance", "检查验收"], ["construction_other", "其他事项"],
];

export default function DailyLogPrintPage() {
  const { id } = useParams<{ id: string }>();
  const [log, setLog] = useState<DailyLog>();
  const [error, setError] = useState("");
  useEffect(() => { api<DailyLog>(`/api/daily-logs/${id}`).then(setLog).catch((reason: ApiError) => setError(reason.message)); }, [id]);
  if (error) return <main className="mx-auto max-w-3xl p-6"><Notice tone="error">{error}</Notice></main>;
  if (!log) return <p className="p-8 text-center text-slate-500">正在生成打印预览…</p>;
  const construction = log.log_type === "CONSTRUCTION";
  const fields = construction ? CONSTRUCTION_LABELS : SAFETY_LABELS;
  const classifications = log.manual_content.hazard_classifications;
  return <main className="print-page mx-auto p-4">
    <div className="print-toolbar mx-auto mb-4 flex max-w-[210mm] items-center justify-between gap-3"><Button asChild variant="secondary"><Link href={`/logs/${log.id}`}><ArrowLeft size={17}/>返回编辑</Link></Button><Button onClick={() => window.print()}><Printer size={17}/>打印 / 另存 PDF</Button></div>
    <article className="print-sheet relative mx-auto bg-white p-[12mm] text-black shadow-lg">
      {log.status === "DRAFT" && <div className="draft-watermark">草稿</div>}
      <header className="border-b-2 border-black pb-3 text-center"><h1 className="text-2xl font-bold">{construction ? "施工日志" : "房屋市政工程施工安全日志"}</h1><p className="mt-2 text-sm">项目：{log.project_name}　日期：{log.date}　版本：v{log.version}　状态：{log.status === "CONFIRMED" ? "已确认" : "草稿"}</p></header>
      <section className="mt-4"><h2 className="mb-2 font-bold">{construction ? "当日施工记录" : "今日施工内容"}</h2><table className="print-table w-full table-fixed border-collapse text-xs"><thead><tr><th>时间</th><th>施工部位</th><th>施工内容</th><th>班组 / 人数</th><th>进度</th><th>记录人</th></tr></thead><tbody>{log.auto_content.entries.length ? log.auto_content.entries.map((entry) => <tr key={entry.event_id}><td>{new Date(entry.occurred_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</td><td>{entry.location.building} {entry.location.floor} {entry.location.zone}</td><td>{entry.construction.activity || "—"}</td><td>{entry.construction.crew || "—"} / {entry.construction.worker_count == null ? "—" : `${entry.construction.worker_count}人`}</td><td>{entry.construction.progress == null ? "—" : `${Math.round(entry.construction.progress * 10000) / 100}%`}</td><td>{entry.recorder_name}</td></tr>) : <tr><td colSpan={6} className="text-center">当日暂无已确认 Event</td></tr>}</tbody></table></section>
      {construction ? <section className="mt-4"><h2 className="mb-2 font-bold">现场问题</h2><PrintIssues log={log}/></section> : <HazardSections log={log} classifications={classifications}/>} 
      <section className="mt-4"><h2 className="mb-2 font-bold">人工填写栏目</h2><table className="print-table w-full border-collapse text-sm"><tbody>{fields.map(([key, label]) => <tr key={key}><th className="w-1/4 text-left">{label}</th><td className="whitespace-pre-wrap">{log.manual_content[key] as string || "—"}</td></tr>)}</tbody></table></section>
      <footer className="mt-8 flex justify-between border-t border-black pt-3 text-sm"><span>编制人：用户 #{log.updated_by}</span><span>确认人：{log.confirmed_by ? `用户 #${log.confirmed_by}` : "—"}</span><span>确认时间：{log.confirmed_at ? new Date(log.confirmed_at).toLocaleString("zh-CN") : "—"}</span></footer>
    </article>
  </main>;
}

function PrintIssues({ log }: { log: DailyLog }) {
  const issues = log.auto_content.entries.flatMap((entry) => entry.issues.map((issue) => ({ ...issue, entry })));
  if (!issues.length) return <p className="border border-black p-3 text-sm">未记录现场问题</p>;
  return <table className="print-table w-full border-collapse text-sm"><tbody>{issues.map((issue) => <tr key={issue.key}><td>{issue.entry.location.building} {issue.entry.location.floor} {issue.entry.location.zone}</td><td>{issue.description}</td><td>{issue.responsible_person || "—"}</td></tr>)}</tbody></table>;
}

function HazardSections({ log, classifications }: { log: DailyLog; classifications: Record<string, HazardClassification> }) {
  const issues = log.auto_content.entries.flatMap((entry) => entry.issues.map((issue) => ({ ...issue, entry })));
  const rows = (kind: HazardClassification) => issues.filter((issue) => classifications[issue.key] === kind);
  return <section className="mt-4 space-y-3"><HazardTable title="一般隐患" issues={rows("GENERAL")}/><HazardTable title="重大事故隐患（由专业人员人工认定）" issues={rows("MAJOR")}/>{log.status === "DRAFT" && <HazardTable title="待专业归类" issues={rows("UNCLASSIFIED")}/>}</section>;
}

type PrintableIssue = DailyLog["auto_content"]["entries"][number]["issues"][number] & { entry: DailyLog["auto_content"]["entries"][number] };

function HazardTable({ title, issues }: { title: string; issues: PrintableIssue[] }) {
  return <div><h2 className="mb-1 font-bold">{title}</h2><table className="print-table w-full border-collapse text-sm"><tbody>{issues.length ? issues.map((issue) => <tr key={issue.key}><td>{issue.entry.location.building} {issue.entry.location.floor} {issue.entry.location.zone}</td><td>{issue.description}</td><td>{issue.responsible_person || "—"}</td></tr>) : <tr><td>无</td></tr>}</tbody></table></div>;
}

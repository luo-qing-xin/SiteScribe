"use client";

import Link from "next/link";
import { CalendarDays, ChevronRight, ClipboardPenLine, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, Input, Notice } from "@/components/ui";
import { useWorkspace } from "@/components/workspace";
import { api, ApiError } from "@/lib/api";
import type { DailyLog, DailyLogList, DailyLogType } from "@/lib/types";
import { projectDate } from "@/lib/utils";

const TYPES: DailyLogType[] = ["CONSTRUCTION", "SAFETY"];

export default function LogsPage() {
  const { project } = useWorkspace();
  const [date, setDate] = useState(() => projectDate(project.timezone));
  const [logs, setLogs] = useState<DailyLog[]>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const listed = await api<DailyLogList>(`/api/projects/${project.id}/daily-logs?date=${date}`);
      const present = new Set(listed.logs.map((log) => log.log_type));
      const created = await Promise.all(TYPES.filter((type) => !present.has(type)).map((log_type) =>
        api<DailyLog>(`/api/projects/${project.id}/daily-logs`, {
          method: "POST", body: JSON.stringify({ date, log_type }),
        })
      ));
      setLogs([...listed.logs, ...created].sort((a, b) => TYPES.indexOf(a.log_type) - TYPES.indexOf(b.log_type)));
    } catch (reason) { setError((reason as ApiError).message); }
    finally { setBusy(false); }
  }, [date, project.id]);

  useEffect(() => { load(); }, [load]);

  return <div className="mx-auto max-w-4xl">
    <div className="mb-5">
      <p className="text-sm font-semibold text-site-700">Evidence First · 按项目时区汇总</p>
      <h1 className="mt-1 text-2xl font-bold">施工日志</h1>
      <p className="mt-1 text-sm text-slate-600">只带入已由人员确认的 Event；缺失内容保持空白。</p>
    </div>
    <Card className="mb-5">
      <label className="block space-y-2"><span className="flex items-center gap-2 text-sm font-semibold"><CalendarDays size={17}/>日志日期</span><Input aria-label="日志日期" type="date" value={date} onChange={(event) => setDate(event.target.value)}/></label>
      <p className="mt-2 text-xs text-slate-500">项目时区：{project.timezone}</p>
    </Card>
    {error && <div className="mb-4"><Notice tone="error">{error}</Notice><Button className="mt-2" variant="secondary" onClick={load}><RefreshCw size={16}/>重试</Button></div>}
    {busy && !logs ? <p className="py-12 text-center text-slate-500">正在准备日志草稿…</p> : <div className="grid gap-4 md:grid-cols-2">{logs?.map((log) => <LogCard key={log.id} log={log}/>)}</div>}
  </div>;
}

function LogCard({ log }: { log: DailyLog }) {
  const construction = log.log_type === "CONSTRUCTION";
  const Icon = construction ? ClipboardPenLine : ShieldCheck;
  const issues = log.auto_content.entries.reduce((count, entry) => count + entry.issues.length, 0);
  return <Link href={`/logs/${log.id}`} className="block">
    <Card className="paper-grid competition-card relative h-full overflow-hidden border-t-4 border-t-site-600 bg-[#fffdf8]">
      <span className="absolute right-4 top-16 rotate-[-8deg] rounded border border-site-300 px-2 py-1 text-[10px] font-black text-site-600/60">EVIDENCE FIRST</span>
      <div className="flex items-start justify-between gap-3">
        <span className={`grid size-11 place-items-center rounded-xl ${construction ? "bg-site-50 text-site-800" : "bg-amber-50 text-amber-800"}`}><Icon size={23}/></span>
        <span className={`rounded-full px-2 py-1 text-xs font-bold ${log.status === "CONFIRMED" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>{log.status === "CONFIRMED" ? "已确认" : "草稿"} · v{log.version}</span>
      </div>
      <h2 className="mt-4 text-lg font-bold">{construction ? "施工日志" : "施工安全日志"}</h2>
      <p className="mt-1 text-sm text-slate-600">{log.auto_content.entries.length} 条已确认 Event · {issues} 个现场问题</p>
      {log.stale && <p className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-800">有 {log.new_event_count} 条新证据待刷新</p>}
      {!log.auto_content.entries.length && <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">当日暂无已确认 Event，未生成施工事实</p>}
      <span className="mt-4 flex items-center justify-end text-sm font-semibold text-site-700">查看与填写<ChevronRight size={17}/></span>
    </Card>
  </Link>;
}

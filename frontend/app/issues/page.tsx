"use client";

import Link from "next/link";
import { AlertTriangle, ChevronRight, MapPin } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/workspace";
import { Card, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Issue } from "@/lib/types";

export default function IssuesPage() {
  const { project } = useWorkspace(); const search = useSearchParams(); const eventId = search.get("event_id");
  const [issues, setIssues] = useState<Issue[]>(); const [error, setError] = useState("");
  useEffect(() => { api<Issue[]>(`/api/projects/${project.id}/issues`).then((rows) => setIssues(eventId ? rows.filter((item) => item.event_id === eventId) : rows)).catch((e: ApiError) => setError(e.message)); }, [project.id, eventId]);
  return <div className="mx-auto max-w-3xl"><div className="mb-5"><h1 className="flex items-center gap-2 text-2xl font-bold"><AlertTriangle/>安全问题</h1><p className="mt-1 text-sm text-slate-600">来自已人工确认 Event 的不可变快照；先查询依据，再由人工决定建单或忽略。</p></div>{error && <Notice tone="error">{error}</Notice>}{issues?.length === 0 && <Card className="py-10 text-center"><p className="font-semibold">没有待处理的安全问题</p></Card>}<div className="space-y-3">{issues?.map((issue) => <Link key={issue.id} href={`/issues/${issue.id}`}><Card className="mb-3 hover:border-site-300"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><span className="text-xs font-semibold text-amber-800">{issue.category}</span><h2 className="mt-1 break-words font-bold">{issue.description}</h2><p className="mt-2 flex items-center gap-1 text-xs text-slate-500"><MapPin size={13}/>{[issue.location.building, issue.location.floor, issue.location.zone].filter(Boolean).join(" · ")}</p></div><ChevronRight className="shrink-0 text-slate-400"/></div><div className="mt-3 border-t border-slate-100 pt-3 text-xs"><Status value={issue.status}/>{issue.task_id && <span className="ml-2">整改任务 #{issue.task_id}</span>}</div></Card></Link>)}</div></div>;
}
function Status({ value }: { value: string }) { const labels: Record<string,string> = { PENDING_ANALYSIS: "待查询依据", INSUFFICIENT_EVIDENCE: "依据不足", ANALYSIS_FAILED: "分析失败", AWAITING_CONFIRMATION: "待人工确认", TASK_CREATED: "已建整改任务", IGNORED: "已忽略" }; return <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold">{labels[value] ?? value}</span>; }

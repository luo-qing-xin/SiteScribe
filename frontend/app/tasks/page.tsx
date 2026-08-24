"use client";
import Link from "next/link";
import { CalendarClock, ListChecks, Plus, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/workspace";
import { Button, Card, Notice, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { TaskItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const statuses = ["全部状态", "待处理", "处理中", "已完成", "已取消"];
export default function TasksPage() {
  const { project } = useWorkspace(); const [status, setStatus] = useState("全部状态"); const [tasks, setTasks] = useState<TaskItem[]>(); const [error, setError] = useState("");
  useEffect(() => { const params = new URLSearchParams({ project_id: String(project.id) }); if (status !== "全部状态") params.set("status", status); setTasks(undefined); api<TaskItem[]>(`/api/tasks?${params}`).then(setTasks).catch((e: ApiError) => setError(e.message)); }, [project.id, status]);
  return <div><div className="mb-5 flex items-start justify-between gap-3"><div><h1 className="text-2xl font-bold">待办中心</h1><p className="mt-1 text-sm text-slate-600">跟踪现场工作责任与进度</p></div><Button asChild size="sm"><Link href="/tasks/new"><Plus size={17}/>新建</Link></Button></div><Card className="mb-4"><label className="text-sm font-semibold">状态筛选</label><Select className="mt-2" value={status} onChange={(e) => setStatus(e.target.value)}>{statuses.map((item) => <option key={item}>{item}</option>)}</Select></Card>{error && <Notice tone="error">{error}</Notice>}{!tasks && !error && <div className="py-12 text-center text-slate-500">正在加载待办…</div>}{tasks?.length === 0 && <Card className="py-12 text-center"><ListChecks className="mx-auto mb-3 text-slate-400" size={34}/><p className="font-semibold">没有符合条件的待办</p><p className="mt-1 text-sm text-slate-500">可单独创建，也可从现场记录创建</p></Card>}<div className="space-y-3">{tasks?.map((task) => <Link key={task.id} href={`/tasks/${task.id}`}><Card className="mb-3 hover:border-site-300"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{task.title}</h2><p className="mt-1 line-clamp-2 text-sm text-slate-600">{task.description}</p></div><Status value={task.status}/></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500"><span className="flex items-center gap-1"><UserRound size={13}/>{task.assignee.name}</span><span className="flex items-center gap-1"><CalendarClock size={13}/>{formatDate(task.due_at)}</span>{task.source_record_id && <span>来自记录 #{task.source_record_id}</span>}</div></Card></Link>)}</div></div>;
}
function Status({ value }: { value: string }) { const style = value === "已完成" ? "bg-emerald-50 text-emerald-800" : value === "已取消" ? "bg-slate-100 text-slate-600" : value === "处理中" ? "bg-blue-50 text-blue-800" : "bg-amber-50 text-amber-800"; return <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>{value}</span>; }

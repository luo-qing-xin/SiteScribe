"use client";
import Link from "next/link";
import { ArrowRight, Camera, CheckCircle2, Clock3, ClipboardList, ListChecks, MapPin, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Card, Notice } from "@/components/ui";
import { useWorkspace } from "@/components/workspace";
import { api, ApiError } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function HomePage() {
  const { user, project } = useWorkspace(); const [data, setData] = useState<Dashboard>(); const [error, setError] = useState("");
  const load = () => { setError(""); api<Dashboard>(`/api/projects/${project.id}/dashboard`).then(setData).catch((e: ApiError) => setError(e.message)); };
  useEffect(load, [project.id]);
  return <div><div className="mb-5"><p className="text-sm font-semibold text-site-700">{project.status} · {project.address}</p><h1 className="mt-1 text-2xl font-bold">{project.name}</h1><p className="mt-1 text-slate-600">你好，{user.name} · {user.role}</p></div>
    <Button asChild size="lg" className="mb-6 w-full text-lg shadow-lg md:w-auto"><Link href="/records/new"><Plus size={23}/>新建现场记录</Link></Button>
    {error && <Notice tone="error"><span>{error}</span><button className="ml-2 underline" onClick={load}><RefreshCw className="inline" size={14}/>重试</button></Notice>}
    {!data && !error ? <div className="py-12 text-center text-slate-500">正在读取今日数据…</div> : data && <>
      <div className="grid grid-cols-3 gap-2 md:gap-4"><Metric icon={Camera} value={data.today_records} label="今日记录"/><Metric icon={Clock3} value={data.pending_tasks} label="待处理"/><Metric icon={CheckCircle2} value={data.completed_tasks} label="已完成"/></div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2"><section><SectionTitle title="最近现场记录" href="/records"/><div className="space-y-3">{data.recent_records.length ? data.recent_records.map((record) => <Link key={record.id} href={`/records/${record.id}`}><Card className="mb-3 transition hover:border-site-300"><div className="flex items-start justify-between gap-3"><div><span className="rounded-md bg-site-50 px-2 py-1 text-xs font-semibold text-site-800">{record.category}</span><p className="mt-2 line-clamp-2 text-sm">{record.description}</p><p className="mt-2 flex items-center gap-1 text-xs text-slate-500"><MapPin size={13}/>{record.location.building} {record.location.floor} {record.location.zone}</p></div><span className="shrink-0 text-xs text-slate-500">{formatDate(record.occurred_at)}</span></div></Card></Link>) : <Empty text="今天还没有现场记录"/>}</div></section>
      <section><SectionTitle title="即将到期" href="/tasks"/><div className="space-y-3">{data.upcoming_tasks.length ? data.upcoming_tasks.map((task) => <Link key={task.id} href={`/tasks/${task.id}`}><Card className="mb-3 transition hover:border-site-300"><div className="flex justify-between gap-3"><div><h3 className="font-semibold">{task.title}</h3><p className="mt-1 text-sm text-slate-500">责任人：{task.assignee.name}</p></div><span className="shrink-0 text-sm font-semibold text-amber-700">{formatDate(task.due_at)}</span></div></Card></Link>) : <Empty text="没有即将到期的待办"/>}</div></section></div>
      <div className="mt-6 grid grid-cols-2 gap-3"><Button asChild variant="secondary"><Link href="/records"><ClipboardList size={18}/>现场记录</Link></Button><Button asChild variant="secondary"><Link href="/tasks"><ListChecks size={18}/>待办中心</Link></Button></div>
    </>}
  </div>;
}
function Metric({ icon: Icon, value, label }: { icon: typeof Camera; value: number; label: string }) { return <Card className="p-3 md:p-5"><Icon className="mb-3 text-site-700" size={21}/><strong className="block text-2xl md:text-3xl">{value}</strong><span className="text-xs text-slate-500 md:text-sm">{label}</span></Card>; }
function SectionTitle({ title, href }: { title: string; href: string }) { return <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold">{title}</h2><Link href={href} className="flex items-center text-sm font-semibold text-site-700">查看全部<ArrowRight size={15}/></Link></div>; }
function Empty({ text }: { text: string }) { return <Card className="py-8 text-center text-sm text-slate-500">{text}</Card>; }

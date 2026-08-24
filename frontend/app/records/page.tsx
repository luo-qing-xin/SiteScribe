"use client";
import Link from "next/link";
import { Camera, Crosshair, Filter, MapPin, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/workspace";
import { Button, Card, Notice, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { RecordItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const categories = ["全部类别", "施工进度", "安全巡查", "质量检查", "材料进场", "人员作业", "其他"];
export default function RecordsPage() {
  const { project } = useWorkspace(); const [records, setRecords] = useState<RecordItem[]>(); const [category, setCategory] = useState("全部类别"); const [today, setToday] = useState(false); const [error, setError] = useState("");
  useEffect(() => { const params = new URLSearchParams({ project_id: String(project.id), today_only: String(today) }); if (category !== "全部类别") params.set("category", category); setRecords(undefined); setError(""); api<RecordItem[]>(`/api/records?${params}`).then(setRecords).catch((e: ApiError) => setError(e.message)); }, [project.id, category, today]);
  return <div><div className="mb-5 flex items-start justify-between gap-3"><div><h1 className="text-2xl font-bold">现场记录</h1><p className="mt-1 text-sm text-slate-600">按时间保留现场原始证据</p></div><Button asChild size="sm"><Link href="/records/new"><Plus size={17}/>新建</Link></Button></div>
    <Card className="mb-4"><div className="flex items-center gap-2 text-sm font-semibold"><Filter size={17} className="text-site-700"/>筛选记录</div><div className="mt-3 grid grid-cols-[1fr_auto] gap-2"><Select aria-label="记录类别" value={category} onChange={(e) => setCategory(e.target.value)}>{categories.map((item) => <option key={item}>{item}</option>)}</Select><button aria-pressed={today} onClick={() => setToday(!today)} className={`min-h-12 rounded-xl border px-4 text-sm font-semibold ${today ? "border-site-700 bg-site-50 text-site-800" : "border-slate-300 bg-white"}`}>只看今日</button></div></Card>
    {error && <Notice tone="error">{error}</Notice>}
    {!records && !error && <div className="py-12 text-center text-slate-500">正在加载记录…</div>}
    {records?.length === 0 && <Card className="py-12 text-center"><Camera className="mx-auto mb-3 text-slate-400" size={34}/><p className="font-semibold">没有符合条件的记录</p><p className="mt-1 text-sm text-slate-500">新建一条现场记录开始留痕</p></Card>}
    <div className="space-y-3">{records?.map((record) => <Link key={record.id} href={`/records/${record.id}`}><Card className="mb-3 hover:border-site-300"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><span className="rounded-md bg-site-50 px-2 py-1 text-xs font-semibold text-site-800">{record.category}</span><p className="mt-2 line-clamp-2 font-medium">{record.description}</p></div><time className="shrink-0 text-xs text-slate-500">{formatDate(record.occurred_at)}</time></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500"><span className="flex items-center gap-1"><MapPin size={13}/>{record.location.building} · {record.location.floor} · {record.location.zone}</span><span className="flex items-center gap-1"><Camera size={13}/>{record.photos.length} 张</span><span className="flex items-center gap-1"><Crosshair size={13}/>{record.gps_status === "success" ? "已定位" : "未获取定位"}</span><span>{record.recorder.name}</span></div></Card></Link>)}</div>
  </div>;
}


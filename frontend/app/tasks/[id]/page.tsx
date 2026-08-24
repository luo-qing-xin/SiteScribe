"use client";
import Link from "next/link";
import { ArrowLeft, CalendarClock, Edit3, ExternalLink, Trash2, UserRound } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { TaskForm } from "@/components/task-form";
import { Button, Card, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { TaskItem } from "@/lib/types";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>(); const router = useRouter(); const search = useSearchParams(); const [task, setTask] = useState<TaskItem>(); const [editing, setEditing] = useState(false); const [error, setError] = useState(""); const [confirming, setConfirming] = useState(false); useEffect(() => { api<TaskItem>(`/api/tasks/${id}`).then(setTask).catch((e: ApiError) => setError(e.message)); }, [id]);
  const remove = async () => { try { await api(`/api/tasks/${id}`, { method: "DELETE" }); router.replace("/tasks"); } catch (e) { setError((e as ApiError).message); } };
  if (error && !task) return <Notice tone="error">{error}</Notice>;
  if (!task) return <div className="py-12 text-center text-slate-500">正在加载待办详情…</div>;
  return <div className="mx-auto max-w-2xl"><Link href="/tasks" className="mb-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-site-700"><ArrowLeft size={17}/>返回待办中心</Link>{search.get("created") && <div className="mb-4"><Notice tone="success">待办已创建</Notice></div>}{error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
    <div className="mb-5 flex items-start justify-between gap-3"><div className="min-w-0"><div className="mb-2"><Status value={task.status}/></div><h1 className="text-2xl font-bold">{task.title}</h1></div><Button size="sm" variant="secondary" onClick={() => setEditing(!editing)}><Edit3 size={16}/>{editing ? "取消编辑" : "编辑"}</Button></div>
    {editing ? <TaskForm initial={task} onSaved={(updated) => { setTask(updated); setEditing(false); }}/>: <><Card className="mb-4"><h2 className="mb-3 font-bold">待办描述</h2><p className="whitespace-pre-wrap leading-7">{task.description}</p></Card><Card className="mb-4 space-y-3"><Detail icon={UserRound} label="责任人" value={`${task.assignee.name} · ${task.assignee.role}`}/><Detail label="创建人" value={`${task.creator.name} · ${task.creator.role}`}/><Detail icon={CalendarClock} label="截止时间" value={new Date(task.due_at).toLocaleString("zh-CN")}/><Detail label="创建时间" value={new Date(task.created_at).toLocaleString("zh-CN")}/><Detail label="更新时间" value={new Date(task.updated_at).toLocaleString("zh-CN")}/>{task.source_record_id ? <Link href={`/records/${task.source_record_id}`} className="flex min-h-11 items-center gap-2 rounded-xl bg-site-50 px-3 text-sm font-semibold text-site-800"><ExternalLink size={16}/>查看来源现场记录 #{task.source_record_id}</Link> : <p className="text-sm text-slate-500">此待办为独立创建，无来源现场记录</p>}</Card><Card className="border-red-200"><h2 className="font-bold text-red-800">删除待办</h2><p className="mt-1 text-sm text-slate-600">删除后不可恢复。</p>{confirming ? <div className="mt-3 flex gap-2"><Button variant="danger" onClick={remove}>确认删除</Button><Button variant="secondary" onClick={() => setConfirming(false)}>取消</Button></div> : <Button className="mt-3" variant="danger" onClick={() => setConfirming(true)}><Trash2 size={16}/>删除待办</Button>}</Card></>}
  </div>;
}
function Detail({ icon: Icon, label, value }: { icon?: typeof UserRound; label: string; value: string }) { return <div className="flex gap-2 text-sm">{Icon && <Icon className="mt-0.5 text-site-700" size={16}/>}<span className="w-20 shrink-0 text-slate-500">{label}</span><strong>{value}</strong></div>; }
function Status({ value }: { value: string }) { const style = value === "已完成" ? "bg-emerald-50 text-emerald-800" : value === "已取消" ? "bg-slate-100 text-slate-600" : value === "处理中" ? "bg-blue-50 text-blue-800" : "bg-amber-50 text-amber-800"; return <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>{value}</span>; }

"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarClock, Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useWorkspace } from "./workspace";
import { Button, Card, Field, Input, Notice, Select, Textarea } from "./ui";
import { api, ApiError } from "@/lib/api";
import type { TaskItem, User } from "@/lib/types";
import { localDateTime } from "@/lib/utils";

const schema = z.object({ title: z.string().min(1, "请输入待办标题").max(120), description: z.string().min(1, "请输入待办描述").max(5000), assignee_id: z.number().positive("请选择责任人"), due_at: z.string().min(1, "请选择截止时间"), status: z.enum(["待处理", "处理中", "已完成", "已取消"]) });
type Values = z.infer<typeof schema>;

export function TaskForm({ sourceRecordId, initial, onSaved }: { sourceRecordId?: number; initial?: TaskItem; onSaved: (task: TaskItem) => void }) {
  const { project } = useWorkspace(); const [members, setMembers] = useState<User[]>([]); const [serverError, setServerError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { title: initial?.title ?? "", description: initial?.description ?? "", assignee_id: initial?.assignee.id ?? 0, due_at: localDateTime(initial?.due_at), status: (initial?.status as Values["status"]) ?? "待处理" } });
  useEffect(() => { api<User[]>(`/api/projects/${project.id}/members`).then(setMembers).catch((e: ApiError) => setServerError(e.message)); }, [project.id]);
  const submit = async (values: Values) => { setServerError(""); try { const body = initial ? { ...values, due_at: new Date(values.due_at).toISOString() } : { ...values, project_id: project.id, source_record_id: sourceRecordId ?? null, due_at: new Date(values.due_at).toISOString() }; const task = await api<TaskItem>(initial ? `/api/tasks/${initial.id}` : "/api/tasks", { method: initial ? "PATCH" : "POST", body: JSON.stringify(body) }); onSaved(task); } catch (e) { setServerError((e as ApiError).message); } };
  return <form className="space-y-4" onSubmit={handleSubmit(submit)}>{serverError && <Notice tone="error">{serverError}</Notice>}<Card className="space-y-4"><Field label="待办标题" error={errors.title?.message}><Input placeholder="用一句话说明需要完成的工作" {...register("title")}/></Field><Field label="待办描述" error={errors.description?.message}><Textarea placeholder="描述工作要求、位置和完成标准" {...register("description")}/></Field><Field label="责任人" error={errors.assignee_id?.message}><Select {...register("assignee_id", { valueAsNumber: true })}><option value="0">请选择项目成员</option>{members.map((member) => <option key={member.id} value={member.id}>{member.name} · {member.role}</option>)}</Select></Field><Field label="截止时间" error={errors.due_at?.message}><div className="relative"><CalendarClock className="pointer-events-none absolute left-3 top-3.5 text-slate-400" size={18}/><Input type="datetime-local" className="pl-10" {...register("due_at")}/></div></Field><Field label="状态" error={errors.status?.message}><Select {...register("status")}><option>待处理</option><option>处理中</option><option>已完成</option><option>已取消</option></Select></Field></Card><Button className="w-full" size="lg" disabled={isSubmitting}>{isSubmitting ? <><Loader2 className="animate-spin"/>正在保存…</> : <><Save/>保存待办</>}</Button></form>;
}

"use client";
import Link from "next/link";
import { ArrowLeft, Link2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { TaskForm } from "@/components/task-form";
import { Notice } from "@/components/ui";

export default function NewTaskPage() {
  const router = useRouter(); const search = useSearchParams(); const source = Number(search.get("source_record_id")) || undefined;
  return <div className="mx-auto max-w-2xl"><Link href={source ? `/records/${source}` : "/tasks"} className="mb-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-site-700"><ArrowLeft size={17}/>返回</Link><div className="mb-5"><h1 className="text-2xl font-bold">新建待办</h1><p className="mt-1 text-sm text-slate-600">责任人仅可选择当前项目成员</p></div>{source && <div className="mb-4"><Notice><span className="flex items-center gap-2"><Link2 size={16}/>来源：现场记录 #{source}，保存后将保持关联</span></Notice></div>}<TaskForm sourceRecordId={source} onSaved={(task) => router.push(`/tasks/${task.id}?created=1`)}/></div>;
}


"use client";

import { Archive, FileText, Library, RefreshCw, UploadCloud } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspace } from "@/components/workspace";
import { Button, Card, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeDocument } from "@/lib/types";

export default function KnowledgePage() {
  const { project } = useWorkspace();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<KnowledgeDocument[]>(`/api/projects/${project.id}/knowledge-documents`).then(setDocuments).catch((e: ApiError) => setError(e.message)), [project.id]);
  useEffect(() => { void load(); }, [load]);
  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return setError("请选择 PDF、DOCX、TXT 或 MD 文件");
    setBusy("upload"); setError("");
    const body = new FormData(); body.append("file", file);
    try { await api(`/api/projects/${project.id}/knowledge-documents`, { method: "POST", body }); if (fileRef.current) fileRef.current.value = ""; load(); }
    catch (e) { setError((e as ApiError).message); } finally { setBusy(""); }
  };
  const seed = async () => {
    setBusy("seed"); const body = new FormData(); body.append("seed_demo", "true");
    try { await api(`/api/projects/${project.id}/knowledge-documents`, { method: "POST", body }); load(); }
    catch (e) { setError((e as ApiError).message); } finally { setBusy(""); }
  };
  const action = async (id: string, name: "retry" | "archive") => {
    setBusy(id); try { await api(`/api/knowledge-documents/${id}/${name}`, { method: "POST" }); load(); }
    catch (e) { setError((e as ApiError).message); } finally { setBusy(""); }
  };
  return <div className="mx-auto max-w-3xl"><div className="mb-5"><h1 className="flex items-center gap-2 text-2xl font-bold"><Library/>项目知识库</h1><p className="mt-1 text-sm text-slate-600">仅检索当前项目的有效资料；历史引用在资料归档后仍保留。</p></div>
    {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
    <Card className="mb-5 space-y-3"><label className="text-sm font-bold" htmlFor="knowledge-file">上传项目资料（单文件 ≤ 20MB）</label><input ref={fileRef} className="block min-h-12 w-full max-w-full rounded-xl border border-slate-300 p-2 text-sm" id="knowledge-file" type="file" accept=".pdf,.docx,.txt,.md"/><p className="text-xs text-slate-500">扫描 PDF 暂不支持 OCR；解析失败后可重试。</p><div className="grid gap-2 sm:grid-cols-2"><Button onClick={upload} disabled={!!busy}><UploadCloud size={17}/>{busy === "upload" ? "正在解析…" : "上传并解析"}</Button><Button variant="secondary" onClick={seed} disabled={!!busy}>创建非正式演示材料</Button></div></Card>
    {!documents && <p className="py-10 text-center text-slate-500">正在读取知识文档…</p>}
    {documents?.length === 0 && <Card className="py-10 text-center"><FileText className="mx-auto mb-2 text-slate-400"/><p className="font-semibold">知识库为空</p><p className="mt-1 text-sm text-slate-500">无依据时系统不会生成整改建议。</p></Card>}
    <div className="space-y-3">{documents?.map((document) => <Card key={document.id} className={document.is_demo ? "border-amber-300 bg-amber-50/40" : ""}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="break-words font-bold">{document.title}</h2><p className="mt-1 break-all text-xs text-slate-500">{document.original_name} · {(document.size_bytes / 1024).toFixed(1)} KB</p></div><Status value={document.status}/></div>{document.notice && <div className="mt-3"><Notice>{document.notice}</Notice></div>}<p className="mt-3 text-sm">已建立 {document.chunk_count} 个可定位文段</p>{document.error_message && <p className="mt-2 rounded-lg bg-red-50 p-2 text-sm text-red-800">{document.error_message}</p>}<div className="mt-3 flex flex-wrap gap-2">{document.status === "FAILED" && <Button size="sm" variant="secondary" disabled={busy === document.id} onClick={() => action(document.id, "retry")}><RefreshCw size={15}/>重试</Button>}{document.status !== "ARCHIVED" && <Button size="sm" variant="secondary" disabled={busy === document.id} onClick={() => action(document.id, "archive")}><Archive size={15}/>归档</Button>}</div></Card>)}</div>
  </div>;
}
function Status({ value }: { value: string }) { const labels: Record<string,string> = { PROCESSING: "解析中", ACTIVE: "有效", FAILED: "解析失败", ARCHIVED: "已归档" }; return <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold">{labels[value] ?? value}</span>; }

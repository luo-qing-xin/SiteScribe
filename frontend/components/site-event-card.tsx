"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Plus,
  RotateCcw,
  Save,
  Trash2,
  XCircle,
} from "lucide-react";
import { api, ApiError, photoUrl } from "@/lib/api";
import type {
  EventExtractionJob,
  RecordEventState,
  RecordItem,
  SiteEvidenceRef,
  SiteEvent,
  SiteEventPayload,
} from "@/lib/types";
import { Button, Card, Field, Input, Notice, Select, Textarea } from "./ui";

const emptyIssue = () => ({
  description: "",
  category: "其他" as const,
  risk_level: "pending_confirmation" as const,
  responsible_person: undefined,
  due_at: undefined,
  due_text: undefined,
  confidence: 0,
  evidence: [],
  needs_confirmation: true,
});

export function SiteEventCard({ record }: { record: RecordItem }) {
  const [state, setState] = useState<RecordEventState>();
  const [draft, setDraft] = useState<SiteEventPayload>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await api<RecordEventState>(`/api/records/${record.id}/event`);
      setState(next);
      if (next.event) setDraft(next.event.confirmed_data ?? next.event.draft_data);
    } catch (reason) {
      setError((reason as ApiError).message);
    }
  }, [record.id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!state?.latest_job || !["QUEUED", "RUNNING"].includes(state.latest_job.status)) return;
    const timer = window.setInterval(() => void load(), 1200);
    return () => window.clearInterval(timer);
  }, [load, state?.latest_job]);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const job = await api<EventExtractionJob>(
        `/api/records/${record.id}/event-extractions`,
        { method: "POST" },
      );
      setState((current) => (current ? { ...current, latest_job: job } : current));
      await load();
    } catch (reason) {
      setError((reason as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!state?.latest_job) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/event-extraction-jobs/${state.latest_job.id}/retry`, { method: "POST" });
      await load();
    } catch (reason) {
      setError((reason as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!state?.event || !draft) return false;
    setBusy(true);
    setError("");
    try {
      const event = await api<SiteEvent>(`/api/events/${state.event.id}`, {
        method: "PATCH",
        body: JSON.stringify({ payload: draft }),
      });
      setState((current) => (current ? { ...current, event } : current));
      setDraft(event.draft_data);
      return true;
    } catch (reason) {
      setError((reason as ApiError).message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!state?.event || !window.confirm("确认这是人工核对后的 Event？确认后将不能继续编辑。")) return;
    if (!(await save())) return;
    setBusy(true);
    try {
      await api(`/api/events/${state.event.id}/confirm`, { method: "POST" });
      await load();
    } catch (reason) {
      setError((reason as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!state?.event || !window.confirm("拒绝整个 AI Event 草稿？原始 AI 输出仍会保留用于审计。")) return;
    setBusy(true);
    try {
      await api(`/api/events/${state.event.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: "用户拒绝该草稿" }),
      });
      await load();
    } catch (reason) {
      setError((reason as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  if (!state) {
    return <Card className="mb-4"><p className="text-sm text-slate-500">正在检查 AI 结构化状态…</p></Card>;
  }
  const job = state.latest_job;
  const event = state.event;
  const editable = event?.status === "DRAFT";

  return (
    <Card className="mb-4 overflow-hidden border-site-200" aria-label="AI 结构化结果">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-bold"><Bot size={19}/>AI 结构化结果</h2>
          <p className="mt-1 text-sm text-slate-600">AI 结果仅供辅助，需由专业人员确认。</p>
        </div>
        {event && <Status status={event.status}/>} 
      </div>
      {error && <div className="mt-3"><Notice tone="error">{error}</Notice></div>}

      <section className="mt-4 rounded-xl bg-slate-50 p-3" aria-label="原始证据卡片">
        <h3 className="text-sm font-bold">本次可用的原始证据</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{state.confirmed_text || "尚无人工确认文本"}</p>
        <p className="mt-2 text-xs text-slate-500">人工位置：{state.authoritative.building} / {state.authoritative.floor} / {state.authoritative.zone}</p>
        <p className="text-xs text-slate-500">记录人：{state.authoritative.recorder_name} · {state.authoritative.recorder_role}　记录时间：{new Date(state.authoritative.occurred_at).toLocaleString("zh-CN")}</p>
        {record.photos.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {record.photos.map((photo, index) => (
              <a key={photo.id} href={photoUrl(photo.content_url)} target="_blank" rel="noreferrer" className="rounded-lg bg-white px-3 py-2 font-semibold text-site-700">照片 {index + 1} · ID {photo.id}</a>
            ))}
          </div>
        )}
      </section>

      {!state.confirmed_text && (
        <div className="mt-4"><Notice>没有人工确认文本，暂不能开始 AI 结构化。</Notice><Button className="mt-3 w-full" disabled>AI 结构化</Button></div>
      )}
      {state.confirmed_text && !event && !job && (
        <Button className="mt-4 w-full" onClick={start} disabled={busy || !state.can_extract}>开始 AI 结构化</Button>
      )}
      {job && ["QUEUED", "RUNNING"].includes(job.status) && (
        <div className="mt-4"><Notice>{job.stage}，页面刷新后也会继续显示任务状态。</Notice><Button className="mt-3 w-full" disabled>分析中…</Button></div>
      )}
      {job?.status === "FAILED" && (
        <div className="mt-4"><Notice tone="error">{job.error_message || "分析失败，请重试"}</Notice><Button className="mt-3 w-full" onClick={retry} disabled={busy}><RotateCcw size={17}/>重试 AI 结构化</Button></div>
      )}

      {event && draft && (
        <div className="mt-5 space-y-5">
          {event.status === "CONFIRMED" && <Notice tone="success">此 Event 已由人工确认；AI 原始输出仍独立保留。</Notice>}
          {event.status === "REJECTED" && <div><Notice tone="error">此 Event 已拒绝。{event.rejection_reason ? ` 原因：${event.rejection_reason}` : ""}</Notice>{state.can_extract && job?.status !== "FAILED" && <Button className="mt-2 w-full" variant="secondary" onClick={start} disabled={busy}><RotateCcw size={17}/>重新提取</Button>}</div>}

          <section>
            <h3 className="mb-3 font-bold">施工信息</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <EventField label="施工活动" path="construction.activity" payload={draft}><Input value={draft.construction.activity ?? ""} disabled={!editable} onChange={(e) => setDraft({ ...draft, construction: { ...draft.construction, activity: e.target.value || undefined } })}/></EventField>
              <EventField label="班组" path="construction.crew" payload={draft}><Input value={draft.construction.crew ?? ""} disabled={!editable} placeholder="证据不足时留空" onChange={(e) => setDraft({ ...draft, construction: { ...draft.construction, crew: e.target.value || undefined } })}/></EventField>
              <EventField label="人数" path="construction.worker_count" payload={draft}><Input type="number" min={0} value={draft.construction.worker_count ?? ""} disabled={!editable} onChange={(e) => setDraft({ ...draft, construction: { ...draft.construction, worker_count: e.target.value === "" ? undefined : Number(e.target.value) } })}/></EventField>
              <EventField label="进度（%）" path="construction.progress" payload={draft}><Input type="number" min={0} max={100} step="1" value={draft.construction.progress == null ? "" : Math.round(draft.construction.progress * 10000) / 100} disabled={!editable} onChange={(e) => setDraft({ ...draft, construction: { ...draft.construction, progress: e.target.value === "" ? undefined : Number(e.target.value) / 100 } })}/></EventField>
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between gap-3"><h3 className="font-bold">识别到的问题</h3>{editable && <Button size="sm" variant="secondary" onClick={() => setDraft({ ...draft, issues: [...draft.issues, emptyIssue()] })}><Plus size={16}/>补充问题</Button>}</div>
            {draft.issues.length === 0 ? (
              <p className="rounded-xl bg-slate-50 p-4 text-center text-sm text-slate-500">未提取到问题</p>
            ) : (
              <div className="space-y-3">{draft.issues.map((issue, index) => (
                <div key={index} className="rounded-xl border border-amber-200 bg-amber-50/40 p-3">
                  <div className="flex items-start justify-between gap-2"><strong>问题 {index + 1}</strong>{editable && <button className="flex min-h-11 items-center gap-1 px-2 text-sm font-semibold text-red-700" onClick={() => removeIssue(draft, index, setDraft)}><Trash2 size={15}/>删除</button>}</div>
                  <div className="mt-2 grid gap-3">
                    <EventField label="问题描述" path={`issues.${index}.description`} payload={draft}><Textarea value={issue.description} disabled={!editable} onChange={(e) => updateIssue(draft, index, { description: e.target.value }, setDraft)}/></EventField>
                    <EventField label="问题类别" path={`issues.${index}.category`} payload={draft}><Select value={issue.category} disabled={!editable} onChange={(e) => updateIssue(draft, index, { category: e.target.value as typeof issue.category }, setDraft)}>{["文明施工/安全", "安全", "质量", "文明施工", "其他"].map((value) => <option key={value}>{value}</option>)}</Select></EventField>
                    <EventField label="责任人（文本）" path={`issues.${index}.responsible_person`} payload={draft}><Input value={issue.responsible_person ?? ""} disabled={!editable} onChange={(e) => updateIssue(draft, index, { responsible_person: e.target.value || undefined }, setDraft)}/></EventField>
                    <div className="grid gap-1 text-sm"><span className="font-semibold">风险等级</span><span className="rounded-lg bg-amber-100 px-3 py-2 text-amber-900">待人工确认</span></div>
                    {event.status === "CONFIRMED" && ["安全", "文明施工/安全"].includes(issue.category) && <Link href={`/issues?event_id=${event.id}`} className="flex min-h-11 items-center justify-center rounded-xl border border-site-300 bg-white px-3 text-sm font-semibold text-site-800">查询项目资料依据</Link>}
                  </div>
                </div>
              ))}</div>
            )}
          </section>

          {draft.warnings.length > 0 && (
            <section className="rounded-xl bg-amber-50 p-3"><h3 className="flex items-center gap-2 text-sm font-bold text-amber-900"><AlertTriangle size={16}/>AI warnings</h3><ul className="mt-2 space-y-1 text-sm text-amber-900">{draft.warnings.map((warning, index) => <li key={`${warning}-${index}`}>• {warning}</li>)}</ul></section>
          )}
          {editable && (
            <div className="grid gap-2 sm:grid-cols-3"><Button variant="secondary" onClick={save} disabled={busy}><Save size={17}/>保存修改</Button><Button onClick={confirm} disabled={busy}><CheckCircle2 size={17}/>确认 Event</Button><Button variant="danger" onClick={reject} disabled={busy}><XCircle size={17}/>拒绝 Event</Button></div>
          )}
          <details><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold text-site-700">查看 AI 原始结果与审计记录</summary><pre className="max-w-full overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-white">{JSON.stringify(event.ai_output, null, 2)}</pre><p className="mt-2 text-xs text-slate-500">审计记录 {event.revisions.length} 条；AI 原始结果不会被人工编辑覆盖。</p></details>
        </div>
      )}
    </Card>
  );
}

function Status({ status }: { status: "DRAFT" | "CONFIRMED" | "REJECTED" }) {
  const labels = { DRAFT: "草稿待确认", CONFIRMED: "已确认", REJECTED: "已拒绝" };
  const styles = { DRAFT: "bg-amber-100 text-amber-900", CONFIRMED: "bg-emerald-100 text-emerald-900", REJECTED: "bg-red-100 text-red-900" };
  return <span className={`rounded-full px-3 py-1 text-xs font-bold ${styles[status]}`}>{labels[status]}</span>;
}

function EventField({ label, path, payload, children }: { label: string; path: string; payload: SiteEventPayload; children: ReactNode }) {
  const refs = payload.field_evidence[path] ?? [];
  const needs = payload.needs_confirmation_fields.includes(path) || refs.some((ref) => ref.confidence < 0.6);
  return <Field label={label}>{children}<Evidence refs={refs} needs={needs}/></Field>;
}

function Evidence({ refs, needs }: { refs: SiteEvidenceRef[]; needs: boolean }) {
  if (!refs.length) return <span className="flex items-center gap-1 text-xs font-semibold text-amber-700"><AlertTriangle size={13}/>缺少有效证据，需人工确认</span>;
  return <span className="block space-y-1">{refs.map((ref, index) => <span key={`${ref.source_id}-${index}`} className={`block rounded-lg px-2 py-1 text-xs ${needs ? "bg-amber-100 text-amber-900" : "bg-emerald-50 text-emerald-800"}`}>证据：{evidenceLabel(ref)} · 置信度 {Math.round(ref.confidence * 100)}% {ref.media_file_id ? <a href={`#event-photo-${ref.media_file_id}`} className="ml-1 underline">定位照片</a> : null}</span>)}</span>;
}

function evidenceLabel(ref: SiteEvidenceRef) {
  return ref.quote ? `“${ref.quote}”` : ref.description || ref.evidence_type;
}

function updateIssue(payload: SiteEventPayload, index: number, values: Partial<SiteEventPayload["issues"][number]>, setter: (value: SiteEventPayload) => void) {
  const issues = [...payload.issues];
  issues[index] = { ...issues[index], ...values };
  setter({ ...payload, issues });
}

function removeIssue(payload: SiteEventPayload, index: number, setter: (value: SiteEventPayload) => void) {
  const issues = payload.issues.filter((_, current) => current !== index);
  const field_evidence = Object.fromEntries(Object.entries(payload.field_evidence).filter(([path]) => !path.startsWith("issues.")));
  setter({
    ...payload,
    issues,
    field_evidence,
    needs_confirmation_fields: payload.needs_confirmation_fields.filter((path) => !path.startsWith("issues.")),
  });
}

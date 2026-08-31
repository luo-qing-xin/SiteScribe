"use client";

import { FileAudio, Loader2, Mic, RotateCcw, Square, Trash2, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "./workspace";
import { Button, Card, Notice } from "./ui";
import { ApiError, api, upload } from "@/lib/api";
import type { TranscriptionJob } from "@/lib/types";

type RecorderState = "idle" | "requesting" | "recording" | "ready" | "uploading" | "failed";

export function VoiceCapture({ onManual }: { onManual: () => void }) {
  const { project } = useWorkspace();
  const router = useRouter();
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [audio, setAudio] = useState<File>();
  const [photos, setPhotos] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | undefined>(undefined);
  const stream = useRef<MediaStream | undefined>(undefined);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const chunks = useRef<Blob[]>([]);
  const preview = useMemo(() => audio ? URL.createObjectURL(audio) : "", [audio]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
    if (timer.current) clearInterval(timer.current);
    stream.current?.getTracks().forEach((track) => track.stop());
  }, [preview]);

  const start = async () => {
    setError("");
    if (!("MediaRecorder" in window) || !navigator.mediaDevices?.getUserMedia) {
      setError("当前浏览器不支持录音，请改用文字填写或选择已有音频");
      setState("failed");
      return;
    }
    setState("requesting");
    try {
      const source = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = source;
      const preferred = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((type) => MediaRecorder.isTypeSupported(type));
      const instance = new MediaRecorder(source, preferred ? { mimeType: preferred } : undefined);
      recorder.current = instance;
      chunks.current = [];
      instance.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      instance.onerror = () => { setError("录音失败，请重新录制或改用文字填写"); setState("failed"); };
      instance.onstop = () => {
        const type = instance.mimeType || "audio/webm";
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        setAudio(new File(chunks.current, `recording.${extension}`, { type }));
        source.getTracks().forEach((track) => track.stop());
        if (timer.current) clearInterval(timer.current);
        setState("ready");
      };
      instance.start(500);
      setSeconds(0);
      timer.current = setInterval(() => setSeconds((value) => value + 1), 1000);
      setState("recording");
    } catch (reason) {
      const denied = reason instanceof DOMException && (reason.name === "NotAllowedError" || reason.name === "SecurityError");
      setError(denied ? "麦克风权限已被拒绝，可在浏览器设置中允许，或改用文字填写" : "无法开始录音，请重试或改用文字填写");
      setState("failed");
    }
  };

  const stop = () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  };
  const reset = () => { setAudio(undefined); setSeconds(0); setProgress(0); setError(""); setState("idle"); };
  const pickAudio = (file?: File) => { if (!file) return; setAudio(file); setState("ready"); setError(""); };
  const submit = async () => {
    if (!audio) return;
    setState("uploading"); setProgress(0); setError("");
    try {
      const body = new FormData(); body.append("project_id", String(project.id)); body.append("audio", audio);
      const job = await upload<TranscriptionJob>("/api/transcription-jobs", body, setProgress);
      if (photos.length) {
        const photoBody = new FormData(); photos.forEach((photo) => photoBody.append("files", photo));
        await api(`/api/transcription-jobs/${job.id}/photos`, { method: "POST", body: photoBody });
      }
      router.push(`/records/voice/${job.id}`);
    } catch (reason) {
      setError((reason as ApiError).message); setState("ready");
    }
  };

  return <div className="mx-auto max-w-2xl">
    <div className="mb-5"><h1 className="text-2xl font-bold">新建现场记录</h1><p className="mt-1 text-sm text-slate-600">录音只生成待确认草稿，不会自动写入事实或待办</p></div>
    <div className="mb-4 grid grid-cols-2 rounded-xl bg-slate-200 p-1"><button className="min-h-11 rounded-lg font-semibold text-slate-700" onClick={onManual}>文字填写</button><button className="min-h-11 rounded-lg bg-white font-semibold text-site-800 shadow-sm">语音记录</button></div>
    {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
    <Card className="text-center">
      <div className={`mx-auto grid size-24 place-items-center rounded-full ${state === "recording" ? "animate-pulse bg-red-100 text-red-700" : "bg-site-50 text-site-700"}`}><Mic size={42}/></div>
      <p className="mt-4 text-3xl font-bold tabular-nums">{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</p>
      <p className="mt-1 text-sm text-slate-500">{state === "recording" ? "正在录音，请点击停止" : audio ? "录音已就绪，请试听并核对" : "点击按钮开始录音"}</p>
      <div className="mt-5">
        {state === "recording" ? <Button type="button" size="lg" variant="danger" className="w-full" onClick={stop}><Square size={20}/>停止录音</Button> : !audio ? <Button type="button" size="lg" className="w-full" onClick={start} disabled={state === "requesting"}>{state === "requesting" ? <><Loader2 className="animate-spin"/>正在请求权限…</> : <><Mic/>开始录音</>}</Button> : null}
      </div>
      {audio && <div className="mt-5 space-y-3"><audio className="w-full" controls src={preview}/><div className="grid grid-cols-2 gap-2"><Button type="button" variant="secondary" onClick={reset}><RotateCcw size={17}/>重新录制</Button><Button type="button" variant="danger" onClick={reset}><Trash2 size={17}/>删除录音</Button></div></div>}
      {!audio && state !== "recording" && <label className="mt-4 flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white text-sm font-semibold"><FileAudio size={18}/>选择已有音频<input type="file" className="sr-only" accept="audio/*,.webm,.m4a,.aac,.ogg,.wav,.mp3" onChange={(event) => pickAudio(event.target.files?.[0])}/></label>}
    </Card>
    <Card className="mt-4"><h2 className="font-bold">现场照片（可选）</h2><p className="mt-1 text-xs text-slate-500">照片仅作为 Evidence，不参与 AI 判断，最多 9 张</p><label className="mt-3 flex min-h-12 cursor-pointer items-center justify-center rounded-xl border border-dashed border-slate-300 text-sm font-semibold"><UploadCloud className="mr-2" size={18}/>选择照片（{photos.length}/9）<input type="file" accept="image/jpeg,image/png,image/webp" multiple className="sr-only" onChange={(event) => setPhotos(Array.from(event.target.files ?? []).slice(0, 9))}/></label></Card>
    {state === "uploading" && <div className="mt-4"><div className="mb-1 flex justify-between text-sm"><span>正在上传原始音频</span><strong>{progress}%</strong></div><div className="h-3 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-site-600 transition-all" style={{ width: `${progress}%` }}/></div></div>}
    <Button size="lg" className="mt-4 w-full" disabled={!audio || state === "uploading"} onClick={submit}>{state === "uploading" ? <><Loader2 className="animate-spin"/>上传并创建转写任务</> : <><UploadCloud/>上传并开始转写</>}</Button>
    <Button variant="ghost" className="mt-2 w-full" onClick={onManual}>录音遇到问题？返回文字填写</Button>
  </div>;
}

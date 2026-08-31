"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Camera, FileCheck2, HardHat, ShieldCheck, Workflow } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import { Button, Card, Field, Input, Notice } from "@/components/ui";

const schema = z.object({ username: z.string().min(1, "请输入用户名"), password: z.string().min(1, "请输入密码") });
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const [serverError, setServerError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting }, setValue } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: "zhangwei", password: "demo123" } });
  const submit = async (values: Values) => {
    setServerError("");
    try { await api("/api/auth/login", { method: "POST", body: JSON.stringify(values) }); window.location.assign("/"); }
    catch (error) { setServerError((error as ApiError).message); }
  };
  return <main className="min-h-screen w-full bg-ink-950 md:grid md:grid-cols-[1.15fr_.85fr]">
    <section className="blueprint-grid relative overflow-hidden px-6 py-8 text-white md:flex md:min-h-screen md:flex-col md:justify-between md:px-[8vw] md:py-[7vh]">
      <div className="absolute -right-24 -top-24 size-96 rounded-full border border-gold-300/20"/><div className="absolute -right-8 top-12 size-64 rounded-full border border-white/10"/>
      <div className="relative flex items-center gap-3"><span className="grid size-12 place-items-center rounded-2xl bg-site-600 shadow-[0_12px_32px_rgba(201,54,42,.4)]"><HardHat size={27}/></span><div><h1 className="text-xl font-bold tracking-wider">工地小秘</h1><p className="text-xs text-white/50">SITE EVIDENCE AGENT</p></div></div>
      <div className="relative mt-12 max-w-3xl md:mt-0"><p className="mb-4 flex items-center gap-2 text-sm font-bold tracking-[.22em] text-gold-300"><span className="h-px w-9 bg-gold-300"/>现场履职智能体</p><h2 className="max-w-2xl text-4xl font-black leading-[1.15] tracking-tight sm:text-5xl lg:text-6xl">让工地人员<br/><span className="text-site-500">少填表，多做事</span></h2><p className="mt-5 max-w-xl text-base leading-8 text-white/65 lg:text-lg">拍一次、说一次，现场事实自动沉淀为可追溯资料，问题持续跟进到整改闭环。</p>
        <div className="mt-8 hidden grid-cols-3 gap-3 sm:grid"><Feature icon={Camera} title="多模态采集" text="照片、语音、位置一次留存"/><Feature icon={FileCheck2} title="证据驱动资料" text="每个字段都能回到现场"/><Feature icon={Workflow} title="整改闭环" text="建单、整改、复核全程可查"/></div>
      </div>
      <p className="relative mt-10 hidden text-xs tracking-widest text-white/35 md:block">为人民建好房 · 为工友谋幸福</p>
    </section>
    <section className="paper-grid flex items-center bg-paper px-4 py-8 md:px-[6vw]">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6"><p className="text-sm font-bold text-site-600">海悦花园项目工作台</p><h2 className="mt-2 text-3xl font-black text-ink-900">欢迎回到现场</h2><p className="mt-2 text-sm text-slate-500">登录后继续记录、核对和闭环今日工作</p></div>
      <Card className="border-white/80 p-5 shadow-lift md:p-7">
        <form className="space-y-4" onSubmit={handleSubmit(submit)}>
          {serverError && <Notice tone="error">{serverError}</Notice>}
          <Field label="用户名" error={errors.username?.message}><Input autoComplete="username" {...register("username")}/></Field>
          <Field label="密码" error={errors.password?.message}><Input type="password" autoComplete="current-password" {...register("password")}/></Field>
          <Button className="w-full" size="lg" disabled={isSubmitting}>{isSubmitting ? "正在登录…" : <><span>登录</span><ArrowRight aria-hidden="true" size={18}/></>}</Button>
        </form>
        <div className="mt-6 border-t border-black/5 pt-4"><p className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-500"><ShieldCheck size={15} className="text-site-600"/>比赛演示账号 · 密码均为 demo123</p><div className="grid grid-cols-3 gap-2">{[["zhangwei","张伟","安全员"],["wangqiang","王强","施工员"],["lijianguo","李建国","班组长"]].map(([username,name,role]) => <button type="button" key={username} onClick={() => { setValue("username", username); setValue("password", "demo123"); }} className="min-h-12 rounded-xl border border-transparent bg-ink-50 px-2 text-left text-sm text-ink-800 transition hover:border-site-300 hover:bg-site-50"><strong className="block">{name}</strong><span className="text-[10px] text-slate-500">{role}</span></button>)}</div></div>
      </Card>
      <p className="mt-5 text-center text-xs text-slate-400">AI 仅提供辅助建议，所有正式结论均需人工确认</p>
    </div>
    </section>
  </main>;
}

function Feature({ icon: Icon, title, text }: { icon: typeof Camera; title: string; text: string }) { return <div className="rounded-2xl border border-white/10 bg-white/[.055] p-4 backdrop-blur"><Icon className="mb-5 text-gold-300" size={22}/><strong className="block text-sm">{title}</strong><span className="mt-1 block text-xs leading-5 text-white/45">{text}</span></div>; }

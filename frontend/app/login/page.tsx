"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { HardHat, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import { Button, Card, Field, Input, Notice } from "@/components/ui";

const schema = z.object({ username: z.string().min(1, "请输入用户名"), password: z.string().min(1, "请输入密码") });
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting }, setValue } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: "zhangwei", password: "demo123" } });
  const submit = async (values: Values) => {
    setServerError("");
    try { await api("/api/auth/login", { method: "POST", body: JSON.stringify(values) }); router.replace("/"); router.refresh(); }
    catch (error) { setServerError((error as ApiError).message); }
  };
  return <main className="min-h-screen bg-site-900 px-4 py-10 md:grid md:place-items-center">
    <div className="mx-auto w-full max-w-md">
      <div className="mb-7 text-center text-white"><span className="mx-auto mb-4 grid size-16 place-items-center rounded-2xl bg-white/10"><HardHat size={36}/></span><h1 className="text-3xl font-bold">工地小秘</h1><p className="mt-2 text-emerald-100">现场有据，工作有序</p></div>
      <Card className="p-5 md:p-7"><h2 className="text-xl font-bold text-slate-900">登录工作台</h2><p className="mb-5 mt-1 text-sm text-slate-500">使用项目成员账号继续</p>
        <form className="space-y-4" onSubmit={handleSubmit(submit)}>
          {serverError && <Notice tone="error">{serverError}</Notice>}
          <Field label="用户名" error={errors.username?.message}><Input autoComplete="username" {...register("username")}/></Field>
          <Field label="密码" error={errors.password?.message}><Input type="password" autoComplete="current-password" {...register("password")}/></Field>
          <Button className="w-full" size="lg" disabled={isSubmitting}>{isSubmitting ? "正在登录…" : "登录"}</Button>
        </form>
        <div className="mt-6 border-t border-slate-200 pt-4"><p className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-500"><ShieldCheck size={15}/>演示账号（密码均为 demo123）</p><div className="grid grid-cols-3 gap-2">{[["zhangwei","张伟"],["wangqiang","王强"],["lijianguo","李建国"]].map(([username,name]) => <button key={username} onClick={() => { setValue("username", username); setValue("password", "demo123"); }} className="min-h-11 rounded-lg bg-slate-100 text-sm text-slate-700 hover:bg-site-50">{name}</button>)}</div></div>
      </Card>
    </div>
  </main>;
}


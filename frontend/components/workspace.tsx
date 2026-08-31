"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { BookOpenText, Building2, ClipboardList, HardHat, Home, Library, ListChecks, LogOut } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Project, User } from "@/lib/types";
import { Button } from "./ui";
import { cn } from "@/lib/utils";

type Workspace = { user: User; project: Project; projects: Project[]; setProject: (project: Project) => void };
const WorkspaceContext = createContext<Workspace | null>(null);

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("Workspace is unavailable");
  return value;
}

export function Chrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname.endsWith("/print")) return children;
  return <WorkspaceProvider>{children}</WorkspaceProvider>;
}

function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<{ user: User; projects: Project[]; project: Project }>();
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<User>("/api/auth/me"), api<Project[]>("/api/projects")])
      .then(([user, projects]) => {
        if (!projects.length) { setError("您还未加入任何项目，请联系管理员"); return; }
        const savedId = Number(localStorage.getItem("projectId"));
        const project = projects.find((item) => item.id === savedId) ?? projects[0];
        localStorage.setItem("projectId", String(project.id));
        setData({ user, projects, project });
        if (projects.length > 1 && !savedId && pathname !== "/projects") router.replace("/projects");
      })
      .catch((reason: ApiError) => {
        if (reason.status === 401) router.replace("/login");
        else setError(reason.message);
      });
  }, [pathname, router]);

  if (error) return <main className="mx-auto max-w-lg p-6"><div className="rounded-xl bg-red-50 p-4 text-red-800">{error}</div></main>;
  if (!data) return <main className="grid min-h-screen place-items-center bg-paper"><div className="text-center"><span className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-ink-900 text-white shadow-lift"><HardHat className="animate-pulse" size={30}/></span><p className="font-semibold text-ink-700">正在进入项目现场…</p></div></main>;

  const setProject = (project: Project) => { localStorage.setItem("projectId", String(project.id)); setData({ ...data, project }); };
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }); localStorage.removeItem("projectId"); router.replace("/login"); router.refresh(); };
  const nav = [{ href: "/", label: "首页", icon: Home }, { href: "/records", label: "现场记录", icon: ClipboardList }, { href: "/logs", label: "日志", icon: BookOpenText }, { href: "/knowledge", label: "知识库", icon: Library }, { href: "/tasks", label: "待办中心", icon: ListChecks }];
  return <WorkspaceContext.Provider value={{ ...data, setProject }}>
    <div className="min-h-screen bg-paper pb-24 md:pb-8">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-ink-950 text-white shadow-[0_8px_30px_rgba(0,0,0,.16)]">
        <div className="blueprint-grid mx-auto flex max-w-[1380px] items-center justify-between gap-5 px-4 py-3 md:px-8">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <span className="relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-site-600 shadow-[0_8px_24px_rgba(201,54,42,.35)]"><span className="absolute -right-3 -top-3 size-8 rounded-full border border-gold-300/60"/><HardHat className="relative" size={24}/></span>
            <span className="min-w-0"><strong className="block text-lg tracking-wide">工地小秘</strong><span className="block truncate text-[11px] text-white/55">现场履职多模态智能体</span></span>
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">{nav.map(({ href, label, icon: Icon }) => { const active = pathname === href || (href !== "/" && pathname.startsWith(href)); return <Link key={href} href={href} className={cn("flex min-h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-white/70 transition hover:bg-white/8 hover:text-white", active && "bg-white/10 text-white ring-1 ring-white/10")}><Icon size={16}/>{label}</Link>; })}</nav>
          <div className="hidden items-center gap-3 md:flex"><Link href="/projects" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.06] px-3 py-2"><Building2 size={16} className="text-gold-300"/><span className="max-w-48 truncate text-xs"><strong className="block text-white">{data.project.name}</strong><span className="text-white/50">{data.user.name} · {data.user.role}</span></span></Link><Button variant="ghost" size="sm" className="text-white/70 hover:bg-white/10 hover:text-white" onClick={logout}><LogOut size={16}/>退出</Button></div>
        </div>
      </header>
      <main className="page-enter mx-auto max-w-[1380px] px-4 py-5 md:px-8 md:py-7">{children}</main>
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-black/5 bg-white/95 px-1 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(23,25,22,.08)] backdrop-blur md:hidden">{nav.map(({ href, label, icon: Icon }) => { const active = pathname === href || (href !== "/" && pathname.startsWith(href)); return <Link key={href} href={href} className={cn("relative flex min-h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[11px] transition", active ? "font-bold text-site-700" : "text-ink-700")}><Icon size={20}/>{active && <span className="absolute top-0 h-0.5 w-5 rounded-full bg-site-600"/>}<span className="truncate">{label}</span></Link>; })}</nav>
    </div>
  </WorkspaceContext.Provider>;
}

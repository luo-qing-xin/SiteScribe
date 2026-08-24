"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { ClipboardList, HardHat, Home, ListChecks, LogOut } from "lucide-react";
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
  if (pathname === "/login") return children;
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
  if (!data) return <main className="grid min-h-screen place-items-center"><div className="text-center"><HardHat className="mx-auto mb-3 animate-pulse text-site-700" size={36}/><p className="text-slate-600">正在加载项目…</p></div></main>;

  const setProject = (project: Project) => { localStorage.setItem("projectId", String(project.id)); setData({ ...data, project }); };
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }); localStorage.removeItem("projectId"); router.replace("/login"); router.refresh(); };
  const nav = [{ href: "/", label: "首页", icon: Home }, { href: "/records", label: "现场记录", icon: ClipboardList }, { href: "/tasks", label: "待办中心", icon: ListChecks }];
  return <WorkspaceContext.Provider value={{ ...data, setProject }}>
    <div className="min-h-screen pb-20 md:pb-6">
      <header className="border-b border-site-800 bg-site-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="flex min-w-0 items-center gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10"><HardHat size={24}/></span><span className="min-w-0"><strong className="block text-lg">工地小秘</strong><span className="block truncate text-xs text-emerald-100">{data.project.name} · {data.user.name} {data.user.role}</span></span></Link>
          <div className="hidden items-center gap-1 md:flex">{nav.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={cn("rounded-lg px-3 py-2 text-sm", pathname === href ? "bg-white/15" : "hover:bg-white/10")}><Icon className="mr-1 inline" size={16}/>{label}</Link>)}<Button variant="ghost" size="sm" className="text-white hover:bg-white/10" onClick={logout}><LogOut size={16}/>退出</Button></div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-5 md:py-7">{children}</main>
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-slate-200 bg-white px-2 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 md:hidden">{nav.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={cn("flex min-h-12 flex-col items-center justify-center gap-1 rounded-lg text-xs", pathname === href || (href !== "/" && pathname.startsWith(href)) ? "bg-site-50 font-semibold text-site-800" : "text-slate-600")}><Icon size={21}/>{label}</Link>)}</nav>
    </div>
  </WorkspaceContext.Provider>;
}


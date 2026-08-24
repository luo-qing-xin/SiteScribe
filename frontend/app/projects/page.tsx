"use client";
import { useRouter } from "next/navigation";
import { Building2, CheckCircle2, MapPin } from "lucide-react";
import { useWorkspace } from "@/components/workspace";
import { Button, Card } from "@/components/ui";

export default function ProjectsPage() {
  const { projects, project: current, setProject } = useWorkspace(); const router = useRouter();
  return <div className="mx-auto max-w-2xl"><div className="mb-5"><h1 className="text-2xl font-bold">选择项目</h1><p className="mt-1 text-slate-600">选择本次工作的施工项目</p></div><div className="space-y-3">{projects.map((project) => <Card key={project.id} className={project.id === current.id ? "border-site-600 ring-2 ring-site-100" : ""}><div className="flex gap-3"><Building2 className="mt-1 shrink-0 text-site-700"/><div className="min-w-0 flex-1"><h2 className="font-bold">{project.name}</h2><p className="mt-1 text-sm text-slate-600">{project.organization}</p><p className="mt-2 flex items-center gap-1 text-sm text-slate-500"><MapPin size={15}/>{project.address} · {project.status}</p></div>{project.id === current.id && <CheckCircle2 className="text-site-700"/>}</div><Button className="mt-4 w-full" variant={project.id === current.id ? "secondary" : "primary"} onClick={() => { setProject(project); router.push("/"); }}>{project.id === current.id ? "进入当前项目" : "选择并进入"}</Button></Card>)}</div></div>;
}


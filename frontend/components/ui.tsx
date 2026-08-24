import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-site-600 disabled:pointer-events-none disabled:opacity-50", {
  variants: { variant: { primary: "bg-site-700 text-white hover:bg-site-800", secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50", danger: "bg-red-50 text-red-700 hover:bg-red-100", ghost: "text-slate-700 hover:bg-slate-100" }, size: { default: "h-11", lg: "min-h-14 px-6 text-base", sm: "min-h-9 px-3" } },
  defaultVariants: { variant: "primary", size: "default" },
});

export function Button({ className, variant, size, asChild = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn("rounded-2xl border border-slate-200 bg-white p-4 shadow-card", className)} {...props} />; }
export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) { return <input className={cn("min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 outline-none focus:border-site-600 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) { return <select className={cn("min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 outline-none focus:border-site-600 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className={cn("min-h-28 w-full rounded-xl border border-slate-300 bg-white p-3 text-base text-slate-900 outline-none focus:border-site-600 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) { return <label className="block space-y-2"><span className="text-sm font-semibold text-slate-800">{label}</span>{children}{error && <span className="block text-sm text-red-600">{error}</span>}</label>; }
export function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "success" | "error" }) { const styles = { info: "bg-blue-50 text-blue-800", success: "bg-emerald-50 text-emerald-800", error: "bg-red-50 text-red-800" }; return <div role="status" className={cn("rounded-xl px-4 py-3 text-sm", styles[tone])}>{children}</div>; }

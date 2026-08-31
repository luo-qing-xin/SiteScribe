import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-site-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50", {
  variants: { variant: { primary: "bg-site-600 text-white shadow-[0_8px_20px_rgba(201,54,42,.2)] hover:bg-site-700 hover:-translate-y-0.5", secondary: "border border-ink-100 bg-white text-ink-800 hover:border-site-300 hover:bg-site-50", danger: "bg-red-50 text-red-700 hover:bg-red-100", ghost: "text-slate-700 hover:bg-black/5" }, size: { default: "h-11", lg: "min-h-14 px-6 text-base", sm: "min-h-10 px-3" } },
  defaultVariants: { variant: "primary", size: "default" },
});

export function Button({ className, variant, size, asChild = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn("rounded-[1.25rem] border border-black/[.07] bg-white p-4 shadow-card", className)} {...props} />; }
export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) { return <input className={cn("min-h-12 w-full rounded-xl border border-ink-100 bg-white px-3 text-base text-slate-900 outline-none transition focus:border-site-500 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) { return <select className={cn("min-h-12 w-full rounded-xl border border-ink-100 bg-white px-3 text-base text-slate-900 outline-none transition focus:border-site-500 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className={cn("min-h-28 w-full rounded-xl border border-ink-100 bg-white p-3 text-base text-slate-900 outline-none transition focus:border-site-500 focus:ring-2 focus:ring-site-100", className)} {...props} />; }
export function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) { return <label className="block space-y-2"><span className="text-sm font-semibold text-slate-800">{label}</span>{children}{error && <span className="block text-sm text-red-600">{error}</span>}</label>; }
export function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "success" | "error" }) { const styles = { info: "border border-blue-100 bg-blue-50 text-blue-900", success: "border border-emerald-100 bg-emerald-50 text-emerald-900", error: "border border-red-100 bg-red-50 text-red-900" }; return <div role="status" className={cn("rounded-xl px-4 py-3 text-sm", styles[tone])}>{children}</div>; }
export function Badge({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: "neutral" | "brand" | "gold" | "success" | "warning"; className?: string }) { const styles = { neutral: "bg-ink-50 text-ink-700", brand: "bg-site-50 text-site-800", gold: "bg-gold-100 text-gold-700", success: "bg-emerald-50 text-emerald-800", warning: "bg-amber-50 text-amber-800" }; return <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold", styles[tone], className)}>{children}</span>; }

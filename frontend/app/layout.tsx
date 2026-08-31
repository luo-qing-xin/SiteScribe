import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Chrome } from "@/components/workspace";

export const metadata: Metadata = { title: "工地小秘｜现场履职智能体", description: "基于现场证据链的施工履职多模态智能体" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#171916" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Chrome>{children}</Chrome></body></html>;
}

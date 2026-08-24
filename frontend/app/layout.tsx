import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Chrome } from "@/components/workspace";

export const metadata: Metadata = { title: "工地小秘", description: "施工现场工作助手" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#075f47" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Chrome>{children}</Chrome></body></html>;
}


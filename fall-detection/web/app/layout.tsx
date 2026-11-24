import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FallAllD · Safety Console",
  description: "Bảng điều khiển demo phát hiện té ngã từ cảm biến cổ tay FallAllD.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}

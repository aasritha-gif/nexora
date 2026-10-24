import "./globals.css";
import type { Metadata } from "next";
import { AuthProvider } from "@/hooks/useAuth";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "NEXORA — Your Knowledge. One Intelligent Universe.",
  description:
    "Next-generation AI-powered Academic Library and Knowledge Discovery Platform. Explore departments, research papers, textbooks, and intelligent study assistants.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem('nexora-theme')==='light'){document.documentElement.classList.remove('dark');document.documentElement.classList.add('light')}}catch(e){}`,
          }}
        />
      </head>
      <body className="bg-midnight-950 text-slate-100 min-h-screen flex flex-col selection:bg-indigo-brand selection:text-white">
        <AuthProvider>
          <Navbar />
          <main className="flex-1">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}

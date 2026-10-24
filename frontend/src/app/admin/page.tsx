"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api";
import {
  Shield,
  Database,
  RefreshCw,
  Users,
  Layers,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";

export default function AdminPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [dbStatus, setDbStatus] = useState<Record<string, any>>({});
  const [systemInfo, setSystemInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && (!user || user.role !== "admin")) {
      router.push("/login");
      return;
    }

    if (user?.role === "admin") {
      fetchAdminData();
    }
  }, [user, authLoading]);

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [dbs, sys] = await Promise.all([
        apiClient<any>("/admin/databases"),
        apiClient<any>("/admin/system"),
      ]);
      setDbStatus(dbs);
      setSystemInfo(sys);
    } catch (err: unknown) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const triggerSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await apiClient<any>("/admin/ingestion/sync", { method: "POST" });
      setSyncResult(res.message || "Ingestion sync initiated successfully.");
    } catch (err: unknown) {
      setSyncResult(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-brand mb-3" />
        <p className="text-sm">Loading administrator telemetry...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-brand/20 border border-indigo-brand/30 text-indigo-accent text-xs font-mono uppercase mb-2">
            <Shield className="w-3.5 h-3.5" />
            <span>Administrator Control Center</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            System Telemetry & Administration
          </h1>
        </div>

        <button
          onClick={triggerSync}
          disabled={syncing}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow text-white text-xs font-semibold shadow-md flex items-center gap-2 transition-all self-start sm:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Synchronizing..." : "Trigger Ingestion Sync"}
        </button>
      </div>

      {syncResult && (
        <div className="mb-6 p-3 rounded-xl bg-midnight-900 border border-white/10 text-xs text-slate-300">
          <span className="font-semibold text-cyan-accent">Sync Report: </span>
          {syncResult}
        </div>
      )}

      {/* Polyglot 4 Database Monitoring Section */}
      <div className="mb-8">
        <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-accent" />
          Polyglot NoSQL Databases
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {["MongoDB", "Redis", "Neo4j", "MonetDB"].map((dbName) => {
            const info = dbStatus[dbName] || {};
            const isConnected = info.status === "CONNECTED";

            return (
              <div key={dbName} className="glass-panel rounded-xl p-5 border border-white/10">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-sm text-white">{dbName}</span>
                  {isConnected ? (
                    <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      CONNECTED
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[11px] font-mono text-amber-400">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      DEGRADED
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400">
                  {dbName === "MongoDB" && "Canonical document store"}
                  {dbName === "Redis" && "Cache & rate limiting speed layer"}
                  {dbName === "Neo4j" && "Knowledge graph relationships"}
                  {dbName === "MonetDB" && "Columnar analytical workloads"}
                </p>
                {info.latency_ms !== undefined && (
                  <span className="text-[10px] text-slate-500 font-mono block mt-2">
                    Probe Latency: {info.latency_ms.toFixed(1)} ms
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* System Telemetry & Uptime */}
      {systemInfo && (
        <div className="glass-panel rounded-2xl p-6 border border-white/10">
          <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-violet-glow" />
            Core Runtime Status
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-xs">
            <div>
              <span className="text-slate-400 block mb-1">Application Version</span>
              <span className="font-mono text-slate-200">{systemInfo.version || "1.0.0"}</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-1">Process Uptime</span>
              <span className="font-mono text-slate-200">
                {systemInfo.uptime_seconds !== undefined
                  ? `${systemInfo.uptime_seconds} seconds`
                  : "Active"}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-1">Analytics Buffer</span>
              <span className="font-mono text-slate-200">
                {systemInfo.analytics_buffer?.pending_events || 0} buffered events
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

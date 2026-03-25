import { recoveryColor, recoveryLabel } from "../data";

export function Badge({ value, size = 13 }) {
  const color = recoveryColor(value);
  return (
    <span style={{
      display: "inline-block",
      background: color + "22",
      color,
      borderRadius: 4,
      padding: "2px 8px",
      fontSize: size,
      fontWeight: 600,
      letterSpacing: 0.3,
    }}>
      {recoveryLabel(value)}
    </span>
  );
}

export function MetricCard({ label, value, unit, sub, color, onAction }) {
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "0.5px solid var(--border)",
      borderRadius: 12,
      padding: "14px 16px",
      flex: 1,
      minWidth: 0,
      position: "relative",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 6, letterSpacing: 0.5, textTransform: "uppercase" }}>{label}</div>
        {onAction && (
          <button onClick={onAction} style={{
            background: "none", border: "none", cursor: "pointer", padding: 4, marginTop: -4, marginRight: -4, color: "var(--text-tertiary)",
            display: "flex", alignItems: "center"
          }} title="Ask AI about this">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83" />
            </svg>
          </button>
        )}
      </div>
      <div style={{ fontSize: 26, fontWeight: 500, color: color || "var(--text-primary)", letterSpacing: "-0.8px" }}>
        {value}
        <span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 3 }}>{unit}</span>
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

export function TodaySnapshot({ latest, avgHRV, avgSleep }) {
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "0.5px solid var(--border)",
      borderRadius: 14,
      padding: "18px 22px",
      marginBottom: 14,
      display: "flex",
      alignItems: "center",
      gap: 20,
      flexWrap: "wrap",
    }}>
      {/* Recovery ring */}
      <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
        <div style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: recoveryColor(latest.recovery) + "18",
          border: `2px solid ${recoveryColor(latest.recovery)}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: recoveryColor(latest.recovery) }}>
            {latest.recovery}
          </span>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>Recovery score</div>
          <Badge value={latest.recovery} />
        </div>
      </div>

      <div style={{ width: "0.5px", height: 44, background: "var(--border)", flexShrink: 0 }} />

      {/* Stats row */}
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap", flex: 1 }}>
        {[
          { label: "HRV", val: `${latest.rmssd}ms`, note: `avg ${avgHRV}ms` },
          { label: "Sleep", val: `${latest.sleep}h`, note: `avg ${avgSleep}h` },
          { label: "Strain", val: latest.strain, note: `/ ${Math.max(10, Math.round(latest.recovery * 0.21))}` },
          { label: "SDNN", val: `${latest.sdnn}ms`, note: "variability" },
        ].map(({ label, val, note }) => (
          <div key={label}>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 500, color: "var(--text-primary)" }}>{val}</div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{note}</div>
          </div>
        ))}
        {/* Alerts / Strain Budget Advisor */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginLeft: "auto", justifyContent: "center" }}>
          {latest.rmssd < avgHRV * 0.8 && (
            <div style={{ fontSize: 10, padding: "4px 8px", background: "rgba(216,90,48,0.15)", color: "#D85A30", borderRadius: 4, fontWeight: 500, border: "0.5px solid rgba(216,90,48,0.3)" }}>
              ⚠️ Baseline Drift: HRV down {(100 - (latest.rmssd / avgHRV) * 100).toFixed(0)}%
            </div>
          )}
          {latest.lh_hf > 3.5 && (
            <div style={{ fontSize: 10, padding: "4px 8px", background: "rgba(186,117,23,0.15)", color: "#BA7517", borderRadius: 4, fontWeight: 500, border: "0.5px solid rgba(186,117,23,0.3)" }}>
              🚨 Clinical Alert: Elevated LF/HF Ratio
            </div>
          )}
          {latest.recovery > 0 && (
             <div style={{ fontSize: 10, padding: "4px 8px", background: "rgba(29,158,117,0.1)", color: "#1D9E75", borderRadius: 4, fontWeight: 500, border: "0.5px solid rgba(29,158,117,0.3)" }}>
               🎯 Strain Budget: Cap at {Math.max(10, Math.round(latest.recovery * 0.21))} today
             </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#1f1f1f",
      border: "0.5px solid rgba(255,255,255,0.1)",
      borderRadius: 8,
      padding: "10px 14px",
      fontSize: 12,
      boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
    }}>
      <div style={{ fontWeight: 500, marginBottom: 6, color: "var(--text-secondary)", fontSize: 11 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: p.color, display: "inline-block", flexShrink: 0 }} />
          <span style={{ color: "var(--text-secondary)" }}>{p.name}:</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
}

import { useState, useMemo, useRef, useEffect } from "react";
import "./index.css";
import { generateHRVData, recoveryColor, avg } from "./data";
import { MetricCard, TodaySnapshot } from "./components/Cards";
import { HRVChart, RecoveryChart, SleepStrainChart, CorrelationChart } from "./components/Charts";
import AICoach from "./components/AICoach";

const TEAL = "#1D9E75";
const CORAL = "#D85A30";

const DATA = generateHRVData();
const LATEST = DATA[DATA.length - 1];
const AVG_HRV = Math.round(avg(DATA, "rmssd"));
const AVG_RECOVERY = Math.round(avg(DATA, "recovery"));
const AVG_SLEEP = avg(DATA, "sleep").toFixed(1);

const tabs = [["hrv", "HRV"], ["recovery", "Recovery"], ["sleep", "Sleep & Strain"], ["correlation", "Sleep vs HRV"]];

export default function App() {
  const [activeChart, setActiveChart] = useState("hrv");
  const chartData = useMemo(() => DATA.map(d => ({ ...d, avg: AVG_HRV })), []);
  const trendDiff = LATEST.rmssd - AVG_HRV;
  const aiCoachRef = useRef(null);

  const [theme, setTheme] = useState(() => localStorage.getItem("hrv-theme") || "system");

  useEffect(() => {
    if (theme === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
    localStorage.setItem("hrv-theme", theme);
  }, [theme]);

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      overflow: "hidden",
      background: "var(--bg-primary)",
    }}>

      {/* ══════════════════════════════════════════════
          LEFT PANEL — 75% — Dashboard
      ══════════════════════════════════════════════ */}
      <div style={{
        flex: "0 0 75%",
        overflowY: "auto",
        padding: "1.75rem 1.75rem 1.75rem 2rem",
        borderRight: "0.5px solid var(--border)",
      }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: TEAL, fontWeight: 600, textTransform: "uppercase", marginBottom: 6 }}>
              HRV Intelligence
            </div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 500, color: "var(--text-primary)", letterSpacing: "-0.5px" }}>
              Recovery Dashboard
            </h1>
          </div>
          <div style={{ textAlign: "right", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", background: "var(--bg-card)", border: "0.5px solid var(--border)", borderRadius: 8, padding: 3, gap: 2 }}>
              {[
                { 
                  id: "system", 
                  title: "System",
                  icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
                },
                { 
                  id: "light", 
                  title: "Light",
                  icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                },
                { 
                  id: "dark", 
                  title: "Dark",
                  icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                }
              ].map(t => (
                <button
                  key={t.id}
                  onClick={() => setTheme(t.id)}
                  title={t.title}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center",
                    width: 24, height: 24, borderRadius: 5,
                    border: "none", cursor: "pointer",
                    background: theme === t.id ? TEAL + "22" : "transparent",
                    color: theme === t.id ? TEAL : "var(--text-tertiary)",
                    transition: "all 0.2s ease"
                  }}
                >
                  {t.icon}
                </button>
              ))}
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 500 }}>
                {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </div>
            </div>
            <div style={{
              fontSize: 10, padding: "3px 8px",
              background: "rgba(29,158,117,0.12)", color: TEAL,
              borderRadius: 4, display: "inline-block", letterSpacing: 0.5,
            }}>
              ● API Connected
            </div>
          </div>
        </div>

        {/* Today's snapshot */}
        <TodaySnapshot latest={LATEST} avgHRV={AVG_HRV} avgSleep={AVG_SLEEP} />

        {/* 4 metric cards */}
        <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
          <MetricCard 
            label="30d avg HRV" value={AVG_HRV} unit="ms" sub="RMSSD" color={TEAL} 
            onAction={() => aiCoachRef.current?.sendMessage(`Explain why my 30-day average HRV is ${AVG_HRV}ms.`)}
          />
          <MetricCard
            label="Avg recovery" value={AVG_RECOVERY} unit="%"
            sub={AVG_RECOVERY >= 67 ? "Green zone" : AVG_RECOVERY >= 34 ? "Yellow zone" : "Red zone"}
            color={recoveryColor(AVG_RECOVERY)}
            onAction={() => aiCoachRef.current?.sendMessage(`Explain why my average recovery score is ${AVG_RECOVERY}% today.`)}
          />
          <MetricCard 
            label="Avg sleep" value={AVG_SLEEP} unit="h" sub="per night" 
            onAction={() => aiCoachRef.current?.sendMessage("How does my sleep duration correlate with my HRV?")}
          />
          <MetricCard
            label="HRV trend"
            value={(trendDiff >= 0 ? "+" : "") + trendDiff} unit="ms"
            sub="vs 30d avg"
            color={trendDiff >= 0 ? TEAL : CORAL}
            onAction={() => aiCoachRef.current?.sendMessage(`What causes a baseline drift of ${trendDiff}ms in HRV?`)}
          />
        </div>

        {/* Chart panel */}
        <div style={{
          background: "var(--bg-card)",
          border: "0.5px solid var(--border)",
          borderRadius: 14,
          padding: "16px 20px",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>30-day trends</div>
            <div style={{ display: "flex", gap: 4 }}>
              {tabs.map(([key, label]) => (
                <button key={key} onClick={() => setActiveChart(key)}
                  style={{
                    fontSize: 11, padding: "4px 11px", borderRadius: 6,
                    border: `0.5px solid ${activeChart === key ? TEAL : "var(--border)"}`,
                    background: activeChart === key ? TEAL + "18" : "transparent",
                    color: activeChart === key ? TEAL : "var(--text-secondary)",
                    cursor: "pointer",
                  }}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {activeChart === "hrv" && <HRVChart data={chartData} avgHRV={AVG_HRV} />}
          {activeChart === "recovery" && <RecoveryChart data={DATA} />}
          {activeChart === "sleep" && <SleepStrainChart data={DATA} />}
          {activeChart === "correlation" && <CorrelationChart data={DATA} />}

          {/* Legend */}
          <div style={{ display: "flex", gap: 16, marginTop: 10 }}>
            {activeChart === "hrv" && [
              { color: TEAL, label: "HRV (RMSSD ms)" },
              { color: TEAL, label: `avg ${AVG_HRV}ms`, dashed: true },
            ].map(({ color, label, dashed }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-tertiary)" }}>
                <div style={{ width: 16, height: 1.5, background: dashed ? "transparent" : color, borderTop: dashed ? `1.5px dashed ${color}` : "none" }} />
                {label}
              </div>
            ))}
            {activeChart === "recovery" && [
              { color: TEAL, label: "≥67 Green" },
              { color: "#BA7517", label: "34–66 Yellow" },
              { color: CORAL, label: "<34 Red" },
            ].map(({ color, label }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-tertiary)" }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                {label}
              </div>
            ))}
            {activeChart === "sleep" && [
              { color: "#7B6FDB", label: "Sleep (h)" },
              { color: CORAL, label: "Strain", dashed: true },
            ].map(({ color, label, dashed }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-tertiary)" }}>
                <div style={{ width: 16, height: 1.5, background: dashed ? "transparent" : color, borderTop: dashed ? `1.5px dashed ${color}` : "none" }} />
                {label}
              </div>
            ))}
            {activeChart === "correlation" && (
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                <span style={{ color: TEAL, fontWeight: 500 }}>Insight:</span> Every extra hour of sleep improves HRV by ~4ms.
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div style={{ marginTop: 16, fontSize: 11, color: "var(--text-tertiary)" }}>
          HRV Intelligence · LangGraph + Claude Sonnet 4 + XGBoost ·{" "}
          <span style={{ color: TEAL }}>AUC-ROC 0.9311</span>
        </div>
      </div>

      {/* ══════════════════════════════════════════════
          RIGHT PANEL — 25% — AI Recovery Coach
      ══════════════════════════════════════════════ */}
      <div style={{
        flex: "0 0 25%",
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
      }}>
        <AICoach ref={aiCoachRef} data={DATA} fullHeight />
      </div>
    </div>
  );
}

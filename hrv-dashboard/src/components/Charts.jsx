import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell
} from "recharts";
import { recoveryColor } from "../data";
import { CustomTooltip } from "./Cards";

const TEAL = "#1D9E75";
const CORAL = "#D85A30";
const AMBER = "#BA7517";
const GRAY = "var(--text-tertiary)";

export function HRVChart({ data, avgHRV }) {
  const ticks = data.filter((_, i) => i % 6 === 0).map(d => d.label);
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <defs>
          <linearGradient id="gHRV" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={TEAL} stopOpacity={0.22} />
            <stop offset="95%" stopColor={TEAL} stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="label" ticks={ticks} tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={avgHRV} stroke={TEAL} strokeDasharray="4 3" strokeWidth={1}
          label={{ value: `avg ${avgHRV}ms`, position: "right", fontSize: 9, fill: TEAL }} />
        <Area type="monotone" dataKey="rmssd" name="HRV (ms)" stroke={TEAL} strokeWidth={2}
          fill="url(#gHRV)" dot={false} activeDot={{ r: 4, fill: TEAL, strokeWidth: 0 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function RecoveryChart({ data }) {
  const ticks = data.filter((_, i) => i % 6 === 0).map(d => d.label);
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="label" ticks={ticks} tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} domain={[0, 100]} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={67} stroke={TEAL} strokeDasharray="4 3" strokeWidth={1} />
        <ReferenceLine y={34} stroke={AMBER} strokeDasharray="4 3" strokeWidth={1} />
        <Bar dataKey="recovery" name="Recovery %" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={recoveryColor(entry.recovery)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SleepStrainChart({ data }) {
  const ticks = data.filter((_, i) => i % 6 === 0).map(d => d.label);
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="label" ticks={ticks} tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} domain={[4, 10]} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={8} stroke={TEAL} strokeDasharray="4 3" strokeWidth={1}
          label={{ value: "8h", position: "right", fontSize: 9, fill: TEAL }} />
        <Line type="monotone" dataKey="sleep" name="Sleep (h)" stroke="#7B6FDB"
          strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
        <Line type="monotone" dataKey="strain" name="Strain" stroke={CORAL}
          strokeWidth={1.5} dot={false} strokeDasharray="4 2" activeDot={{ r: 3, strokeWidth: 0 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CorrelationChart({ data }) {
  // Map data to [{x: sleep, y: rmssd}]
  const scatterData = data.map(d => ({ x: d.sleep, y: d.rmssd, date: d.label })).filter(d => d.x > 0);
  
  return (
    <ResponsiveContainer width="100%" height={200}>
      <ScatterChart margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
        <XAxis type="number" dataKey="x" name="Sleep" unit="h" domain={["auto", "auto"]} tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} />
        <YAxis type="number" dataKey="y" name="HRV" unit="ms" domain={["auto", "auto"]} tick={{ fontSize: 10, fill: GRAY }} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} content={(props) => {
           if (!props.active || !props.payload?.length) return null;
           const d = props.payload[0].payload;
           return (
             <div style={{ background: "#1f1f1f", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: "10px 14px", fontSize: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}>
               <div style={{ fontWeight: 500, marginBottom: 6, color: "var(--text-secondary)", fontSize: 11 }}>{d.date}</div>
               <div style={{ color: "var(--text-primary)" }}>Sleep: <span style={{ fontWeight: 600 }}>{d.x}h</span></div>
               <div style={{ color: "var(--text-primary)", marginTop: 2 }}>HRV: <span style={{ fontWeight: 600, color: TEAL }}>{d.y}ms</span></div>
             </div>
           );
         }} />
        <Scatter name="Sleep vs HRV" data={scatterData} fill={TEAL} shape="circle" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

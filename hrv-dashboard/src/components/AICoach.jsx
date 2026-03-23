import { useState, useRef, useEffect, useCallback } from "react";

const TEAL = "#1D9E75";
const API_URL = "http://localhost:8000";
const API_KEY = "hrv-agent-dev-key-2024";

const QUICK_PROMPTS = [
  "What's my biggest HRV risk pattern?",
  "How does my sleep affect recovery?",
  "When should I take a rest day?",
  "Analyze my last 7 days",
];

// Converts structured plain-text + minimal markdown to clean HTML
function formatMsg(text) {
  return text
    // Strip raw markdown headers (##, ###, ####)
    .replace(/^#{1,4}\s+(.+)$/gm, (_, t) =>
      `<span style="font-weight:600;color:var(--text-primary);display:block;margin-top:4px">${t}</span>`
    )
    // Section labels like "SUMMARY:", "KEY FINDINGS:", "RECOMMENDATION:", "TREND:"
    .replace(/^(SUMMARY|KEY FINDINGS|FINDINGS|TREND|RECOMMENDATION|RECOMMENDATION\(S\)|ACTION|ALERT):?/gim, (_, label) =>
      `<span style="font-size:10px;font-weight:700;letter-spacing:1px;color:var(--text-secondary);text-transform:uppercase;display:block;margin-top:8px;margin-bottom:2px">${label}</span>`
    )
    // Remove markdown table pipes entirely — replace rows with clean lines
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split("|").map(c => c.trim()).filter(Boolean);
      if (cells.every(c => /^[-:]+$/.test(c))) return ""; // skip separator rows
      return `<span style="display:block;font-size:12px;color:var(--text-primary);margin:2px 0">${cells.join("  ·  ")}</span>`;
    })
    // Bullet points — •, -, * at line start
    .replace(/^[•\-\*]\s+(.+)$/gm, (_, content) =>
      `<span style="display:flex;gap:6px;margin:3px 0;align-items:flex-start"><span style="color:#1D9E75;flex-shrink:0;margin-top:1px">•</span><span>${content}</span></span>`
    )
    // Bold **text**
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Inline code `text`
    .replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:3px;font-size:11px">$1</code>')
    // Line breaks
    .replace(/\n/g, "<br/>");
}


export default function AICoach({ data }) {
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: `HRV coach online. I have access to your last **${data.length} days** of biometric data. Your most recent HRV is **${data[data.length-1].rmssd}ms**. Ask me anything.`,
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  const sendMessage = useCallback(async (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);
    const userMessages = [...messages, { role: "user", content: msg }];
    setMessages(userMessages);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
        body: JSON.stringify({ message: msg }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const d = await res.json();
      setMessages(prev => [...prev, { role: "assistant", content: d.reply || "No response." }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "⚠️ Can't reach API at `localhost:8000`. Is the backend running?",
      }]);
    }
    setLoading(false);
  }, [input, messages, loading]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      background: "var(--bg-secondary)",
    }}>

      {/* Header */}
      <div style={{
        padding: "18px 16px 14px",
        borderBottom: "0.5px solid var(--border)",
        flexShrink: 0,
        background: "rgba(29,158,117,0.04)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: TEAL, boxShadow: `0 0 8px ${TEAL}`,
            flexShrink: 0,
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>AI Recovery Coach</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", paddingLeft: 16 }}>
          Powered by Claude Sonnet 4
        </div>
      </div>

      {/* Quick prompts */}
      <div style={{
        padding: "10px 12px",
        borderBottom: "0.5px solid var(--border-soft)",
        display: "flex",
        flexDirection: "column",
        gap: 5,
        flexShrink: 0,
        background: "rgba(255,255,255,0.01)",
      }}>
        {QUICK_PROMPTS.map(q => (
          <button key={q} onClick={() => sendMessage(q)}
            style={{
              fontSize: 11, padding: "6px 10px", borderRadius: 7,
              border: "0.5px solid var(--border)",
              background: "transparent",
              color: "var(--text-secondary)",
              cursor: "pointer",
              textAlign: "left",
              lineHeight: 1.3,
            }}>
            {q}
          </button>
        ))}
      </div>

      {/* Messages — fills remaining space */}
      <div ref={chatRef} style={{
        flex: 1,
        overflowY: "auto",
        padding: "14px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}>
        {messages.map((m, i) => (
          <div key={i} className="fade-in" style={{
            display: "flex",
            justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            alignItems: "flex-start",
            gap: 6,
          }}>
            {m.role === "assistant" && (
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: TEAL + "18", border: `1px solid ${TEAL}44`,
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, marginTop: 2,
              }}>
                <span style={{ fontSize: 8, color: TEAL, fontWeight: 700 }}>AI</span>
              </div>
            )}
            <div style={{
              maxWidth: m.role === "user" ? "80%" : "88%",
              padding: "9px 12px",
              borderRadius: m.role === "user" ? "12px 12px 3px 12px" : "12px 12px 12px 3px",
              background: m.role === "user" ? TEAL + "18" : "rgba(255,255,255,0.05)",
              border: m.role === "user" ? `0.5px solid ${TEAL}33` : "0.5px solid var(--border-soft)",
              fontSize: 12.5,
              lineHeight: 1.6,
              color: "var(--text-primary)",
            }}
              dangerouslySetInnerHTML={{ __html: formatMsg(m.content) }}
            />
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{
              width: 22, height: 22, borderRadius: "50%",
              background: TEAL + "18", border: `1px solid ${TEAL}44`,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <span style={{ fontSize: 8, color: TEAL, fontWeight: 700 }}>AI</span>
            </div>
            <div style={{
              display: "flex", gap: 4, padding: "10px 14px",
              background: "rgba(255,255,255,0.05)",
              borderRadius: "12px 12px 12px 3px",
              border: "0.5px solid var(--border-soft)",
            }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 5, height: 5, borderRadius: "50%", background: TEAL,
                  animation: `pulse 1.2s ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input — pinned to bottom */}
      <div style={{
        padding: "10px 12px",
        borderTop: "0.5px solid var(--border)",
        display: "flex",
        gap: 7,
        flexShrink: 0,
        background: "rgba(255,255,255,0.01)",
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
          placeholder="Ask about your HRV..."
          style={{
            flex: 1,
            padding: "8px 11px",
            fontSize: 12.5,
            borderRadius: 7,
            border: "0.5px solid var(--border)",
            background: "rgba(255,255,255,0.04)",
            color: "var(--text-primary)",
            outline: "none",
          }}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          style={{
            padding: "8px 14px",
            fontSize: 12.5,
            borderRadius: 7, border: "none",
            background: loading || !input.trim() ? "rgba(255,255,255,0.05)" : TEAL,
            color: loading || !input.trim() ? "var(--text-tertiary)" : "#fff",
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontWeight: 500,
            flexShrink: 0,
          }}>
          Send
        </button>
      </div>
    </div>
  );
}

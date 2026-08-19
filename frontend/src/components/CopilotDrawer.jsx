import { useState, useRef, useEffect } from "react";
import api from "@/lib/api";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Brain, Send, Sparkles, User } from "lucide-react";
import { toast } from "sonner";

const SUGGESTIONS = [
  "Which leads should I contact today?",
  "Which deals are at risk?",
  "Show my highest-value opportunities",
  "Which deals have been inactive for 7+ days?",
  "Give me today's sales priorities",
];

export default function CopilotDrawer({ open, onOpenChange, focus }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setInput("");
    const userKey = `u${Date.now()}`;
    setMessages((m) => [...m, { key: userKey, role: "user", text: msg }]);
    setBusy(true);
    try {
      const { data } = await api.post("/ai/copilot", {
        message: msg,
        context_type: focus?.type,
        context_id: focus?.id,
      });
      setMessages((m) => [...m, { key: `a${Date.now()}`, role: "ai", text: data.answer }]);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Copilot failed");
    } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg p-0 flex flex-col ai-grain bg-background">
        <SheetHeader className="px-6 py-4 border-b border-border">
          <SheetTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-[#FF3823]" />
            <span className="font-heading text-xl">Sales Copilot</span>
            <span className="ml-2 text-[10px] uppercase font-mono-data tracking-widest text-muted-foreground">Claude 4.6</span>
          </SheetTitle>
        </SheetHeader>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Ask about your pipeline, at-risk deals, top leads, or draft follow-ups. I read your CRM live.
              </p>
              <div className="space-y-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)}
                          className="w-full text-left px-3 py-2 border border-border rounded-sm hover:border-primary/50 hover:bg-primary/5 text-sm transition-colors"
                          data-testid={`copilot-suggestion-${s.slice(0,10)}`}>
                    <Sparkles className="h-3 w-3 inline mr-2 text-[#FF3823]" /> {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={m.key || `msg-${i}`} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`h-7 w-7 shrink-0 rounded-full flex items-center justify-center ${m.role === "user" ? "bg-[#0047FF] text-white" : "bg-[#FF3823] text-white"}`}>
                {m.role === "user" ? <User className="h-3.5 w-3.5" /> : <Brain className="h-3.5 w-3.5" />}
              </div>
              <div className={`max-w-[80%] rounded-sm px-3 py-2 text-sm whitespace-pre-wrap ${
                m.role === "user" ? "bg-[#0047FF] text-white" : "bg-card border border-border"
              }`}>
                {m.text}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex gap-3">
              <div className="h-7 w-7 rounded-full bg-[#FF3823] text-white flex items-center justify-center">
                <Brain className="h-3.5 w-3.5" />
              </div>
              <div className="text-sm text-muted-foreground bg-card border border-border rounded-sm px-3 py-2">
                Analysing your workspace…
              </div>
            </div>
          )}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(); }}
              className="p-4 border-t border-border flex gap-2">
          <Textarea value={input} onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                    placeholder="Ask anything about your CRM…" rows={2}
                    className="rounded-sm resize-none" data-testid="copilot-input" />
          <Button type="submit" disabled={busy || !input.trim()}
                  className="rounded-sm bg-[#FF3823] hover:bg-[#e02f1c] text-white shrink-0 self-end"
                  data-testid="copilot-send">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

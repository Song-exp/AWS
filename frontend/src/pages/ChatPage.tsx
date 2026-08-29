import { useEffect, useRef, useState } from "react";
import { sendMessage, uploadChatFile } from "../api";
import type { Candidate, Draft } from "../types";

interface Msg {
  role: "user" | "bot";
  text: string;
  candidates?: Candidate[];
  draft?: Draft | null;
  file?: string;
}

const GREETING =
  "안녕하세요! 조건에 맞는 장학금을 찾아드릴게요. 소득분위나 학점, 지역을 알려주세요.\n예전에 쓴 신청서가 있으면 📎로 첨부해 주시면 초안까지 만들어 드려요.";

const ACCEPT = ".pdf,.docx,.hwp,.txt";

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([{ role: "bot", text: GREETING }]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const busy = loading || uploading;

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setInput("");
    setLoading(true);
    try {
      const res = await sendMessage({
        session_id: sessionId,
        user_id: null,
        message: trimmed,
      });
      setSessionId(res.session_id);
      setMessages((m) => [
        ...m,
        { role: "bot", text: res.message, candidates: res.candidates, draft: res.draft },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: `오류가 발생했어요: ${(e as Error).message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleFile(file: File) {
    if (busy) return;
    setMessages((m) => [
      ...m,
      { role: "user", text: `📎 ${file.name}`, file: file.name },
    ]);
    setUploading(true);
    try {
      const res = await uploadChatFile(file, sessionId);
      setSessionId(res.session_id);
      setMessages((m) => [...m, { role: "bot", text: res.message }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: `첨부 실패: ${(e as Error).message}` },
      ]);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="chat-page">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            <div className={`bubble ${m.role}`}>
              <div className="text">{m.text}</div>

              {m.candidates && m.candidates.length > 0 && (
                <div className="cards">
                  {m.candidates.map((c) => (
                    <button
                      key={c.id}
                      className="card"
                      onClick={() => submit(`${c.index}번`)}
                      disabled={busy}
                    >
                      <span className="card-index">{c.index}</span>
                      <span className="card-title">{c.title}</span>
                      {c.deadline && <span className="card-reasons">마감 {c.deadline}</span>}
                    </button>
                  ))}
                </div>
              )}

              {m.draft && (
                <div className="draft">
                  <div className="draft-head">
                    초안 {m.draft.used_history ? "(과거 이력 기반)" : "(자기소개 기반)"}
                  </div>
                  {m.draft.answers.map((a, j) => (
                    <div key={j} className="draft-item">
                      <div className="q">{a.question}</div>
                      <div className="a">{a.draft_text}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="row bot">
            <div className="bubble bot">{uploading ? "파일을 읽고 있어요…" : "…"}</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="input-bar"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
        <button
          type="button"
          className="attach-button"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          aria-label="신청서 파일 첨부"
          title="과거 신청서 첨부 (PDF/DOCX/HWP/TXT)"
        >
          📎
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="예: 저 3분위이고 학점 3.8이에요"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          전송
        </button>
      </form>
    </div>
  );
}

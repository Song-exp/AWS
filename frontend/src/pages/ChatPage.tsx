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
  "안녕하세요! 조건에 맞는 장학금을 찾아드릴게요. 소득분위나 학점, 지역을 알려주세요.\n예전에 쓴 신청서가 있다면 첨부해 주세요. 맞춤 초안까지 함께 만들 수 있어요.";

const ACCEPT = ".pdf,.docx,.hwpx,.hwp,.txt";

interface Props {
  userId: string | null;
}

export default function ChatPage({ userId }: Props) {
  const [messages, setMessages] = useState<Msg[]>([
    { role: "bot", text: GREETING },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, uploading]);

  const busy = loading || uploading;

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    setMessages((current) => [
      ...current,
      { role: "user", text: trimmed },
    ]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendMessage({
        session_id: sessionId,
        user_id: userId,
        message: trimmed,
      });
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        {
          role: "bot",
          text: response.message,
          candidates: response.candidates,
          draft: response.draft,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "bot",
          text: `오류가 발생했어요: ${(error as Error).message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleFile(file: File) {
    if (busy) return;

    setMessages((current) => [
      ...current,
      { role: "user", text: `신청서 첨부 · ${file.name}`, file: file.name },
    ]);
    setUploading(true);

    try {
      const response = await uploadChatFile(file, sessionId, userId);
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        { role: "bot", text: response.message },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "bot",
          text: `첨부 실패: ${(error as Error).message}`,
        },
      ]);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="chat-page page-shell">
      <section className="hero chat-hero" aria-labelledby="chat-page-title">
        <nav className="page-steps compact" aria-label="장학금 상담 단계">
          <span className="page-step is-active"><b>1</b> 조건 상담</span>
          <span className="page-step"><b>2</b> 장학금 선택</span>
          <span className="page-step"><b>3</b> 초안 저장</span>
        </nav>
        <p className="eyebrow">SCHOLARSHIP ASSISTANT</p>
        <h1 id="chat-page-title">
          내 조건에 맞는<br />
          <strong>장학금</strong>을 대화로.
        </h1>
        <p className="location-status">
          조건 탐색부터 신청서 초안까지, 확인된 공고를 기준으로 함께 준비해요.
        </p>
      </section>

      <section className="chat-panel" aria-label="장학금 상담 채팅">
        <header className="chat-panel-head">
          <div className="assistant-avatar" aria-hidden="true">P</div>
          <div>
            <strong>TMI 장학 도우미</strong>
            <span><i /> 상담 가능 · 공고 데이터 기반</span>
          </div>
          <span className="chat-security">근거 중심 답변</span>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <div key={index} className={`row ${message.role}`}>
              {message.role === "bot" && (
                <span className="message-avatar" aria-hidden="true">P</span>
              )}
              <div className={`bubble ${message.role}`}>
                {message.file && <span className="file-label">첨부 파일</span>}
                <div className="text">{message.text}</div>

                {message.candidates && message.candidates.length > 0 && (
                  <div className="scholarship-cards">
                    {message.candidates.map((candidate) => (
                      <button
                        key={candidate.id}
                        className="scholarship-card"
                        type="button"
                        onClick={() => submit(`${candidate.index}번`)}
                        disabled={busy}
                      >
                        <span className="card-index">{candidate.index}</span>
                        <span className="scholarship-card-copy">
                          <strong>{candidate.title}</strong>
                          {candidate.reasons.length > 0 && (
                            <small>{candidate.reasons.join(" · ")}</small>
                          )}
                        </span>
                        {candidate.deadline && (
                          <span className="deadline">마감 {candidate.deadline}</span>
                        )}
                        <span className="card-arrow" aria-hidden="true">→</span>
                      </button>
                    ))}
                  </div>
                )}

                {message.draft && (
                  <div className="draft">
                    <div className="draft-head">
                      <span>DRAFT</span>
                      초안 {message.draft.used_history ? "· 과거 이력 기반" : "· 자기소개 기반"}
                    </div>
                    {message.draft.answers.map((answer, answerIndex) => (
                      <article key={answerIndex} className="draft-item">
                        <div className="q">{answer.question}</div>
                        <div className="a">{answer.draft_text}</div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="row bot">
              <span className="message-avatar" aria-hidden="true">P</span>
              <div className="bubble bot loading-bubble">
                {uploading ? "파일을 읽고 있어요" : "답변을 준비하고 있어요"}
                <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form
          className="input-bar"
          onSubmit={(event) => {
            event.preventDefault();
            submit(input);
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
          <button
            type="button"
            className="attach-button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            aria-label="과거 신청서 파일 첨부"
            title="과거 신청서 첨부 (PDF/DOCX/HWPX/HWP/TXT)"
          >
            <span aria-hidden="true">＋</span>
          </button>
          <label className="message-input">
            <span className="sr-only">장학금 조건 입력</span>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="예: 소득 3분위, 학점 3.8이고 서울에 살아요"
              disabled={busy}
            />
          </label>
          <button className="send-button" type="submit" disabled={busy || !input.trim()}>
            보내기 <span aria-hidden="true">→</span>
          </button>
        </form>
        <p className="chat-footnote">
          AI가 작성한 내용은 제출 전 반드시 공고 원문과 함께 확인해 주세요.
        </p>
      </section>
    </div>
  );
}

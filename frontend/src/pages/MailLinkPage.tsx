import { useEffect, useState } from "react";
import { submitMailLink } from "../api";

interface Props {
  /** 메일 링크의 종류. 이메일 인증이거나 알림 수신 거부다. */
  kind: "verify" | "unsubscribe";
  token: string;
  /** 처리 후 앱으로 돌아간다(URL의 토큰도 함께 지운다). */
  onDone: () => void;
}

const TEXT = {
  verify: {
    eyebrow: "이메일 인증",
    pending: "인증하는 중…",
    done: "인증 완료",
    doneLead: "이메일 주소를 확인했어요. 이제 마감 알림을 받을 수 있어요.",
  },
  unsubscribe: {
    eyebrow: "알림 수신 거부",
    pending: "알림 메일을 그만 받을까요?",
    done: "수신 거부 완료",
    doneLead: "마감 알림 메일을 더 보내지 않아요. 마이페이지에서 다시 켤 수 있어요.",
  },
};

export default function MailLinkPage({ kind, token, onDone }: Props) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const text = TEXT[kind];

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await submitMailLink(kind, token);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // 인증은 링크를 연 것만으로 끝낸다. 수신 거부는 버튼을 눌러야 처리한다.
  // 메일 보안 검사가 링크를 미리 열어 보는 경우가 있어, 설정을 바꾸는 쪽은
  // 사람이 직접 누르게 한다.
  useEffect(() => {
    if (kind === "verify") void submit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="auth-page">
      <section className="hero">
        <p className="eyebrow">{text.eyebrow}</p>
        <h1>{done ? text.done : error ? "처리하지 못했어요" : text.pending}</h1>
        {done && <p className="auth-lead">{text.doneLead}</p>}
      </section>

      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}

      {kind === "unsubscribe" && !done && (
        <button type="button" className="auth-submit" disabled={busy} onClick={() => void submit()}>
          {busy ? "처리 중…" : "알림 메일 그만 받기"}
        </button>
      )}

      <button type="button" className="auth-switch" onClick={onDone}>
        서비스로 돌아가기
      </button>
    </div>
  );
}

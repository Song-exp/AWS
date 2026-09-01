import { useState } from "react";
import { resetPassword } from "../api";

interface Props {
  token: string;
  /** 완료·취소 후 로그인 화면으로 돌아간다(URL의 토큰도 함께 지운다). */
  onDone: () => void;
}

const MIN_PASSWORD_LENGTH = 8;

export default function ResetPasswordPage({ token, onDone }: Props) {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="auth-page">
        <section className="hero">
          <p className="eyebrow">비밀번호 재설정</p>
          <h1>변경 완료</h1>
          <p className="auth-lead">
            새 비밀번호로 다시 로그인해 주세요. 기존에 로그인돼 있던 기기는
            모두 로그아웃됐어요.
          </p>
        </section>
        <button type="button" className="auth-submit" onClick={onDone}>
          로그인하러 가기
        </button>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <section className="hero">
        <p className="eyebrow">비밀번호 재설정</p>
        <h1>새 비밀번호 설정</h1>
      </section>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          <span>새 비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            required
          />
        </label>

        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="auth-submit" disabled={busy}>
          {busy ? "처리 중…" : "비밀번호 변경"}
        </button>
      </form>

      <button type="button" className="auth-switch" onClick={onDone}>
        로그인 화면으로
      </button>
    </div>
  );
}

import { useState } from "react";
import { login, requestPasswordReset, signup } from "../api";
import type { AuthUser } from "../types";

interface Props {
  /** 로그인 이전 이 브라우저가 쓰던 익명 UUID. 가입 시 데이터를 승계한다. */
  claimUserId: string | null;
  onAuthenticated: (user: AuthUser) => void;
}

const MIN_PASSWORD_LENGTH = 8;

export default function AuthPage({ claimUserId, onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "signup" | "forgot">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";
  const isForgot = mode === "forgot";
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    // 서버도 같은 규칙으로 검증한다. 여기서 미리 막는 건 왕복을 줄이려는 것뿐이다.
    if (isSignup && password.length < MIN_PASSWORD_LENGTH) {
      setError(`비밀번호는 최소 ${MIN_PASSWORD_LENGTH}자 이상이어야 해요.`);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      if (isForgot) {
        await requestPasswordReset(email);
        // 가입 여부와 무관하게 같은 안내를 보여준다. 화면이 갈리면
        // 서버가 감춘 계정 존재 여부가 UI에서 드러난다.
        setSent(true);
        return;
      }
      const user = isSignup
        ? await signup(email, password, claimUserId)
        : await login(email, password);
      onAuthenticated(user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (isForgot && sent) {
    return (
      <div className="auth-page">
        <section className="hero">
          <p className="eyebrow">비밀번호 찾기</p>
          <h1>메일을 확인해주세요</h1>
          <p className="auth-lead">
            가입된 이메일이라면 재설정 링크를 보냈어요. 메일이 오지 않으면
            스팸함을 확인하거나 주소를 다시 확인해주세요.
          </p>
        </section>
        <button
          type="button"
          className="auth-submit"
          onClick={() => {
            setMode("login");
            setSent(false);
          }}
        >
          로그인 화면으로
        </button>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <section className="hero">
        <p className="eyebrow">대학생 혜택 통합 서비스</p>
        <h1>{isForgot ? "비밀번호 찾기" : isSignup ? "회원가입" : "로그인"}</h1>
        <p className="auth-lead">
          {isForgot
            ? "가입한 이메일 주소로 재설정 링크를 보내드려요."
            : "내 절감 기록과 자기소개서를 안전하게 보관하려면 계정이 필요해요."}
        </p>
      </section>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          <span>이메일</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>

        {!isForgot && (
          <label>
            <span>비밀번호</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSignup ? "new-password" : "current-password"}
              minLength={isSignup ? MIN_PASSWORD_LENGTH : undefined}
              required
            />
          </label>
        )}

        {isSignup && claimUserId && (
          <p className="auth-hint">
            이 기기에 저장된 기존 기록을 새 계정으로 옮겨드릴게요.
          </p>
        )}

        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="auth-submit" disabled={busy}>
          {busy
            ? "처리 중…"
            : isForgot
              ? "재설정 링크 받기"
              : isSignup
                ? "가입하고 시작하기"
                : "로그인"}
        </button>
      </form>

      <button
        type="button"
        className="auth-switch"
        onClick={() => {
          setMode(isSignup || isForgot ? "login" : "signup");
          setError(null);
        }}
      >
        {isSignup || isForgot ? "이미 계정이 있어요 · 로그인" : "처음이신가요? 회원가입"}
      </button>

      {mode === "login" && (
        <button
          type="button"
          className="auth-switch"
          onClick={() => {
            setMode("forgot");
            setError(null);
          }}
        >
          비밀번호를 잊으셨나요?
        </button>
      )}
    </div>
  );
}

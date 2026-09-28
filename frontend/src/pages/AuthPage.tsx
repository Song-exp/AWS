import { useState } from "react";
import { login, requestPasswordReset, signup } from "../api";
import type { AuthUser } from "../types";

interface Props {
  onAuthenticated: (user: AuthUser) => void;
}

const MIN_PASSWORD_LENGTH = 8;

export default function AuthPage({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "signup" | "forgot">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // 동의는 기본으로 체크해 두지 않는다. 미리 체크된 동의는 동의로 보기 어렵다.
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [wantReminders, setWantReminders] = useState(false);

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
        ? await signup(email, password, {
            privacy: agreePrivacy,
            reminders: wantReminders,
          })
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

        {isSignup && (
          <div className="auth-consent">
            <label className="auth-check">
              <input
                type="checkbox"
                checked={agreePrivacy}
                onChange={(e) => setAgreePrivacy(e.target.checked)}
                required
              />
              <span>[필수] 개인정보 수집·이용에 동의합니다</span>
            </label>
            <details className="auth-consent-detail">
              <summary>수집 항목과 이용 목적 보기</summary>
              <ul>
                <li>
                  수집 항목: 이메일, 비밀번호(암호화 저장), 닉네임,
                  소득분위·학점·학년·지역·전공, 결제수단·보유 카드·통신사,
                  직접 올린 신청서와 자기소개서
                </li>
                <li>이용 목적: 장학금·혜택 맞춤 추천, 자기소개서 초안 작성, 절감 기록 보관</li>
                <li>보유 기간: 회원 탈퇴 시 바로 삭제</li>
                <li>동의하지 않을 수 있지만, 그러면 가입할 수 없어요.</li>
              </ul>
              <a href="/privacy.html" target="_blank" rel="noreferrer">
                개인정보 처리방침 전문 보기
              </a>
            </details>
            <label className="auth-check">
              <input
                type="checkbox"
                checked={wantReminders}
                onChange={(e) => setWantReminders(e.target.checked)}
              />
              <span>[선택] 장학금 마감 알림 메일을 받습니다</span>
            </label>
            <p className="auth-consent-note">
              가입하면 인증 메일을 보내드려요. 알림은 인증을 마친 주소로만 가고,
              마이페이지에서 언제든 끌 수 있어요.
            </p>
          </div>
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

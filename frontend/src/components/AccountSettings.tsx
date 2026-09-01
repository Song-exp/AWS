import { useState } from "react";
import { changePassword, deleteAccount, logoutEverywhere } from "../api";
import type { AuthUser } from "../types";

interface Props {
  user: AuthUser;
  /** 세션이 끊긴 뒤 앱을 로그인 화면으로 되돌린다. */
  onSignedOut: () => void;
}

const MIN_PASSWORD_LENGTH = 8;

export default function AccountSettings({ user, onSignedOut }: Props) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>, success?: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      if (success) setMessage(success);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="account-settings">
      <div className="account-identity">
        <span className="account-label">로그인 계정</span>
        <strong>{user.email}</strong>
      </div>

      {message && <p className="notice success">{message}</p>}
      {error && <p className="notice error" role="alert">{error}</p>}

      <form
        className="account-block"
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await changePassword(currentPassword, newPassword);
            setCurrentPassword("");
            setNewPassword("");
          }, "비밀번호를 변경했어요. 다른 기기는 모두 로그아웃됩니다.");
        }}
      >
        <h3>비밀번호 변경</h3>
        <label>
          <span>현재 비밀번호</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          <span>새 비밀번호</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            required
          />
        </label>
        <button type="submit" disabled={busy}>변경하기</button>
      </form>

      <div className="account-block">
        <h3>모든 기기에서 로그아웃</h3>
        <p className="account-desc">
          공용 PC에 로그인한 채로 두고 왔다면 여기서 전부 끊을 수 있어요.
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(async () => {
            await logoutEverywhere();
            onSignedOut();
          })}
        >
          전부 로그아웃
        </button>
      </div>

      <div className="account-block danger">
        <h3>회원 탈퇴</h3>
        <p className="account-desc">
          신청서·자기소개서·절감 기록이 <strong>모두 삭제</strong>되며 되돌릴 수 없어요.
        </p>
        {!confirmingDelete ? (
          <button type="button" onClick={() => setConfirmingDelete(true)}>
            탈퇴하기
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await deleteAccount(deletePassword);
                onSignedOut();
              });
            }}
          >
            <label>
              <span>확인을 위해 비밀번호를 입력해주세요</span>
              <input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <div className="account-actions">
              <button type="submit" className="danger-button" disabled={busy}>
                영구 삭제
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmingDelete(false);
                  setDeletePassword("");
                }}
              >
                취소
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

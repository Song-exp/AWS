import { useEffect, useState } from "react";
import { installBackGuard, useNavState } from "./useNavState";
import AuthPage from "./pages/AuthPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import MailLinkPage from "./pages/MailLinkPage";
import ChatPage from "./pages/ChatPage";
import CommunityPage from "./pages/CommunityPage";
import MapPage from "./pages/MapPage";
import MyPage from "./pages/MyPage";
import OnboardingPage from "./pages/OnboardingPage";
import {
  DEMO_PERSONAS,
  getPersona,
  getPersonaForProfile,
  isDemoPersonaId,
  isPersonaId,
} from "./personas";
import {
  fetchCurrentUser,
  logout as apiLogout,
  updateProfile,
} from "./api";
import type { AuthUser, ProfileSettings, UserProfileLocal } from "./types";

type Tab = "map" | "chat" | "community" | "my";

const STORAGE_KEY = "paypick.profile.v1";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function cloneSettings(settings: ProfileSettings): ProfileSettings {
  return {
    gender: settings.gender,
    cardIds: [...settings.cardIds],
    telecom: settings.telecom,
    payMethods: [...settings.payMethods],
    studentCredentials: [...settings.studentCredentials],
    benefitPrograms: [...settings.benefitPrograms],
  };
}

function settingsForDemo(personaId: Exclude<UserProfileLocal["personaId"], "me">): ProfileSettings {
  const persona = getPersona(personaId);
  return {
    gender: persona.gender,
    cardIds: [...persona.cardIds],
    telecom: persona.telecom,
    payMethods: [...persona.payMethods],
    studentCredentials: [...persona.studentCredentials],
    benefitPrograms: [...persona.benefitPrograms],
  };
}

function normalizeSettings(
  source: Partial<ProfileSettings>,
  fallback: ProfileSettings
): ProfileSettings {
  const validPayMethods = ["kakao", "toss", "naver"];
  const validCredentials = ["student_card", "student_tok"];
  const validPrograms = ["khu_alliance", "onnuri", "seoulpay", "zeropay"];
  return {
    gender:
      source.gender === "male" || source.gender === "female"
        ? source.gender
        : null,
    cardIds: Array.isArray(source.cardIds)
      ? source.cardIds.filter(
          (id): id is number => typeof id === "number" && Number.isInteger(id)
        )
      : [...fallback.cardIds],
    telecom: typeof source.telecom === "string" ? source.telecom : null,
    payMethods: Array.isArray(source.payMethods)
      ? source.payMethods.filter((value) => validPayMethods.includes(value))
      : [...fallback.payMethods],
    studentCredentials: Array.isArray(source.studentCredentials)
      ? source.studentCredentials.filter((value) => validCredentials.includes(value))
      : [...fallback.studentCredentials],
    benefitPrograms: Array.isArray(source.benefitPrograms)
      ? source.benefitPrograms.filter((value) => validPrograms.includes(value))
      : [...fallback.benefitPrograms],
  } as ProfileSettings;
}

function saveProfile(profile: UserProfileLocal) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

function loadProfile(): UserProfileLocal | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const stored = JSON.parse(raw) as Partial<UserProfileLocal>;
    if (!Array.isArray(stored.cardIds) || !Array.isArray(stored.payMethods)) {
      return null;
    }

    const fallbackId = isDemoPersonaId(stored.personaId)
      ? stored.personaId
      : stored.gender === "male"
        ? "demo_b"
        : "demo_a";
    const fallback = settingsForDemo(fallbackId);
    const hasPersonalProfile =
      stored.personalProfile !== null &&
      typeof stored.personalProfile === "object";
    const personalProfile = normalizeSettings(
      hasPersonalProfile ? stored.personalProfile ?? {} : stored,
      fallback
    );

    // 기존 v1 프로필은 온보딩 사용자의 실제 설정이므로 최초 마이그레이션 시 '나'로 귀속한다.
    const personaId = hasPersonalProfile && isPersonaId(stored.personaId)
      ? stored.personaId
      : "me";
    const activeSettings = personaId === "me"
      ? cloneSettings(personalProfile)
      : settingsForDemo(personaId);
    const profile: UserProfileLocal = {
      userId: isUuid(stored.userId) ? stored.userId : crypto.randomUUID(),
      personaId,
      ...activeSettings,
      personalProfile,
    };

    saveProfile(profile);
    return profile;
  } catch {
    return null;
  }
}

/** 계정에 온보딩 설정이 이미 있는지. 있으면 온보딩을 건너뛴다. */
function hasServerSettings(user: AuthUser): boolean {
  return (
    user.gender !== null &&
    user.card_ids.length +
      user.preferred_pay_methods.length +
      user.student_credentials.length +
      user.benefit_programs.length >
      0
  );
}

/** 서버 계정 설정을 로컬 프로필 형태로 되싣는다(계정이 진실의 출처). */
function mergeServerProfile(
  prev: UserProfileLocal | null,
  user: AuthUser
): UserProfileLocal {
  const base: UserProfileLocal = prev ?? {
    userId: user.id,
    personaId: "me",
    ...settingsForDemo("demo_a"),
    personalProfile: settingsForDemo("demo_a"),
  };
  if (!hasServerSettings(user)) {
    return { ...base, userId: user.id };
  }
  const serverSettings: ProfileSettings = {
    gender: (user.gender as ProfileSettings["gender"]) ?? null,
    cardIds: [...user.card_ids],
    telecom: user.telecom,
    payMethods: user.preferred_pay_methods as ProfileSettings["payMethods"],
    studentCredentials:
      user.student_credentials as ProfileSettings["studentCredentials"],
    benefitPrograms: user.benefit_programs as ProfileSettings["benefitPrograms"],
  };
  return {
    ...base,
    userId: user.id,
    personaId: "me",
    ...cloneSettings(serverSettings),
    personalProfile: cloneSettings(serverSettings),
  };
}

export default function App() {
  const [profile, setProfile] = useState<UserProfileLocal | null>(null);
  const [onboarding, setOnboarding] = useState(true);
  // 탭 이동은 브라우저 기록에 남겨 뒤로가기로 이전 탭에 돌아온다.
  const [tab, setTab] = useNavState<Tab>("tab", "map", true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  // 메일의 재설정 링크는 ?reset_token=... 으로 들어온다.
  // 라우터를 두기엔 화면이 하나뿐이라 쿼리스트링만 읽는다.
  const [resetToken, setResetToken] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("reset_token")
  );

  function clearResetToken() {
    setResetToken(null);
    // 토큰이 주소창·히스토리에 남지 않게 지운다.
    window.history.replaceState(window.history.state, "", window.location.pathname);
  }

  // 이메일 인증(?verify_token=)과 알림 수신 거부(?unsubscribe_token=) 링크.
  const [mailLink, setMailLink] = useState<{
    kind: "verify" | "unsubscribe";
    token: string;
  } | null>(() => {
    const query = new URLSearchParams(window.location.search);
    const verify = query.get("verify_token");
    const unsubscribe = query.get("unsubscribe_token");
    if (verify) return { kind: "verify", token: verify };
    if (unsubscribe) return { kind: "unsubscribe", token: unsubscribe };
    return null;
  });

  function clearMailLink() {
    setMailLink(null);
    window.history.replaceState(window.history.state, "", window.location.pathname);
    // 인증 여부·알림 설정이 바뀌었을 수 있으니 로그인 상태면 다시 읽는다.
    fetchCurrentUser()
      .then((fresh) => fresh && setUser(fresh))
      .catch(() => undefined);
  }

  // 첫 화면에서 뒤로가기를 눌러도 앱 밖(이전 사이트)으로 나가지 않게 한다.
  useEffect(() => installBackGuard(), []);

  useEffect(() => {
    const saved = loadProfile();
    if (saved) {
      const myProfile: UserProfileLocal = {
        ...saved,
        ...cloneSettings(saved.personalProfile),
        personaId: "me",
      };
      setProfile(myProfile);
      saveProfile(myProfile);
    }
    // 앱을 새로 열 때는 저장값 유무와 관계없이 내 정보 입력부터 시작한다.
    setOnboarding(true);
  }, []);

  // 세션 복원. 새로고침해도 로그인이 유지돼야 한다.
  useEffect(() => {
    fetchCurrentUser()
      .then((restored) => {
        setUser(restored);
        if (restored) {
          setProfile((prev) => {
            const next = mergeServerProfile(prev, restored);
            saveProfile(next);
            return next;
          });
          setOnboarding(!hasServerSettings(restored));
        }
      })
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  function handleAuthenticated(nextUser: AuthUser) {
    setUser(nextUser);
    // userId의 출처를 서버 계정으로 옮긴다. 이후 요청은 세션 쿠키로 인증되고,
    // localStorage의 UUID는 더 이상 신원 근거가 아니다.
    setProfile((prev) => {
      const next = mergeServerProfile(prev, nextUser);
      saveProfile(next);
      return next;
    });
    // 계정에 설정이 있으면 온보딩을 건너뛴다. 기기를 바꿔도 다시 묻지 않는다.
    setOnboarding(!hasServerSettings(nextUser));
  }

  async function handleLogout() {
    await apiLogout();
    setUser(null);
    setOnboarding(true);
  }

  function handleComplete(nextProfile: UserProfileLocal) {
    const personalProfile = cloneSettings(nextProfile);
    const normalized: UserProfileLocal = {
      ...nextProfile,
      ...cloneSettings(personalProfile),
      userId: isUuid(nextProfile.userId)
        ? nextProfile.userId
        : crypto.randomUUID(),
      personaId: "me",
      personalProfile,
    };
    setProfile(normalized);
    saveProfile(normalized);
    setOnboarding(false);
    setTab("map");

    // 계정에도 남긴다. 실패해도 화면을 막지 않는다(localStorage 에는 이미 저장됨).
    updateProfile({
      gender: normalized.gender,
      telecom: normalized.telecom,
      card_ids: normalized.cardIds,
      preferred_pay_methods: normalized.payMethods,
      student_credentials: normalized.studentCredentials,
      benefit_programs: normalized.benefitPrograms,
    }).catch(() => undefined);
  }

  function applyPersona(value: string) {
    if (!profile || !isPersonaId(value)) return;
    const settings = value === "me"
      ? cloneSettings(profile.personalProfile)
      : settingsForDemo(value);
    const nextProfile: UserProfileLocal = {
      ...profile,
      ...settings,
      personaId: value,
    };
    setProfile(nextProfile);
    saveProfile(nextProfile);
  }

  function editMyProfile() {
    if (profile) {
      const myProfile: UserProfileLocal = {
        ...profile,
        ...cloneSettings(profile.personalProfile),
        personaId: "me",
      };
      setProfile(myProfile);
      saveProfile(myProfile);
    }
    setOnboarding(true);
  }

  // 세션 확인이 끝나기 전에 화면을 그리면 로그인 상태인데도 로그인창이
  // 잠깐 번쩍인다.
  if (!authChecked) {
    return (
      <div className="app">
        <main className="content">
          <p className="notice">불러오는 중…</p>
        </main>
      </div>
    );
  }

  // 로그인이 온보딩보다 앞선다. 온보딩에서 모은 설정을 계정에 붙이려면
  // 그 시점에 이미 계정이 있어야 한다.
  // 재설정 링크로 들어왔으면 로그인보다 먼저 처리한다.
  if (resetToken) {
    return <ResetPasswordPage token={resetToken} onDone={clearResetToken} />;
  }

  // 메일 링크는 다른 기기에서 열 수 있으므로 로그인 여부와 무관하게 처리한다.
  if (mailLink) {
    return (
      <MailLinkPage kind={mailLink.kind} token={mailLink.token} onDone={clearMailLink} />
    );
  }

  if (!user) {
    return (
      <AuthPage onAuthenticated={handleAuthenticated} />
    );
  }

  if (onboarding) {
    return (
      <div className="app">
        <header className="topbar">
          <span className="brand">
            <span>TMI</span>
          </span>
          <span className="tagline">대학생 혜택 모음</span>
        </header>
        <main className="content">
          <OnboardingPage initial={profile} onComplete={handleComplete} />
        </main>
      </div>
    );
  }

  const selectedPersona = profile ? getPersonaForProfile(profile) : null;

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">
          <span>TMI</span>
        </span>
        <div className="topbar-actions">
          {selectedPersona && profile && (
            <>
              <label className="global-persona-control">
                <span>페르소나</span>
                <select
                  aria-label="전역 페르소나 선택"
                  value={profile.personaId}
                  onChange={(event) => applyPersona(event.target.value)}
                >
                  <option value="me">나 · 직접 설정</option>
                  {DEMO_PERSONAS.map((persona) => (
                    <option key={persona.id} value={persona.id}>
                      {persona.name} · {persona.archetype}
                    </option>
                  ))}
                </select>
              </label>
              <span className="global-persona-summary">
                {selectedPersona.cardLabel}
              </span>
            </>
          )}
          <button
            className="text-button"
            type="button"
            onClick={editMyProfile}
          >
            내 정보 수정
          </button>
          <button className="text-button" type="button" onClick={handleLogout}>
            로그아웃
          </button>
        </div>
      </header>

      <main className="content">
        {tab === "map" ? (
          <MapPage profile={profile} />
        ) : tab === "chat" ? (
          <ChatPage />
        ) : tab === "community" ? (
          <CommunityPage />
        ) : (
          <MyPage
            profile={profile}
            user={user}
            onUserChange={setUser}
            onSignedOut={() => {
              setUser(null);
              setOnboarding(true);
            }}
          />
        )}
      </main>

      <nav className="bottom-nav" role="tablist" aria-label="서비스 전환">
        <button
          role="tab"
          aria-selected={tab === "map"}
          className={tab === "map" ? "on" : ""}
          onClick={() => setTab("map")}
        >
          <span aria-hidden="true">⌖</span>
          지도 할인
        </button>
        <button
          role="tab"
          aria-selected={tab === "chat"}
          className={tab === "chat" ? "on" : ""}
          onClick={() => setTab("chat")}
        >
          <span aria-hidden="true">✦</span>
          장학금 챗봇
        </button>
        <button
          role="tab"
          aria-selected={tab === "community"}
          className={tab === "community" ? "on" : ""}
          onClick={() => setTab("community")}
        >
          <span aria-hidden="true">▤</span>
          게시판
        </button>
        <button
          role="tab"
          aria-selected={tab === "my"}
          className={tab === "my" ? "on" : ""}
          onClick={() => setTab("my")}
        >
          <span aria-hidden="true">●</span>
          마이페이지
        </button>
      </nav>
    </div>
  );
}

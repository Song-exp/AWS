import { useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
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
import type { ProfileSettings, UserProfileLocal } from "./types";

type Tab = "map" | "chat" | "my";

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

export default function App() {
  const [profile, setProfile] = useState<UserProfileLocal | null>(null);
  const [onboarding, setOnboarding] = useState(true);
  const [tab, setTab] = useState<Tab>("map");

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
        </div>
      </header>

      <main className="content">
        {tab === "map" ? (
          <MapPage profile={profile} />
        ) : tab === "chat" ? (
          <ChatPage userId={profile?.userId ?? null} />
        ) : (
          <MyPage profile={profile} />
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

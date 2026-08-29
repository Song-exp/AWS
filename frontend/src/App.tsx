import { useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
import MapPage from "./pages/MapPage";
import MyPage from "./pages/MyPage";
import OnboardingPage from "./pages/OnboardingPage";
import type { UserProfileLocal } from "./types";

type Tab = "map" | "chat" | "my";

const STORAGE_KEY = "paypick.profile.v1";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function loadProfile(): UserProfileLocal | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const stored = JSON.parse(raw) as Partial<UserProfileLocal>;
    if (!Array.isArray(stored.cardIds) || !Array.isArray(stored.payMethods)) {
      return null;
    }

    // userId 도입 전에 저장된 프로필도 같은 키를 사용한다. UUID가 없거나
    // 잘못된 경우 여기서 한 번 생성해 채팅 저장과 마이페이지 조회가 공유한다.
    const profile: UserProfileLocal = {
      userId: isUuid(stored.userId) ? stored.userId : crypto.randomUUID(),
      cardIds: stored.cardIds.filter(
        (id): id is number => typeof id === "number" && Number.isInteger(id)
      ),
      telecom: typeof stored.telecom === "string" ? stored.telecom : null,
      payMethods: stored.payMethods,
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
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
      setProfile(saved);
      setOnboarding(false);
    }
  }, []);

  function handleComplete(nextProfile: UserProfileLocal) {
    const normalized = {
      ...nextProfile,
      userId: isUuid(nextProfile.userId)
        ? nextProfile.userId
        : crypto.randomUUID(),
    };
    setProfile(normalized);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    setOnboarding(false);
    setTab("map");
  }

  if (onboarding) {
    return (
      <div className="app">
        <header className="topbar">
          <span className="brand">
            <span>Pay</span>Pick
          </span>
          <span className="tagline">대학생 혜택 모음</span>
        </header>
        <main className="content">
          <OnboardingPage initial={profile} onComplete={handleComplete} />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">
          <span>Pay</span>Pick
        </span>
        <button
          className="text-button"
          type="button"
          onClick={() => setOnboarding(true)}
        >
          내 정보 수정
        </button>
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
          <span aria-hidden="true">🗺️</span>
          지도 할인
        </button>
        <button
          role="tab"
          aria-selected={tab === "chat"}
          className={tab === "chat" ? "on" : ""}
          onClick={() => setTab("chat")}
        >
          <span aria-hidden="true">🎓</span>
          장학금 챗봇
        </button>
        <button
          role="tab"
          aria-selected={tab === "my"}
          className={tab === "my" ? "on" : ""}
          onClick={() => setTab("my")}
        >
          <span aria-hidden="true">👤</span>
          마이페이지
        </button>
      </nav>
    </div>
  );
}

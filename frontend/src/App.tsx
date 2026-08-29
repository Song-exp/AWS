import { useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
import MapPage from "./pages/MapPage";
import MyPage from "./pages/MyPage";
import OnboardingPage from "./pages/OnboardingPage";
import type { UserProfileLocal } from "./types";

type Tab = "map" | "chat" | "my";

const STORAGE_KEY = "paypick.profile.v1";

function loadProfile(): UserProfileLocal | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as UserProfileLocal;
    if (!Array.isArray(p.cardIds) || !Array.isArray(p.payMethods)) return null;
    return p;
  } catch {
    return null;
  }
}

export default function App() {
  const [profile, setProfile] = useState<UserProfileLocal | null>(null);
  const [onboarding, setOnboarding] = useState(true);
  const [tab, setTab] = useState<Tab>("map");

  // 저장된 프로필이 있으면 온보딩을 건너뛴다.
  useEffect(() => {
    const saved = loadProfile();
    if (saved) {
      setProfile(saved);
      setOnboarding(false);
    }
  }, []);

  function handleComplete(p: UserProfileLocal) {
    setProfile(p);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
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
          <ChatPage />
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

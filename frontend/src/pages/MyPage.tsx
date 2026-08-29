import { useEffect, useState } from "react";
import { fetchMyPage } from "../api";
import type { MyPageData, UserProfileLocal } from "../types";

interface Props {
  profile: UserProfileLocal | null;
}

const RESULT_LABELS: Record<string, string> = {
  draft: "작성중",
  submitted: "제출완료",
  accepted: "합격",
  rejected: "불합격",
};

const SOURCE_LABELS: Record<string, string> = {
  uploaded: "업로드",
  generated: "서비스 작성",
};

export default function MyPage({ profile }: Props) {
  const [data, setData] = useState<MyPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"applications" | "documents" | "cards">(
    "applications"
  );

  useEffect(() => {
    if (!profile) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchMyPage(profile.userId, profile.cardIds)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [profile]);

  if (!profile) {
    return <div className="mypage"><p className="notice">먼저 온보딩에서 내 정보를 입력해주세요.</p></div>;
  }
  if (loading) return <div className="mypage"><p className="notice">불러오는 중…</p></div>;
  if (error) return <div className="mypage"><p className="notice error">{error}</p></div>;
  if (!data) return null;

  return (
    <div className="mypage">
      <section className="hero">
        <p className="eyebrow">MY PAGE</p>
        <h1>내 장학 기록</h1>
        <div className="mypage-stats">
          <span>신청 {data.counts.applications ?? 0}</span>
          <span>자기소개서 {data.counts.documents ?? 0}</span>
          <span>보유 카드 {data.counts.cards ?? 0}</span>
        </div>
      </section>

      <div className="mypage-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "applications"} className={tab === "applications" ? "on" : ""} onClick={() => setTab("applications")}>신청 기록</button>
        <button role="tab" aria-selected={tab === "documents"} className={tab === "documents" ? "on" : ""} onClick={() => setTab("documents")}>자기소개서</button>
        <button role="tab" aria-selected={tab === "cards"} className={tab === "cards" ? "on" : ""} onClick={() => setTab("cards")}>보유 카드</button>
      </div>

      <div className="mypage-body">
        {tab === "applications" && (
          data.applications.length === 0 ? (
            <p className="notice">아직 신청 기록이 없어요. 챗봇에서 장학금을 찾아 지원서를 저장해보세요.</p>
          ) : (
            data.applications.map((a) => (
              <article key={a.id} className="mypage-card">
                <div className="mypage-card-top">
                  <strong>{a.scholarship_name}</strong>
                  <span className={`badge ${a.result}`}>{RESULT_LABELS[a.result] ?? a.result}</span>
                </div>
                <p className="mypage-meta">
                  {a.organization ?? "기관 미상"} · {SOURCE_LABELS[a.source] ?? a.source}
                  {a.created_at ? ` · ${a.created_at.slice(0, 10)}` : ""}
                </p>
                {a.documents.length > 0 && (
                  <p className="mypage-doc-count">문서 {a.documents.length}건</p>
                )}
              </article>
            ))
          )
        )}

        {tab === "documents" && (
          data.documents.length === 0 ? (
            <p className="notice">저장된 자기소개서가 없어요. 신청서를 업로드하거나 작성하면 여기 모입니다.</p>
          ) : (
            data.documents.map((d) => (
              <article key={d.id} className="mypage-card">
                <div className="mypage-card-top">
                  <strong>{d.prompt_question ?? "(제목 없음)"}</strong>
                  <span className="badge">{d.char_count}자</span>
                </div>
                <p className="mypage-doc-text">{d.content_text.slice(0, 200)}{d.content_text.length > 200 ? "…" : ""}</p>
              </article>
            ))
          )
        )}

        {tab === "cards" && (
          data.cards.length === 0 ? (
            <p className="notice">등록된 카드가 없어요. 온보딩에서 보유 카드를 선택하면 여기 표시됩니다.</p>
          ) : (
            data.cards.map((c) => (
              <article key={c.id} className="mypage-card">
                <div className="mypage-card-top">
                  <strong>{c.card_name}</strong>
                </div>
                <p className="mypage-meta">{c.issuer ?? "발급사 미상"}</p>
              </article>
            ))
          )
        )}
      </div>

      <section className="scholarship-savings" aria-labelledby="scholarship-savings-title">
        <p className="eyebrow">SCHOLARSHIP SAVINGS</p>
        <h2 id="scholarship-savings-title">이제까지 아낀 장학금</h2>
        <div className="character-walkway" aria-label="경희 남녀 캐릭터가 걷는 모습">
          <div className="walking-pair">
            <span className="walking-character">
              <img
                src="/khu-male-walk.gif"
                alt="걷는 경희 남학생 캐릭터"
                loading="lazy"
              />
            </span>
            <span className="walking-character">
              <img
                src="/khu-female-walk.gif"
                alt="걷는 경희 여학생 캐릭터"
                loading="lazy"
              />
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}

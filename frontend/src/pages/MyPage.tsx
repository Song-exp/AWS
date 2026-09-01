import { useEffect, useState } from "react";
import { fetchMyPage, fetchSavingsSummary } from "../api";
import { DEMO_PERSONAS, getPersonaForProfile } from "../personas";
import AccountSettings from "../components/AccountSettings";
import type { AuthUser, MyPageData, SavingSummary, UserProfileLocal } from "../types";

interface Props {
  profile: UserProfileLocal | null;
  user: AuthUser;
  onSignedOut: () => void;
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

const RANKED_PERSONAS = [...DEMO_PERSONAS].sort(
  (a, b) =>
    b.savingsAmount + b.scholarshipAmount -
    (a.savingsAmount + a.scholarshipAmount)
);

const formatWon = (amount: number) => `${amount.toLocaleString("ko-KR")}원`;

export default function MyPage({ profile, user, onSignedOut }: Props) {
  const [data, setData] = useState<MyPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savings, setSavings] = useState<SavingSummary | null>(null);
  const [tab, setTab] = useState<
    "savings" | "applications" | "documents" | "cards" | "account"
  >("savings");

  useEffect(() => {
    if (!profile) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchMyPage(profile.cardIds)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [profile?.userId, profile?.cardIds]);

  useEffect(() => {
    if (!profile) return;
    // 세이빙은 보조 지표라 실패해도 마이페이지 전체를 막지 않는다.
    fetchSavingsSummary()
      .then(setSavings)
      .catch(() => setSavings(null));
  }, [profile?.userId]);

  if (!profile) {
    return <div className="mypage"><p className="notice">먼저 온보딩에서 내 정보를 입력해주세요.</p></div>;
  }
  if (loading) return <div className="mypage"><p className="notice">불러오는 중…</p></div>;
  if (error) return <div className="mypage"><p className="notice error">{error}</p></div>;
  if (!data) return null;

  const selectedPersona = getPersonaForProfile(profile);
  const genderLabel = selectedPersona.gender === "male" ? "남성" : "여성";
  const character = selectedPersona.gender === "male"
    ? {
        src: "/khu-male-walk.gif",
        alt: "걷는 경희 남학생 캐릭터",
      }
    : {
        src: "/khu-female-walk.gif",
        alt: "걷는 경희 여학생 캐릭터",
      };

  return (
    <div className="mypage">
      <section className="hero">
        <p className="eyebrow">MY PAGE</p>
        <h1>내 장학 기록</h1>
        <div className="mypage-stats">
          <span>{genderLabel} 프로필</span>
          <span>신청 {data.counts.applications ?? 0}</span>
          <span>자기소개서 {data.counts.documents ?? 0}</span>
          <span>보유 카드 {data.counts.cards ?? 0}</span>
          {savings && <span>이번 달 {formatWon(savings.month_saved)} 세이브</span>}
        </div>
      </section>

      <div className="mypage-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "savings"} className={tab === "savings" ? "on" : ""} onClick={() => setTab("savings")}>세이빙</button>
        <button role="tab" aria-selected={tab === "applications"} className={tab === "applications" ? "on" : ""} onClick={() => setTab("applications")}>신청 기록</button>
        <button role="tab" aria-selected={tab === "documents"} className={tab === "documents" ? "on" : ""} onClick={() => setTab("documents")}>자기소개서</button>
        <button role="tab" aria-selected={tab === "cards"} className={tab === "cards" ? "on" : ""} onClick={() => setTab("cards")}>보유 카드</button>
        <button role="tab" aria-selected={tab === "account"} className={tab === "account" ? "on" : ""} onClick={() => setTab("account")}>계정</button>
      </div>

      <div className="mypage-body">
        {tab === "account" && (
          <AccountSettings user={user} onSignedOut={onSignedOut} />
        )}

        {tab === "savings" && (
          !savings ? (
            <p className="notice">세이빙 기록을 불러오지 못했어요.</p>
          ) : (
            <>
              <section className="saving-summary">
                <p className="saving-month">{savings.month} 누적</p>
                <strong className="saving-amount">{formatWon(savings.month_saved)}</strong>
                {savings.reward ? (
                  <p className="saving-reward">{savings.reward.message}</p>
                ) : (
                  <p className="saving-reward muted">
                    지도에서 혜택을 쓰고 '소비 완료'를 누르면 절감액이 쌓여요.
                  </p>
                )}
                <div className="saving-metrics">
                  <span>소비 완료 {savings.month_count}건</span>
                  <span>혜택 조회 {savings.viewed_count}건</span>
                  <span>전환율 {Math.round(savings.conversion_rate * 100)}%</span>
                </div>
                <p className="saving-total">전체 누적 {formatWon(savings.total_saved)}</p>
              </section>

              {savings.recent.length === 0 ? (
                <p className="notice">아직 소비 완료 기록이 없어요.</p>
              ) : (
                savings.recent.map((r) => (
                  <div key={r.id} className="mypage-card">
                    <div className="mypage-card-top">
                      <strong>{r.store_label || "매장 미지정"}</strong>
                      <span className="badge">-{formatWon(r.saved_amount)}</span>
                    </div>
                    <p className="mypage-meta">
                      {formatWon(r.original_amount)} → {formatWon(r.final_amount)}
                      {r.method_label ? ` · ${r.method_label}` : ""}
                      {r.created_at ? ` · ${r.created_at.slice(0, 10)}` : ""}
                    </p>
                  </div>
                ))
              )}
            </>
          )
        )}

        {tab === "applications" && (
          data.applications.length === 0 ? (
            <p className="notice">아직 신청 기록이 없어요. 챗봇에서 장학금을 찾아 지원서를 저장해보세요.</p>
          ) : (
            data.applications.map((a) => (
              <details key={a.id} className="mypage-card mypage-detail-card">
                <summary>
                  <div className="mypage-card-top">
                    <strong>{a.scholarship_name}</strong>
                    <span className={`badge ${a.result}`}>{RESULT_LABELS[a.result] ?? a.result}</span>
                  </div>
                  <p className="mypage-meta">
                    {a.organization ?? "기관 미상"} · {SOURCE_LABELS[a.source] ?? a.source}
                    {a.created_at ? ` · ${a.created_at.slice(0, 10)}` : ""}
                  </p>
                  <div className="mypage-detail-footer">
                    <span className="mypage-doc-count">문서 {a.documents.length}건</span>
                    <span className="mypage-detail-action" aria-hidden="true">내용 보기</span>
                  </div>
                </summary>
                <div className="mypage-detail-content">
                  {a.documents.length === 0 ? (
                    <p className="notice">이 신청 기록에는 저장된 문서 내용이 없어요.</p>
                  ) : (
                    a.documents.map((d, index) => (
                      <section key={d.id} className="mypage-document-section">
                        <div className="mypage-document-heading">
                          <strong>{d.prompt_question ?? `첨부 문서 ${index + 1}`}</strong>
                          <span>{d.char_count.toLocaleString("ko-KR")}자</span>
                        </div>
                        <p className="mypage-full-text">{d.content_text || "저장된 내용이 없어요."}</p>
                      </section>
                    ))
                  )}
                </div>
              </details>
            ))
          )
        )}

        {tab === "documents" && (
          data.documents.length === 0 ? (
            <p className="notice">저장된 자기소개서가 없어요. 신청서를 업로드하거나 작성하면 여기 모입니다.</p>
          ) : (
            data.documents.map((d) => (
              <details key={d.id} className="mypage-card mypage-detail-card">
                <summary>
                  <div className="mypage-card-top">
                    <strong>{d.prompt_question ?? "첨부 자기소개서"}</strong>
                    <span className="badge">{d.char_count.toLocaleString("ko-KR")}자</span>
                  </div>
                  <p className="mypage-doc-text">{d.content_text.slice(0, 200)}{d.content_text.length > 200 ? "…" : ""}</p>
                  <div className="mypage-detail-footer">
                    <span className="mypage-detail-action" aria-hidden="true">전체 내용 보기</span>
                  </div>
                </summary>
                <div className="mypage-detail-content">
                  <p className="mypage-full-text">{d.content_text || "저장된 내용이 없어요."}</p>
                </div>
              </details>
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
        <div className="savings-title-row">
          <div className="savings-section-heading">
            <p className="eyebrow">SERVICE IMPACT</p>
            <h2 id="scholarship-savings-title">이제까지 아낀 금액</h2>
          </div>
        </div>

        <div className="savings-overview">
          <div className="persona-character-card" data-persona-gender={selectedPersona.gender}>
            <span className="persona-gender-chip">
              {selectedPersona.name} · {genderLabel} 페르소나
            </span>
            <div className="character-walkway" aria-label={`${selectedPersona.name} ${genderLabel} 페르소나 캐릭터`}>
              <span className="walking-character walking-solo">
                <img src={character.src} alt={character.alt} loading="lazy" />
              </span>
            </div>
            <strong>내 프로필 캐릭터</strong>
            <p>선택한 성별에 맞는 캐릭터만 표시돼요.</p>
            <div className="persona-saving-total">
              <span>내가 아낀 금액</span>
              <strong>{formatWon(selectedPersona.savingsAmount)}</strong>
            </div>
          </div>

          <div className="savings-leaderboard">
            <div className="leaderboard-head">
              <div>
                <span>DEMO PERSONAS</span>
                <h3>누적 혜택 TOP 3</h3>
              </div>
              <small>시연용 누적 데이터</small>
            </div>
            <ol className="leaderboard-list">
              {RANKED_PERSONAS.map((persona, index) => {
                const total = persona.savingsAmount + persona.scholarshipAmount;
                return (
                  <li
                    key={persona.id}
                    className={`${index === 0 ? "is-winner " : ""}${persona.id === selectedPersona.id ? "is-selected" : ""}`.trim()}
                  >
                    <span className="leader-rank" aria-label={`${index + 1}위`}>
                      {index === 0 ? "★" : index + 1}
                    </span>
                    <div className="leader-persona">
                      <div className="leader-name-line">
                        <strong>{persona.name}</strong>
                        <span>{persona.gender === "male" ? "남성" : "여성"}</span>
                      </div>
                      <p>{persona.archetype}</p>
                      <div className="leader-breakdown">
                        <span>서비스 절약 <b>{formatWon(persona.savingsAmount)}</b></span>
                        <span>신청 완료 장학금 <b>{formatWon(persona.scholarshipAmount)}</b></span>
                      </div>
                    </div>
                    <div className="leader-total">
                      <small>합계</small>
                      <strong>{formatWon(total)}</strong>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}

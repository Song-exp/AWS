import { useCallback, useEffect, useState } from "react";
import ChatPage from "./ChatPage";
import {
  fetchBenefitItems,
  fetchPosting,
  fetchPostings,
  toggleBenefitCheck,
} from "../api";
import { SPEND_LABELS } from "../types";
import type {
  BenefitItem,
  Posting,
  PostingDetail,
  SpendCategory,
} from "../types";

/** 혜택 탭 — 신청해서 받는 것들.
 *
 * 지도가 '지금 여기서 깎는 것'이라면 이쪽은 '내 조건으로 받는 것'이다.
 * 기본 진입은 대화가 아니라 목록이다. 예전에는 매칭 엔드포인트뿐이라
 * 뭐가 올라와 있는지 구경하려면 소득분위부터 말해야 했다.
 *
 * 목록을 둘로 나눈다. 정렬 규칙과 수명이 다르기 때문이다.
 *   공고   — 마감 임박순, 지나면 사라짐
 *   상시   — 절감액순, 영구, 한 번 켜면 끝
 * 섞으면 마감이 없는 상시 항목이 영원히 바닥에 깔린다.
 */
type Section = "postings" | "standing";

type View =
  | { kind: "list" }
  | { kind: "posting"; id: number }
  | { kind: "chat" };

const CATEGORY_KEYS = Object.keys(SPEND_LABELS) as SpendCategory[];

function won(value: number): string {
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

/** 마감까지 남은 날. 이 화면이 시간축을 대신하므로 가장 먼저 읽혀야 한다. */
function deadlineLabel(posting: Posting): string {
  if (posting.days_left === null) return "상시 모집";
  if (posting.days_left < 0) return "마감";
  if (posting.days_left === 0) return "오늘 마감";
  return `D-${posting.days_left}`;
}

function urgency(posting: Posting): string {
  if (posting.days_left === null) return "";
  if (posting.days_left <= 3) return " urgent";
  if (posting.days_left <= 7) return " soon";
  return "";
}

export default function BenefitsPage() {
  const [section, setSection] = useState<Section>("postings");
  const [view, setView] = useState<View>({ kind: "list" });

  const [postings, setPostings] = useState<Posting[]>([]);
  const [items, setItems] = useState<BenefitItem[]>([]);
  const [remaining, setRemaining] = useState({ count: 0, krw: 0 });
  const [filters, setFilters] = useState<SpendCategory[]>([]);
  const [detail, setDetail] = useState<PostingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (section === "postings") {
        const page = await fetchPostings({ sort: "deadline", limit: 30 });
        setPostings(page.items);
      } else {
        const page = await fetchBenefitItems(filters);
        setItems(page.items);
        setRemaining({
          count: page.remaining_count,
          krw: page.remaining_hint_krw,
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [section, filters]);

  useEffect(() => {
    if (view.kind === "list") void load();
  }, [load, view.kind]);

  useEffect(() => {
    if (view.kind !== "posting") return;
    setDetail(null);
    fetchPosting(view.id)
      .then(setDetail)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "공고를 불러오지 못했습니다.")
      );
  }, [view]);

  function toggleFilter(key: SpendCategory) {
    setFilters((current) =>
      current.includes(key)
        ? current.filter((c) => c !== key)
        : [...current, key]
    );
  }

  async function check(item: BenefitItem) {
    // 낙관적 반영. 체크는 되돌릴 수 있으니 응답을 기다릴 이유가 없다.
    setItems((current) =>
      current.map((i) => (i.key === item.key ? { ...i, done: !i.done } : i))
    );
    try {
      await toggleBenefitCheck(item.key);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크에 실패했습니다.");
      await load();
    }
  }

  // ---------------- 대화 ----------------
  if (view.kind === "chat") {
    return (
      <section className="benefits">
        <header className="benefits-head">
          <button className="link-back" onClick={() => setView({ kind: "list" })}>
            ← 목록
          </button>
          <h2>초안 도우미</h2>
        </header>
        <ChatPage />
      </section>
    );
  }

  // ---------------- 공고 상세 ----------------
  if (view.kind === "posting") {
    return (
      <section className="benefits">
        <header className="benefits-head">
          <button className="link-back" onClick={() => setView({ kind: "list" })}>
            ← 목록
          </button>
        </header>

        {!detail ? (
          <p className="notice">불러오는 중…</p>
        ) : (
          <article className="posting-detail">
            <span className={`deadline${urgency(detail)}`}>
              {deadlineLabel(detail)}
            </span>
            <h2>{detail.title}</h2>
            <p className="posting-org">
              {detail.organization ?? "기관 미상"} · {detail.source_platform}
            </p>

            {detail.required_documents.length > 0 && (
              <div className="posting-block">
                <h3>필요 서류</h3>
                <ul>
                  {detail.required_documents.map((doc) => (
                    <li key={doc}>{doc}</li>
                  ))}
                </ul>
              </div>
            )}

            {detail.body_text && (
              <div className="posting-block">
                <h3>공고 내용</h3>
                <p className="posting-body">{detail.body_text.slice(0, 1200)}</p>
              </div>
            )}

            <div className="posting-actions">
              {/* 신청은 앱 안에서 끝나지 않는다. 원문으로 나간다. */}
              <a
                className="primary"
                href={detail.source_url}
                target="_blank"
                rel="noreferrer"
              >
                신청하러 가기
              </a>
              <button onClick={() => setView({ kind: "chat" })}>
                초안 써달라기
              </button>
            </div>
          </article>
        )}
      </section>
    );
  }

  // ---------------- 목록 ----------------
  return (
    <section className="benefits">
      <div className="segment" role="tablist" aria-label="혜택 종류">
        <button
          role="tab"
          aria-selected={section === "postings"}
          className={section === "postings" ? "on" : ""}
          onClick={() => setSection("postings")}
        >
          모집 공고
        </button>
        <button
          role="tab"
          aria-selected={section === "standing"}
          className={section === "standing" ? "on" : ""}
          onClick={() => setSection("standing")}
        >
          상시 혜택
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {section === "postings" ? (
        <>
          {loading && postings.length === 0 && <p className="notice">불러오는 중…</p>}
          {!loading && postings.length === 0 && (
            <p className="notice">지금 모집 중인 공고가 없어요.</p>
          )}
          <ul className="posting-list">
            {postings.map((p) => (
              <li key={p.id}>
                <button onClick={() => setView({ kind: "posting", id: p.id })}>
                  <span className={`deadline${urgency(p)}`}>{deadlineLabel(p)}</span>
                  <strong>{p.title}</strong>
                  <span className="posting-org">
                    {p.organization ?? p.source_platform}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <p className="standing-hint">
            아직 안 챙긴 혜택 <strong>{remaining.count}개</strong> · 연{" "}
            <strong>{won(remaining.krw)}</strong> 추정
          </p>

          <div className="chips" role="group" aria-label="분야 필터">
            {CATEGORY_KEYS.map((key) => (
              <button
                key={key}
                className={filters.includes(key) ? "chip on" : "chip"}
                aria-pressed={filters.includes(key)}
                onClick={() => toggleFilter(key)}
              >
                {SPEND_LABELS[key]}
              </button>
            ))}
          </div>

          {loading && items.length === 0 && <p className="notice">불러오는 중…</p>}

          <ul className="benefit-list">
            {items.map((item) => (
              <li key={item.key} className={item.done ? "done" : ""}>
                <label>
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => void check(item)}
                  />
                  <span className="benefit-body">
                    <strong>{item.title}</strong>
                    <span className="benefit-summary">{item.summary}</span>
                    <span className="benefit-meta">
                      {item.category_label} · 연 {won(item.saving_hint_krw)} 추정 ·{" "}
                      {item.effort_min}분
                      {item.credential ? ` · ${item.credential}` : ""}
                    </span>
                  </span>
                </label>
                <a
                  className="benefit-go"
                  href={
                    item.url ??
                    `https://search.naver.com/search.naver?query=${encodeURIComponent(
                      item.search_hint ?? item.title
                    )}`
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  {item.url ? "신청" : "찾기"}
                </a>
              </li>
            ))}
          </ul>

          <p className="notice small">
            절감액은 추정치예요. 요금제와 환급률은 수시로 바뀌니 신청 화면에서
            확인해 주세요.
          </p>
        </>
      )}
    </section>
  );
}

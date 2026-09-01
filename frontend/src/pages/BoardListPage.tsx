import { useEffect, useState } from "react";
import { fetchBoards } from "../api";
import type { BoardCategory, CommunityBoard } from "../types";

interface Props {
  onOpenBoard: (slug: string, name: string) => void;
  onOpenFeed: (feed: FeedKey, label: string) => void;
}

export type FeedKey = "me/posts" | "me/commented" | "me/scraps" | "hot" | "best";

const CATEGORIES: { key: BoardCategory | null; label: string }[] = [
  { key: null, label: "전체" },
  { key: "career", label: "진로" },
  { key: "promo", label: "홍보" },
  { key: "group", label: "단체" },
];

const SHORTCUTS: { key: FeedKey; label: string; icon: string; tone: string }[] = [
  { key: "me/posts", label: "내가 쓴 글", icon: "📄", tone: "blue" },
  { key: "me/commented", label: "댓글 단 글", icon: "💬", tone: "teal" },
  { key: "me/scraps", label: "스크랩", icon: "🔖", tone: "amber" },
  { key: "hot", label: "HOT 게시판", icon: "🔥", tone: "red" },
  { key: "best", label: "BEST 게시판", icon: "🏆", tone: "grey" },
];

export default function BoardListPage({ onOpenBoard, onOpenFeed }: Props) {
  const [category, setCategory] = useState<BoardCategory | null>(null);
  const [query, setQuery] = useState("");
  const [boards, setBoards] = useState<CommunityBoard[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // 입력할 때마다 요청하면 타이핑 중에 낭비가 크다. 잠깐 멈추면 보낸다.
    const timer = setTimeout(() => {
      fetchBoards(category, query.trim() || undefined)
        .then((rows) => {
          if (!cancelled) setBoards(rows);
        })
        .catch((e: Error) => {
          if (!cancelled) setError(e.message);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [category, query]);

  return (
    <div className="board-list">
      <div className="board-chips" role="tablist" aria-label="게시판 분류">
        {CATEGORIES.map((c) => (
          <button
            key={c.label}
            role="tab"
            aria-selected={category === c.key}
            className={`board-chip ${category === c.key ? "on" : ""}`}
            onClick={() => setCategory(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <label className="board-search">
        <span aria-hidden="true">🔍</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="다른 게시판을 검색해보세요"
          aria-label="게시판 검색"
        />
      </label>

      {/* 검색 중에는 바로가기가 결과를 가리므로 숨긴다 */}
      {!query.trim() && (
        <ul className="board-shortcuts">
          {SHORTCUTS.map((s) => (
            <li key={s.key}>
              <button onClick={() => onOpenFeed(s.key, s.label)}>
                <span className={`shortcut-icon ${s.tone}`} aria-hidden="true">
                  {s.icon}
                </span>
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="notice error">{error}</p>}

      <ul className="board-items">
        {boards.length === 0 && !error ? (
          <li className="notice">게시판이 없어요.</li>
        ) : (
          boards.map((b) => (
            <li key={b.id}>
              <button onClick={() => onOpenBoard(b.slug, b.name)}>
                <span className="board-pin" aria-hidden="true">
                  📌
                </span>
                <span className="board-name">{b.name}</span>
                {b.has_new && (
                  <span className="board-new" aria-label="새 글 있음">
                    N
                  </span>
                )}
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

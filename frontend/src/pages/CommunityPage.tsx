import { useEffect, useState } from "react";
import BoardPage from "./BoardPage";
import PostDetailPage from "./PostDetailPage";
import { fetchBoards } from "../api";
import { useNavState } from "../useNavState";
import type { CommunityBoard, FeedKey } from "../types";

/** 커뮤니티 섹션 안의 화면 전환.
 *
 * 게시판이 둘(절약 꿀팁·공동구매)뿐이라 게시판 목록 화면을 두지 않는다.
 * 목록을 보여줄 게 두 개면 그 화면은 탭 한 번을 더 먹을 뿐이다. 그래서
 * 커뮤니티 탭은 바로 글 목록으로 열리고, 게시판 전환은 상단 세그먼트가 한다.
 *
 * 앱 전체에 라우터는 여전히 들이지 않는다. 화면이 둘이고 하단 탭이 이미
 * 최상위 내비게이션이라, 라우터를 넣으면 탭 상태와 URL 상태를 양쪽으로
 * 맞추는 일이 늘어난다.
 */
type View =
  | { kind: "board"; slug: string | null; feed: FeedKey | null; title: string }
  | { kind: "post"; postId: number };

const FEEDS: { key: FeedKey; label: string }[] = [
  { key: "hot", label: "HOT" },
  { key: "me/posts", label: "내 글" },
  { key: "me/scraps", label: "스크랩" },
];

export default function CommunityPage() {
  const [boards, setBoards] = useState<CommunityBoard[]>([]);
  // 화면 전환은 브라우저 기록에 쌓는다. 뒤로가기가 글 → 목록 → 이전 게시판 순으로 돌아온다.
  const [navView, setView] = useNavState<View | null>("community", null);

  useEffect(() => {
    fetchBoards()
      .then(setBoards)
      .catch(() => setBoards([]));
  }, []);

  // 첫 진입은 첫 게시판(절약 꿀팁)으로 연다. 기록을 쌓지 않으려고 상태가 아니라 파생값으로 둔다.
  const view: View = navView ?? {
    kind: "board",
    slug: boards[0]?.slug ?? null,
    feed: null,
    title: boards[0]?.name ?? "커뮤니티",
  };

  if (view.kind === "post") {
    // 글은 언제나 목록에서 열리므로, 돌아가기는 브라우저 뒤로가기와 같다.
    return (
      <div className="community page-shell">
        <PostDetailPage
          postId={view.postId}
          onBack={() => window.history.back()}
          onDeleted={() => window.history.back()}
        />
      </div>
    );
  }

  return (
    <div className="community page-shell">
      <section className="hero community-hero" aria-labelledby="community-title">
        <p className="eyebrow">COMMUNITY</p>
        <h1 id="community-title">
          아낀 방법을<br />
          <strong>함께</strong> 나눠요.
        </h1>
        <p className="location-status">
          절약 꿀팁과 공동구매를 경희대 학생끼리 공유해요.
        </p>
      </section>

      <div className="community-nav">
        <div className="segment" role="tablist" aria-label="게시판 전환">
          {boards.map((b) => (
            <button
              key={b.slug}
              role="tab"
              aria-selected={view.slug === b.slug}
              className={view.slug === b.slug ? "on" : ""}
              onClick={() =>
                setView({ kind: "board", slug: b.slug, feed: null, title: b.name })
              }
            >
              {b.name}
              {b.has_new && <span className="new-dot" aria-label="새 글" />}
            </button>
          ))}
        </div>

        <div className="feed-links">
          {FEEDS.map((f) => (
            <button
              key={f.key}
              className={view.feed === f.key ? "on" : ""}
              onClick={() =>
                setView({ kind: "board", slug: null, feed: f.key, title: f.label })
              }
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {(view.slug || view.feed) && (
        <BoardPage
          slug={view.slug}
          feed={view.feed}
          title={view.title}
          onBack={null}
          onOpenPost={(postId) => setView({ kind: "post", postId })}
        />
      )}
    </div>
  );
}

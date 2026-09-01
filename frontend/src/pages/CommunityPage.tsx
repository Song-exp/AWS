import { useState } from "react";
import BoardListPage, { type FeedKey } from "./BoardListPage";
import BoardPage from "./BoardPage";
import PostDetailPage from "./PostDetailPage";

/** 커뮤니티 섹션 안의 화면 전환.
 *
 * 앱 전체에 라우터를 들이지 않고 이 섹션 안에서만 스택을 관리한다.
 * 화면이 셋뿐이고 하단 탭이 이미 최상위 내비게이션이라, 라우터를 넣으면
 * 탭 상태와 URL 상태를 양쪽으로 맞추는 일이 더 늘어난다.
 */
type View =
  | { kind: "boards" }
  | { kind: "board"; slug: string | null; feed: FeedKey | null; title: string }
  | { kind: "post"; postId: number };

export default function CommunityPage() {
  const [view, setView] = useState<View>({ kind: "boards" });
  // 글 상세에서 뒤로 갈 목록을 기억한다.
  const [origin, setOrigin] = useState<View>({ kind: "boards" });

  if (view.kind === "post") {
    return (
      <PostDetailPage
        postId={view.postId}
        onBack={() => setView(origin)}
        onDeleted={() => setView(origin)}
      />
    );
  }

  if (view.kind === "board") {
    return (
      <BoardPage
        slug={view.slug}
        feed={view.feed}
        title={view.title}
        onBack={() => setView({ kind: "boards" })}
        onOpenPost={(postId) => {
          setOrigin(view);
          setView({ kind: "post", postId });
        }}
      />
    );
  }

  return (
    <BoardListPage
      onOpenBoard={(slug, name) =>
        setView({ kind: "board", slug, feed: null, title: name })
      }
      onOpenFeed={(feed, label) =>
        setView({ kind: "board", slug: null, feed, title: label })
      }
    />
  );
}

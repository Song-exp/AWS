import { useCallback, useEffect, useState } from "react";
import {
  createPost,
  fetchBoardPosts,
  fetchBoardQuestions,
  fetchBoards,
  fetchPostFeed,
} from "../api";
import type { CommunityBoard, PostSummary } from "../types";
import type { FeedKey } from "./BoardListPage";

interface Props {
  /** 게시판 slug. 피드(HOT/내 글 등)를 볼 때는 null. */
  slug: string | null;
  feed: FeedKey | null;
  title: string;
  onBack: () => void;
  onOpenPost: (postId: number) => void;
}

const PAGE_SIZE = 20;

/** '3분 전'처럼 상대 시각으로 보여준다. 목록에서는 이 편이 읽기 쉽다. */
function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}시간 전`;
  const day = Math.floor(hour / 24);
  if (day < 7) return `${day}일 전`;
  return iso.slice(5, 10).replace("-", "/");
}

export default function BoardPage({
  slug,
  feed,
  title,
  onBack,
  onOpenPost,
}: Props) {
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [questions, setQuestions] = useState<PostSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [composing, setComposing] = useState(false);
  const [board, setBoard] = useState<CommunityBoard | null>(null);

  const load = useCallback(
    async (offset = 0) => {
      setLoading(true);
      setError(null);
      try {
        const page = slug
          ? await fetchBoardPosts(slug, offset, PAGE_SIZE)
          : await fetchPostFeed(feed!, offset, PAGE_SIZE);
        setPosts((prev) => (offset === 0 ? page.items : [...prev, ...page.items]));
        setTotal(page.total);
        if (slug && offset === 0) {
          setQuestions(await fetchBoardQuestions(slug));
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [slug, feed]
  );

  useEffect(() => {
    setPosts([]);
    load(0);
  }, [load]);

  useEffect(() => {
    if (!slug) return;
    // 익명 허용 여부는 게시판마다 다르다. 글쓰기 폼이 그에 맞춰야 한다.
    fetchBoards()
      .then((rows) => setBoard(rows.find((b) => b.slug === slug) ?? null))
      .catch(() => setBoard(null));
  }, [slug]);

  // HOT 글은 목록 상단에 따로 띄운다(화면 3의 붉은 카드).
  const hotPost = slug ? posts.find((p) => p.like_count >= 10) ?? null : null;

  return (
    <div className="board-page">
      <header className="board-header">
        <button className="icon-button" onClick={onBack} aria-label="뒤로">
          ←
        </button>
        <div className="board-title">
          <strong>{title}</strong>
          <span>경희대</span>
        </div>
      </header>

      {questions.length > 0 && (
        <div className="question-strip">
          {questions.map((q) => (
            <button
              key={q.id}
              className="question-card"
              onClick={() => onOpenPost(q.id)}
            >
              <span className="question-badge">질문글</span>
              <strong>{q.title}</strong>
              <span className="question-preview">{q.preview}</span>
            </button>
          ))}
        </div>
      )}

      {hotPost && (
        <button className="hot-strip" onClick={() => onOpenPost(hotPost.id)}>
          <span aria-hidden="true">🔥</span>
          <span className="hot-title">{hotPost.title}</span>
          <span className="hot-likes">👍 {hotPost.like_count}</span>
        </button>
      )}

      {error && <p className="notice error">{error}</p>}

      <ul className="post-list">
        {posts.length === 0 && !loading ? (
          <li className="notice">아직 글이 없어요. 첫 글을 남겨보세요.</li>
        ) : (
          posts.map((p) => (
            <li key={p.id}>
              <button onClick={() => onOpenPost(p.id)}>
                <strong className="post-title">{p.title}</strong>
                <span className="post-preview">{p.preview}</span>
                <span className="post-meta">
                  {timeAgo(p.created_at)} | {p.author_label}
                  {p.comment_count > 0 && (
                    <span className="post-count">💬 {p.comment_count}</span>
                  )}
                  {p.like_count > 0 && (
                    <span className="post-count">👍 {p.like_count}</span>
                  )}
                </span>
              </button>
            </li>
          ))
        )}
      </ul>

      {posts.length < total && (
        <button
          className="load-more"
          disabled={loading}
          onClick={() => load(posts.length)}
        >
          {loading ? "불러오는 중…" : "더 보기"}
        </button>
      )}

      {slug && (
        <button className="write-fab" onClick={() => setComposing(true)}>
          ✏️ 글쓰기
        </button>
      )}

      {composing && slug && (
        <ComposeDialog
          board={board}
          slug={slug}
          onClose={() => setComposing(false)}
          onCreated={() => {
            setComposing(false);
            load(0);
          }}
        />
      )}
    </div>
  );
}

function ComposeDialog({
  board,
  slug,
  onClose,
  onCreated,
}: {
  board: CommunityBoard | null;
  slug: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  // 게시판이 익명을 강제하거나 금지하면 사용자가 고를 여지가 없다.
  const anonymousLocked = !!board && (board.forces_anonymous || !board.allows_anonymous);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(board?.allows_anonymous ?? true);
  const [isQuestion, setIsQuestion] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (board) setIsAnonymous(board.forces_anonymous || board.allows_anonymous);
  }, [board]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await createPost({
        board_slug: slug,
        title: title.trim(),
        body: body.trim(),
        is_anonymous: isAnonymous,
        is_question: isQuestion,
      });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="compose-backdrop" role="dialog" aria-label="글쓰기">
      <form className="compose" onSubmit={submit}>
        <header>
          <button type="button" className="icon-button" onClick={onClose}>
            ✕
          </button>
          <strong>글쓰기</strong>
          <button type="submit" className="compose-submit" disabled={busy}>
            {busy ? "등록 중…" : "등록"}
          </button>
        </header>

        <input
          className="compose-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="제목"
          maxLength={200}
          required
        />
        <textarea
          className="compose-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="내용을 입력하세요"
          maxLength={10000}
          required
        />

        <div className="compose-options">
          <label>
            <input
              type="checkbox"
              checked={isAnonymous}
              disabled={anonymousLocked}
              onChange={(e) => setIsAnonymous(e.target.checked)}
            />
            익명
            {board?.forces_anonymous && <em> (이 게시판은 익명만 가능해요)</em>}
            {board && !board.allows_anonymous && <em> (이 게시판은 실명만 가능해요)</em>}
          </label>
          <label>
            <input
              type="checkbox"
              checked={isQuestion}
              onChange={(e) => setIsQuestion(e.target.checked)}
            />
            질문글
          </label>
        </div>

        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}

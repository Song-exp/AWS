import { useEffect, useState } from "react";
import {
  apiUrl,
  createComment,
  deleteComment,
  deletePost,
  fetchPost,
  reportPost,
  toggleCommentLike,
  togglePostLike,
  togglePostScrap,
} from "../api";
import type { PostDetail } from "../types";

interface Props {
  postId: number;
  onBack: () => void;
  /** 글이 삭제되면 목록으로 돌아가며 새로고침한다. */
  onDeleted: () => void;
}

/** 본문의 URL을 링크로 만든다. 커뮤니티 글은 링크 공유가 잦다. */
function renderBody(body: string) {
  return body.split(/(https?:\/\/\S+)/g).map((chunk, i) =>
    /^https?:\/\//.test(chunk) ? (
      <a key={i} href={chunk} target="_blank" rel="noopener noreferrer">
        {chunk}
      </a>
    ) : (
      <span key={i}>{chunk}</span>
    )
  );
}

function formatStamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}`;
}

export default function PostDetailPage({ postId, onBack, onDeleted }: Props) {
  const [post, setPost] = useState<PostDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [anonymous, setAnonymous] = useState(true);
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchPost(postId).then(setPost).catch((e: Error) => setError(e.message));
  }, [postId]);

  async function act(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitComment(e: React.FormEvent) {
    e.preventDefault();
    const text = comment.trim();
    if (!text) return;
    await act(async () => {
      setPost(await createComment(postId, text, anonymous, replyTo));
      setComment("");
      setReplyTo(null);
    });
  }

  if (error && !post) return <p className="notice error">{error}</p>;
  if (!post) return <p className="notice">불러오는 중…</p>;

  const topLevel = post.comments.filter((c) => c.parent_id === null);
  const repliesOf = (id: number) =>
    post.comments.filter((c) => c.parent_id === id);

  return (
    <div className="post-detail">
      <header className="board-header">
        <button className="icon-button" onClick={onBack} aria-label="뒤로">
          ←
        </button>
        <div className="board-title">
          <strong>{post.board_name}</strong>
          <span>경희대</span>
        </div>
        {post.is_mine ? (
          <button
            className="icon-button"
            aria-label="글 삭제"
            onClick={() =>
              act(async () => {
                await deletePost(post.id);
                onDeleted();
              })
            }
          >
            🗑
          </button>
        ) : (
          <button
            className="icon-button"
            aria-label="신고"
            onClick={() =>
              act(async () => {
                await reportPost(post.id, "부적절한 게시물");
                setError("신고가 접수됐어요.");
              })
            }
          >
            ⚠
          </button>
        )}
      </header>

      <article className="post-body">
        <div className="post-author">
          <span className="avatar" aria-hidden="true">
            👤
          </span>
          <div>
            <strong>{post.author_label}</strong>
            <span className="post-stamp">{formatStamp(post.created_at)}</span>
          </div>
        </div>

        <h1>{post.title}</h1>
        <div className="post-text">{renderBody(post.body)}</div>
        {post.image_urls.length > 0 && (
          <div className="post-images">
            {post.image_urls.map((url, i) => (
              <a key={url} href={apiUrl(url)} target="_blank" rel="noreferrer">
                <img src={apiUrl(url)} alt={`첨부 이미지 ${i + 1}`} loading="lazy" />
              </a>
            ))}
          </div>
        )}
      </article>

      <div className="post-actions">
        <button
          className={post.liked_by_me ? "on" : ""}
          onClick={() =>
            act(async () => {
              const r = await togglePostLike(post.id);
              setPost({ ...post, liked_by_me: r.active, like_count: r.count });
            })
          }
        >
          👍 공감 {post.like_count > 0 && post.like_count}
        </button>
        <button>💬 댓글 {post.comment_count > 0 && post.comment_count}</button>
        <button
          className={post.scrapped_by_me ? "on" : ""}
          onClick={() =>
            act(async () => {
              const r = await togglePostScrap(post.id);
              setPost({ ...post, scrapped_by_me: r.active });
            })
          }
        >
          🔖 스크랩
        </button>
      </div>

      {error && <p className="notice">{error}</p>}

      <section className="comment-list">
        {topLevel.length === 0 ? (
          <p className="comment-empty">
            <span aria-hidden="true">💬</span>
            첫 댓글을 남겨주세요.
          </p>
        ) : (
          topLevel.map((c) => (
            <div key={c.id}>
              <CommentRow
                comment={c}
                onReply={() => setReplyTo(c.id)}
                onLike={() =>
                  act(async () => {
                    await toggleCommentLike(c.id);
                    setPost(await fetchPost(postId));
                  })
                }
                onDelete={() =>
                  act(async () => {
                    await deleteComment(c.id);
                    setPost(await fetchPost(postId));
                  })
                }
              />
              {repliesOf(c.id).map((r) => (
                <div key={r.id} className="comment-reply">
                  <CommentRow
                    comment={r}
                    onLike={() =>
                      act(async () => {
                        await toggleCommentLike(r.id);
                        setPost(await fetchPost(postId));
                      })
                    }
                    onDelete={() =>
                      act(async () => {
                        await deleteComment(r.id);
                        setPost(await fetchPost(postId));
                      })
                    }
                  />
                </div>
              ))}
            </div>
          ))
        )}
      </section>

      <form className="comment-form" onSubmit={submitComment}>
        {replyTo !== null && (
          <div className="reply-hint">
            답글 작성 중
            <button type="button" onClick={() => setReplyTo(null)}>
              취소
            </button>
          </div>
        )}
        <div className="comment-input-row">
          <label className="anon-toggle">
            <input
              type="checkbox"
              checked={anonymous}
              onChange={(e) => setAnonymous(e.target.checked)}
            />
            익명
          </label>
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="댓글을 입력하세요."
            maxLength={3000}
            aria-label="댓글 입력"
          />
          <button type="submit" className="comment-send" disabled={busy}>
            ➤
          </button>
        </div>
      </form>
    </div>
  );
}

function CommentRow({
  comment,
  onReply,
  onLike,
  onDelete,
}: {
  comment: PostDetail["comments"][number];
  onReply?: () => void;
  onLike: () => void;
  onDelete: () => void;
}) {
  return (
    <div className={`comment-row ${comment.is_deleted ? "deleted" : ""}`}>
      <div className="comment-head">
        <strong>{comment.is_deleted ? "" : comment.author_label}</strong>
        <span className="post-stamp">{formatStamp(comment.created_at)}</span>
      </div>
      <p>{comment.body}</p>
      {!comment.is_deleted && (
        <div className="comment-actions">
          <button className={comment.liked_by_me ? "on" : ""} onClick={onLike}>
            👍 {comment.like_count > 0 && comment.like_count}
          </button>
          {onReply && <button onClick={onReply}>답글</button>}
          {comment.is_mine && <button onClick={onDelete}>삭제</button>}
        </div>
      )}
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  apiUrl,
  createPost,
  fetchBoardPosts,
  fetchBoardQuestions,
  fetchPostFeed,
  fetchSavingsSummary,
  uploadPostImages,
} from "../api";
import { SPEND_LABELS } from "../types";
import type {
  FeedKey,
  PostSummary,
  SavingRecord,
  SpendCategory,
} from "../types";

const CATEGORY_KEYS = Object.keys(SPEND_LABELS) as SpendCategory[];
// 서버 제한과 같다(app/api/community.py MAX_IMAGES_PER_POST, settings.max_upload_mb).
const MAX_IMAGES = 4;
const MAX_IMAGE_MB = 10;

interface Props {
  /** 게시판 slug. 피드(HOT/내 글 등)를 볼 때는 null. */
  slug: string | null;
  feed: FeedKey | null;
  title: string;
  /** 상위가 세그먼트로 전환하면 뒤로가기가 필요 없다. */
  onBack: (() => void) | null;
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
  const [filters, setFilters] = useState<SpendCategory[]>([]);

  const load = useCallback(
    async (offset = 0) => {
      setLoading(true);
      setError(null);
      try {
        const page = slug
          ? await fetchBoardPosts(slug, offset, PAGE_SIZE, filters)
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
    [slug, feed, filters]
  );

  useEffect(() => {
    setPosts([]);
    load(0);
  }, [load]);

  // HOT 글은 목록 상단에 따로 띄운다(화면 3의 붉은 카드).
  const hotPost = slug ? posts.find((p) => p.like_count >= 10) ?? null : null;

  return (
    <div className="board-page">
      <header className="section-heading board-heading">
        {onBack && (
          <button className="icon-button" onClick={onBack} aria-label="뒤로">
            ←
          </button>
        )}
        <h2>
          {title} <span>{total}</span>
        </h2>
        <span className="filter-summary">경희대</span>
      </header>

      {slug && (
        <div className="chips" role="group" aria-label="분야 필터">
          {CATEGORY_KEYS.map((key) => (
            <button
              key={key}
              className={filters.includes(key) ? "chip on" : "chip"}
              aria-pressed={filters.includes(key)}
              onClick={() =>
                setFilters((current) =>
                  current.includes(key)
                    ? current.filter((c) => c !== key)
                    : [...current, key]
                )
              }
            >
              {SPEND_LABELS[key]}
            </button>
          ))}
        </div>
      )}

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
                {p.thumbnail_url && (
                  <img className="post-thumb" src={apiUrl(p.thumbnail_url)} alt="" loading="lazy" />
                )}
                <strong className="post-title">
                  {p.is_question && <span className="question-badge">질문</span>}
                  {p.title}
                </strong>
                <span className="post-preview">{p.preview}</span>
                <span className="post-meta">
                  {p.category_label && (
                    <span className="post-cat">{p.category_label}</span>
                  )}
                  {timeAgo(p.created_at)} | {p.author_label}
                  {p.author_tier && (
                    <span className="tier-badge">{p.author_tier}</span>
                  )}
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
        <button className="write-fab primary-button" onClick={() => setComposing(true)}>
          ＋ 글쓰기
        </button>
      )}

      {composing && slug && (
        <ComposeDialog
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
  slug,
  onClose,
  onCreated,
}: {
  slug: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState<SpendCategory | "">("");
  const [savings, setSavings] = useState<SavingRecord[]>([]);
  const [images, setImages] = useState<File[]>([]);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 자유게시판을 뺀 대신 앱이 첫 콘텐츠를 공급해야 한다. 내가 실제로 아낀
  // 기록이 글 초안이 되는 경로가 그것이다. 없으면 게시판이 빈 채로 시작한다.
  useEffect(() => {
    fetchSavingsSummary()
      .then((summary) => setSavings(summary.recent.slice(0, 5)))
      .catch(() => setSavings([]));
  }, []);

  function prefillFrom(record: SavingRecord) {
    const saved = Math.round(record.saved_amount).toLocaleString("ko-KR");
    setTitle(`${record.store_label}에서 ${saved}원 아꼈어요`);
    setBody(
      `${record.store_label}
` +
        (record.method_label ? `${record.method_label}
` : "") +
        `${Math.round(record.original_amount).toLocaleString("ko-KR")}원 → ` +
        `${Math.round(record.final_amount).toLocaleString("ko-KR")}원 ` +
        `(${saved}원 절약)

`
    );
    if (record.category) setCategory(record.category);
  }

  // 미리보기 URL은 파일이 바뀌거나 창이 닫힐 때 해제한다.
  const previews = useMemo(() => images.map((f) => URL.createObjectURL(f)), [images]);
  useEffect(() => () => previews.forEach(URL.revokeObjectURL), [previews]);

  function addImages(list: FileList | null) {
    if (!list) return;
    const picked = Array.from(list).filter((f) => f.type.startsWith("image/"));
    const tooBig = picked.find((f) => f.size > MAX_IMAGE_MB * 1024 * 1024);
    if (tooBig) {
      setError(`${tooBig.name}: 이미지는 ${MAX_IMAGE_MB}MB까지 올릴 수 있어요.`);
      return;
    }
    setError(null);
    setImages((current) => [...current, ...picked].slice(0, MAX_IMAGES));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      // 이미지 업로드만 실패했다면 재시도 때 글을 다시 만들지 않는다.
      const postId =
        createdId ??
        (
          await createPost({
            board_slug: slug,
            title: title.trim(),
            body: body.trim(),
            // 익명 여부는 고르지 않는다. 기본 익명, 실명 전용 게시판이면 서버가 실명으로 바꾼다.
            is_anonymous: true,
            is_question: false,
            category: category || null,
          })
        ).id;
      setCreatedId(postId);
      if (images.length > 0) {
        try {
          await uploadPostImages(postId, images);
        } catch (err) {
          setError(
            `글은 등록됐어요. 사진을 올리지 못했어요: ${(err as Error).message} ` +
              "사진을 고쳐 다시 등록하거나, 사진을 빼고 등록하세요."
          );
          return;
        }
      }
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
          <button type="button" className="icon-button" onClick={createdId === null ? onClose : onCreated} aria-label="닫기">
            ✕
          </button>
          <strong>글쓰기</strong>
          <button type="submit" className="compose-submit" disabled={busy}>
            {busy ? "등록 중…" : "등록"}
          </button>
        </header>

        {savings.length > 0 && (
          <div className="compose-prefill">
            <span>내 절감 내역에서 가져오기</span>
            <div className="chips">
              {savings.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="chip"
                  onClick={() => prefillFrom(r)}
                >
                  {r.store_label} -{Math.round(r.saved_amount).toLocaleString("ko-KR")}원
                </button>
              ))}
            </div>
          </div>
        )}

        <input
          className="compose-title"
          disabled={createdId !== null}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="제목"
          maxLength={200}
          required
        />
        <textarea
          className="compose-body"
          disabled={createdId !== null}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="내용을 입력하세요"
          maxLength={10000}
          required
        />

        <div className="compose-images">
          <span className="compose-label">
            사진 <em>{images.length}/{MAX_IMAGES}</em>
          </span>
          <div className="compose-image-row">
            {previews.map((src, i) => (
              <figure key={src} className="compose-thumb">
                <img src={src} alt={`첨부 이미지 ${i + 1}`} />
                <button
                  type="button"
                  aria-label={`첨부 이미지 ${i + 1} 삭제`}
                  onClick={() => setImages((current) => current.filter((_, j) => j !== i))}
                >
                  ✕
                </button>
              </figure>
            ))}
            {images.length < MAX_IMAGES && (
              <label className="compose-upload">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  multiple
                  className="sr-only"
                  onChange={(e) => {
                    addImages(e.target.files);
                    e.target.value = "";
                  }}
                />
                <span aria-hidden="true">＋</span>
                사진 추가
              </label>
            )}
          </div>
          <small>JPG·PNG·GIF·WEBP · 장당 {MAX_IMAGE_MB}MB · 최대 {MAX_IMAGES}장</small>
        </div>

        <div className="compose-options">
          <label className="compose-category">
            분야
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SpendCategory | "")}
            >
              <option value="">선택 안 함</option>
              {CATEGORY_KEYS.map((key) => (
                <option key={key} value={key}>
                  {SPEND_LABELS[key]}
                </option>
              ))}
            </select>
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

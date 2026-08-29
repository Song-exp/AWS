import { useEffect, useState } from "react";
import { fetchOptions } from "../api";
import SearchSelect from "../components/SearchSelect";
import type { MetaOptions, PayMethod, UserProfileLocal } from "../types";

interface Props {
  initial: UserProfileLocal | null;
  onComplete: (profile: UserProfileLocal) => void;
}

export default function OnboardingPage({ initial, onComplete }: Props) {
  const [opts, setOpts] = useState<MetaOptions | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [cardIds, setCardIds] = useState<string[]>(
    initial ? initial.cardIds.map(String) : []
  );
  const [telecom, setTelecom] = useState<string[]>(
    initial?.telecom ? [initial.telecom] : []
  );
  const [pays, setPays] = useState<string[]>(initial ? initial.payMethods : []);

  useEffect(() => {
    fetchOptions()
      .then(setOpts)
      .catch((e: Error) => setError(e.message));
  }, []);

  function submit() {
    onComplete({
      userId: initial?.userId || crypto.randomUUID(),
      cardIds: cardIds.map((v) => Number(v)),
      telecom: telecom[0] ?? null,
      payMethods: pays as PayMethod[],
    });
  }

  // 아무것도 안 고르면 필터가 무의미하므로 최소 1개는 요구한다.
  const canSubmit = cardIds.length > 0 || pays.length > 0;

  return (
    <div className="onboarding">
      <section className="hero">
        <p className="eyebrow">STEP 1 · 내 정보</p>
        <h1>
          내가 쓰는 <strong>카드와 결제수단</strong>을 알려주세요.
        </h1>
        <p className="sub">선택한 정보 기준으로 주변 할인을 골라 보여드려요.</p>
      </section>

      {error && <p className="notice error">{error}</p>}
      {!opts && !error && <p className="notice">불러오는 중…</p>}

      {opts && (
        <div className="onboarding-form">
          <SearchSelect
            title="보유 카드"
            items={opts.cards.map((c) => ({
              key: String(c.id),
              label: c.card_name,
              sub: `${c.issuer ?? "발급사 미상"} · 혜택 ${c.benefit_count}건`,
            }))}
            selected={cardIds}
            onChange={setCardIds}
            multiple
            placeholder="카드명 또는 발급사로 검색"
          />

          <SearchSelect
            title="통신사"
            items={opts.telecoms.map((t) => ({ key: t, label: t }))}
            selected={telecom}
            onChange={setTelecom}
            multiple={false}
            placeholder="통신사 검색"
            emptyNote={
              opts.telecom_supported
                ? undefined
                : "통신사 혜택 데이터는 준비 중이라 지금은 할인 계산에 반영되지 않아요."
            }
          />

          <SearchSelect
            title="온라인 결제(간편결제)"
            items={opts.pay_methods.map((p) => ({ key: p.value, label: p.label }))}
            selected={pays}
            onChange={setPays}
            multiple
            placeholder="결제수단 검색"
          />

          <button
            className="primary-button"
            type="button"
            onClick={submit}
            disabled={!canSubmit}
          >
            다음 →
          </button>
          {!canSubmit && (
            <p className="select-note">카드 또는 결제수단을 하나 이상 골라주세요.</p>
          )}
        </div>
      )}
    </div>
  );
}

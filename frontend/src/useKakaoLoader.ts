import { useEffect, useState } from "react";

declare global {
  interface Window {
    kakao: any;
  }
}

/**
 * 카카오맵 SDK를 한 번만 로드하고, 모든 호출자가 같은 Promise를 공유한다.
 *
 * React StrictMode는 개발 모드에서 effect를 두 번 실행한다. 스크립트 태그
 * 존재 여부로만 판단하면 두 번째 실행이 이미 끝난 load 이벤트를 기다리다
 * 영원히 준비되지 않는다(지도가 안 뜨는 원인). 그래서 모듈 스코프에
 * Promise를 캐시해 재사용한다.
 */
let sdkPromise: Promise<void> | null = null;

function loadKakaoSdk(appKey: string): Promise<void> {
  // 이미 사용 가능하면 즉시 완료
  if (window.kakao?.maps?.Map && window.kakao?.maps?.services) return Promise.resolve();
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise<void>((resolve, reject) => {
    const finish = () => {
      // autoload=false 이므로 maps.load로 실제 모듈 초기화
      if (window.kakao?.maps?.load) {
        window.kakao.maps.load(() => resolve());
      } else {
        reject(new Error("카카오 SDK 객체를 찾을 수 없습니다."));
      }
    };

    const existing = document.getElementById(
      "kakao-map-sdk"
    ) as HTMLScriptElement | null;

    if (existing) {
      // 스크립트가 이미 있으면 로드 완료 여부를 직접 확인
      if (window.kakao?.maps) {
        finish();
      } else {
        existing.addEventListener("load", finish, { once: true });
        existing.addEventListener(
          "error",
          () => reject(new Error("카카오맵 SDK 로드 실패")),
          { once: true }
        );
      }
      return;
    }

    const script = document.createElement("script");
    script.id = "kakao-map-sdk";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false&libraries=services`;
    script.async = true;
    script.addEventListener("load", finish, { once: true });
    script.addEventListener(
      "error",
      () =>
        reject(
          new Error(
            "카카오맵 SDK를 불러오지 못했습니다. 키와 플랫폼 도메인 등록을 확인하세요."
          )
        ),
      { once: true }
    );
    document.head.appendChild(script);
  }).catch((e) => {
    // 실패 시 다음 시도를 위해 캐시를 비운다
    sdkPromise = null;
    throw e;
  });

  return sdkPromise;
}

export function useKakaoLoader(appKey: string | undefined) {
  const [ready, setReady] = useState<boolean>(
    () => !!window.kakao?.maps?.Map && !!window.kakao?.maps?.services
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!appKey) {
      setError(
        "VITE_KAKAO_MAP_KEY가 설정되지 않았습니다. frontend/.env를 확인하세요."
      );
      return;
    }
    let alive = true;
    loadKakaoSdk(appKey)
      .then(() => {
        if (alive) setReady(true);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [appKey]);

  return { ready, error };
}

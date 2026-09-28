import { useCallback, useEffect, useRef, useState } from "react";

/** 브라우저 뒤로가기와 연결된 화면 상태.
 *
 * 라우터 없이 history.state 한 칸에 화면별 키를 나눠 담는다. 값을 바꾸면
 * 새 기록을 쌓고(pushState), 뒤로가기(popstate)를 하면 그 기록의 값으로
 * 돌아간다. 기록에 키가 없으면 초기값이다.
 */
export function useNavState<T>(
  key: string,
  initial: T,
  /** true면 다른 키(하위 화면 상태)를 버린다. 탭을 옮기면 이전 탭의 세부 화면은 새로 시작한다. */
  clearOthers = false
): [T, (next: T) => void] {
  const initialRef = useRef(initial);
  const [value, setValue] = useState<T>(
    () => (window.history.state?.[key] as T | undefined) ?? initial
  );

  useEffect(() => {
    const onPop = (event: PopStateEvent) =>
      setValue((event.state?.[key] as T | undefined) ?? initialRef.current);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [key]);

  const navigate = useCallback(
    (next: T) => {
      const current = (window.history.state?.[key] as T | undefined) ?? initialRef.current;
      setValue(next);
      // 같은 화면을 다시 누르면 기록을 쌓지 않는다(뒤로가기가 헛돌지 않게).
      if (JSON.stringify(current) === JSON.stringify(next)) return;
      const { guard: _guard, ...rest } = window.history.state ?? {};
      const base = clearOthers ? { app: true } : rest;
      window.history.pushState({ ...base, [key]: next }, "");
    },
    [key, clearOthers]
  );

  return [value, navigate];
}

/** 첫 화면에서 뒤로가기를 눌러도 앱을 떠나지 않게 막는다.
 *
 * 맨 아래에 guard 기록을 하나 깔고 그 위에서 앱을 시작한다. guard까지
 * 돌아오면 첫 화면 기록을 다시 쌓아 그 자리에 머문다.
 */
export function installBackGuard(): () => void {
  if (!window.history.state?.app) {
    window.history.replaceState({ guard: true }, "");
    window.history.pushState({ app: true }, "");
  }
  const onPop = (event: PopStateEvent) => {
    if (event.state?.guard) window.history.pushState({ app: true }, "");
  };
  window.addEventListener("popstate", onPop);
  return () => window.removeEventListener("popstate", onPop);
}

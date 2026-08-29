import { useMemo, useState } from "react";

export interface SelectItem {
  key: string;
  label: string;
  sub?: string;
}

interface Props {
  title: string;
  items: SelectItem[];
  selected: string[];
  onChange: (next: string[]) => void;
  multiple?: boolean;
  placeholder?: string;
  emptyNote?: string;
}

/**
 * 검색 + 드롭다운(목록) 방식의 선택 컴포넌트.
 * multiple=true면 여러 개, false면 하나만 고른다.
 */
export default function SearchSelect({
  title,
  items,
  selected,
  onChange,
  multiple = true,
  placeholder = "검색해서 선택하세요",
  emptyNote,
}: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.label.toLowerCase().includes(q) ||
        (i.sub ? i.sub.toLowerCase().includes(q) : false)
    );
  }, [items, query]);

  function toggle(key: string) {
    if (multiple) {
      onChange(
        selected.includes(key)
          ? selected.filter((k) => k !== key)
          : [...selected, key]
      );
    } else {
      onChange(selected.includes(key) ? [] : [key]);
      setOpen(false);
    }
  }

  const selectedItems = items.filter((i) => selected.includes(i.key));

  return (
    <div className="select-field">
      <div className="select-head">
        <label>{title}</label>
        <span className="select-count">
          {selected.length > 0 ? `${selected.length}개 선택` : "미선택"}
        </span>
      </div>

      {/* 선택된 항목 칩 */}
      {selectedItems.length > 0 && (
        <div className="chips">
          {selectedItems.map((i) => (
            <button
              key={i.key}
              type="button"
              className="chip"
              onClick={() => toggle(i.key)}
              aria-label={`${i.label} 선택 해제`}
            >
              {i.label} <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}

      <input
        className="select-search"
        value={query}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />

      {emptyNote && <p className="select-note">{emptyNote}</p>}

      {(open || query) && (
        <ul className="select-list" role="listbox">
          {filtered.length === 0 && <li className="select-empty">검색 결과가 없어요.</li>}
          {filtered.map((i) => {
            const on = selected.includes(i.key);
            return (
              <li key={i.key}>
                <button
                  type="button"
                  role="option"
                  aria-selected={on}
                  className={`select-option ${on ? "on" : ""}`}
                  onClick={() => toggle(i.key)}
                >
                  <span className="opt-label">{i.label}</span>
                  {i.sub && <span className="opt-sub">{i.sub}</span>}
                  {on && <span className="opt-check" aria-hidden="true">✓</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

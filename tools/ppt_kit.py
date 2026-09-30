# -*- coding: utf-8 -*-
"""발표 템플릿(첨부 PDF 6p) 형식을 재현하기 위한 python-pptx 헬퍼 모듈.

docs/ppt_template_spec.md 의 디자인 시스템을 코드로 옮긴 것.
좌표 단위는 모두 inch (슬라이드 13.333 x 7.5).
"""

from pptx.util import Inches as In, Pt, Emu
from pptx.dml.color import RGBColor as RGB
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.oxml.ns import qn

# ---------------------------------------------------------------- 디자인 토큰
FONT = "맑은 고딕"

# ── 브랜드 앵커 컬러 (경희대 UI) ──────────────────────────────
#   PANTONE 201 C = #9D2235  (경희 레드)
#   PANTONE 872 C = #85714D  (경희 골드 / 메탈릭 골드의 sRGB 환산값)
KHU_RED = RGB(0x9D, 0x22, 0x35)
KHU_GOLD = RGB(0x85, 0x71, 0x4D)

_WARM_WHITE = (0xFF, 0xFC, 0xF2)     # 골드 계열 틴트용 웜 화이트


def tint(color, ratio, target=(0xFF, 0xFF, 0xFF)):
    """color 를 target(기본 흰색) 쪽으로 ratio(0~1)만큼 섞어 연하게."""
    r, g, b = color[0], color[1], color[2]
    return RGB(int(round(r + (target[0] - r) * ratio)),
               int(round(g + (target[1] - g) * ratio)),
               int(round(b + (target[2] - b) * ratio)))


def shade(color, ratio):
    """color 를 검정 쪽으로 ratio(0~1)만큼 섞어 어둡게."""
    return RGB(int(round(color[0] * (1 - ratio))),
               int(round(color[1] * (1 - ratio))),
               int(round(color[2] * (1 - ratio))))


# 레드 계열 (강조 · 진행/예정 · Key Question)
RED_DEEP = shade(KHU_RED, 0.20)          # #7E1B2A  가장 진한 밴드
RED = KHU_RED                            # #9D2235  기본 강조
RED_MID = tint(KHU_RED, 0.45)            # 화살표 · 보조선
RED_SOFT = tint(KHU_RED, 0.76)           # 연한 채움 (연결 화살표)
RED_LIGHT = tint(KHU_RED, 0.87)          # 라이트 채움 박스
RED_WASH = tint(KHU_RED, 0.94)           # 그룹 배경 워시

# 골드 계열 (완료 · 결론 · 보조 구분)
GOLD_DEEP = shade(KHU_GOLD, 0.16)        # #706040  진한 밴드
GOLD = KHU_GOLD                          # #85714D  기본 보조 강조
GOLD_MID = tint(KHU_GOLD, 0.45, _WARM_WHITE)
GOLD_SOFT = tint(KHU_GOLD, 0.70, _WARM_WHITE)
GOLD_LIGHT = tint(KHU_GOLD, 0.83, _WARM_WHITE)
GOLD_WASH = tint(KHU_GOLD, 0.92, _WARM_WHITE)

# 중립 (가독성 확보용 — 브랜드색과 충돌 없이 유지)
GRAY_BOX = RGB(0xF4, 0xF3, 0xF1)     # 라이트 박스 (살짝 웜 그레이)
GRAY_LINE = RGB(0xDA, 0xD6, 0xD1)    # 박스 테두리
RULE = RGB(0xBF, 0xBB, 0xB6)         # 구분선
TEXT = RGB(0x1A, 0x14, 0x15)         # 본문
TEXT_SUB = RGB(0x5A, 0x52, 0x53)     # 보조 텍스트
CAPTION = RGB(0x85, 0x7D, 0x7E)      # 캡션 / 페이지 번호
SUBTITLE = RGB(0x33, 0x2A, 0x2C)     # 소제목
WHITE = RGB(0xFF, 0xFF, 0xFF)
BLACK = RGB(0x1A, 0x14, 0x15)

# 표 헤더 (열=레드 / 행=골드)
TBL_COL_HDR = KHU_RED
TBL_ROW_HDR = KHU_GOLD

# 공통 여백
M_LEFT = 0.62          # 좌측 기준선
CONTENT_RIGHT = 12.72  # 우측 기준선 (13.333 - 0.62)
CONTENT_W = CONTENT_RIGHT - M_LEFT

L, C, R = PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.RIGHT
TOP, MID, BOT = MSO_ANCHOR.TOP, MSO_ANCHOR.MIDDLE, MSO_ANCHOR.BOTTOM


def ea_wrap(text_frame):
    """동아시아 줄바꿈 옵션. LibreOffice 등 일부 렌더러에만 효과가 있고
    PowerPoint 자체 레이아웃 엔진은 이 속성을 무시하므로, 실제 줄바꿈 제어는
    wrap_ko() 로 파이썬에서 미리 끊어서 처리한다."""
    bodyPr = text_frame._txBody.bodyPr
    bodyPr.set("eaLnBrk", "0")
    bodyPr.set("hangingPunct", "1")
    return text_frame


# ------------------------------------------------- 한글 어절 단위 줄바꿈 (핵심)
def _char_adv(ch):
    """맑은 고딕 기준 글자 폭을 em 단위로 근사."""
    o = ord(ch)
    if ch == " ":
        return 0.30
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F:   # 한글
        return 1.0
    if 0x4E00 <= o <= 0x9FFF:                            # 한자
        return 1.0
    if 0x3000 <= o <= 0x303F or 0xFF01 <= o <= 0xFF60:   # 전각 기호
        return 1.0
    if ch in "·•・":
        return 0.50
    if ch.isdigit() or ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return 0.55
    if o < 128:
        return 0.42
    return 0.60


def text_width_em(s):
    return sum(_char_adv(c) for c in s)


def wrap_ko(text, box_w, pt, margin=0.03, safety=0.97):
    """텍스트를 어절 단위로 미리 줄바꿈해 리스트로 돌려준다.

    PowerPoint 는 한글을 글자 단위로 끊어(예: '앱 굿' / '딜') 가독성을 떨어뜨리므로
    박스 폭에 맞는 줄을 파이썬에서 직접 계산해 넣는다.

    box_w  : 텍스트 박스 전체 폭(inch)
    margin : 좌/우 내부 여백(inch, 한쪽 값)
    """
    limit = (box_w - 2 * margin) * safety / (pt / 72.0)   # em 단위 한 줄 한도
    out = []

    def flush_long(token):
        """한 어절이 한 줄보다 길면 글자 단위로 잘라 낸다."""
        rest = token
        while text_width_em(rest) > limit and len(rest) > 1:
            cut = len(rest)
            while cut > 1 and text_width_em(rest[:cut]) > limit:
                cut -= 1
            out.append(rest[:cut])
            rest = rest[cut:]
        return rest

    for seg in text.split("\n"):
        line = ""
        for token in seg.split(" "):
            if not line:
                line = flush_long(token)
                continue
            cand = line + " " + token
            if text_width_em(cand) <= limit:
                line = cand
            else:
                out.append(line)
                line = flush_long(token)
        if line:
            out.append(line)
    return out


# ---------------------------------------------------------------- 텍스트
def _norm(lines, size, bold, color):
    """lines 를 (텍스트, size, bold, color) 튜플 리스트로 정규화.

    허용 입력: "여러\n줄 문자열" / ["줄", "줄"] / [(텍스트, size, bold, color), ...]
    """
    if isinstance(lines, str):
        lines = lines.split("\n")
    out = []
    for item in lines:
        if isinstance(item, str):
            item = (item,)
        t, sz, bd, col = (tuple(item) + (None,) * 4)[:4]
        out.append((t,
                    size if sz is None else sz,
                    bold if bd is None else bd,
                    color if col is None else col))
    return out


def txt(slide, x, y, w, h, lines, size=10, bold=False, color=TEXT,
        align=C, anchor=MID, line=1.25, space=0):
    """텍스트 박스. lines 는 str(개행 분리) 또는 (텍스트, size, bold, color) 튜플 리스트."""
    tb = slide.shapes.add_textbox(In(x), In(y), In(w), In(h))
    tf = tb.text_frame
    tf.word_wrap = True
    ea_wrap(tf)
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = In(0.03)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor

    for i, item in enumerate(_norm(lines, size, bold, color)):
        t, sz, bd, col = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space)
        run = p.add_run()
        run.text = t
        run.font.size = Pt(sz)
        run.font.bold = bd
        run.font.color.rgb = col
        run.font.name = FONT
    return tb


def set_spacing(run, pt):
    """글자 간격(자간)을 pt 단위로 지정. 로고타입·레터스페이싱용."""
    run.font._rPr.set("spc", str(int(round(pt * 100))))
    return run


def rich(slide, x, y, w, h, runs, align=C, anchor=MID, line=1.20, spacing=None):
    """한 단락 안에 서식이 다른 여러 런을 넣는다. (예: '경희대학교 × AWS' 두 톤)

    runs: [(텍스트, size, bold, color), ...]
    spacing: 전체 런에 적용할 자간(pt)
    """
    tb = slide.shapes.add_textbox(In(x), In(y), In(w), In(h))
    tf = tb.text_frame
    tf.word_wrap = True
    ea_wrap(tf)
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line
    for t, sz, bd, col in runs:
        run = p.add_run()
        run.text = t
        run.font.size = Pt(sz)
        run.font.bold = bd
        run.font.color.rgb = col
        run.font.name = FONT
        if spacing:
            set_spacing(run, spacing)
    return tb


def shape_text(shape, lines, size=10, bold=False, color=WHITE,
               align=C, anchor=MID, line=1.15, margin=0.03):
    tf = shape.text_frame
    tf.word_wrap = True
    ea_wrap(tf)
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = In(margin)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, (t, sz, bd, col) in enumerate(_norm(lines, size, bold, color)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        run = p.add_run()
        run.text = t
        run.font.size = Pt(sz)
        run.font.bold = bd
        run.font.color.rgb = col
        run.font.name = FONT
    return shape


# ---------------------------------------------------------------- 도형
def box(slide, x, y, w, h, fill=None, border=None, dash=False,
        shape=MSO_SHAPE.RECTANGLE, bw=0.75, radius=None):
    sh = slide.shapes.add_shape(shape, In(x), In(y), In(w), In(h))
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if border is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = border
        sh.line.width = Pt(bw)
        if dash:
            sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if radius is not None:
        try:
            sh.adjustments[0] = radius
        except (IndexError, ValueError):
            pass
    tf = sh.text_frame
    tf.word_wrap = True
    ea_wrap(tf)
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = In(0.04)
    tf.margin_top = tf.margin_bottom = 0
    return sh


def pill(slide, x, y, w, h, text, fill=RED, color=WHITE, size=11, bold=True):
    """라운드 사각형 pill (Key Question 스타일)."""
    sh = box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    shape_text(sh, text, size=size, bold=bold, color=color)
    return sh


def arrow(slide, x, y, w, h, direction="right", fill=GRAY_LINE):
    shapes = {"right": MSO_SHAPE.RIGHT_ARROW, "down": MSO_SHAPE.DOWN_ARROW,
              "left": MSO_SHAPE.LEFT_ARROW, "up": MSO_SHAPE.UP_ARROW}
    return box(slide, x, y, w, h, fill=fill, shape=shapes[direction])


def hline(slide, x, y, w, color=RULE, thick=0.012):
    return box(slide, x, y, w, thick, fill=color)


def vline(slide, x, y, h, color=RULE, thick=0.012):
    return box(slide, x, y, thick, h, fill=color)


def plus_badge(slide, cx, cy, d=0.26, fill=BLACK):
    sh = box(slide, cx - d / 2, cy - d / 2, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    shape_text(sh, "+", size=11, bold=True, color=WHITE)
    return sh


def num_badge(slide, x, y, n, d=0.20, fill=BLACK, color=WHITE, size=9):
    sh = box(slide, x, y, d, d, fill=fill)
    shape_text(sh, str(n), size=size, bold=True, color=color, margin=0)
    return sh


# ---------------------------------------------------------------- 표 (네이티브)
_PLAIN_STYLE = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # No Style, No Grid


def add_table(slide, x, y, col_widths, row_heights):
    rows, cols = len(row_heights), len(col_widths)
    gf = slide.shapes.add_table(rows, cols, In(x), In(y),
                               In(sum(col_widths)), In(sum(row_heights)))
    table = gf.table
    table.first_row = False
    table.first_col = False
    table.horz_banding = False
    table.vert_banding = False

    tbl = gf._element.graphic.graphicData.tbl
    tblPr = tbl.tblPr
    for el in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(el)
    sid = tblPr.makeelement(qn("a:tableStyleId"), {})
    sid.text = _PLAIN_STYLE
    tblPr.append(sid)

    for i, w in enumerate(col_widths):
        table.columns[i].width = In(w)
    for i, h in enumerate(row_heights):
        table.rows[i].height = In(h)
    return table


def cell_border(cell, color="D9D9D9", width=0.75, edges="LRTB"):
    """셀 테두리. 반드시 fill 설정 뒤에 호출 (스키마 순서: lnL/lnR/lnT/lnB → fill)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tags = {"L": "a:lnL", "R": "a:lnR", "T": "a:lnT", "B": "a:lnB"}
    for e in "LRTB":
        for el in tcPr.findall(qn(tags[e])):
            tcPr.remove(el)
    for e in reversed("LRTB"):
        if e not in edges:
            continue
        ln = tcPr.makeelement(qn(tags[e]), {
            "w": str(int(width * 12700)), "cap": "flat", "cmpd": "sng", "algn": "ctr"})
        sf = ln.makeelement(qn("a:solidFill"), {})
        clr = sf.makeelement(qn("a:srgbClr"), {"val": color})
        sf.append(clr)
        ln.append(sf)
        tcPr.insert(0, ln)


def cell(table, r, c, lines, size=9, bold=False, color=TEXT, align=C, anchor=MID,
         fill=None, border="D9D9D9", bw=0.75, edges="LRTB", line=1.24,
         mh=0.07, mv=0.045):
    cl = table.cell(r, c)
    if fill is None:
        cl.fill.background()
    else:
        cl.fill.solid()
        cl.fill.fore_color.rgb = fill
    if border:
        cell_border(cl, border, bw, edges)
    else:
        cell_border(cl, "FFFFFF", 0.0, "")

    tf = cl.text_frame
    tf.word_wrap = True
    ea_wrap(tf)
    cl.margin_left = cl.margin_right = In(mh)
    cl.margin_top = cl.margin_bottom = In(mv)
    cl.vertical_anchor = anchor

    for i, (t, sz, bd, col) in enumerate(_norm(lines, size, bold, color)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        run = p.add_run()
        run.text = t
        run.font.size = Pt(sz)
        run.font.bold = bd
        run.font.color.rgb = col
        run.font.name = FONT
    return cl


# ---------------------------------------------------------------- 슬라이드 골격
def new_slide(prs, label, headline, subtitle=None, page=None,
              headline_size=20.5, sub_x=None, sub_w=None):
    """템플릿 공통 4단 골격: 섹션 라벨 / 헤드라인 / 소제목+구분선 / (본문은 호출측)."""
    s = prs.slides.add_slide(prs.slide_layouts[6])

    # ① 섹션 라벨
    txt(s, M_LEFT, 0.36, 4.0, 0.24, label, size=11, bold=True, color=RED,
        align=L, anchor=TOP)

    # ② 헤드라인
    nlines = headline.count("\n") + 1
    txt(s, M_LEFT, 0.66, CONTENT_W, 0.42 * nlines + 0.2, headline,
        size=headline_size, bold=True, color=TEXT, align=L, anchor=TOP, line=1.30)

    # ③ 소제목 + 구분선
    if subtitle:
        txt(s, M_LEFT, 1.90, 8.5, 0.30, subtitle, size=14, bold=True,
            color=SUBTITLE, align=L, anchor=TOP)
        hline(s, M_LEFT, 2.26, CONTENT_W)

    # 페이지 번호
    if page is not None:
        txt(s, CONTENT_RIGHT - 1.0, 6.98, 1.0, 0.24, str(page), size=10,
            color=CAPTION, align=R, anchor=TOP)
    return s


def col_header(slide, x, w, y, title, caption=None, size=13, cap_size=9.5,
               cap_x=2.30):
    """p3 스타일 컬럼 헤더 (제목 + 캡션 + 구분선).

    cap_x: 컬럼 좌측 기준 캡션 시작 오프셋(inch). 제목 길이에 맞춰 조정한다.
    """
    txt(slide, x, y, cap_x - 0.06, 0.26, title, size=size, bold=True,
        color=SUBTITLE, align=L, anchor=TOP)
    if caption:
        txt(slide, x + cap_x, y + 0.05, w - cap_x, 0.22, caption, size=cap_size,
            color=CAPTION, align=L, anchor=TOP)
    hline(slide, x, y + 0.32, w)

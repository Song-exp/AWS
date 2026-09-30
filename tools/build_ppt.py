# -*- coding: utf-8 -*-
"""TMI 발표자료 생성 스크립트.

서비스명 TMI — 대학생을 위한 초개인화 혜택 추천 플랫폼.
(서비스 정식 명칭: TMI)

첨부 발표 템플릿 PDF(6p)의 레이아웃 형식만 차용하고, 컬러는 경희대 UI
(PANTONE 201 C 레드 / PANTONE 872 C 골드) 기반으로 재구성한다.

- 슬라이드 1 : 템플릿 p1 형식 -> 아이디어 발굴
- 슬라이드 2 : 템플릿 p2 형식 -> Pain Point x 구현 결과 매핑
- 슬라이드 3 : 템플릿 p3 형식 -> 수집/구축 데이터 설명
- 슬라이드 4 : 구현 화면 시연 (캡처 삽입용으로 본문 비움)
- 슬라이드 5 : 템플릿 p6 형식 -> 구현 완료 + 추가 구현 로드맵

내용 수치는 data.js / engine.js / benefits*.json / local_currency_merchants.json
에서 실측한 값이다. (tools/_counts.py 로 집계)

실행:  python tools/build_ppt.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx import Presentation
from pptx.util import Inches as In
from pptx.enum.shapes import MSO_SHAPE

from ppt_kit import (
    KHU_RED, KHU_GOLD,
    RED, RED_DEEP, RED_MID, RED_SOFT, RED_LIGHT, RED_WASH,
    GOLD, GOLD_DEEP, GOLD_MID, GOLD_SOFT, GOLD_LIGHT, GOLD_WASH,
    GRAY_BOX, GRAY_LINE, RULE, TEXT, TEXT_SUB, CAPTION, SUBTITLE,
    WHITE, BLACK, TBL_COL_HDR, TBL_ROW_HDR,
    M_LEFT, CONTENT_RIGHT, CONTENT_W, L, C, R, TOP, MID, BOT,
    txt, shape_text, box, pill, arrow, hline, vline, plus_badge, num_badge,
    add_table, cell, new_slide, col_header, wrap_ko, rich,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "TMI_발표자료.pptx")

# 서비스 아이덴티티
BRAND = "TMI"
TAGLINE = "대학생을 위한 초개인화 혜택 추천 플랫폼"
PARTNER_LEFT = "경희대학교"
PARTNER_RIGHT = "AWS"
FOOTER_RIGHT = "팀명 | 2026. 08"      # 발표 전 팀명·날짜로 교체

SLIDE_W = 13.333
SLIDE_H = 7.5


def _center_x(w):
    return (SLIDE_W - w) / 2


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def brand_band(s, footer_left):
    """하단 공통 밴드: 얇은 골드 라인 + 레드 밴드 + 좌우 푸터."""
    box(s, 0, 6.86, SLIDE_W, 0.05, fill=KHU_GOLD)
    box(s, 0, 6.91, SLIDE_W, 0.59, fill=KHU_RED)
    txt(s, M_LEFT, 7.06, 6.0, 0.28, footer_left, size=10.5, color=WHITE,
        align=L, anchor=MID)
    txt(s, CONTENT_RIGHT - 5.0, 7.06, 5.0, 0.28, FOOTER_RIGHT, size=10.5,
        color=WHITE, align=R, anchor=MID)


# ===================================================================== 표지
def slide_cover(prs):
    """표지: 경희대학교 × AWS + TMI 로고타입 + 태그라인 + 하단 브랜드 밴드."""
    s = blank(prs)

    # 파트너십 라인 (경희 레드 × AWS 골드 두 톤)
    rich(s, 0, 1.00, SLIDE_W, 0.34, [
        (PARTNER_LEFT, 15, True, KHU_RED),
        ("   ×   ", 15, True, CAPTION),
        (PARTNER_RIGHT, 15, True, KHU_GOLD),
    ], spacing=0.6)
    hline(s, _center_x(1.60), 1.46, 1.60, color=GOLD_SOFT, thick=0.014)

    # 서비스 정체성 (헤더 하단 1.46 ~ 밴드 상단 6.86 사이의 광학 중앙에 배치)
    txt(s, 0, 2.75, SLIDE_W, 0.32, TAGLINE, size=16, bold=True, color=KHU_RED,
        align=C, anchor=MID)

    # 로고타입
    rich(s, 0, 3.15, SLIDE_W, 1.62, [(BRAND, 88, True, KHU_RED)],
         align=C, anchor=MID, spacing=4.0)

    hline(s, _center_x(0.90), 4.95, 0.90, color=KHU_GOLD, thick=0.022)

    txt(s, 0, 5.21, SLIDE_W, 0.36,
        "흩어진 할인 혜택과 장학 정보를 내 조건에 맞춰 계산해주는 서비스",
        size=15, color=TEXT_SUB, align=C, anchor=MID)

    brand_band(s, "경희대학교 × AWS 프로그램")
    return s


# ===================================================================== 감사합니다
def slide_thanks(prs):
    """마무리: THANK YOU + 감사합니다 + 서비스 한 줄."""
    s = blank(prs)

    rich(s, 0, 2.52, SLIDE_W, 0.30, [("THANK YOU", 12.5, True, KHU_GOLD)],
         align=C, anchor=MID, spacing=3.0)

    rich(s, 0, 2.92, SLIDE_W, 1.16, [("감사합니다", 52, True, KHU_RED)],
         align=C, anchor=MID, spacing=2.5)

    hline(s, _center_x(1.20), 4.24, 1.20, color=GOLD_SOFT, thick=0.018)

    rich(s, 0, 4.50, SLIDE_W, 0.32, [
        (BRAND, 14, True, KHU_RED),
        ("  ·  ", 14, False, CAPTION),
        (TAGLINE, 14, False, TEXT_SUB),
    ], align=C, anchor=MID)

    txt(s, 0, 4.94, SLIDE_W, 0.28, "질문과 피드백 환영합니다",
        size=11, color=CAPTION, align=C, anchor=MID)

    brand_band(s, "경희대학교 × AWS 프로그램")
    return s


# ===================================================================== 슬라이드 1
def slide1_idea(prs):
    """템플릿 p1 형식: 2x2 매트릭스 + Key Question pill + 점선 박스 + 결론 박스."""
    s = new_slide(
        prs,
        label="아이디어 발굴",
        headline="대학생이 이미 가진 결제수단과, 받을 수 있었던 장학금을 모두 놓치는 현실에 주목해,\n"
                 "'결제수단 혜택'과 '장학금 정보' 두 축으로 아이디어를 구체화했습니다",
        subtitle="아이디어 도출 과정 & Key Questions",
        page=1,
    )

    # ---- 매트릭스 (네이티브 표) : 행헤더(도메인) + 2열(문제 유형) x 2행
    tx, ty = M_LEFT, 2.45
    cw = [0.72, 2.79, 2.79]
    rh = [0.30, 1.15, 1.15]
    t = add_table(s, tx, ty, cw, rh)

    cell(t, 0, 0, "", fill=WHITE, border="FFFFFF")
    cell(t, 0, 1, "정보 접근", size=10.5, bold=True, color=WHITE, fill=TBL_COL_HDR)
    cell(t, 0, 2, "판단 · 실행", size=10.5, bold=True, color=WHITE, fill=TBL_COL_HDR)
    cell(t, 1, 0, "결제수단\n혜택", size=9.5, bold=True, color=WHITE,
         fill=TBL_ROW_HDR, mh=0.02, line=1.25)
    cell(t, 2, 0, "장학금\n정보", size=9.5, bold=True, color=WHITE,
         fill=TBL_ROW_HDR, mh=0.02, line=1.25)

    matrix = {
        (1, 1): ("[ 흩어진 혜택, 모르는 최대 할인 ]",
                 "학생증·통신사 멤버십·간편결제·체크카드를 모두 "
                 "보유하고 있으나 각 사가 따로 공지해 무엇이 최대 "
                 "할인인지 알 수 없음"),
        (1, 2): ("[ 조합 규칙의 비가시성 ]",
                 "중복 가능 여부·할인 한도·제외 품목이 약관에 흩어져 "
                 "있어 결제 직전 실제 금액을 계산하는 것이 사실상 불가능함"),
        (2, 1): ("[ 공고를 몰라서 놓침 ]",
                 "교내 공지·민간 재단·청년 정책이 각각 다른 사이트에 "
                 "올라와 마감이 지난 뒤에야 알게 되는 경우가 반복됨"),
        (2, 2): ("[ 자격 대조 · 서류 부담 ]",
                 "소득분위·학점·거주지 요건을 일일이 대조해야 하고 "
                 "자기소개서 작성 부담으로 마감 직전 포기하게 됨"),
    }
    for (r_, c_), (title, desc) in matrix.items():
        lines = [(title, 10, True, KHU_RED)]
        lines += [(v, 8.5, False, TEXT_SUB)
                  for v in wrap_ko(desc, cw[c_], 8.5, margin=0.07)]
        cell(t, r_, c_, lines, fill=WHITE)

    mtx_bottom = ty + sum(rh)
    row1_c = ty + rh[0] + rh[1] / 2
    row2_c = ty + rh[0] + rh[1] + rh[2] / 2

    # ---- 우측: 화살표 + pill + 점선 박스
    arrow(s, tx + sum(cw) + 0.08, row1_c - 0.11, 0.32, 0.22, "right", RED_MID)
    arrow(s, tx + sum(cw) + 0.08, row2_c - 0.11, 0.32, 0.22, "right", RED_MID)

    pill(s, 7.45, 2.86, 1.95, 0.30, "Key Question 1", size=10.5)
    txt(s, 7.23, 3.20, 2.40, 0.20, "결제수단 혜택 × 정보 접근 + 판단·실행",
        size=8, bold=True, color=TEXT, align=C, anchor=TOP)
    pill(s, 7.45, 4.02, 1.95, 0.30, "Key Question 2", size=10.5)
    txt(s, 7.23, 4.36, 2.40, 0.20, "장학금 정보 × 정보 접근 + 판단·실행",
        size=8, bold=True, color=TEXT, align=C, anchor=TOP)

    b1 = box(s, 9.63, 2.50, 3.09, 1.16, fill=WHITE, border=KHU_RED, dash=True)
    shape_text(b1, "내가 이미 가진 수단으로\n지금 이 매장에서 가장 싸게\n결제할 방법을 알 수 있을까?",
               size=10, bold=True, color=TEXT, line=1.35)
    b2 = box(s, 9.63, 3.80, 3.09, 1.16, fill=WHITE, border=KHU_RED, dash=True)
    shape_text(b2, "내 조건에 맞는 장학금을\n놓치지 않고 지원까지\n마칠 수 있을까?",
               size=10, bold=True, color=TEXT, line=1.35)

    # ---- 하단: 화살표 + pill + 점선 박스
    col2_c = tx + cw[0] + cw[1] / 2
    col3_c = tx + cw[0] + cw[1] + cw[2] / 2
    arrow(s, col2_c - 0.15, mtx_bottom + 0.04, 0.30, 0.26, "down", GOLD_MID)
    arrow(s, col3_c - 0.15, mtx_bottom + 0.04, 0.30, 0.26, "down", GOLD_MID)

    pill(s, col2_c - 1.15, 5.40, 2.30, 0.30, "Key Question 3", size=10.5)
    txt(s, col2_c - 1.30, 5.74, 2.60, 0.20, "결제수단 + 장학금 × 정보 접근",
        size=8, bold=True, color=TEXT, align=C, anchor=TOP)
    pill(s, col3_c - 1.15, 5.40, 2.30, 0.30, "Key Question 4", size=10.5)
    txt(s, col3_c - 1.30, 5.74, 2.60, 0.20, "결제수단 + 장학금 × 판단·실행",
        size=8, bold=True, color=TEXT, align=C, anchor=TOP)

    b3 = box(s, col2_c - 1.27, 6.04, 2.54, 0.90, fill=WHITE, border=KHU_RED, dash=True)
    shape_text(b3, "흩어진 혜택과 공고를 계산 가능한\n하나의 데이터 구조로 모을 수 있을까?",
               size=9.5, bold=True, color=TEXT, line=1.35)
    b4 = box(s, col3_c - 1.27, 6.04, 2.54, 0.90, fill=WHITE, border=KHU_RED, dash=True)
    shape_text(b4, "조건 대조와 금액 계산을 자동화해\n판단까지 대신할 수 있을까?",
               size=9.5, bold=True, color=TEXT, line=1.35)

    # ---- 결론 박스
    arrow(s, 10.00, 5.06, 0.42, 0.38, "down", RED_SOFT)
    arrow(s, 7.10, 6.28, 0.85, 0.40, "right", RED_SOFT)
    concl = box(s, 8.10, 5.52, 4.62, 1.42, fill=GOLD_WASH, border=KHU_GOLD)
    shape_text(concl,
               "새는 돈(결제수단 혜택)과 못 받은 돈(장학금)을\n한 앱에서 함께 계산해 대학생의 실질\n가처분 소득을 늘리는 서비스가 필요함",
               size=12, bold=True, color=TEXT, line=1.45)
    return s


# ===================================================================== 슬라이드 2
def slide2_strategy(prs):
    """템플릿 p2 형식: 현재 상황 -> Pain Points -> 구현 결과 / 기대 효과."""
    s = new_slide(
        prs,
        label="전략 제안",
        headline="결제수단 혜택의 파편화와 장학 정보의 산재를 4개 Pain Point로 정리하고,\n"
                 "검증 게이트를 통과한 혜택만 금액 계산에 쓰는 구조로 결제 영역을 먼저 구현했습니다",
        subtitle="Pain Point 대응 구현 결과 및 기대 효과",
        page=2,
    )

    # ---- 좌: 현재 상황
    cx, cwid = M_LEFT, 2.95
    hdr = box(s, cx, 2.45, cwid, 0.42, fill=GOLD_DEEP)
    shape_text(hdr, "현재 상황", size=12, bold=True, color=WHITE)

    current = [
        ("편의점 중심 소비 구조", "식비·간식 지출이 캠퍼스 주변\n편의점과 카페에 집중되어 있음"),
        ("결제수단은 이미 다수 보유", "학생증·통신사·페이·카드·지역화폐를\n대부분 이미 갖고 있음"),
        ("장학·지원금 수요도 높음", "소득분위 지원금과 외부 재단\n장학금에 관심이 높은 편"),
    ]
    ys = [3.10, 4.35, 5.60]
    for (title, desc), y in zip(current, ys):
        box(s, cx, y, cwid, 1.02, fill=WHITE, border=GRAY_LINE)
        chip = box(s, cx + 0.16, y + 0.10, cwid - 0.32, 0.28, fill=GOLD_WASH,
                   border=GOLD_SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        shape_text(chip, title, size=10, bold=True, color=TEXT)
        txt(s, cx + 0.08, y + 0.42, cwid - 0.16, 0.54, desc, size=8.5,
            color=TEXT_SUB, align=C, anchor=MID, line=1.30)
        arrow(s, cx + cwid + 0.08, y + 0.40, 0.36, 0.22, "right", GOLD_MID)

    # ---- 중앙: Pain Points
    px, pwid = 4.15, 2.72
    box(s, px, 2.45, pwid, 4.50, fill=None, border=KHU_RED)
    ph = box(s, px, 2.45, pwid, 0.42, fill=RED_WASH)
    shape_text(ph, "Pain Points", size=12, bold=True, color=KHU_RED)

    # 결제수단 축 2개 + 장학금 축 2개 = 4개 (슬라이드 1 매트릭스 4칸과 1:1 대응)
    pains = [
        ("혜택 정보의 파편화", "페이·통신사·매장별 할인율이\n서로 다른 채널에 흩어져 있음"),
        ("조합 규칙의 불투명성", "중복 여부·한도·제외 품목이 약관에\n묻혀 결제 직전 계산이 불가능함"),
        ("장학 공고를 몰라서 놓침", "교내·재단·정책 공고가 각각 다른\n사이트에 올라와 마감 후 인지"),
        ("자격 대조 · 서류 부담", "요건 확인과 자기소개서 부담으로\n마감 직전 포기하는 경우 반복"),
    ]
    ph_h, ph_gap = 0.82, 0.24
    pys = [2.94 + i * (ph_h + ph_gap) for i in range(4)]
    for (title, desc), y in zip(pains, pys):
        box(s, px + 0.13, y, pwid - 0.26, ph_h, fill=WHITE, border=RED_MID)
        txt(s, px + 0.18, y + 0.06, pwid - 0.36, 0.24, title, size=10.5, bold=True,
            color=KHU_RED, align=C, anchor=MID)
        txt(s, px + 0.18, y + 0.32, pwid - 0.36, 0.46, desc, size=8.5,
            color=TEXT_SUB, align=C, anchor=MID, line=1.28)
    for i in range(3):
        plus_badge(s, px + pwid / 2, (pys[i] + ph_h + pys[i + 1]) / 2,
                   d=0.22, fill=KHU_RED)

    # ---- 우: 구현 결과 / 기대 효과
    gx, gwid = 8.12, 1.62
    dx, dwid = 9.82, 2.90
    ih, gap = 0.68, 0.075
    iy = [2.48 + i * (ih + gap) for i in range(6)]

    built = [
        ("5카테고리 17종 온보딩",
         "학생증·통신사·페이·카드·지역화폐를 등록하고 데모 사용자 3명으로 추천 변화를 시연"),
        ("최적 조합 계산 엔진",
         "할인 레이어와 결제 레이어를 분리해 잔액 기준 순차 적용, 퍼센트 합산 과장을 차단"),
        ("지도 기반 개인화 추천",
         "정적 55개 매장 + 반경 1.5km 자동수집, 보유 수단으로 혜택 있는 매장만 노출"),
    ]
    effects = [
        ("추천 신뢰성 확보",
         "verified × calculable 이중 게이트로 근거 확인된 35건만 금액 계산에 사용"),
        ("장학금으로 확장 가능",
         "동일 스키마와 검증 게이트를 그대로 재사용해 장학 공고까지 확장할 계획"),
        ("지출 절감 + 수입 확보",
         "새는 돈과 못 받은 돈을 한 화면에서 관리해 실질 가처분 소득을 늘림"),
    ]

    for i, (title, desc) in enumerate(built + effects):
        y = iy[i]
        is_built = i < 3
        gb = box(s, gx, y, gwid, ih,
                 fill=KHU_RED if is_built else GOLD_LIGHT,
                 border=None if is_built else GOLD_SOFT)
        shape_text(gb, wrap_ko(title, gwid, 9), size=9, bold=True,
                   color=WHITE if is_built else TEXT, line=1.25)
        box(s, dx, y, dwid, ih, fill=WHITE, border=GRAY_LINE)
        txt(s, dx + 0.07, y, dwid - 0.14, ih,
            wrap_ko(desc, dwid - 0.14, 8.3), size=8.3, color=TEXT_SUB,
            align=C, anchor=MID, line=1.32)

    groups = ((slice(0, 3), "구현\n결과", KHU_RED), (slice(3, 6), "기대\n효과", KHU_GOLD))
    for grp, label, tone in groups:
        top = iy[grp.start]
        bottom = iy[grp.stop - 1] + ih
        mid = (top + bottom) / 2
        lb = box(s, 7.22, mid - 0.31, 0.74, 0.62, fill=tone,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
        shape_text(lb, label, size=10.5, bold=True, color=WHITE, line=1.20)
        arrow(s, 6.94, mid - 0.11, 0.24, 0.22, "right", RED_MID)
        vline(s, 8.00, top + 0.30, bottom - top - 0.60, color=GRAY_LINE)
        for i in range(grp.start, grp.stop):
            hline(s, 8.00, iy[i] + ih / 2, 0.12, color=GRAY_LINE)
        hline(s, 7.96, mid, 0.05, color=GRAY_LINE)
    return s


# ===================================================================== 슬라이드 3
def slide3_data(prs):
    """템플릿 p3 형식: 좌우 2컬럼 + 각 컬럼 네이티브 표(구분/수집 항목/활용)."""
    s = new_slide(
        prs,
        label="데이터 설명",
        headline="결제수단 5개 축의 혜택 177건을 직접 수집·검증해 계산 가능한 스키마로 구조화하고,\n"
                 "매장·지역화폐 가맹점 원본과 브랜드 키로 연결했습니다",
        subtitle=None,
        page=3,
    )

    lx, rx, w = M_LEFT, 6.97, 5.75
    hy = 2.42
    col_header(s, lx, w, hy, "결제수단별 혜택 데이터",
               "앱 런타임 기준 · 2026.08 갱신", cap_x=2.30)
    col_header(s, rx, w, hy, "매장 · 가맹점 · 검증 데이터",
               "회기동·이문동 일대", cap_x=2.55)

    # 구분 열은 좁으므로 라벨을 직접 2줄로 끊고, 수집 항목도 한 줄에 들어가는
    # 단위로 미리 쪼갠다. (표 행이 자동으로 늘어나 하단을 침범하는 것을 막기 위함)
    cw = [1.02, 2.05, 2.68]
    rh = [0.32] + [0.9075] * 4
    ty = 2.95

    def build(x, rows):
        t = add_table(s, x, ty, cw, rh)
        cell(t, 0, 0, "구분", size=9.5, bold=True, color=WHITE, fill=TBL_COL_HDR)
        cell(t, 0, 1, "수집 항목", size=9.5, bold=True, color=WHITE, fill=TBL_COL_HDR)
        cell(t, 0, 2, "데이터 활용", size=9.5, bold=True, color=WHITE, fill=TBL_COL_HDR)
        for i, (kind, cnt, tone, items, usage) in enumerate(rows, start=1):
            cell(t, i, 0,
                 [(v, 10, True, TEXT) for v in kind] + [(cnt, 8.5, False, TEXT_SUB)],
                 fill=tone, mh=0.02, line=1.30)
            cell(t, i, 1, [(v, 9, True, TEXT) for v in items],
                 fill=WHITE, line=1.42)
            cell(t, i, 2, wrap_ko(usage, cw[2], 8.3, margin=0.07),
                 size=8.3, color=TEXT_SUB, fill=WHITE, line=1.40)
        return t

    build(lx, [
        (["페이"], "28건 + 82건", RED_LIGHT,
         ["카카오 21 · 토스 4 · 네이버 3", "카카오페이 굿딜 82건 별도"],
         "바코드·QR 현장결제의 브랜드별 할인율. 앱 굿딜 화면을 직접 캡처해 "
         "외부 수집이 불가능한 수치까지 확보"),
        (["통신사"], "17건", GOLD_LIGHT,
         ["SKT 7 · KT 5 · LG U+ 5"],
         "멤버십 등급(VIP·Gold·Silver)별 할인·적립 조건. 등급을 프로필에 저장해 "
         "사용자별로 적용 혜택을 분기"),
        (["카드"], "8건 / 5종", RED_SOFT,
         ["KB 나라사랑 · 펭수 노리", "하나 나라사랑 · 네이버페이", "IBK EASY Cashback"],
         "업종별 캐시백·적립률. 전월실적과 월 한도를 컬럼으로 분리해 "
         "조건부 계산에 사용"),
        (["학생증", "지역화폐"], "11건 + 19건", GOLD_SOFT,
         ["경희대 제휴 · 톡학생증", "동대문구사랑 · 온누리", "단과대 제휴 19건 별도"],
         "학생증 제휴는 매장명 부분일치로 매칭. 지역화폐는 가맹점 원본에 있는 "
         "매장에서만 적용"),
    ])

    build(rx, [
        (["매장 데이터"], "55개 + 자동수집", RED_WASH,
         ["편의점 15 · 음식점 15", "카페 14 · 문화 5", "생활 4 · 캠퍼스 2"],
         "실제 위경도로 지도 마커 배치. 카카오맵 반경 1.5km 자동수집 매장은 "
         "상호명에서 브랜드를 역추출해 매칭"),
        (["지역화폐", "가맹점"], "1,180곳", GOLD_WASH,
         ["서울Pay+ 1,140곳", "디지털 온누리 40곳"],
         "상호명·주소 이중 매칭으로 가맹 여부를 판정. 매칭 실패 시 자동으로 "
         "할인 미적용(fail-closed)"),
        (["팀 수집 원본"], "166건 / 24컬럼", RED_LIGHT,
         ["Y 86 · PARTIAL 74 · N 6", "앱캡처 82 · 공식표 56", "블로그 11 · 뉴스 9"],
         "모든 행에 출처명과 수집 일자를 필수 기록. 3년 전 프로모션이 현재 혜택으로 "
         "섞이는 오류를 사전 차단"),
        (["검증 게이트"], "35 / 64건 통과", GOLD_LIGHT,
         ["verified 37건 · 미검증 27건", "조건 확인 필요 17건 제외"],
         "근거가 확인되고 계산 전제가 갖춰진 혜택만 금액·순위에 반영. 나머지는 "
         "'참고' 목록으로 분리"),
    ])
    return s


# ===================================================================== 슬라이드 4
def slide4_demo(prs):
    """구현 화면 시연 - 캡처 삽입용으로 본문을 비워 둔 슬라이드."""
    s = new_slide(
        prs,
        label="구현 화면",
        headline="온보딩부터 매장 상세까지, TMI 화면으로 결제 직전 의사결정 흐름을 시연합니다",
        subtitle="TMI 구현 화면 시연",
        page=4,
    )
    slots = [
        ("① 온보딩 · 수단 선택", "마이데이터 연결 시뮬레이션 · 데모 사용자 3명"),
        ("② 지도 · 개인화 추천", "보유 수단 기준 매장 필터 · 카테고리별 마커"),
        ("③ 매장 상세 · 조합 내역", "최적 조합과 절약액 · 참고 혜택 분리 표시"),
    ]
    x, w, gap = M_LEFT, 3.87, 0.245
    for i, (title, desc) in enumerate(slots):
        bx = x + i * (w + gap)
        box(s, bx, 2.52, w, 3.66, fill=WHITE, border=GOLD_MID, dash=True)
        txt(s, bx, 4.22, w, 0.26, "화면 캡처를 이 영역에 붙여 주세요",
            size=9, color=GOLD_SOFT, align=C, anchor=MID)
        txt(s, bx, 6.30, w, 0.28, title, size=11.5, bold=True, color=KHU_RED,
            align=C, anchor=TOP)
        txt(s, bx, 6.60, w, 0.24, desc, size=9, color=TEXT_SUB, align=C, anchor=TOP)
    return s


# ===================================================================== 슬라이드 5
def slide5_roadmap(prs):
    """템플릿 p6 형식: 상단 밴드 + 셰브론 4단 + 4컬럼 x 3블록."""
    s = new_slide(
        prs,
        label="로드맵 정리",
        headline="지도·데이터 기반 조회와 결제수단 조합 추천 엔진까지 구현을 완료했으며,\n"
                 "이후 AI 자동 수집·검증과 장학금 어시스턴트로 단계적으로 확장할 계획입니다",
        subtitle="구현 완료 및 추가 구현 로드맵",
        page=5,
    )

    cw, gap = 2.92, 0.14
    cx = [M_LEFT + i * (cw + gap) for i in range(4)]

    # 상단 밴드 : 좌 2열 = 구현 완료(골드) / 우 2열 = 추가 구현(레드)
    b1 = box(s, cx[0], 2.42, cx[1] + cw - cx[0], 0.30, fill=GOLD_DEEP)
    shape_text(b1, "구현 완료", size=10, bold=True, color=WHITE)
    b2 = box(s, cx[2], 2.42, CONTENT_RIGHT - cx[2], 0.30, fill=RED_DEEP)
    shape_text(b2, "추가 구현 예정", size=10, bold=True, color=WHITE)

    # 셰브론
    heads = [("지도 · 데이터 기반", GOLD), ("조합 추천 엔진", GOLD),
             ("AI 자동 수집 · 검증", KHU_RED), ("장학금 & 세이빙", KHU_RED)]
    for i, (h, tone) in enumerate(heads):
        if i == 0:
            sh = box(s, cx[0], 2.78, cw + 0.14, 0.36, fill=tone,
                     shape=MSO_SHAPE.PENTAGON)
        else:
            wdt = (cw + 0.14) if i < 3 else (CONTENT_RIGHT - (cx[3] - 0.07))
            sh = box(s, cx[i] - 0.07, 2.78, wdt, 0.36, fill=tone,
                     shape=MSO_SHAPE.CHEVRON)
        shape_text(sh, h, size=10, bold=True, color=WHITE)

    # 추가 구현 영역 테두리
    box(s, cx[2] - 0.08, 3.16, CONTENT_RIGHT - cx[2] + 0.08, 3.80,
        fill=None, border=KHU_RED)

    columns = [
        [  # 1. 지도 · 데이터 기반 (완료)
            ("지도 기반 개인화 조회", "카카오맵 SDK · 정적 55개 + 자동수집",
             ["보유 수단으로 혜택 있는 매장만 노출, 카테고리별 마커",
              "브랜드 자동 감지 · 화면 내 매장 기준 지도 자동 맞춤"]),
            ("5카테고리 17종 온보딩", "학생증·통신사·페이·카드·지역화폐",
             ["마이데이터 연결 시뮬레이션 + 데모 사용자 3명 전환",
              "멤버십 등급·네이버플러스 가입 여부를 프로필에 반영"]),
            ("외부 소스 분리 데이터셋", "JSON 4종 · 혜택 177건",
             ["혜택 64 / 굿딜 82 / 제휴 19 / 편의시설 12건 파일 분리",
              "setBenefits()로 런타임 교체, 서버 API 전환 대비"]),
        ],
        [  # 2. 조합 추천 엔진 (완료)
            ("최적 조합 계산", "할인 레이어 + 결제 레이어 분리",
             ["학생증·통신사 할인 후 잔액 기준으로 페이·카드 계산",
              "단독 최고 vs 조합, 현금전용 제휴까지 이득 비교"]),
            ("실제 규칙 반영", "9개 제약 필드 동시 적용",
             ["최소결제액·1회한도·월한도·전월실적·제외브랜드",
              "유효기간·stackable 규칙으로 중복 불가는 단독 처리"]),
            ("검증 이중 게이트", "verified × calculable",
             ["근거 확인된 35건만 금액·순위 계산에 사용",
              "미확정은 '참고' 목록 분리, 지역화폐는 fail-closed"]),
        ],
        [  # 3. AI 자동 수집 · 검증 (예정)
            ("혜택 문구 자동 구조화", "LLM으로 비정형 약관 → 스키마 변환",
             ["할인율·한도·제외품목·중복규칙 자동 추출 후 정규화",
              "Rule 기반 검증을 통과한 값만 verified 로 승격"]),
            ("변경 감지 & 정기 갱신", "주 1회 배치 · AWS 서버리스 구성",
             ["EventBridge → Lambda → DynamoDB 갱신 파이프라인",
              "현재 수동인 validUntil 갱신을 만료 자동 비활성으로"]),
            ("신뢰도 자동 채점", "출처·보도 시점 교차 검증 자동화",
             ["다수 매체 교차 일치 시 미검증 27건의 등급 자동 상향",
              "조건 확인이 필요한 17건의 점포·메뉴 검증 자동화"]),
        ],
        [  # 4. 장학금 & 세이빙 (예정)
            ("RAG 장학금 매칭", "프로필 x 공고 Vector 검색 · Rule 선필터",
             ["소득분위·학점을 Rule로 선필터한 뒤 RAG 문맥에 주입",
              "교내 공지 · 민간 재단 · 청년 정책 공고를 임베딩"]),
            ("지원서 초안 자동화", "과거 지원서 재활용 · 인터뷰형 생성",
             ["제출본 아카이빙 → 다음 지원 시 레퍼런스로 재사용",
              "신규 지원자는 3~4개 핵심 질문 인터뷰 후 초안 생성"]),
            ("세이빙 대시보드", "절감액 누적 시각화 · 한도 추적",
             ["'소비 완료' 체크 시 월간 누적 세이브 금액에 반영",
              "엔진의 월 한도 잔여량을 추적해 다음 추천에 반영"]),
        ],
    ]

    block_y = [3.28, 4.58, 5.88]
    for ci, blocks in enumerate(columns):
        x = cx[ci]
        done = ci < 2
        badge_fill = GOLD_DEEP if done else RED_DEEP
        title_color = TEXT if done else KHU_RED
        for bi, (title, sub, bullets) in enumerate(blocks):
            y = block_y[bi]
            num_badge(s, x, y + 0.02, bi + 1, d=0.20, fill=badge_fill)
            txt(s, x + 0.27, y - 0.01, cw - 0.27, 0.24, title, size=10.5,
                bold=True, color=title_color, align=L, anchor=MID)
            txt(s, x + 0.27, y + 0.23, cw - 0.27, 0.19, sub, size=8.3,
                color=TEXT_SUB, align=L, anchor=MID)
            box(s, x, y + 0.44, cw, 0.58,
                fill=GOLD_WASH if done else RED_WASH,
                border=GOLD_SOFT if done else RED_SOFT)
            # 불릿도 어절 단위로 미리 끊어 넣어 글자 단위 분리를 막는다
            lines = []
            for b in bullets:
                lines += wrap_ko("- " + b, cw - 0.14, 7.5)
            txt(s, x + 0.07, y + 0.46, cw - 0.14, 0.54,
                [(v, 7.5, False, TEXT_SUB) for v in lines],
                align=L, anchor=MID, line=1.22)
    return s


# ===================================================================== 저장
STAMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".build_stamp.json")


def _read_stamp():
    import json
    try:
        with open(STAMP, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_stamp(path):
    import json
    data = _read_stamp()
    st = os.stat(path)
    data[os.path.basename(path)] = {"mtime": st.st_mtime, "size": st.st_size}
    with open(STAMP, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _externally_modified(path):
    """대상 파일이 마지막 빌드 이후 외부(파워포인트/한쇼)에서 수정됐는지 판정."""
    if not os.path.exists(path):
        return False
    rec = _read_stamp().get(os.path.basename(path))
    if rec is None:
        return True                      # 빌드 기록이 없으면 남의 파일로 간주
    st = os.stat(path)
    return abs(st.st_mtime - rec["mtime"]) > 1 or st.st_size != rec["size"]


def _versioned(path, suffix):
    import time
    return "%s_%s_%s.pptx" % (path[:-5], suffix, time.strftime("%H%M%S"))


def save_deck(prs, path, force=False):
    """안전 저장.

    1) 대상 파일이 마지막 빌드 이후 외부에서 수정됐으면 덮어쓰지 않고
       버전 파일로 저장한다. (수작업 편집분 유실 방지 — 과거 사고 재발 방지)
    2) 다른 프로세스가 파일을 잠그고 있으면 역시 버전 파일로 저장한다.
    3) force=True 면 1)을 무시하고 덮어쓴다.
    """
    tmp = path + ".tmp"
    prs.save(tmp)

    if not force and _externally_modified(path):
        alt = _versioned(path, "복원")
        os.replace(tmp, alt)
        print("[보호] 대상 파일이 마지막 빌드 이후 외부에서 수정됐습니다.")
        print("       수작업 편집분을 지우지 않기 위해 덮어쓰지 않았습니다.")
        print("       기존:", path)
        print("       생성:", alt)
        return alt

    try:
        os.replace(tmp, path)
        _write_stamp(path)
        print("생성 완료:", path)
        return path
    except PermissionError:
        alt = _versioned(path, "복원")
        os.replace(tmp, alt)
        _write_stamp(alt)
        print("[보호] 대상 파일이 다른 프로세스에 잠겨 있습니다.")
        print("       생성:", alt)
        print("       -> 기존 파일을 닫은 뒤 이 파일로 교체하세요.")
        return alt


# ===================================================================== main
def main():
    prs = Presentation()
    prs.slide_width = In(13.333)
    prs.slide_height = In(7.5)

    slide_cover(prs)
    slide1_idea(prs)
    slide2_strategy(prs)
    slide3_data(prs)
    slide4_demo(prs)
    slide5_roadmap(prs)
    slide_thanks(prs)

    save_deck(prs, OUT)
    print("슬라이드 수:", len(prs.slides))


if __name__ == "__main__":
    main()

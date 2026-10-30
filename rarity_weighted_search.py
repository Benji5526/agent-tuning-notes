"""상품명 검색에서 흔한 단어의 영향을 줄이는 점수 계산 예제.

문제: 고객이 "요일팬티 세트"라고 쓰면 '세트'가 들어간 모든 상품이 같은 점수를 받아,
검색이 "후보가 여러 개"라고 판정한다. 그러면 에이전트가 이미 말한 상품을 다시 묻는다.

해결: 질의의 각 단어에 "그 단어를 온전히 포함한 상품 수의 역수"를 가중치로 준다.
여러 상품에 흔히 들어 있는 단어일수록 가중치가 작고, 한두 상품에만 있는 단어가 점수를 좌우한다.
또, 질의 단어가 상품명 안에 그대로 있으면 1.0, 상품명의 짧은 단어가 질의 단어 안에
들어 있는 정도의 약한 일치는 0.5 만 준다.
"""
import re


def tokens(text):
    return [t for t in re.split(r"[\s·()]+", text) if t]


def match_strength(token, name):
    if token in name.replace(" ", ""):
        return 1.0
    return 0.5 if any(part in token for part in tokens(name)) else 0.0


def rank(query, names):
    qt = tokens(query)
    if not qt:
        return []
    weight = {t: 1.0 / max(1, sum(match_strength(t, n) == 1.0 for n in names)) for t in qt}
    total = sum(weight.values())
    scored = [(n, round(sum(weight[t] * match_strength(t, n) for t in qt) / total, 2))
              for n in names]
    return sorted([s for s in scored if s[1] > 0], key=lambda s: -s[1])


def resolve(query, names):
    """최고점 후보가 하나뿐이면 그 상품을, 동점이면 None(되물어야 함)을 돌려준다."""
    ranked = rank(query, names)
    if not ranked:
        return None
    top = [n for n, s in ranked if s == ranked[0][1]]
    return top[0] if len(top) == 1 else None


if __name__ == "__main__":
    # 실제 상품 데이터가 아니라, 문제를 보여 주기 위해 만든 예시 상품명이다.
    catalog = ["요일속옷 7종 세트", "코튼 속옷 5매 세트", "브라·속옷 세트", "가죽 지갑"]
    for q in ["요일속옷 세트", "속옷 세트", "세트", "가죽 지갑"]:
        print(f"{q!r:14} -> {resolve(q, catalog)}   {rank(q, catalog)[:3]}")

"""가상 쇼핑몰 '토이몰' 상담 챗봇. 터미널에서 바로 대화해 볼 수 있다.

    python chatbot.py                 # 대화 시작 (종료: 빈 줄 또는 Ctrl+C)
    python chatbot.py "텀블러 재고 있어요?"   # 한 번만 묻고 종료

모델이 스스로 도구를 골라 부르고(함수 호출), 조회 결과에 근거해서만 답하게 만든 최소 구현이다.
상품·주문 데이터는 이 파일 안의 가상 데이터이고, 실제 쇼핑몰과 관계없다.
"""
import json
import os
import sys

from openai import BadRequestError, OpenAI

from rarity_weighted_search import rank

MODEL = os.environ.get("CHATBOT_MODEL", "gpt-5.6-terra")
MAX_TOOL_ROUNDS = 5

# ───────────────────────── 가상 데이터 ─────────────────────────
PRODUCTS = {
    "P1": {"name": "블루 머그컵", "price": 12000, "stock": 30, "material": "도자기",
           "set_only": False, "made_to_order": False},
    "P2": {"name": "화이트 머그컵 세트(2P)", "price": 22000, "stock": 0, "material": "도자기",
           "set_only": True, "made_to_order": False, "restock": "2026-11-20 입고 예정(확정)"},
    "P3": {"name": "캔버스 에코백", "price": 18000, "stock": 15, "material": "면 100%",
           "set_only": False, "made_to_order": False},
    "P4": {"name": "스테인리스 텀블러", "price": 25000, "stock": 8, "material": "스테인리스",
           "set_only": False, "made_to_order": False},
    "P5": {"name": "핸드메이드 가죽 키링", "price": 15000, "stock": 0, "material": "소가죽",
           "set_only": False, "made_to_order": True, "lead_days": 7},
}
ORDERS = {
    "O-1001": {"status": "배송중", "courier": "가상택배", "tracking_no": "000-111-222",
               "items": ["블루 머그컵 x2"], "invoice_printed": True},
    "O-1002": {"status": "상품준비중", "items": ["캔버스 에코백 x1"], "invoice_printed": False},
}
BASE_FEE, FREE_OVER, REMOTE_EXTRA = 3000, 50000, 3000
REMOTE_REGIONS = ("제주", "울릉", "도서산간")


# ───────────────────────── 도구 ─────────────────────────
def search_product(query):
    """상품명으로 찾는다. 후보가 하나로 정해지면 resolved_product_id 를 준다."""
    by_name = {p["name"]: pid for pid, p in PRODUCTS.items()}
    ranked = rank(query, list(by_name))
    cands = [{"product_id": by_name[n], "name": n, "score": s} for n, s in ranked[:5]]
    top = [c for c in cands if cands and c["score"] == cands[0]["score"]]
    return {"candidates": cands,
            "resolved_product_id": top[0]["product_id"] if len(top) == 1 else None,
            "ambiguous": len(top) > 1}


def get_product_detail(product_id):
    """재고, 소재, 세트 단독 구매 가능 여부, 주문 제작 여부, 재입고 정보를 조회한다."""
    p = PRODUCTS.get(product_id)
    if not p:
        return {"error": "상품을 찾을 수 없습니다"}
    out = dict(p, product_id=product_id)
    out["품절"] = p["stock"] == 0
    if p["made_to_order"]:
        out["note"] = "주문 제작 상품은 교환·반품이 불가합니다."
    return out


def get_shipping_policy(order_amount=None, region=None):
    """배송비를 조회한다. 금액을 주면 무료배송 여부를, 지역을 주면 추가 배송비를 함께 준다."""
    out = {"base_fee": BASE_FEE, "free_over": FREE_OVER}
    if order_amount is not None:
        out["shipping_fee"] = 0 if order_amount >= FREE_OVER else BASE_FEE
        if order_amount < FREE_OVER:
            out["shortfall"] = FREE_OVER - order_amount
    if region:
        remote = any(r in region for r in REMOTE_REGIONS)
        out["region"] = region
        out["extra_fee"] = REMOTE_EXTRA if remote else 0
    return out


def get_order_status(order_id):
    """주문번호로 진행 상태를 조회한다. 송장 출력 후에는 주문 변경이 불가하다."""
    o = ORDERS.get(order_id)
    return dict(o, order_id=order_id) if o else {"error": "주문을 찾을 수 없습니다"}


TOOLS = {f.__name__: f for f in (search_product, get_product_detail,
                                 get_shipping_policy, get_order_status)}


def _schema(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


TOOL_SCHEMAS = [
    _schema("search_product", "상품명으로 상품을 찾는다. 상품 ID를 모를 때 가장 먼저 부른다.",
            {"query": {"type": "string"}}, ["query"]),
    _schema("get_product_detail", "상품 ID로 재고·소재·세트 단독 구매 가능 여부·주문 제작 여부를 조회한다.",
            {"product_id": {"type": "string"}}, ["product_id"]),
    _schema("get_shipping_policy", "배송비와 무료배송 기준을 조회한다. 금액이나 지역을 줄 수 있다.",
            {"order_amount": {"type": "integer"}, "region": {"type": "string"}}, []),
    _schema("get_order_status", "주문번호(O-0000 형태)로 주문 진행 상태를 조회한다.",
            {"order_id": {"type": "string"}}, ["order_id"]),
]

SYSTEM_PROMPT = f"""\
너는 온라인 쇼핑몰 '토이몰'의 상담 챗봇이다. [조회 결과]와 아래 [고정 정책]에만 근거해 답하고,
둘에 없는 내용은 지어내지 않는다.

[고정 정책]
- 기본 배송비는 {BASE_FEE:,}원이다. 오전 11시 이전 주문은 당일 출고, 이후 주문은 다음 영업일 출고다.
- 재고, 무료배송 기준, 세트 단독 구매 가능 여부, 주문 상태는 반드시 도구로 조회한 값만 쓴다.

[행동 기준]
1. 고객이 상품 이름을 말했으면 먼저 search_product 를 부른다. resolved_product_id 가 있으면
   그 ID로 다음 도구를 부르고, 후보가 여럿이면 어느 상품인지 되묻는다.
2. 조회에 필요한 값(상품명, 주문번호, 지역)이 고객 말에 없으면 도구를 부르지 않고 되묻는다.
   먼저 알려 줄 수 있는 고정 정책은 안내하고, 답변은 질문으로 끝낸다.
   고객이 이미 말한 값(상품명, '제주도' 같은 지역명, 주문번호)이 있으면 되묻지 않고 조회한다.
3. 조회 결과에 쓰인 상태 표현(품절, 불가 등)은 바꿔 쓰지 말고 그대로 쓴다.
   금액은 '3천 원'이 아니라 '3,000원'처럼 숫자로 적는다. 답을 뒷받침하는 핵심 수치는 한 번 밝힌다.
4. 불가한 사항은 사유를 먼저 밝히고 대안을 제시한다. 존댓말로 1~3문장으로 답한다.
"""


# ───────────────────────── 대화 루프 ─────────────────────────
def _complete(client, messages, use_effort):
    kwargs = {"model": MODEL, "messages": messages, "tools": TOOL_SCHEMAS, "temperature": 0}
    if use_effort:
        # 일부 모델은 추론 모드와 함수 호출을 함께 못 쓴다. 꺼 두고, 지원하지 않으면 뺀다.
        kwargs["reasoning_effort"] = "none"
    return client.chat.completions.create(**kwargs)


def reply(client, messages):
    """messages 에 사용자 발화가 들어 있는 상태로 부른다. 답변을 돌려주고 messages 에 이어 붙인다."""
    use_effort = True
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = _complete(client, messages, use_effort)
        except BadRequestError:
            if not use_effort:
                raise
            use_effort = False
            continue
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            return msg.content
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = TOOLS[call.function.name](**args)
            print(f"  [도구] {call.function.name}({args})", file=sys.stderr)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    return "정확한 확인을 위해 상담원에게 연결해 드리겠습니다."


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 환경변수를 먼저 설정해 주세요. (README 참고)")
    client = OpenAI()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if len(sys.argv) > 1:
        messages.append({"role": "user", "content": " ".join(sys.argv[1:])})
        print(reply(client, messages))
        return

    print("토이몰 상담 챗봇입니다. 무엇을 도와드릴까요? (종료: 빈 줄)")
    while True:
        try:
            q = input("\n고객> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        messages.append({"role": "user", "content": q})
        print("챗봇>", reply(client, messages))


if __name__ == "__main__":
    main()

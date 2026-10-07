"""선택적으로 사용하는 근거 제한 LLM 호출."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from . import ROOT
from .data import Document


def client_and_model() -> tuple[OpenAI, str]:
    load_dotenv(ROOT / ".env", override=False)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다. .env.example을 참고하세요.")
    return OpenAI(api_key=api_key), os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


def grounded_answer(question: str, documents: list[Document]) -> str:
    """회수된 근거만 모델에 제공한다. 빠진 근거를 원본에서 몰래 보충하지 않는다."""
    client, model = client_and_model()
    context = "\n\n".join(f"[{doc.id}] {doc.text}" for doc in documents)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "제공된 근거만 사용해 한국어로 답하라. 질문에 필요한 연결·예외가 근거에 없으면 "
                    "추정하지 말고 부족한 부분을 밝히라. 근거 문장마다 [ID]를 표시하라. "
                    "서로 경로로 연결된 대상을 직접 협업했다고 바꾸지 말라. "
                    "프로그램을 검토한다는 문장을 소속 프로젝트 각각을 검토한다는 문장으로 확대하지 말라."
                ),
            },
            {"role": "user", "content": f"질문: {question}\n\n검색된 근거:\n{context}"},
        ],
    )
    return response.choices[0].message.content or "(빈 응답)"


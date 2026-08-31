import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .knowledge_service import normalize_text
from .models import Issue, KnowledgeChunk, KnowledgeDocument, RagAnalysisJob
from .phase56_schemas import RagResult

BANNED_CONCLUSIONS = (
    "立即停工",
    "必须停工",
    "重大事故",
    "事故等级",
    "一般事故",
    "较大事故",
    "特别重大事故",
)


def _ngrams(value: str, size: int = 2) -> set[str]:
    chars = normalize_text(value)
    return {chars[i : i + size] for i in range(max(0, len(chars) - size + 1))}


def retrieve(db: Session, issue: Issue, limit: int = 5) -> list[dict[str, Any]]:
    query = normalize_text(issue.description_snapshot)
    query_grams = _ngrams(query)
    rows = (
        db.query(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .filter(
            KnowledgeChunk.project_id == issue.project_id,
            KnowledgeDocument.status == "ACTIVE",
        )
        .all()
    )
    scored: list[tuple[float, KnowledgeChunk, KnowledgeDocument]] = []
    terms = [
        term for term in re.split(r"[，。；、\s]+", issue.description_snapshot) if len(term) >= 2
    ]
    for chunk, document in rows:
        content = chunk.normalized_content
        exact = 2.0 if query and query in content else 0.0
        phrase = sum(1.0 for term in terms if normalize_text(term) in content)
        grams = _ngrams(content)
        overlap = len(query_grams & grams) / max(1, len(query_grams))
        length_factor = min(1.0, 800 / max(200, len(content)))
        score = (exact + phrase + overlap * 2.5) * length_factor
        if score >= 0.55:
            scored.append((score, chunk, document))
    scored.sort(key=lambda row: (-row[0], row[1].id))
    return [
        {
            "chunk_id": chunk.id,
            "document_id": document.id,
            "document_title": document.title,
            "locator": chunk.locator,
            "content": chunk.content,
            "score": round(score, 4),
            "is_demo": document.is_demo,
        }
        for score, chunk, document in scored[:limit]
    ]


def _mock_result(issue: Issue, hits: list[dict[str, Any]]) -> dict[str, Any]:
    hit = hits[0]
    excerpt = hit["content"][: min(180, len(hit["content"]))]
    warnings = ["建议仅基于项目知识库命中文段，需人工确认后执行"]
    if hit["is_demo"]:
        warnings.append("引用包含非正式演示材料，仅供功能演示，不是正式规范")
    return {
        "suspected_impact": f"该问题可能影响现场作业安全：{issue.description_snapshot}",
        "recommendations": ["对照引用内容核查现场条件，落实防护并留存整改证据"],
        "confidence": min(0.9, 0.55 + float(hit["score"]) / 10),
        "warnings": warnings,
        "citations": [
            {
                key: hit[key]
                for key in ("chunk_id", "document_id", "document_title", "locator", "is_demo")
            }
            | {"excerpt": excerpt}
        ],
    }


def _provider_result(issue: Issue, hits: list[dict[str, Any]]) -> dict[str, Any]:
    base_url = settings.rag_base_url.rstrip("/")
    if not base_url or not settings.rag_api_key:
        raise ValueError("RAG Provider 未配置")
    prompt = {
        "issue": issue.description_snapshot,
        "rules": [
            "只能根据 supplied_chunks，不能认定事故等级或自动要求停工",
            "citations.chunk_id 必须来自 supplied_chunks，excerpt 必须是对应 content 原文子串",
            "输出 suspected_impact,recommendations,confidence,warnings,citations 的 JSON",
        ],
        "supplied_chunks": hits,
    }
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.rag_api_key}"},
        json={
            "model": settings.rag_model,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            "temperature": 0,
        },
        timeout=settings.rag_timeout_seconds,
    )
    response.raise_for_status()
    return json.loads(response.json()["choices"][0]["message"]["content"])


def validate_result(raw: dict[str, Any], hits: list[dict[str, Any]]) -> RagResult:
    result = RagResult.model_validate(raw)
    hit_by_id = {hit["chunk_id"]: hit for hit in hits}
    all_text = " ".join([result.suspected_impact, *result.recommendations])
    if any(term in all_text for term in BANNED_CONCLUSIONS):
        raise ValueError("建议包含停工或事故等级结论，已拒绝")
    if not result.citations:
        raise ValueError("建议缺少引用")
    for citation in result.citations:
        hit = hit_by_id.get(citation.chunk_id)
        if not hit or citation.document_id != hit["document_id"]:
            raise ValueError("引用超出本次检索结果")
        if not citation.excerpt or citation.excerpt not in hit["content"]:
            raise ValueError("引用摘录不是知识库原文子串")
        citation.document_title = hit["document_title"]
        citation.locator = hit["locator"]
        citation.is_demo = hit["is_demo"]
    return result


def run_analysis(
    db: Session, issue: Issue, actor_id: int, retry_of: str | None = None
) -> RagAnalysisJob:
    job = RagAnalysisJob(
        id=str(uuid4()),
        issue_id=issue.id,
        project_id=issue.project_id,
        requested_by=actor_id,
        status="RUNNING",
        provider=settings.rag_provider,
        model=settings.rag_model,
        query_snapshot=issue.description_snapshot,
        retrieved_snapshot="[]",
        retry_of_job_id=retry_of,
    )
    db.add(job)
    db.flush()
    hits = retrieve(db, issue)
    job.retrieved_snapshot = json.dumps(hits, ensure_ascii=False)
    job.completed_at = datetime.now(UTC)
    if not hits:
        job.status = "NO_EVIDENCE"
        job.error_message = "依据不足：项目知识库没有合格命中文段，未调用模型"
        issue.status = "INSUFFICIENT_EVIDENCE"
        db.commit()
        return job
    try:
        raw = (
            _mock_result(issue, hits)
            if settings.rag_provider == "mock"
            else _provider_result(issue, hits)
        )
        job.raw_result = json.dumps(raw, ensure_ascii=False)
        result = validate_result(raw, hits)
        job.validated_result = result.model_dump_json()
        job.status = "SUCCEEDED"
        issue.status = "AWAITING_CONFIRMATION"
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = str(exc)[:500]
        issue.status = "ANALYSIS_FAILED"
    db.commit()
    return job


def get_job_result(job: RagAnalysisJob) -> RagResult | None:
    return RagResult.model_validate_json(job.validated_result) if job.validated_result else None


def ensure_successful_job(db: Session, issue: Issue, job_id: str) -> RagAnalysisJob:
    job = db.get(RagAnalysisJob, job_id)
    if not job or job.issue_id != issue.id or job.project_id != issue.project_id:
        raise HTTPException(status_code=422, detail="RAG 分析不属于当前问题")
    if job.status != "SUCCEEDED" or not job.validated_result:
        raise HTTPException(status_code=409, detail="只能确认已成功且引用有效的 RAG 建议")
    return job

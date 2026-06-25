# -*- coding: utf-8 -*-
"""Prompt auto-optimizer — inspired by karpathy/autoresearch.

Runs an iterative loop:
  1. Evaluate current prompt against golden test cases
  2. Ask LLM to propose improvements based on failure patterns
  3. Re-evaluate with modified prompt
  4. Keep if score improves, revert if not
  5. Repeat for N iterations

Background execution via asyncio. Status/results tracked in memory.
"""
from __future__ import annotations

import asyncio
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from needradar.llm.provider import llm
from needradar.schemas.schemas import ExtractedRequirement

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config"
PROMPTS_PATH = CONFIG_DIR / "prompts.yaml"
TEST_CASES_PATH = CONFIG_DIR / "prompt_test_cases.yaml"
BACKUP_PATH = CONFIG_DIR / "prompts.yaml.bak"

# ── Data classes ──────────────────────────────────────────────────


@dataclass
class TestCaseResult:
    test_id: str
    passed: bool
    score: float  # 0.0 ~ 1.0
    details: dict = field(default_factory=dict)
    extracted: dict | None = None


@dataclass
class IterationResult:
    iteration: int
    prompt_version: str  # "baseline" | "improved_v{N}"
    score: float  # average across all test cases
    passed: int
    total: int
    results: list[TestCaseResult] = field(default_factory=list)
    prompt_diff: str = ""
    improved: bool = False


@dataclass
class OptimizationRun:
    status: str = "idle"  # idle | running | completed | failed
    current_iteration: int = 0
    max_iterations: int = 10
    patience: int = 5  # early stop after N consecutive rounds without improvement
    num_candidates: int = 3  # parallel candidates per round
    baseline_score: float = 0.0
    best_score: float = 0.0
    best_prompt: str = ""
    iterations: list[IterationResult] = field(default_factory=list)
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    consecutive_no_improve: int = 0


# ── Evaluation ────────────────────────────────────────────────────


def _load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", [])


def _load_prompts() -> dict:
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_requirement_prompt(new_prompt: str) -> None:
    """Replace only the requirement_extraction value in prompts.yaml, preserving YAML | format."""
    import re
    text = PROMPTS_PATH.read_text(encoding="utf-8")
    # Match: requirement_extraction: |  followed by indented block until next top-level key
    pattern = r'(requirement_extraction:\s*\|?\s*\n)((?:  .*\n|\n)*)(?=\n\S|\Z)'
    replacement = 'requirement_extraction: |\n' + "".join(
        f"  {line}\n" if line.strip() else "\n"
        for line in new_prompt.strip().split("\n")
    )
    text = re.sub(pattern, replacement, text)
    PROMPTS_PATH.write_text(text, encoding="utf-8")


def _keyword_overlap(keywords: list[str], text: str) -> float:
    if not keywords:
        return 1.0  # no keywords expected → always passes
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


def _evaluate_single(extracted: ExtractedRequirement, expected: dict) -> TestCaseResult:
    scores = []
    details = {}

    # Sentiment accuracy (binary)
    sentiment_ok = extracted.sentiment.value == expected.get("sentiment")
    sentiment_score = 1.0 if sentiment_ok else 0.0
    scores.append(sentiment_score * 0.25)
    details["sentiment"] = {
        "expected": expected.get("sentiment"),
        "actual": extracted.sentiment.value,
        "ok": sentiment_ok,
    }

    # Emotion accuracy (binary)
    emotion_ok = extracted.emotion.value == expected.get("emotion")
    emotion_score = 1.0 if emotion_ok else 0.0
    scores.append(emotion_score * 0.25)
    details["emotion"] = {
        "expected": expected.get("emotion"),
        "actual": extracted.emotion.value,
        "ok": emotion_ok,
    }

    # Confidence range
    conf = extracted.confidence
    conf_min = expected.get("confidence_min", 0.0)
    conf_max = expected.get("confidence_max", 1.0)
    conf_ok = conf_min <= conf <= conf_max
    conf_penalty = 0.0 if conf_ok else min(abs(conf - conf_min), abs(conf - conf_max))
    conf_score = max(0.0, 1.0 - conf_penalty)
    scores.append(conf_score * 0.15)
    details["confidence"] = {
        "expected_range": [conf_min, conf_max],
        "actual": conf,
        "ok": conf_ok,
    }

    # Title keyword overlap
    title_overlap = _keyword_overlap(expected.get("title_keywords", []), extracted.title)
    scores.append(title_overlap * 0.15)
    details["title_keywords"] = {"overlap": round(title_overlap, 2)}

    # Pain point keyword overlap
    pain_text = extracted.pain_point or ""
    pain_overlap = _keyword_overlap(expected.get("pain_point_keywords", []), pain_text)
    scores.append(pain_overlap * 0.10)
    details["pain_point_keywords"] = {"overlap": round(pain_overlap, 2)}

    # Use case keyword overlap
    use_case_text = extracted.use_case or ""
    uc_overlap = _keyword_overlap(expected.get("use_case_keywords", []), use_case_text)
    scores.append(uc_overlap * 0.10)
    details["use_case_keywords"] = {"overlap": round(uc_overlap, 2)}

    total_score = sum(scores)
    passed = total_score >= 0.7

    return TestCaseResult(
        test_id=expected.get("id", "?"),
        passed=passed,
        score=round(total_score, 4),
        details=details,
        extracted={
            "title": extracted.title,
            "sentiment": extracted.sentiment.value,
            "emotion": extracted.emotion.value,
            "confidence": extracted.confidence,
        },
    )


# ── Prompt Optimizer ──────────────────────────────────────────────


class PromptOptimizer:
    def __init__(self) -> None:
        self._run = OptimizationRun()
        self._task: asyncio.Task | None = None
        self._original_preset_id: str | None = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> dict:
        r = self._run
        return {
            "status": r.status,
            "current_iteration": r.current_iteration,
            "max_iterations": r.max_iterations,
            "baseline_score": round(r.baseline_score, 4),
            "best_score": round(r.best_score, 4),
            "improvement": round(r.best_score - r.baseline_score, 4),
            "iterations_count": len(r.iterations),
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "elapsed_seconds": round(r.finished_at - r.started_at, 1) if r.finished_at else (
                round(time.time() - r.started_at, 1) if r.started_at else 0
            ),
            "error": r.error,
        }

    def get_results(self) -> dict:
        r = self._run
        return {
            **self.status,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "prompt_version": it.prompt_version,
                    "score": round(it.score, 4),
                    "passed": it.passed,
                    "total": it.total,
                    "improved": it.improved,
                    "prompt_diff": it.prompt_diff[:500],
                    "details": [
                        {"test_id": tr.test_id, "passed": tr.passed, "score": round(tr.score, 4), "details": tr.details}
                        for tr in it.results
                    ],
                }
                for it in r.iterations
            ],
            "best_prompt": r.best_prompt[:2000] if r.best_prompt else None,
        }

    def start(self, max_iterations: int = 10, patience: int = 5, num_candidates: int = 3) -> bool:
        if self._run.status == "running" or self._lock.locked():
            return False
        # Guard against excessive resource usage
        num_candidates = min(num_candidates, 10)
        self._run = OptimizationRun(
            status="running",
            max_iterations=max_iterations,
            patience=patience,
            num_candidates=num_candidates,
            started_at=time.time(),
        )
        self._task = asyncio.create_task(self._run_loop())
        return True

    def start_from_feedback(self, max_iterations: int = 10, patience: int = 5,
                            num_candidates: int = 3, min_feedback: int = 1) -> bool:
        """Start optimization using human feedback as test cases.

        Instead of (or in addition to) the golden test cases from
        prompt_test_cases.yaml, this mode derives test cases from
        FeedbackRecord entries — human corrections at quality gates.
        """
        if self._run.status == "running" or self._lock.locked():
            return False
        num_candidates = min(num_candidates, 10)
        self._run = OptimizationRun(
            status="running",
            max_iterations=max_iterations,
            patience=patience,
            num_candidates=num_candidates,
            started_at=time.time(),
        )
        self._task = asyncio.create_task(self._run_loop_from_feedback(min_feedback))
        return True

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._run.status = "stopped"

    async def _run_loop(self) -> None:
        try:
            test_cases = _load_test_cases()
            if not test_cases:
                self._run.status = "failed"
                self._run.error = "No test cases found"
                return
            await self._run_optimization_loop(test_cases, "improved")
        except asyncio.CancelledError:
            self._run.status = "stopped"
            self._run.finished_at = time.time()
        except Exception as e:
            self._run.status = "failed"
            self._run.error = str(e)
            self._run.finished_at = time.time()
            logger.error("prompt_optimizer_failed", error=str(e))

    async def _evaluate_iteration(
        self, iteration: int, version: str, prompt: str, test_cases: list[dict],
    ) -> IterationResult:
        results: list[TestCaseResult] = []

        for tc in test_cases:
            inp = tc.get("input", {})
            expected = tc.get("expected", {})
            text = f"讨论标题：{inp.get('title', '')}\n\n讨论内容：\n{inp.get('content', '')}"

            try:
                extracted: ExtractedRequirement = await llm.extract_structured(
                    prompt=prompt,
                    text=text,
                    schema=ExtractedRequirement,
                )
                result = _evaluate_single(extracted, expected)
            except Exception as e:
                result = TestCaseResult(
                    test_id=tc.get("id", "?"),
                    passed=False,
                    score=0.0,
                    details={"error": str(e)},
                )
            results.append(result)

        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        passed = sum(1 for r in results if r.passed)

        return IterationResult(
            iteration=iteration,
            prompt_version=version,
            score=round(avg_score, 4),
            passed=passed,
            total=len(results),
            results=results,
        )

    async def _run_loop_from_feedback(self, min_feedback: int = 1) -> None:
        """Run optimization loop using feedback-derived test cases."""
        try:
            # Derive test cases from feedback
            from needradar.core.database import async_session_factory
            from needradar.services.feedback_service import FeedbackService
            async with async_session_factory() as db:
                svc = FeedbackService(db)
                test_cases = await svc.derive_test_cases_from_feedback(
                    min_corrections=min_feedback,
                )

            if not test_cases:
                self._run.status = "failed"
                self._run.error = f"Not enough feedback (need {min_feedback}). Record more gate corrections first."
                self._run.finished_at = time.time()
                return

            # Merge with golden test cases if available
            try:
                golden = _load_test_cases()
                test_cases = golden + test_cases
                logger.info("merged_test_cases", golden=len(golden), feedback=len(test_cases) - len(golden))
            except Exception:
                pass

            await self._run_optimization_loop(test_cases, "feedback")
        except asyncio.CancelledError:
            self._run.status = "stopped"
            self._run.finished_at = time.time()
        except Exception as e:
            self._run.status = "failed"
            self._run.error = str(e)
            self._run.finished_at = time.time()
            logger.error("prompt_optimizer_feedback_failed", error=str(e))

    async def _run_optimization_loop(self, test_cases: list[dict], version_prefix: str) -> None:
        """Shared optimization loop used by both golden-test and feedback modes."""
        async with self._lock:
            try:
                self._original_preset_id = llm.active_preset_id
                if llm.active_preset_id == "deepseek-v4-flash":
                    llm.activate_preset("deepseek-v4-pro")
                    logger.info("prompt_optimizer_switched_to_pro")

                shutil.copy2(PROMPTS_PATH, BACKUP_PATH)
                logger.info("prompt_optimizer_started", backup=str(BACKUP_PATH), test_cases=len(test_cases))

                prompts = _load_prompts()
                current_prompt = prompts.get("requirement_extraction", "")
                self._run.best_prompt = current_prompt

                baseline_iter = await self._evaluate_iteration(
                    0, "baseline", current_prompt, test_cases,
                )
                self._run.baseline_score = baseline_iter.score
                self._run.best_score = baseline_iter.score
                self._run.iterations.append(baseline_iter)
                self._run.current_iteration = 0

                for i in range(1, self._run.max_iterations + 1):
                    if self._run.status != "running":
                        break

                    self._run.current_iteration = i
                    last_iter = self._run.iterations[-1]

                    temps = [0.7 + j * 0.15 for j in range(self._run.num_candidates)]
                    proposals = await asyncio.gather(*[
                        self._propose_improvement(current_prompt, last_iter, temperature=t)
                        for t in temps
                    ])
                    valid_proposals = [(j, p) for j, p in enumerate(proposals) if p is not None]

                    if not valid_proposals:
                        self._run.consecutive_no_improve += 1
                        if self._run.consecutive_no_improve >= self._run.patience:
                            break
                        continue

                    best_candidate_result = None
                    best_candidate_prompt = None
                    for j, proposal in valid_proposals:
                        result = await self._evaluate_iteration(
                            i, f"{version_prefix}_v{i}_c{j}", proposal, test_cases,
                        )
                        if best_candidate_result is None or result.score > best_candidate_result.score:
                            best_candidate_result = result
                            best_candidate_prompt = proposal

                    if best_candidate_result.score > self._run.best_score:
                        best_candidate_result.improved = True
                        self._run.best_score = best_candidate_result.score
                        self._run.best_prompt = best_candidate_prompt
                        current_prompt = best_candidate_prompt
                        _save_requirement_prompt(best_candidate_prompt)
                        self._run.consecutive_no_improve = 0
                        logger.info("prompt_improved", iteration=i, score=round(best_candidate_result.score, 4))
                    else:
                        best_candidate_result.improved = False
                        self._run.consecutive_no_improve += 1
                        if self._run.consecutive_no_improve >= self._run.patience:
                            break

                    self._run.iterations.append(best_candidate_result)

                self._run.status = "completed"
                self._run.finished_at = time.time()
                from needradar.services.analysis_service import invalidate_prompts_cache
                invalidate_prompts_cache()
                logger.info("prompt_optimizer_done", baseline=round(self._run.baseline_score, 4), best=round(self._run.best_score, 4))

            except asyncio.CancelledError:
                self._run.status = "stopped"
                self._run.finished_at = time.time()
            except Exception as e:
                self._run.status = "failed"
                self._run.error = str(e)
                self._run.finished_at = time.time()
                logger.error("prompt_optimizer_failed", error=str(e))
            finally:
                if self._original_preset_id:
                    llm.activate_preset(self._original_preset_id)

    async def _propose_improvement(
        self, current_prompt: str, last_iter: IterationResult, temperature: float = 0.7,
    ) -> str | None:
        # Build failure summary
        failures = []
        for r in last_iter.results:
            if not r.passed:
                failures.append(f"- 测试用例 '{r.test_id}': 得分 {r.score:.2f}, 详情: {r.details}")

        failure_summary = "\n".join(failures) if failures else "全部通过，但请尝试微调以进一步提高准确性。"

        meta_prompt = f"""你是一个 prompt 工程专家。你需要改进以下用于从用户讨论中提取 AI 工具需求的 prompt。

## 当前 prompt：
```
{current_prompt}
```

## 当前评分：{last_iter.score:.4f}（满分 1.0），{last_iter.passed}/{last_iter.total} 测试用例通过

## 失败案例分析：
{failure_summary}

## 评分规则（不要改变）：
- sentiment 准确性（25%）：必须精确匹配 strong/moderate/mild
- emotion 准确性（25%）：必须精确匹配 positive/negative/neutral
- confidence 范围（15%）：必须在期望范围内
- title 关键词覆盖（15%）
- pain_point 关键词覆盖（10%）
- use_case 关键词覆盖（10%）

## 要求：
1. 只输出改进后的完整 prompt，不要任何解释
2. 保持 JSON 输出格式不变（字段名和结构完全一致）
3. 保持语言判断指令不变
4. 重点改进导致失败的判断标准描述
5. 不要删减现有的判断标准，只做优化和补充"""

        try:
            messages = [
                {"role": "system", "content": "你是一个 prompt 工程专家，专注于优化 LLM 的结构化提取能力。"},
                {"role": "user", "content": meta_prompt},
            ]
            response = await llm.complete(messages, temperature=temperature, max_tokens=2000)
            # Strip markdown code fences from LLM output
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                response = "\n".join(lines).strip()
            # Basic validation: must be parseable JSON with required fields
            import json
            required_fields = ["title", "description", "sentiment", "emotion", "confidence", "use_case", "pain_point"]
            try:
                parsed = json.loads(response)
                if all(f in parsed for f in required_fields):
                    return response.strip()
            except json.JSONDecodeError:
                pass
            logger.warning("proposal_missing_fields", missing=[
                f for f in required_fields if f not in response
            ])
            return None
        except Exception as e:
            logger.error("propose_improvement_failed", error=str(e))
            return None


optimizer = PromptOptimizer()

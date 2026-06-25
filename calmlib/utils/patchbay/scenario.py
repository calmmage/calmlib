"""Patchbay scenario runner — multi-step sequential execution with validation."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Callable

from loguru import logger
from pydantic import BaseModel

from calmlib.utils.patchbay.session import PatchbaySession


class StepResult(BaseModel):
    step_index: int
    message: str
    response: str
    output_path: str | None = None
    success: bool = True
    error: str | None = None
    duration_ms: int = 0


class ScenarioResult(BaseModel):
    session_id: str | None = None
    steps: list[StepResult] = []
    total_cost: float = 0.0
    success: bool = True
    error: str | None = None


async def run_scenario(
    steps: list[str],
    cwd: str | None = None,
    output_dir: str | None = None,
    model: str | None = None,
    task_description: str | None = None,
    system_prompt: str | None = None,
    parent_session_id: str | None = None,
    validate_fn: Callable[[int, str], bool] | None = None,
) -> ScenarioResult:
    """Run a sequence of messages in a single session.

    Args:
        steps: List of messages to send sequentially.
        cwd: Working directory for the session.
        output_dir: If set, each step's response is saved to {output_dir}/step_{n}.md
        model: Model shortcut or full ID.
        task_description: Description for MongoDB tracking.
        system_prompt: Optional system prompt.
        parent_session_id: Link to parent session.
        validate_fn: Optional callable(step_index, response) -> bool. If returns False, stops.

    Returns:
        ScenarioResult with per-step responses and overall status.
    """
    result = ScenarioResult()

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    async with PatchbaySession(
        cwd=cwd,
        model=model,
        task_description=task_description,
        system_prompt=system_prompt,
        parent_session_id=parent_session_id,
    ) as session:
        result.session_id = None  # will be set after first send

        for i, step_msg in enumerate(steps):
            logger.info(f"Step {i}: {step_msg[:80]}")
            start = datetime.now()

            try:
                response = await session.send(step_msg)
            except Exception as e:
                step = StepResult(
                    step_index=i,
                    message=step_msg,
                    response="",
                    success=False,
                    error=str(e),
                )
                result.steps.append(step)
                result.success = False
                result.error = f"Step {i} failed: {e}"
                logger.error(result.error)
                break

            elapsed = int((datetime.now() - start).total_seconds() * 1000)

            # Save step output to file
            output_path = None
            if output_dir:
                output_path = str(Path(output_dir) / f"step_{i}.md")
                Path(output_path).write_text(
                    f"# Step {i}\n\n## Message\n{step_msg}\n\n## Response\n{response}\n"
                )

            step = StepResult(
                step_index=i,
                message=step_msg,
                response=response,
                output_path=output_path,
                duration_ms=elapsed,
            )

            # Validate
            if validate_fn:
                try:
                    is_valid = validate_fn(i, response)
                except Exception as e:
                    is_valid = False
                    step.error = f"Validation error: {e}"

                if not is_valid:
                    step.success = False
                    result.steps.append(step)
                    result.success = False
                    result.error = f"Step {i} validation failed"
                    logger.warning(result.error)
                    break

            result.steps.append(step)
            logger.info(f"Step {i} done ({elapsed}ms, {len(response)} chars)")

        result.session_id = session.session_id
        result.total_cost = session.total_cost

    return result

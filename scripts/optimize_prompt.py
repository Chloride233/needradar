# -*- coding: utf-8 -*-
"""一键 Prompt 自优化脚本。
用法：python scripts/optimize_prompt.py [迭代次数] [耐心值] [候选数]
示例：
  python scripts/optimize_prompt.py                    # 默认 10 轮, 5 耐心, 3 候选
  python scripts/optimize_prompt.py 20                  # 20 轮
  python scripts/optimize_prompt.py 40 3 2             # 40 轮, 3 轮无提升停止, 2 候选/轮
  python scripts/optimize_prompt.py 10 3               # 10 轮, 3 轮无提升停止
"""
import sys
import time
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from needradar.services.prompt_optimizer import PromptOptimizer


async def main():
    max_iter = max(1, int(sys.argv[1])) if len(sys.argv) > 1 else 10
    patience = max(1, int(sys.argv[2])) if len(sys.argv) > 2 else 5
    num_candidates = max(1, min(int(sys.argv[3]), 10)) if len(sys.argv) > 3 else 3
    opt = PromptOptimizer()

    print(f"=== Prompt Optimization ===")
    print(f"Max rounds:  {max_iter}")
    print(f"Patience:    {patience} (early stop)")
    print(f"Candidates:  {num_candidates} per round")
    print(f"Test set:    config/prompt_test_cases.yaml")
    print()

    opt.start(max_iterations=max_iter, patience=patience, num_candidates=num_candidates)

    printed_iters = 0
    try:
        while opt._run.status == "running":
            iters = opt._run.iterations
            if len(iters) > printed_iters:
                for it in iters[printed_iters:]:
                    icon = "+" if it.improved else "."
                    print(
                        f"  [{icon}] Round {it.iteration}  "
                        f"{it.prompt_version}  "
                        f"score={it.score:.4f}  "
                        f"passed={it.passed}/{it.total}"
                    )
                printed_iters = len(iters)
            await asyncio.sleep(2)

        # Print any remaining iterations
        iters = opt._run.iterations
        if len(iters) > printed_iters:
            for it in iters[printed_iters:]:
                icon = "+" if it.improved else "."
                print(
                    f"  [{icon}] Round {it.iteration}  "
                    f"{it.prompt_version}  "
                    f"score={it.score:.4f}  "
                    f"passed={it.passed}/{it.total}"
                )

        r = opt._run
        print()
        if r.status == "completed" or r.status == "stopped":
            print("=== Done ===")
            if r.consecutive_no_improve >= patience:
                print(f"Early stopped: {r.consecutive_no_improve} rounds without improvement")
            print(f"Rounds run: {len(r.iterations) - 1}")  # exclude baseline
            print(f"Baseline:   {r.baseline_score:.4f}")
            print(f"Best:       {r.best_score:.4f}")
            print(f"Delta:      {r.best_score - r.baseline_score:+.4f}")
            print(f"Time:       {r.finished_at - r.started_at:.0f}s")
            print()
            if r.best_score > r.baseline_score:
                print("Prompt updated in config/prompts.yaml")
                print("Backup at config/prompts.yaml.bak")
            else:
                print("No improvement found, prompt unchanged")
        else:
            print(f"=== Stopped: {r.status} ===")
            if r.error:
                print(f"Error: {r.error}")
    except KeyboardInterrupt:
        print("\nStopping...")
        opt.stop()


if __name__ == "__main__":
    asyncio.run(main())

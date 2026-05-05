# -*- coding: utf-8 -*-
"""一键 Prompt 自优化脚本。用法：python scripts/optimize_prompt.py [迭代次数]"""
import sys
import time
import asyncio

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from needradar.services.prompt_optimizer import PromptOptimizer


async def main():
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    opt = PromptOptimizer()

    print(f"=== Prompt Optimization ({max_iter} rounds) ===")
    print("Test set: config/prompt_test_cases.yaml")
    print()

    opt.start(max_iterations=max_iter)

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
        if r.status == "completed":
            print("=== Done ===")
            print(f"Baseline:  {r.baseline_score:.4f}")
            print(f"Best:      {r.best_score:.4f}")
            print(f"Delta:     {r.best_score - r.baseline_score:+.4f}")
            print(f"Time:      {r.finished_at - r.started_at:.0f}s")
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

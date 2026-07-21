# NeedRadar 单专家相关性盲审指南

> 当前个人审查路径使用 `evaluation/rerank/pilot/annotation-template.csv`：30 个 test 查询，只审三种排序 Top 3 的去重并集。原始 2,000 条模板保留用于完整 qrels 研究，不再要求个人完成。

## 1. 启动工具

Pilot API 排序和盲池生成完成后，在仓库根目录运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_review.py \
  --template evaluation/rerank/pilot/annotation-template.csv --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。页面应显示：

- `30 个查询`及约 210 至 240 个去重候选；
- 与 `evaluation/rerank/pilot/annotation-template.csv` 一致的 SHA-256；
- 阶段为“首轮”。

工具不会连接 SiliconFlow、读取 Rerank 缓存或上传内容。终端按 `Ctrl+C` 可停止服务，再次启动会从浏览器本地进度继续。

## 2. 评分判断树

对每个候选依次问：

1. 它是否在处理 query 表达的同一个需求或问题？
2. 它是否能直接帮助回答、解决或有力证明这个需求？如果是，标 `2`。
3. 它是否只提供相邻问题、有限背景或需要较多推断才有帮助？如果是，标 `1`。
4. 否则标 `0`。

核心标准是“对这个 query 是否有用”，不是“是否出现相同关键词”。

### `0 — 不相关`

- 仅有词面重合，但实际讨论另一个问题。
- 只是依赖升级、项目公告、导航页或通用宣传。
- 无法为 query 提供可用事实、方案或背景。

### `1 — 部分相关`

- 讨论同一领域中的相邻问题。
- 能解释一部分背景，但不能直接解决 query。
- 技术栈不同，但揭示了可迁移的同类需求或约束。
- 摘要被截断，现有内容只能支持有限判断。

### `2 — 高度相关`

- 直接描述同一个问题、需求或使用场景。
- 给出可执行解决方案、明确限制或强支持证据。
- 即使措辞不同，实质上回答了 query 想解决的核心问题。

不要因为来源是 GitHub、StackOverflow 或中文平台而改变等级。写作质量、点赞数和项目知名度也不是相关性。

## 3. 首轮审查

- 数字键 `0`、`1`、`2`：记录等级并前进。
- `U`：切换“不确定”。
- `←`、`→`：前后移动。
- 需要解释时，先填写备注再评分。
- 每完成一段工作，点击“导出进度”，把 `rerank-review-progress.json` 保存到可靠位置。

建议每次连续审查 25 至 40 分钟，然后休息。不要为了让 `0/1/2` 数量看起来均衡而修改判断，也不要查看 `report.json`、Rerank 缓存或模型输出。

全部 pilot 候选完成后，“冻结首轮”按钮才会启用。冻结前可以回看和修改；冻结后首轮判断不能静默覆盖。

按每条 15 至 30 秒估算，首轮大约需要 1.5 至 3 小时，建议拆成多次完成。

## 4. 隐藏重测

首轮冻结后，建议等待至少 48 小时再点击“开始隐藏重测”。工具会显示约 21 至 24 条由模板哈希确定的候选，不显示首轮等级和备注。

按完全相同的判断树重新评分。不要尝试回忆或猜测首轮答案。重测完成后，工具计算：

- 精确一致率；
- 二次加权 Cohen's kappa；
- 分歧数量；
- 首轮到重测的时间间隔。

## 5. 自我裁决

如果两轮存在分歧，工具只显示分歧项，并同时展示首轮和重测等级。重新阅读 query 与候选，选择最终等级，并填写具体理由。

好的理由应说明判断边界，例如：

- `同属导出主题，但正文只讨论格式转换，不解决权限失败，因此最终为 1。`
- `虽然标题相似，正文是依赖更新公告，不能支持该需求，因此最终为 0。`

不要只写“改成 1”“感觉更相关”等无法审计的理由。

## 6. 导出和验证

完成后点击“完整证据包”，应得到：

- `reviewer-single.csv`
- `reviewer-retest.csv`
- `labels-adjudicated.csv`
- `labels-adjudicated.manifest.json`

把四个文件放到 `evaluation/rerank/pilot/`，不要覆盖 `annotation-template.csv`。然后运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_pilot.py --rebuild-report --batch 1
```

如果原始文件哈希、隐藏样本、统计值或裁决记录不一致，runner 会拒绝标签并保持 `missing_human_labels`。通过时，报告中的标签状态为 `single_expert_test_retest_validated`，并保留 `moderate_evidence_single_expert` 限定。

即使门槛通过，也只能声称“单专家、系统盲化、重测验证的相关性标签”，不能声称多人共识或双人独立评审。

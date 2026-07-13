# Phase 2 中文人工抽查

请只判断：原帖作者是否提出了一个与 AI 或软件工具有关的需求、问题或期望功能。

- `yes`：确实提出需求、问题或期望能力。
- `no`：只是新闻、教程、状态记录或知识问答，没有工具需求。
- `unclear`：信息太少，无法判断。

## 1. Spring 程序崩溃

- 平台：GitHub
- 原文情况：只有标题，没有正文。
- 中文意思：外部启动的 Spring UserReport 程序发生崩溃，但退出码显示为 0。
- Agent A：`yes`
- Agent B：`unclear`
- 你的判断：

## 2. 跟踪 Praxis skill 的真实缺口

- 平台：GitHub
- 中文意思：当前已经有 161 个 Praxis skill，作者不希望为了增加数量而继续创建 skill。这个 issue 要求以后只记录真实开发、审计或迁移过程中发现的 skill 路由错误、验证不足、文档过期或平台能力缺口，并规定何时创建后续 issue。
- Agent A：`no`
- Agent B：`yes`
- 你的判断：

## 3. E2E 稳定性改进计划

- 平台：GitHub
- 中文意思：项目制定了 7 项端到端测试标准，每两小时修复一个缺口，直到全部标准连续 7 天通过。当前 7 项中已有 6 项完成，唯一未完成的是把测试设为代码合并前的强制检查，需要人工配置。
- Agent A：`no`
- Agent B：`yes`
- 你的判断：

## 4. LUIS 中的 List entity count 是什么

- 平台：Stack Overflow
- 中文意思：用户看到 LUIS AI 工具显示 `list entity count (x/50)`，询问这个数字具体代表什么。
- Agent A：`no`
- Agent B：`yes`
- 你的判断：

## 5. 不依赖 AI 学好编程

- 平台：Stack Overflow
- 中文意思：初学者担心依赖 AI 写代码会妨碍理解和独立思考，因此询问如何通过练习方法、学习资料或学习策略，在不依赖 AI 的情况下建立扎实的编程基础。
- Agent A：`no`
- Agent B：`yes`
- 你的判断：

## 6. Monorepo 是否能改善 AI 编程工具效果

- 平台：Stack Overflow
- 中文意思：用户正在评估把多个前端项目迁移到 monorepo，想知道完整代码库上下文是否真的能提高 Copilot、Cursor 等 AI 工具的重构质量、一致性和跨项目修改能力，以及是否存在缺点。
- Agent A：`unclear`
- Agent B：`yes`
- 你的判断：

## 7. 如何在不依赖 AI 的情况下搜索编程答案

- 平台：Stack Overflow
- 中文意思：用户遇到编程问题时总是直接让 AI 解答，担心失去思考和解决问题的能力，因此希望获得一套自己搜索、分析并找到解决方案的方法。
- Agent A：`no`
- Agent B：`yes`
- 你的判断：

## 回复格式

直接在对话中回复即可，例如：

```text
1 unclear
2 yes
3 yes
4 no
5 no
6 unclear
7 no
```

---
标题: NeedRadar 知识库
阶段: 已发布
创建时间: 2026-05-03
更新时间: 2026-05-03
关联参考:
发布平台: 内部
---

# NeedRadar 知识库

> 需求雷达——社区需求采集、分析与报告生成的全流程知识管理。

## 管道流转

```
01 原始素材库 → 02 需求池 → 03 分析车间 → 04 报告归档
   爬取采集      LLM提取去重    趋势/聚类分析     最终报告
```

## 工作日志

```dataview
TABLE 日期, 标签, 参与人
FROM "05-工作日志"
SORT 日期 DESC
LIMIT 15
```

## 按阶段浏览

### 01 素材
```dataview
TABLE 阶段, 来源平台, 创建时间
FROM "01-原始素材库"
SORT 创建时间 DESC
LIMIT 20
```

### 02 需求
```dataview
TABLE 阶段, 来源平台, 情感倾向, 创建时间
FROM "02-需求池"
SORT 创建时间 DESC
LIMIT 20
```

### 03 分析
```dataview
TABLE 阶段, 关联需求, 创建时间
FROM "03-分析车间"
SORT 创建时间 DESC
LIMIT 20
```

### 04 归档
```dataview
TABLE 阶段, 关键词, 创建时间
FROM "04-报告归档"
SORT 创建时间 DESC
LIMIT 20
```

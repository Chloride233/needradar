# Palantir Foundry Ontology 范式

> **来源**: [Palantir Foundry 官方文档](https://www.palantir.com/docs/foundry/ontology/overview/)  
> **创建时间**: 2026-06-01  
> **目的**: 学习 Palantir Ontology 的数据建模范式，分析其对 NeedRadar 项目的借鉴意义  
> **相关文档**: [[../CODEMAPS/architecture|架构总览]], [[../CODEMAPS/data|数据模型]]

---

## 目录

1. [Ontology 是什么？](#1-ontology-是什么)
2. [核心概念](#2-核心概念)
3. [Object Views：以对象为中心的视图枢纽](#3-object-views以对象为中心的视图枢纽)
4. [Ontology SDK (OSDK)](#4-ontology-sdk-osdk)
5. [高级建模模式](#5-高级建模模式)
6. [Ontology Language / Engine / Toolchain 三层架构](#6-ontology-language--engine--toolchain-三层架构)
7. [NeedRadar 现状对照分析](#7-needradar-现状对照分析)
8. [差距分析与改进建议](#8-差距分析与改进建议)

---

## 1. Ontology 是什么？

> *"The Ontology is the digital twin of an organization, a rich semantic layer that sits on top of the digital assets."*

Palantir 的 Ontology 不是传统意义上的"本体论"或 RDF/OWL 语义网。它是一套**操作化语义层（operational semantic layer）**，核心思想是：

- **把分散的数据源（datasets、models、APIs）映射为真实世界中的对象**，而不是停留在表/行/列的抽象
- 企业里的"航班"、"患者"、"工单"、"零件"不只是数据库里的行——它们有属性、有关系、有可执行的动作
- Ontology 同时建模**语义（nouns）**和**动力学（verbs）**：对象 + 链接 + 动作 + 函数

### 1.1 四维集成

Palantir 的 Ontology 通过四个维度的集成来建模**决策**：

| 维度 | 含义 | 示例 |
|------|------|------|
| **Data（数据）** | 从任意来源（ERP、CRM、传感器、文档）汇聚为对象/属性/链接 | 航班对象从 15 个系统汇聚 |
| **Logic（逻辑）** | 附加在对象和动作上的计算逻辑（规则、ML 模型、LLM 调用） | 航班延误预测函数 |
| **Action（动作）** | 对对象的修改操作，含副作用和写回 | 改签乘客 → 写回预订系统 |
| **Security（安全）** | 细粒度到行/列/动作的权限模型 | 分析师能读但不能修改航班状态 |

### 1.2 类比：从数据集到 Ontology

| 数据集概念 | Ontology 概念 |
|-----------|---------------|
| Dataset（数据集） | Object Type（对象类型） |
| Row（行） | Object（对象实例） |
| Column（列） | Property（属性） |
| Field（单元格值） | Property Value（属性值） |
| Join（表连接） | Link Type（链接类型） |

这个类比很关键：**Ontology 就是把数据库的范式提升到了业务语义层**。一个 `Patient` 对象类型不仅仅是 `patients` 表的映射——它聚合了来自 EHR、CRM、LIS 等多个系统的数据。

---

## 2. 核心概念

### 2.1 Object Type（对象类型）

**定义**：现实世界中某类实体或事件的 schema 定义。

- 对应一个数据集，但可以映射多个 backing datasources
- 实例称为 **Object**（如"患者 Melissa Chang"）
- 集合称为 **Object Set**（如"所有在职员工"）

**配置要素**：
- **Primary Key**：唯一标识（必须确定性的，不能是随机生成的）
- **Title Key**：显示名称
- **Backing Datasource**：数据来源（可以是多个）
- **Properties**：属性映射
- **API Name**：程序化访问的标识符（有保留关键字限制）

### 2.2 Property（属性）

**定义**：对象类型特征的 schema 定义。

**支持的属性类型**：
- 常用标量：`String`, `Integer`, `Short`, `Long`, `Float`, `Double`, `Decimal`, `Boolean`, `Byte`
- 时间：`Date`, `Timestamp`
- 地理：`Geopoint`, `Geoshape`
- 富媒体：`Media Reference`, `Time Series`, `Attachment`
- 复合类型：`Array`, `Struct`, `Vector`
- 特殊：`Cipher`, `Marking`

**Shared Property**：可在多个对象类型间共享的属性定义，确保跨类型的一致性建模。

### 2.3 Link Type（链接类型）

**定义**：两个对象类型之间关系的 schema 定义。

- 类似数据集之间的 JOIN，但带有语义标签
- 支持不同基数：一对一、一对多、多对多
- 通过 foreign key 关系实现（左对象的某个属性 = 右对象的主键）
- **多对多链接受限**：直接的 many-to-many 链接无法存储元数据 → 需要中间 Join Object

### 2.4 Action Type（动作类型）

**定义**：一套对对象、属性值、链接的修改操作，含副作用行为。

- 对应用户可执行的操作，如"分配航班给飞行员"、"修改患者护理计划"
- 可以触发 Functions、写回外部系统、发送通知
- 有状态机语义：定义对象在其生命周期中的合法转换

### 2.5 Function（函数）

**定义**：代码化的业务逻辑，接收输入参数并返回输出。

- 深度集成 Ontology：可接收 Object / Object Set 作为参数
- 可被 Action Types 和外部应用调用
- 例子：航班延误预测、库存优化、风险评分

### 2.6 Interface（接口）

**定义**：描述对象类型"形状"的抽象类型，提供**对象类型多态**。

- 类似编程语言中的 interface/协议
- 例如：`[I] Asset` 接口定义了 `asset_id` 和 `status` 属性，`[Pump]`、`[Vehicle]`、`[Turbine]` 都实现它
- **关键价值**：Workshop 组件和 Function 可以操作接口类型，无需为每种具体类型编写代码

### 2.7 Role（角色）

**定义**：Ontology 层的权限模型。

- 可在 Ontology 级别或单个资源级别授予
- 控制读/写/编辑权限
- 与 Foundry 的文件系统权限独立

---

## 3. Object Views：以对象为中心的视图枢纽

> *"Object Views are a central hub for all information and workflows related to a particular object."*

这是本文最初抓取的主题，也是 Palantir Ontology 最值得 NeedRadar 借鉴的概念。

### 3.1 核心思想

**Object View 是一个对象的完整信息枢纽**。当你打开一个"航班 UA123"的对象视图，你看到的是：

- 该航班的核心属性（航班号、起降时间、状态）
- 所有关联对象的链接（机组人员、乘客列表、行李件数、维护记录）
- 分析图表（延误趋势、载客率变化）
- 可执行的动作（改签、取消、分配飞行员）
- 关联的 Dashboard 和应用

### 3.2 两种 Object View 类型

| 类型 | 特点 | 适用场景 |
|------|------|----------|
| **Standard Object View** | 自动生成，反映对象类型的 schema 配置，无需手动配置 | 快速了解对象结构、探索数据 |
| **Configured Object View** | 通过 Workshop 完全自定义，可提供特定工作流所需的上下文体验 | 运营工作台、决策面板 |

**关键设计**：两种视图共存，用户可随时切换。Standard View 是"裸数据视图"，Configured View 是"策划后的工作流视图"。

### 3.3 两种形态因子（Form Factor）

| 形态 | 用途 |
|------|------|
| **Full Object View** | 深度展示：全部属性、所有链接、分析图表、关联应用 |
| **Panel Object View** | 嵌入其他应用：仅显示最关键数据，适合侧边栏、列表预览 |

### 3.4 Standard Object View 的能力

1. **Prominent Properties**：标记为"突出"的属性会获得增强视觉处理
   - 媒体 → 专用媒体查看器
   - 时序 → 交互式图表
   - 地理 → 地图渲染
   - 其他 → 卡片式布局，悬浮在属性表之上

2. **Linked Objects 组件**：
   - 按链接类型分组查看关联对象
   - 内联预览关联对象属性（无需离开当前视图）
   - 在新标签页打开关联对象子集
   - 在侧面板预览选中的关联对象

3. **可视化 Widgets**：
   - Linked Object View（表格/列表/卡片视图）
   - Timeline（按时间排列的关联事件）
   - Grouped Events Timeline and Table
   - 嵌入其他应用的图表/仪表盘/报告

### 3.5 Configured Object View 的能力

- 完全自定义的 Workshop 模块
- 多 Tab 结构
- 可添加自定义 Widget、图表、动作按钮
- 使用所有 Workshop 标准功能
- 权限与对象类型的 Ontology 角色对齐
- **编辑后成为用户管理的静态视图**（不再自动同步 Schema 变更）

### 3.6 配置示例：Patient 对象视图

一个完整的 Patient 对象视图包含：

```
┌─────────────────────────────────────────────────┐
│ Patient: Melissa Chang                           │
│ ID: 11502 | DOB: 1987-03-15 | Blood Type: O+    │
├─────────────────────────────────────────────────┤
│ [Tab: Overview] [Tab: Medical History] [Tab: Analytics] │
├─────────────────────────────────────────────────┤
│                                                  │
│ 📊 Vitals (Prominent)                            │
│ ┌──────────────┐ ┌──────────┐ ┌──────────────┐  │
│ │ BP: 120/80   │ │ HR: 72   │ │ Temp: 98.6°F │  │
│ └──────────────┘ └──────────┘ └──────────────┘  │
│                                                  │
│ 📋 Properties                                    │
│ ├─ Insurance: BlueCross PPO                     │
│ ├─ PCP: Dr. Sarah Chen                          │
│ └─ Last Visit: 2025-12-01                       │
│                                                  │
│ 🔗 Linked Objects                                │
│ ├─ 📝 Prescriptions (12) → [View All]           │
│ ├─ 🏥 Procedures (5)     → [View All]           │
│ ├─ 🩺 Diagnoses (3)      → [View All]           │
│ └─ 📅 Appointments (2)   → [View All]           │
│                                                  │
│ 📈 Historical Trends                             │
│ ┌────────────────────────────────────┐           │
│ │ BMI Trend (last 12 months)         │           │
│ └────────────────────────────────────┘           │
│                                                  │
│ ⚡ Actions                                       │
│ [Schedule Appointment] [Update Insurance] [Refer]│
└─────────────────────────────────────────────────┘
```

Panel View（嵌入其他应用时）：
```
┌───────────────────────┐
│ Melissa Chang          │
│ BP: 120/80 HR: 72     │
│ PCP: Dr. Chen         │
│ [Open Full View →]    │
└───────────────────────┘
```

---

## 4. Ontology SDK (OSDK)

### 4.1 核心理念

**"Treat Foundry as your Backend"**

OSDK 从你的 Ontology 定义自动生成类型安全的 SDK（TypeScript / Python / Java），让开发者可以直接在代码中操作 Ontology 对象，无需手写数据访问层。

### 4.2 工作流程

```
┌──────────────────────────────────────────────────────┐
│ 1. Foundry Platform                                  │
│    定义 Object Types (属性、主键)                     │
│    定义 Link Types (关系)                             │
│    定义 Action Types (写回逻辑)                       │
├──────────────────────────────────────────────────────┤
│ 2. Developer Console                                 │
│    注册 OSDK 应用                                    │
│    配置 OAuth + Resource Access Scope                │
│    选择暴露哪些 Object Types / Actions               │
│    生成类型安全的 SDK 包                             │
├──────────────────────────────────────────────────────┤
│ 3. Your Application                                  │
│    安装生成的 SDK                                    │
│    初始化 Client (OAuth credentials)                 │
│    获取全类型化访问：对象查询、动作执行、函数调用      │
└──────────────────────────────────────────────────────┘
```

### 4.3 OSDK 的主要优势

| 优势 | 说明 |
|------|------|
| **加速开发** | 极少的代码即可完成 Ontology 读写 |
| **强类型安全** | SDK 类型基于你的具体 Ontology 子集生成 |
| **集中维护** | Ontology 在 Foundry 中集中管理，应用只需消费 |
| **安全设计** | Token 限定到应用的 Ontology 实体范围，叠加用户自身权限 |

---

## 5. 高级建模模式

### 5.1 Interface 多态建模

**问题**：Pump、Vehicle、Turbine 是不同的实体，但都是"需要维护的资产"。为每种类型独立建模会导致大量重复逻辑。

**解决方案**：
```
[I] Asset (Interface)
  ├─ asset_id: String
  ├─ status: String
  └─ → [Maintenance Log] (link)

[Pump] implements [I] Asset
  + pump_capacity: Float
  + flow_rate: Float

[Vehicle] implements [I] Asset
  + vehicle_vin: String
  + mileage: Integer

[Turbine] implements [I] Asset
  + blade_count: Integer
  + rpm_max: Float
```

**效果**：Workshop Widget 可以操作 `[I] Asset` 接口，Function 可以接收接口作为参数，无需为每种资产类型写专门的代码。

### 5.2 递归层级（Recursive Hierarchies）

**场景**：组织架构（员工 → 汇报关系）、BOM 结构（零件 → 子组件）

**实现**：对象类型链接到自己
```
[Employee]
  └─ reports_to → [Employee]  (many-to-one)
```

**注意事项**：深层递归遍历可能有性能问题。对于深度层级，可能需要在数据管道中预计算路径或聚合值。

### 5.3 中间 Join Object 优化多对多

**问题**：`[Doctor]` ←many-to-many→ `[Patient]` 的链接本身无法存元数据（如就诊日期、诊断结果）。

**解决方案**：
```
[Doctor] ←1:N→ [Encounter] ←N:1→ [Patient]
                   ├─ visit_date
                   ├─ diagnosis
                   └─ treatment
```

这个模式不仅解决了元数据存储问题，在过滤和聚合性能上也优于直接的多对多链接。

---

## 6. Ontology Language / Engine / Toolchain 三层架构

Palantir 的 Ontology 不是薄薄的"语义层"——它是一个多层系统：

### 6.1 Language（语言层）

定义 Ontology 的"语法"：
- 语义元素：对象类型、属性、链接类型
- 动力学元素：动作类型、自动化、Function
- 安全策略：角色、权限约束

### 6.2 Engine（引擎层）

实现 Language 定义的所有组件：
- **读架构**：高扩展 SQL 查询、实时状态订阅、多模态物化视图
- **写架构**：原子事务更新、高扩展批量变更、流式写入、CDC（变更数据捕获）用于低延迟镜像到外部系统

### 6.3 Toolchain（工具链层）

让开发者将 Ontology 作为 Backend：
- OSDK（TypeScript / Python / Java）
- Developer Console（应用注册、SDK 生成）
- Workshop（无代码 UI 构建）
- Object Explorer（Ontology 搜索和分析）
- DevOps 工具（CI/CD、治理、审计）

### 6.4 对 NeedRadar 的启示

这个三层架构提供了一个**架构演进的路线图**：

- **Language 层** → NeedRadar 需要更正式的实体/关系/动作定义（而不是散落在 Markdown frontmatter 和 JSON 字段中）
- **Engine 层** → 现有的 ChromaDB + SQLite + Vault 是原始的 Engine，但缺乏统一的查询/写入抽象
- **Toolchain 层** → 现有的 REST API + CLI + 前端就是 Toolchain 的雏形

---

## 7. NeedRadar 现状对照分析

### 7.1 当前实体映射

| Palantir 概念 | NeedRadar 对应物 | 状态 |
|---------------|-----------------|------|
| **Object Type** | Vault Stage（需求、初稿、终稿）+ DB Model（CrawlTask, Opportunity, Proposal） | 隐式存在，无统一定义 |
| **Property** | Vault Markdown frontmatter 字段 + DB Column | 较完整 |
| **Link Type** | `Proposal.opportunity_id` (唯一 FK)、Vault `[[wikilinks]]`、JSON 引用字段 | **严重不足** |
| **Action Type** | 无 | **缺失** |
| **Function** | LLM extraction/scoring/generation | 存在但未与实体绑定 |
| **Interface** | 无 | **缺失** |
| **Object View** | 前端 Vue 页面（DashboardView, OpportunitiesView, ProposalView） | 页面独立，无"以对象为中心"的枢纽视图 |
| **OSDK** | REST API (`src/needradar/api/v1/`) | 存在，但无代码生成 |
| **Shared Property** | 无（每个 frontmatter 独立定义） | **缺失** |

### 7.2 当前实体清单

NeedRadar 的"对象类型"（隐式）：

| 实体 | 存储 | 属性 | 链接 |
|------|------|------|------|
| **RawDiscussion** (素材) | Vault `01-原始素材库/灵感剪报/` | 标题、来源平台、来源URL、关键词、标签 | → Requirement (via LLM extraction) |
| **Requirement** (需求) | Vault `02-需求池/` | 标题、描述、来源平台、来源URL、情感倾向、情绪极性、置信度、提及次数、关键词 | → RawDiscussion (来源URL), ↔ Report (wikilinks), → Opportunity (cluster) |
| **Opportunity** (机会) | DB `project_opportunities` | 关键词、标题、描述、评分维度、牵引力信号 | → Requirement (source_req_ids JSON), ← Proposal |
| **Proposal** (提案) | DB `project_proposals` + Vault `03-分析车间/初稿打磨/` | 标题、问题陈述、目标用户、MVP范围、技术栈、工时估算、风险 | → Opportunity (FK) |
| **Report** (报告) | Vault `03-分析车间/` | 标题、关键词、关联需求(wikilinks)、统计数据 | → Requirement (关联需求 wikilinks) |
| **CrawlTask** (爬取任务) | DB `crawl_tasks` | 关键词、平台、状态、统计数据 | → PipelineRun (task_ids JSON) |
| **TrendingProject** | DB `trending_projects` | full_name、描述、语言、stars、forks、标签 | 无 |
| **ScheduledJob** | DB `scheduled_jobs` | 名称、关键词、平台列表、间隔 | → CrawlTask (last_task_ids JSON) |
| **LLMUsage** | DB `llm_usage` | 预设、模型、token数、费用 | 无 |
| **VerificationResult** | DB `verification_results` | 报告标题、各项评分、声明列表 | → Report (report_title 字符串引用) |

### 7.3 当前"链接"的表示方式（问题分析）

| 链接类型 | 当前实现 | 问题 |
|----------|----------|------|
| Proposal → Opportunity | SQL FK | ✅ 唯一规范的链接 |
| Opportunity → Requirements | `source_req_ids_json`（JSON 数组） | ❌ 无引用完整性 |
| Report → Requirements | Vault `[[wikilinks]]` + `关联需求` frontmatter | ⚠️ 依赖文件名 |
| PipelineRun → CrawlTasks | `task_ids_json`（JSON 数组） | ⚠️ 无 FK 约束 |
| CrawlTask → PipelineRun | 反向无引用 | ❌ 无法导航到所属 Run |
| VerificationResult → Report | `report_title` 字符串 | ❌ 无引用完整性 |
| Requirement → RawDiscussion | `来源URL` 字符串 | ⚠️ 无法精确定位一对多 |
| TrendingProject → Requirement | 无 | ❌ 孤岛 |

---

## 8. 差距分析与改进建议

### 8.1 核心差距总结

#### Gap 1：缺乏显式的 Link Type 层

**现状**：除了 `Proposal.opportunity_id` 一个 FK，所有"关系"都是通过 JSON 字段、字符串引用、或 Vault wikilinks 隐式表达的。

**影响**：无法做关系遍历查询、引用完整性无法保证、前端无法构建"关联对象"组件。

**建议**：引入显式的 Link 模型（见 8.2）

#### Gap 2：没有 Object View 概念

**现状**：前端页面按功能划分（Dashboard、Opportunities、Proposal），不按**对象**组织。

**影响**：查看一个 Requirement 时，看不到它被哪些 Report 引用、属于哪个 Opportunity。

**建议**：为每种核心实体创建"对象视图"页面（见 8.3）

#### Gap 3：缺失 Interface / 多态建模

**现状**：所有实体类型硬编码，无法定义"具有某些共同属性"的抽象。

**影响**：新增实体类型需大量重复代码，无法用统一接口处理不同类型。

**建议**：在 Schema 层引入 Interface/Mixin（见 8.4）

#### Gap 4：缺失 Action Type

**现状**：对象修改通过 API endpoint 实现，没有"动作"的概念。

**影响**：无法追踪状态变更历史、前端按钮直接触发 API 缺乏语义抽象。

**建议**：定义显式的 Action 类型（见 8.5）

#### Gap 5：Toolchain 薄弱

**现状**：没有自动生成的 SDK，前后端类型不同步。

**影响**：每次 Schema 变更需手动改前端类型定义。

**建议**：生成 TypeScript 类型（见 8.6）

### 8.2 建议一：引入显式 EntityLink 模型

**新模型**：`src/needradar/models/link.py`

```python
class EntityLink(Base, TimestampMixin):
    """显式的实体间关系"""
    __tablename__ = "entity_links"

    id: int           # PK
    source_type: str  # 源对象类型: requirement/report/opportunity/...
    source_id: str    # 源对象 ID (vault 路径或 DB ID)
    link_type: str    # 链接类型: references/derived_from/analyzed_by/...
    target_type: str  # 目标对象类型
    target_id: str    # 目标对象 ID
    metadata_json: str  # 可选的关系元数据 (created_by, confidence, etc.)

    # 索引：(source_type, source_id), (target_type, target_id), link_type
```

**效果**：
- 统一的关系查询接口 → 替代所有 JSON 数组引用和字符串引用
- 可以双向遍历 → 从任一实体导航到所有关联实体
- 前端可以实现 `Linked Objects` 组件 → Object View 的基础
- 可为链接附加元数据 → 记录"为什么关联"、"置信度"等

**迁移路径**：
- `Opportunity.source_req_ids_json` → `EntityLink(source_type="opportunity", link_type="contains", target_type="requirement")`
- `PipelineRun.task_ids_json` → `EntityLink(source_type="pipeline_run", link_type="executed", target_type="crawl_task")`
- `VerificationResult.report_title` → `EntityLink(source_type="verification", link_type="verified", target_type="report")`
- Vault `关联需求` wikilinks → `EntityLink(source_type="report", link_type="references", target_type="requirement")`

### 8.3 建议二：构建 Object View 前端页面

**核心原则**：**每种业务实体都应该有一个"对象视图"页面**，作为查看该实体全部相关信息的枢纽。

#### 需创建的对象视图

| 实体 | Full View 内容 | Panel View 内容 |
|------|---------------|-----------------|
| **Requirement** | 属性表、来源链接、情感分析、关联 Report、关联 Opportunity、相似需求（向量检索） | 标题、情感、置信度、来源 |
| **Opportunity** | 评分雷达图、Traction Signal、源需求表、生成的 Proposal | 标题、总分、关键词 |
| **Proposal** | 完整文档、问题陈述、MVP 范围、技术栈、工时估算、克隆 prompt 按钮 | 标题、状态、工时 |
| **Report** | 报告正文、数据来源统计、关联需求列表、验证结果 | 标题、关键词、生成时间 |
| **CrawlTask** | 执行详情、统计图表、爬取结果、所属 Pipeline | 状态、平台、新增数量 |

#### 前端路由规划

```
/objects/requirement/:id     →  RequirementView.vue
/objects/opportunity/:id     →  OpportunityView.vue
/objects/proposal/:id        →  ProposalView.vue
/objects/report/:id          →  ReportView.vue
/objects/crawl-task/:id      →  CrawlTaskView.vue
```

#### Requirement Object View 的布局建议

```
┌─────────────────────────────────────────────────────────┐
│ ← Back to Requirements Pool                             │
│                                                         │
│ # 📋 [需求] 用户希望 Notion 支持离线编辑                 │
│                                                         │
│ [Tab: 概览] [Tab: 相关报告] [Tab: 相似需求]              │
├─────────────────────────────────────────────────────────┤
│ 📊 核心属性 (Prominent Properties)                       │
│ ┌─────────────────┐ ┌──────────────┐ ┌───────────────┐  │
│ │ 情感: strong    │ │ 置信度: 0.92 │ │ 提及: 8 次    │  │
│ │ 情绪: negative  │ │ 来源: GitHub │ │ 关键词: Notion │  │
│ └─────────────────┘ └──────────────┘ └───────────────┘  │
│                                                         │
│ 📝 描述 / 痛点 / 用例                                    │
│ Knowledge workers who travel frequently need offline    │
│ editing support without internet connectivity.          │
│                                                         │
│ 🔗 关联对象 (Linked Objects)                             │
│ ├─ 📄 来源讨论 (1)  → [GitHub Issue #4521]              │
│ ├─ 📊 分析报告 (2)  → [Notion竞品分析] [协作工具趋势]   │
│ └─ 💼 需求机会 (1)  → [Notion替代品: 离线优先笔记]      │
│                                                         │
│ 🔍 相似需求 (向量检索 Top 5)                             │
│ ├─ "Obsidian 应该支持实时协作" (相似度: 0.89)           │
│ └─ ...                                                  │
│                                                         │
│ ⚡ 动作 (Actions)                                        │
│ [标记为已验证] [关联到需求] [生成报告] [导出]           │
└─────────────────────────────────────────────────────────┘
```

### 8.4 建议三：引入 Interface Mixin

**新文件**：`src/needradar/schemas/mixins.py`

```python
# Pydantic mixins，定义可复用的"形状"（类似 Palantir 的 Interface）

class HasSource:
    """有来源链接的实体"""
    source_platform: str
    source_url: str

class HasSentiment:
    """有情感分析的实体"""
    sentiment: SentimentEnum
    emotion: EmotionEnum

class HasScore:
    """可评分的实体"""
    overall_score: float
    score_breakdown: dict

class HasVaultPath:
    """在 Vault 中有文件的实体"""
    vault_path: str
    vault_stage: str
```

**使用方式**：
```python
class RequirementResponse(BaseModel, HasSource, HasSentiment, HasVaultPath):
    title: str
    description: str
    # ... 自有字段

class CrawlTaskResponse(BaseModel, HasSource):
    keyword: str
    status: str
    # ... 自有字段
```

**前端效果**：可以写通用组件处理"所有带 Sentiment 的对象"、"所有有 SourceURL 的对象"。

### 8.5 建议四：Action Type 建模

**概念模型**：

```python
# 预定义动作注册表
ACTION_REGISTRY = {
    "generate_report": {
        "display": "生成分析报告",
        "target": "requirement[]",
        "params": {"keyword": "str"},
        "side_effects": ["create:report", "create:entity_link(report->requirements)", "write:vault"],
    },
    "generate_proposal": {
        "display": "生成项目提案",
        "target": "opportunity",
        "params": {},
        "side_effects": ["create:proposal", "create:entity_link(proposal->opportunity)", "write:vault"],
    },
    "cluster_opportunities": {
        "display": "聚类分析机会",
        "target": "requirement[]",
        "params": {"keyword": "str"},
        "side_effects": ["create:opportunity[]", "create:entity_link(opportunity->requirements)"],
    },
    "verify_report": {
        "display": "验证报告",
        "target": "report",
        "params": {},
        "side_effects": ["create:verification_result", "update:report.status"],
    },
    "mark_verified": {
        "display": "标记为已验证",
        "target": "requirement",
        "params": {},
        "side_effects": ["update:requirement.frontmatter", "log:audit"],
    },
    "link_entities": {
        "display": "关联实体",
        "target": "(any, any)",
        "params": {"source_type": "str", "source_id": "str", "link_type": "str", "target_type": "str", "target_id": "str"},
        "side_effects": ["create:entity_link"],
    },
}
```

**效果**：前端按钮、CLI 命令、API endpoint 都可以从这个注册表自动生成。

### 8.6 建议五：自动生成 TypeScript 类型

**利用 Pydantic 自动生成前端类型**：

```bash
# 使用 datamodel-code-generator
python scripts/generate_types.py  # → frontend/src/api/generated/types.ts
```

**输出示例**：
```typescript
// 自动生成，与后端 Pydantic Schema 同步
export interface EntityLinkResponse {
  id: number
  source_type: string
  source_id: string
  link_type: string
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface RequirementResponse {
  title: string
  description: string
  source_platform: string
  source_url: string
  sentiment: 'strong' | 'moderate' | 'mild'
  emotion: 'positive' | 'negative' | 'neutral'
  confidence: number
  mention_count: number
  keyword: string
  vault_path: string
  linked_objects: EntityLinkResponse[]
  created_at: string
}
```

### 8.7 建议六：实体注册表

**新文件**：`src/needradar/core/entity_registry.py`

```python
ENTITY_REGISTRY = {
    "requirement": {
        "display_name": "需求",
        "display_name_en": "Requirement",
        "icon": "📋",
        "storage": "vault",
        "stage": "需求",
        "schema": "RequirementResponse",
        "links_from": ["derived_from.raw_discussion", "analyzed_by.report", "clustered_into.opportunity"],
        "links_to": [],
        "actions": ["mark_verified", "link_entities", "generate_report"],
        "prominent_properties": ["sentiment", "confidence", "mention_count", "source_platform"],
    },
    "opportunity": {
        "display_name": "机会",
        "display_name_en": "Opportunity",
        "icon": "💼",
        "storage": "database",
        "schema": "OpportunityResponse",
        "links_from": [],
        "links_to": ["contains.requirement", "generates.proposal"],
        "actions": ["generate_proposal", "refresh_scores"],
        "prominent_properties": ["overall_score", "demand_intensity"],
    },
    # ... 每种实体一个条目
}
```

**效果**：
- 前端可动态渲染对象视图 → 无需为每种实体硬编码页面
- CLI 可自动发现实体类型和可用动作
- 新增实体类型只需在注册表加一个条目 + 定义 Schema

### 8.8 优先级路线图

| 阶段 | 内容 | 预期效果 | 工作量估计 |
|------|------|----------|-----------|
| **Phase 1** | `EntityLink` 模型 + 迁移脚本（替代 JSON/字符串引用） | 关系查询可用，为 Object View 打基础 | 2-3 天 |
| **Phase 2** | Requirement + Opportunity Object View 前端页面 | 体验提升明显，验证范式有效性 | 3-5 天 |
| **Phase 3** | Interface mixin + 实体注册表 | 减少重复代码，新增实体更高效 | 2-3 天 |
| **Phase 4** | Proposal/Report/CrawlTask Object View | 完整覆盖所有实体 | 3-4 天 |
| **Phase 5** | Action Type 建模 + TypeScript 类型自动生成 | 达到 Ontology 范式的基本形态 | 3-5 天 |

---

## 附录 A：Palantir Ontology 术语速查

| 术语 | 英文 | 定义 | NeedRadar 类比 |
|------|------|------|----------------|
| 对象类型 | Object Type | 现实实体/事件的 schema | Requirement, Opportunity |
| 对象 | Object | 对象类型的单个实例 | 一个具体的需求卡片 |
| 对象集 | Object Set | 多个对象的集合 | 按关键词过滤的需求列表 |
| 属性 | Property | 对象类型的特征 | Vault frontmatter 字段 |
| 属性值 | Property Value | 属性的具体值 | frontmatter 中的具体数据 |
| 共享属性 | Shared Property | 跨对象类型的属性定义 | 无（建议引入） |
| 链接类型 | Link Type | 两个对象类型间的关系 | EntityLink 模型 |
| 链接 | Link | 关系的单个实例 | 一条 EntityLink 记录 |
| 动作类型 | Action Type | 对对象的修改操作定义 | generate_report 等 |
| 函数 | Function | 代码化业务逻辑 | LLM extraction/scoring |
| 接口 | Interface | 对象类型的抽象契约 | HasSource, HasSentiment |
| 角色 | Role | Ontology 层权限 | 未实现 |
| 对象视图 | Object View | 对象的完整信息枢纽 | /objects/* 页面 |
| OSDK | Ontology SDK | 自动生成的类型安全 SDK | REST API + 手动类型 |

## 附录 B：关键参考来源

1. [Palantir Foundry — Core Concepts](https://palantir.com/docs/foundry/ontology/core-concepts/)
2. [Palantir Foundry — The Ontology System](https://palantir.com/docs/foundry/architecture-center/ontology-system/)
3. [Palantir Foundry — Object Views Overview](https://www.palantir.com/docs/foundry/object-views/overview/)
4. [Palantir Foundry — Standard Object Views](https://palantir.com/docs/foundry/object-views/standard-object-views/)
5. [Palantir Foundry — Custom Object View Configuration](https://palantir.com/docs/foundry/object-views/config-overview/)
6. [Palantir Foundry — Ontology SDK Overview](https://palantir.com/docs/foundry/ontology-sdk/overview/)
7. [Palantir Foundry — Object Types Overview](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)
8. [Palantir Foundry — Properties Overview](https://palantir.com/docs/foundry/object-link-types/properties-overview/)
9. [Architecting Palantir Foundry Ontologies (oboe.com)](https://oboe.com/learn/architecting-palantir-foundry-ontologies-rfub51)
10. [OSDK Tutorial: External Tenant Portal (YouTube)](https://www.youtube.com/watch?v=9hE5dv5ASYc)

---

> **Next Steps**: 从 Phase 1 开始——引入 `EntityLink` 模型并做一次小规模迁移。验证"可遍历关系图"的价值后，再推进 Phase 2 的 Object View 页面。

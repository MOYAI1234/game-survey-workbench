# Game Survey Workbench 1.0 验收修复设计

**日期：** 2026-03-15

**状态：** 1.0 closeout — 不再增加功能，只修可交付性问题

## 当前产品状态

- Stage 1–7 全部完成，212 tests passing
- 核心循环 `知识库 → 问卷设计 → 数据分析 → Markdown 报告` 在浏览器中可走通
- LLM 降级提示（未配置时）已有初步处理
- 启动脚本 `run.bat` 和 `.env.example` 已创建

## 问题分类与验收判定

### 1.0 阻塞项（不修就不能交付）

| 编号 | 分类 | 问题 | 严重程度 |
|------|------|------|----------|
| A1 | 崩溃 | 知识上传 route 无 try/except，文件格式错误直接 500 | P0 |
| A2 | 崩溃 | 数据导入 form route 的 ValueError 返回裸 JSON 而非用户友好页面 | P0 |
| A3 | 崩溃 | 问卷 refine-form 在非 LLM 异常时无 catch，直接 500 | P0 |
| B1 | 中文化 | 首页表单全英文：Create New Project / Slug / Project Name / Description | P0 |
| B2 | 中文化 | 项目详情 Brief 表单全英文：Background / Objectives / Hypotheses / Target Audience / Success Criteria | P0 |
| B3 | 中文化 | 分析页全英文：Dataset Schema / Column / Type / In Analysis / Yes/No | P0 |
| B4 | 中文化 | 分析页步骤名全英文：Dataset Imported / Text Coding / Insight Synthesis / Report Generated | P0 |
| B5 | 中文化 | 问卷页/报告页/历史页标题和标签全英文 | P0 |
| B6 | 中文化 | 所有 placeholder 英文（"e.g. Understand player satisfaction drivers"） | P0 |
| C1 | 反馈缺失 | 知识上传后静默重定向，无成功/失败提示 | P0 |
| C2 | 反馈缺失 | 数据上传成功后直接跳转，无确认提示 | P1 |
| C3 | 反馈缺失 | Brief 保存后无反馈 | P1 |
| C4 | 引导缺失 | 各步骤之间无"下一步"指引 | P1 |
| C5 | 引导缺失 | 数据上传缺中文格式说明和模板下载链接 | P1 |
| D1 | 内部泄露 | analysis_run_id 直接显示给用户 | P1 |
| D2 | 内部泄露 | 报告历史页显示文件系统路径 | P1 |
| D3 | 内部泄露 | Task Plan 空状态显示 `PUT /projects/{slug}/plan` API 端点 | P0 |
| D4 | 内部泄露 | workflow badges 显示 "coding_complete" 等内部事件名 | P1 |
| D5 | 内部泄露 | 空项目列表显示 `POST /projects` API 指令 | P0 |
| E1 | 空状态 | 首页混合中英文："暂无项目。Use POST /projects to create one." | P0 |

### 延后到 2.0 的增强项（不影响 1.0 交付）

| 编号 | 方向 | 理由 |
|------|------|------|
| F1 | 全局知识库（跨项目共享） | 需要新的数据模型和路由，属于架构增强 |
| F2 | 语义检索替代 TF-IDF | 需引入 embedding 模型或 API，属于核心能力升级 |
| F3 | 自动知识分类/标签/可视化命中 | 需要新 UI 组件和检索反馈机制 |
| F4 | 数据上传智能清洗和格式纠正 | 当前双表头规范可用，智能纠正属于增强 |
| F5 | 知识库管理台（搜索、标签、浏览） | 需要新页面，1.0 靠项目详情页够用 |
| F6 | LLM prompt 中文化 | 问卷/报告输出语言由 prompt 决定，1.0 保持英文输出可接受 |
| F7 | 统计显著性检验 | 确定性分析已可用，显著性是增强 |
| F8 | 图表可视化 | 需引入图表库，属于新功能 |
| F9 | Word/PDF 导出 | Markdown 是产品定位，导出属于增强 |
| F10 | 加载状态/进度条 | 长操作无反馈体验差，但功能可用，属于 polish |

### 划分原则

- **1.0 阻塞 = 用户无法正常操作 或 看到不应该看到的东西**
  - 500 错误、静默失败 → 阻塞
  - 全英文界面（中文用户无法理解操作含义） → 阻塞
  - 内部 API 概念暴露给终端用户 → 阻塞
  - 操作无任何反馈 → 阻塞

- **2.0 延后 = 功能结构完整但不够好**
  - 检索质量不够高但能用 → 延后
  - 知识库不能跨项目但能用 → 延后
  - 没有图表但数据文字可读 → 延后
  - 没有导出但 Markdown 可复制 → 延后

## 修复范围边界

1. **只改模板层和路由层**，不改模型定义、服务逻辑、检索引擎
2. **只做文案替换和错误处理**，不做 UI 重构或组件化
3. **不加新依赖**
4. **不改产品方向**，遵守 north-star 约束
5. **问卷/报告输出内容可以是英文**，但操作界面（按钮、标签、提示、引导）必须中文

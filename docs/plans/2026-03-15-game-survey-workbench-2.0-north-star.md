# Game Survey Workbench 2.0 北极星

**日期：** 2026-03-15

**状态：** 已启动，2.0A / 2.0B 已进入实现

**前置条件：** 1.0 验收通过

## 定位

2.0 不改变产品形态（仍然是本地 Web 研究工作台），而是在 1.0 可用的基础上提升三个维度：

1. **知识智能** — 从被动文档存储到主动研究辅助
2. **数据宽容** — 从严格规范到智能适配
3. **研究连续性** — 从单项目孤岛到跨项目经验复用

## 核心方向

### 方向一：全局知识库

**现状（1.0 验证发现）：**

存储层已经是全局共享的——知识文档保存在 `workspace/knowledge/`，检索时 `LocalVectorStore.query()` 搜索全部 chunk，仅靠 `knowledge_pack` 做筛选。但 UI 把上传入口放在项目详情页，用户误以为知识是项目私有的。

这意味着"全局知识库"不需要重新设计存储层，而是需要：

1. **新增知识库管理页面**（独立于项目），让用户看到所有已入库文档
2. **项目页改为"选择/筛选"**，而非"上传"——从全局知识库中勾选当前项目需要的知识
3. **上传入口移到知识库管理页**，项目页只保留快捷补充入口
4. 全局知识支持分类、标签、优先级
5. 显示每篇文档的入库状态、被哪些项目使用、命中频率

**目标：**
- 知识库管理页：搜索、浏览、标签过滤、删除、上传
- 项目内知识选择器：从全局知识库勾选，而非逐个上传
- 知识使用统计：哪些文档被频繁命中，哪些从未被使用

**价值：** 行业知识（如品类趋势、设计范式、竞品报告）不需要每个项目重复上传。研究者可以维护一个持续增长的知识库，每个新项目自动受益。

### 方向二：检索策略分层升级

**现状：** LocalVectorStore 使用 TF-IDF 关键字匹配，所有知识文档混在同一个检索池里统一打分。这导致一个根本矛盾：

- **方法论知识**（问卷设计原则、编码方法论、李克特量表原理等）与当前业务场景 query 词汇交集很小，TF-IDF 永远得分低，但它们在每次执行对应任务时都应该被引用
- **领域知识**（手游玩家行为报告、竞品分析、付费转化研究等）才应该根据业务场景内容做相似度检索

embedding 升级也无法解决这个问题，因为"手游内购转化"和"survey measurement validity"在语义空间里本就距离很远——这是领域跨度问题，不是词面匹配问题。

**目标：**

**第一步：双池检索（主要改动）**
- Pool A（方法论池）：按任务类型强制拉取，不参与相似度打分
  - `stages` 标签包含当前任务阶段的文档无条件进入 context
  - 例：触发问卷设计 → 总是拉 `stages=questionnaire_design` 的文档
  - 例：触发文本编码 → 总是拉 `stages=coding` 的文档
- Pool B（领域知识池）：按内容相似度检索，走现有 TF-IDF
  - `doc_type = experience / research / benchmark` 的文档
  - 用项目 Brief 的业务描述作为 query
- 最终 context = Pool A top-3 + Pool B top-5，合并去重
- `priority >= 8` 的文档强制进入 context（无论得分）

**第二步：Query 扩展（辅助改动）**
- 用项目 Brief 的 research_goal 做检索前，扩展领域桥接词汇
- 例：brief 含"手游玩家付费意愿" → 自动追加 "willingness to pay, in-app purchase, consumer behavior" 作为检索词
- 桥接词典作为配置文件维护，不需要 AI

**第三步：Embedding 升级（后续可选）**
- 在双池检索稳定后，可将 Pool B 的 TF-IDF 替换为 embedding 相似度
- 本地小模型（如 `sentence-transformers/paraphrase-multilingual`）或 API embedding
- 保留 TF-IDF 作为无 embedding 环境的 fallback
- 此步骤优先级低于前两步，待 2.0 验收后根据实际效果再决定

**实现路径（最小改动，改 `retrieve_project_knowledge()` 函数）：**
```python
def retrieve_project_knowledge(session, project_slug, task_stage, query, top_k=8):
    # Pool A：按 stage 强制拉取方法论文档
    pool_a = [c for c in all_chunks
              if task_stage in c.stages or c.priority >= 8][:3]

    # Pool B：TF-IDF 检索领域知识
    domain_chunks = [c for c in all_chunks
                     if c.doc_type in ("experience", "research", "benchmark")]
    pool_b = tfidf_query(domain_chunks, query, top_k=5)

    return deduplicate(pool_a + pool_b)
```

`stages`、`doc_type`、`priority` 字段均已存在，不改存储层，只改检索逻辑。

**价值：** 方法论文献不再因词汇跨度问题被排除，领域知识仍按内容相关性检索，两类知识各得其所，直接提升问卷、编码、洞察的输出质量。

### 方向三：智能数据适配与大规模文本处理

**现状一：数据格式** 数据上传必须严格遵循双层表头规范，格式不对直接 400。

**现状二：开放文本编码规模限制** 文本编码将某列的所有响应拼成一个 prompt 发给 LLM。数据量较大时（如 3000 条 × 平均 50 字 = 15 万字）会超出模型 context window，导致截断或报错。

**目标一：数据格式宽容化**
- 上传后自动检测格式，给出修复建议（而非直接拒绝）
- 支持常见问卷平台导出格式的自动识别（问卷星、SurveyMonkey 等）
- 支持单层表头 + 启发式题型推断（作为 fallback）
- 上传后展示数据预览和题型确认界面

**目标二：分批文本编码**
- 超过阈值（如 500 条响应）时自动切换为分批模式
- 每批独立提取主题，再做二次归并去重
- 进度反馈：显示"第 2/6 批处理中…"

**分批编码实现路径（改 `text_coding.py` 服务层）：**
```python
BATCH_SIZE = 300  # 每批最多 N 条响应

def code_open_text_column(responses, ...):
    if len(responses) <= BATCH_SIZE:
        return _code_single_batch(responses, ...)  # 现有逻辑不变

    # 分批编码
    batches = [responses[i:i+BATCH_SIZE]
               for i in range(0, len(responses), BATCH_SIZE)]
    batch_themes = [_code_single_batch(b, ...) for b in batches]

    # 二次归并：把各批主题合并，让 LLM 去重并统一命名
    return _merge_themes(batch_themes, ...)
```

路由层和模型层不变，只改服务层函数内部逻辑。

**价值：** 数据格式宽容化降低入门门槛；分批编码解除数据规模瓶颈，支持千级别以上的开放题数据集。

### 方向四：知识可视化与命中反馈

**现状：** 用户看不到系统检索了哪些知识、命中了哪些片段、相关度如何。

**目标：**
- 问卷设计页展示 "本次使用了 N 篇知识文档，最相关的 3 条："
- 洞察生成页展示命中知识的标题和片段摘要
- 提供知识命中率统计：哪些文档被频繁命中，哪些从未被使用

**价值：** 让研究者理解 AI 决策依据，建立对输出的信任。

### 方向五：跨项目经验复用

**现状：** 报告→知识反馈已实现（Stage 4E），但只是保存为文件，无主动复用机制。

**目标：**
- 历史项目的洞察和报告发现自动进入全局知识库
- 新项目创建时推荐相关历史项目
- 支持"从历史项目克隆"快速启动新研究
- Brief 编写时参考历史项目的研究目标和假设

**价值：** 研究经验不再丢失，每个项目都站在前人肩膀上。

### 方向六：Prompt 中文化与输出语言控制

**现状：** LLM prompt 为英文，输出语言取决于模型行为，不可控。

**目标：**
- Prompt 模板支持中英文切换（项目级配置）
- 问卷输出语言可指定（中文/英文/跟随 prompt）
- 报告模板支持中文章节标题

**价值：** 中文用户得到中文研究产出，减少翻译成本。

### 方向七：知识来源格式扩展（PDF / Word 自动转换）

**现状：** 知识库入库只支持 `.md` 文件。实际研究工作中，知识来源大量是 PDF 报告（行业白皮书、竞品分析、学术论文）和 Word 文档。

**目标：**
- 支持直接上传 `.pdf`、`.docx`、`.pptx` 格式文件
- 上传时自动转换为 Markdown，再走现有入库流程（不改服务层）
- 转换工具优先使用 `markitdown`（微软出品，Python 原生，支持 PDF/Word/PPT/Excel，无需 API）
- 转换失败时给出明确提示和手动编辑入口

**实现路径（最小改动）：**
```python
# 在 knowledge_ingest.py 上游加一个格式检测 + 转换步骤
from markitdown import MarkItDown
md = MarkItDown()
result = md.convert(uploaded_file_path)
markdown_text = result.text_content
# 之后走现有 ingest 流程
```

**依赖：** `pip install markitdown`（新增一个 Python 依赖，可选安装）

**价值：** 行业报告、白皮书不再需要手动转 Markdown，极大降低知识入库的准备成本。

### 方向八：产品界面视觉升级

**现状：** 1.0 使用手写 CSS（约 250 行 `app.css`），功能可用但视觉较为粗糙。

**目标：**
- 引入轻量 CSS 框架，不改变 Jinja2 模板结构，不增加构建步骤
- 候选方案：
  - **Pico CSS**（推荐首选）：CDN 引入，语义 HTML 自动美化，对 `<form>/<table>/<button>` 零改动即生效
  - **Tailwind CSS CDN**：更精细可控，但需要替换大量 class
- 界面层级、信息密度、中文排版优化
- 移动端基本可读（不做响应式大改）

**实现路径（Pico CSS 最小改动）：**
```html
<!-- 在 templates/layout.html 的 <head> 加一行 -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
```

**价值：** 产品从"可用"升级到"好用"，降低用户认知负担，提升汇报和演示时的可信度。

### 方向九：LLM 生成过程流式反馈

**现状：** 问卷生成、洞察合成、文本编码等操作触发后，页面无任何进度提示，用户只能等待静默重定向，不清楚系统是否在正常运行。

**目标：**
- LLM 调用期间展示加载状态（进度条或 spinner）
- 理想状态：支持流式输出（SSE / Server-Sent Events），逐字显示生成内容
- 最小可行状态：按钮变为"生成中…"禁用态 + 超时提示
- 优先在问卷生成页实现，其次是洞察生成

**实现路径建议：**
- **最小改动**：表单提交后用 JS 禁用按钮并显示 spinner，等待重定向
- **完整方案**：后端 LLM 路由改为 `StreamingResponse`（FastAPI 原生支持），前端用 `EventSource` 接收并实时渲染
- 不引入 WebSocket，保持 HTTP-only

**价值：** 解决"生成黑盒"体验，用户知道系统在工作，减少误操作（重复点击/刷新）。

### 方向十：问卷中英双语版本与下载

**现状：** 问卷只生成单语言 Markdown，无下载入口，研究者需手动复制后在外部工具处理。

**目标：**
- **双语问卷**：单次生成输出上半部分英文、下半部分中文（两套完整问卷，分隔线隔开），不做题目级别的中英穿插
- **下载功能**：
  - 下载 `.md` 文件（现有内容直接输出）
  - 下载 `.txt` 纯文本（去除 Markdown 格式符号）
  - 可选：下载 `.docx`（使用 `python-docx`，新增依赖）
- 问卷详情页增加下载按钮区域

**实现路径（最小改动）：**
```python
# routes/questionnaires.py 增加下载路由
@router.get("/projects/{slug}/questionnaires/{version_id}/download")
def download_questionnaire(slug: str, version_id: str, fmt: str = "md"):
    # fmt = "md" | "txt"
    # 从 DB 读取 markdown_spec，按格式处理后返回 FileResponse
```

**双语 Prompt 策略：**
```
# 在 questionnaire_design prompt 末尾追加：
After the English questionnaire, add a horizontal divider (---), then provide
the complete Chinese translation of the same questionnaire below.
```

**价值：** 游戏调研问卷通常需要同时面向国内外玩家，双语版直接可用，省去翻译和排版工作；下载功能让问卷能进入实际分发流程。

### 方向十一：报告中文化与下载

**现状：** 报告由 `report_builder.py` 的章节注册表驱动，章节标题为英文，输出 Markdown；报告详情页只能浏览，无下载入口。

**目标：**
- **报告中文化**：
  - 章节标题改为中文（如 `## Research Methodology` → `## 研究方法`）
  - Prompt 追加中文输出指令，确保叙述文本为中文而非跟随模型默认行为
  - 项目级配置语言偏好（中文/英文），默认中文
- **报告下载功能**：
  - 下载 `.md` 文件（现有报告内容直接输出）
  - 下载 `.txt` 纯文本版
  - 可选：下载 `.docx`（与问卷 `.docx` 共用 `python-docx` 依赖）
- 报告详情页增加下载按钮区域，与问卷下载区域保持一致的交互设计

**实现路径（最小改动）：**
```python
# routes/reports.py 增加下载路由
@router.get("/projects/{slug}/reports/{report_id}/download")
def download_report(slug: str, report_id: int, fmt: str = "md"):
    # 从 ReportRecord 读取 path（已持久化的 .md 文件），按格式处理后返回 FileResponse
```

```python
# services/report_sections.py 章节标题中文化示例：
SECTION_REGISTRY = {
    "methodology": {"title": "研究方法", "order": 1},
    "findings": {"title": "核心发现", "order": 2},
    "recommendations": {"title": "行动建议", "order": 3},
    "evidence": {"title": "证据基础", "order": 4},
}
```

**与方向十的关系：** 问卷下载（方向十）和报告下载（方向十一）共用相同的下载路由模式和可选 `.docx` 依赖，建议同一个 stage 一起实现，复用下载基础设施。

**价值：** 中文报告直接可用于内部汇报和归档，下载功能让报告脱离工具本身独立流通，不依赖研究者手动复制。

## 非目标（2.0 仍然不做）

- 多用户协作
- 权限系统
- 云端部署
- 原生桌面客户端
- BI/Dashboard 产品化
- 复杂工作流编排引擎
- 问卷分发和回收

## 优先级建议

如果 2.0 必须分阶段：

| 阶段 | 方向 | 理由 |
|------|------|------|
| 2.0A | 全局知识库 + 知识管理页 | 基础设施，后续方向都依赖它。存储层已就绪，主要工作是 UI 和路由 |
| 2.0B | 检索策略分层（双池 + query 扩展，embedding 可选后续） | 解决方法论知识和领域知识混池问题，直接提升输出质量 |
| 2.0C | 智能数据适配 + 分批文本编码 | 降低格式门槛；解除大规模开放文本的处理瓶颈 |
| 2.0D | 知识可视化 + 命中反馈 | 建立用户信任 |
| 2.0E | 知识来源格式扩展（PDF/Word） | 与 2.0A 知识管理页配套，降低知识入库门槛 |
| 2.0F | 跨项目经验复用 | 长期价值积累 |
| 2.0G | Prompt 中文化 | 跟随用户需求优先级 |
| 2.0H | 界面视觉升级（Pico CSS） | 不阻塞核心功能，可随时并入任何阶段 |
| 2.0I | LLM 生成流式反馈 | 最小改动可先做 spinner，完整方案做 SSE 流式输出 |
| 2.0J | 问卷双语版 + 下载 | 直接提升问卷可用性，Prompt 改动极小，下载路由新增即可 |
| 2.0K | 报告中文化 + 下载 | 与 2.0J 共用下载基础设施，建议同阶段实现；章节标题中文化改动极小 |

## 当前执行状态

截至 2026-03-19：

- `2.0A 全局知识库`：已完成并合并到 `master`
  - 共享知识库页已升级为全局管理页，支持基础筛选与元数据浏览
  - 项目页已改为“项目知识选择”，不再以项目内上传作为主入口
- `2.0B 检索策略分层升级`：已完成并合并到 `master`
  - 项目检索已切到“仅在已选知识集合内检索”
  - 已实现双池检索的首版：方法论池 + 领域知识池
  - 问卷页与分析页已开始展示基础命中反馈
- `2.0C 智能数据容错 + 分批编码`：已完成
  - 数据导入新增 `upload-preview -> confirm-import` 两步流，支持双表头与单表头 CSV/Excel 的格式检测、题型推断和预览确认
  - `DatasetRecord` 已记录 `format_type` 与 `column_overrides_json`，便于后续追踪用户确认过的列级 schema
  - 新增 `CodingJob` / `CodingBatch` 持久化模型与分批编码服务，大样本开放题会自动走串行 batch + rolling codebook 路径
  - 新增编码任务路由、merge-review 页面与 staging 清理工具
  - 2026-03-19 最终验证：`pytest -v` 通过（274 passed），`python -m compileall src` 通过
- `2.0D 知识来源格式扩展`：已完成
  - 新增 `markitdown` 依赖，支持直接上传 PDF、Word、PowerPoint 文件
  - 非 Markdown 文件经自动转换后展示预览页，用户可确认入库、下载副本或放弃
  - 转换质量检测：自动识别空内容和乱码，给出警告
  - `KnowledgeDocument` 新增 `source_format` 字段追溯原始格式
  - 知识库页面显示来源格式标签，上传表单已支持 `.pdf` / `.docx` / `.pptx`
  - 2026-03-19 最终验证：`pytest -v` 通过（288 passed, 3 skipped），`python -m compileall src` 通过

这意味着 2.0A / 2.0B / 2.0C / 2.0D 的首轮实现已经全部落地，2.0 已从方向储备进入可持续迭代阶段。后续优先级可以转向更高阶段，但应优先围绕当前闭环补手动体验、性能与稳定性。

## 与 1.0 north-star 的关系

2.0 不改变 1.0 north-star 中定义的产品形态和核心循环。所有方向都是在 `Knowledge Base → Questionnaire Design → Data Analysis → Markdown Report` 循环内部的增强，不是新产品方向。

1.0 north-star 中明确的非目标（多用户、SaaS、原生客户端等）在 2.0 中继续保持为非目标。

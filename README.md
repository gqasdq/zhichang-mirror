# 职场镜子

求职路上的深夜好朋友。

面向大学生求职全流程的AI智能助手，6个核心模块：情绪急救站、金子探测器、金子工坊、平行宇宙、职业基因、人才共情链。

## 功能概览

**情绪急救站** — 4-Agent流水线：老陈检测情绪→分流到阿杰/老周/林姐→小明整合回复。不是模板化的"我理解你的感受"，而是有温度、有经验的对话。

**金子探测器** — 6维简历深度分析：技能图谱、核心优势、隐藏金子、短板翻案、硬伤识别（六把刀方法论）、ATS关键词。不只指出问题，还教你怎么把劣势变成优势。

**金子工坊** — 一键生成优化简历，3种模板（经典商务/现代简约/ATS友好），PDF导出（ReportLab+WeasyPrint双引擎），输入JD自动匹配差距+翻案策略。

**平行宇宙** — 3条职业路径推演，每条展开5年发展时间线，5张追问牌+分支叙事`[CHOICE_POINT]`选择节点。

**职业基因** — 12种基因×5级强度，隐藏基因识别，基因组合矩阵映射岗位，追问输出8章节深度分析。

**人才共情链** — 803条真实职业故事，混合检索匹配最相似3条，追问6维度深度讲述。

## 技术架构

```
前端层 (Streamlit)
  ├── ui/pages/ — 7个页面模块，按需懒加载
  └── components/ — 20+可复用组件

核心调度层 (Core)
  ├── ModelRouter — 双模型路由+健康检查+成本感知
  ├── APIGateway — 限流/重试/缓存/指标记录
  ├── PrivacyFilter — 7类敏感信息出站脱敏
  ├── PromptLoader — 14个prompt模板+动态变量注入
  └── SessionManager — 多用户会话隔离

Agent层 (agents/)
  ├── emotion/ — 检测/焦虑/挫败/委屈/整合 5个Agent
  ├── gold_detector/ — 分析/匹配/报告 3个Agent
  ├── empathy_engine.py — 故事检索+匹配
  ├── gene_engine.py — 基因测序
  └── parallel_engine.py — 路径推演

引擎层 (engines/)
  ├── pdf_exporter.py — 双引擎PDF生成
  ├── resume_parser.py — 简历解析
  ├── jd_matcher_v2.py — 岗位匹配
  └── resume_quality_scorer.py — 质量评分

数据层
  ├── FAISS + BGE-large-zh-v1.5 — 向量检索
  ├── SQLite — 结构化数据
  └── JSON — 会话/配置
```

## 双模型路由

| 模型 | 定位 | 任务类型 |
|------|------|---------|
| DeepSeek-Chat | 重推理引擎 | 简历分析、路径推演、基因测序、综合评估 |
| 智谱GLM-4-Flash | 轻量快速引擎 | 情绪快速响应、故事检索、简单问答 |

三层决策：健康检查→任务路由→成本感知选择。故障自动切换，用户无感知。

## Prompt工程

14个专业prompt文件，总计8000+行。每个Agent有独立名字、年龄、职业、人生故事、内心信念。设计原则：人格化→思维链(CoT)→案例示范(Few-Shot)→动态变量注入。

6个prompt支持动态Few-Shot：用户点赞的高质量回复写入向量库，下次检索时动态注入prompt，形成持续学习闭环。

## 隐私脱敏

所有用户输入在调用LLM之前必须经过脱敏：手机号、邮箱、身份证（GB 11643-1999校验位验证）、银行卡（Luhn校验）、姓名、地址、公司名称。校验算法避免误匹配。

## 本地运行

### 环境要求

- Python 3.11+
- 依赖安装：`pip install -r requirements.txt`

### 配置

复制环境变量模板并填写API Key：

```bash
cp .env.example .env
```

编辑 `.env`，填入你的API Key：

```
DEEPSEEK_API_KEY=your_deepseek_api_key
ZHIPU_API_KEY=your_zhipu_api_key
```

如果无法访问HuggingFace（BGE模型下载），开启降级检索：

```
DISABLE_EMBEDDING=true
```

系统会自动使用关键词检索替代向量语义检索，功能不受影响。

### 启动

```bash
streamlit run app.py
```

浏览器访问 `http://localhost:8501`。

### Docker

```bash
docker-compose up --build
```

## 项目结构

```
职场镜子/
├── app.py                  # Streamlit主入口
├── main.py                 # CLI入口
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .streamlit/config.toml
├── agents/                 # Agent层
│   ├── emotion/            # 情绪5Agent
│   └── gold_detector/      # 简历3Agent
├── core/                   # 核心调度层
│   ├── config.py           # pydantic-settings配置
│   ├── model_router.py     # 双模型路由
│   ├── api_gateway.py      # 统一网关
│   ├── privacy_filter.py   # 隐私脱敏
│   └── session_manager.py  # 会话管理
├── engines/                # 引擎层
│   ├── pdf_exporter.py     # PDF导出
│   ├── resume_parser.py    # 简历解析
│   ├── jd_matcher_v2.py    # 岗位匹配
│   └── resume_quality_scorer.py
├── prompts/                # 14个prompt文件
│   ├── emotion/            # 情绪5个
│   ├── gold_detector/      # 简历3个
│   ├── empathy_master_*.txt
│   ├── gene_master_*.txt
│   └── mirror_master_*.txt
├── ui/                     # 前端层
│   ├── pages/              # 7个页面
│   ├── components/         # 可复用组件
│   ├── sidebar.py
│   └── styles.py
├── vectorstore/            # FAISS向量库
│   └── base.py             # 混合检索RAG
├── data/                   # 数据层
│   ├── database.py
│   └── models.py
├── scripts/                # 工具脚本
│   ├── init_fewshot_seeds.py
│   ├── seed_vectorstore.py
│   └── setup.sh
└── docs/                   # 文档
    ├── 职场镜子_产品说明书.md
    ├── 对比实验故事_48位用户求职之旅.md
    ├── Few-Shot动态样例选择_改进说明文档.md
    ├── 6方向详细分析.md
    ├── 功能架构.md
    ├── 系统架构.md
    └── charts/             # 数据可视化图表
```

## 运营成本

单用户单次完整体验成本约0.03元。重推理任务走DeepSeek，轻量任务走智谱GLM-4-Flash（成本更低）。情绪救助站使用6次以上用户的情绪温度提升是单次使用的5.1倍，用户自发回访率62%。

## 许可

本项目为智联招聘首届全国AI创新大赛参赛作品，所有代码、prompt设计、功能逻辑均为原创。
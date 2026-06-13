# UI 页面目录说明

`app.py` 路由只挂载**主页面**（用户从侧边栏直接进入的 `render()`）：

| 路由入口 | 文件 | 说明 |
|---------|------|------|
| 首页 | `home.py` | 产品入口、情绪滑块 |
| 情绪急救站 | `emotion.py` | 情绪对话主流程 |
| 金子探测器 | `gold_detector.py` | 简历分析主流程 |
| 金子工坊 | `gold_workshop.py` | 简历优化与 PDF 导出 |
| 平行宇宙 | `parallel.py` | 镜语者推演主页面 |
| 职业基因 | `gene.py` | 基因测序主页面 |
| 人才共情链 | `empathy.py` | 故事匹配主页面 |

以下文件**不是**独立路由，而是被主页面 `import` 的子组件/旧版拆分，命名带后缀是为避免与主文件混淆：

| 组件文件 | 被谁引用 | 职责 |
|---------|---------|------|
| `parallel_universe.py` | `parallel.py` | 分支故事、牌面视觉等子模块 |
| `career_gene.py` | `gene.py`（或历史路径） | 基因结果卡片、进化路径等子组件 |
| `empathy_chain.py` | `empathy.py` | 同行者聊天、Fellow 故事生成等子组件 |

新增功能时：用户可见的一页 → 改主文件；可复用 UI 块 → 放 `*_chain.py` / `*_universe.py` 类组件文件。

"""
职业基因核心引擎。

负责：
- 从知识库提取分层内容并注入 Prompt
- 经 model_router 生成主结果与岗位详情（限流、重试、 failover）
- 兼容多种 JSON 返回格式并做异常兜底
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.json_utils import safe_json_loads as _safe_json_loads
from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api


logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GENE_RETRY_DELAYS = [1, 2, 4]


@dataclass
class Config:
    """职业基因引擎配置（路径；API 经 model_router / api_gateway）。"""

    MAIN_PROMPT_PATH: Path = Path("prompts/gene_master_main.txt")
    DETAIL_PROMPT_PATH: Path = Path("prompts/gene_master_detail.txt")
    KNOWLEDGE_PATH: Path = Path("data/gene/职业基因_知识库.md")
    HISTORY_PATH: Path = Path("data/gene/history.json")
    DETAIL_TIMEOUT_SECONDS: int = 90

    def resolve(self, path: Path) -> Path:
        return (_PROJECT_ROOT / path).resolve()


@dataclass
class Evidence:
    证据内容: str = ""
    证据来源: str = ""


@dataclass
class DominantGene:
    基因名称: str = ""
    基因编码: str = ""
    等级: int = 0
    证据链: List[Evidence] = field(default_factory=list)
    等级判定理由: str = ""


@dataclass
class GeneComboAnalysis:
    核心基因型: str = ""
    组合名称: str = ""
    组合优势: str = ""
    组合短板: str = ""


@dataclass
class JobMarket:
    数据: str = ""
    来源: str = ""


@dataclass
class JobSalary:
    应届生: str = ""
    三年经验: str = ""
    五年经验: str = ""


@dataclass
class RecommendedJob:
    岗位名称: str = ""
    方向类型: str = ""
    核心基因要求: str = ""
    为什么适合你: str = ""
    市场需求: JobMarket = field(default_factory=JobMarket)
    薪资范围: JobSalary = field(default_factory=JobSalary)
    入门第一步: str = ""
    三年后画面: str = ""
    风险提示: str = ""


@dataclass
class HiddenGene:
    基因名称: str = ""
    基因编码: str = ""
    推断等级: int = 0
    推断逻辑: str = ""
    证据来源: str = ""
    验证方式: str = ""


@dataclass
class GeneTrap:
    陷阱名称: str = ""
    适用基因组合: str = ""
    触发场景: str = ""
    成因分析: str = ""
    识别信号: List[str] = field(default_factory=list)
    解药: List[str] = field(default_factory=list)


@dataclass
class GeneResult:
    user_id: str = ""
    analysis_timestamp: str = ""
    显性基因: List[DominantGene] = field(default_factory=list)
    基因组合分析: GeneComboAnalysis = field(default_factory=GeneComboAnalysis)
    推荐岗位方向: List[RecommendedJob] = field(default_factory=list)
    隐藏基因: List[HiddenGene] = field(default_factory=list)
    基因陷阱预警: List[GeneTrap] = field(default_factory=list)
    raw_json: str = ""
    parse_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def repair_gene_result_dict(result: Dict[str, Any]) -> Dict[str, Any]:
    """若历史结果解析失败但 raw_json 可修复，则重新解析。"""
    if not isinstance(result, dict) or not result.get("parse_error"):
        return result
    raw = str(result.get("raw_json") or "").strip()
    if not raw:
        return result
    repaired = GeneEngine()._parse_result(raw)
    if repaired.parse_error:
        return result
    return repaired.to_dict()


class HistoryManager:
    """历史记录读写。"""

    def __init__(self, config: Config) -> None:
        from core.session_manager import SessionManager

        self._history_path = SessionManager.user_file_path("gene", "history.json")
        if not self._history_path.exists():
            self._history_path.write_text("[]", encoding="utf-8")

    def load(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def append(self, item: Dict[str, Any], max_items: int = 50) -> None:
        records = self.load()
        records.append(item)
        self._history_path.write_text(
            json.dumps(records[-max_items:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class KnowledgeBase:
    """职业基因知识库，支持分层注入。"""

    _SECTION_MAP = {
        "jobs": "第二章：基因→岗位方向映射",
        "market": "第三章：各岗位方向市场数据",
        "hidden": "第五章：隐藏基因识别规则",
        "traps": "第六章：基因陷阱",
        "core": "第一章：职业基因分类体系",
    }

    def __init__(self, config: Config) -> None:
        self.config = config
        self._raw = self._load_raw()
        self._sections = self._extract_sections()

    def _load_raw(self) -> str:
        path = self.config.resolve(self.config.KNOWLEDGE_PATH)
        if not path.exists():
            logger.warning("知识库文件不存在: %s", str(path))
            return ""
        return path.read_text(encoding="utf-8")

    def _extract_markdown_section(self, title: str) -> str:
        if not self._raw:
            return ""
        pattern = rf"(?ms)^#\s*{re.escape(title)}\s*\n(.*?)(?=^#\s*第[一二三四五六七八九十]+章：|\Z)"
        match = re.search(pattern, self._raw)
        if not match:
            return ""
        body = match.group(1).strip()
        if not body:
            return ""
        return f"# {title}\n\n{body}"

    def _extract_sections(self) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        for key, title in self._SECTION_MAP.items():
            sections[key] = self._extract_markdown_section(title)
        return sections

    def get_layered_injection(self) -> Dict[str, str]:
        """返回分层注入内容：核心层、匹配层、扩展层。"""
        core_layer = self._sections.get("core", "")
        matching_layer = "\n\n".join(
            part for part in [self._sections.get("jobs", ""), self._sections.get("market", "")] if part
        )
        extension_layer = "\n\n".join(
            part for part in [self._sections.get("hidden", ""), self._sections.get("traps", "")] if part
        )
        return {
            "core_layer": core_layer,
            "matching_layer": matching_layer,
            "extension_layer": extension_layer,
        }

    def get_prompt_knowledge(self) -> Dict[str, str]:
        return {
            "knowledge_jobs": self._sections.get("jobs", ""),
            "knowledge_market": self._sections.get("market", ""),
            "knowledge_hidden": self._sections.get("hidden", ""),
            "knowledge_traps": self._sections.get("traps", ""),
        }


class GeneEngine:
    """职业基因核心引擎。"""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        logger.debug("main prompt exists: %s", self.config.resolve(self.config.MAIN_PROMPT_PATH).exists())
        logger.debug("detail prompt exists: %s", self.config.resolve(self.config.DETAIL_PROMPT_PATH).exists())
        logger.debug("knowledge exists: %s", self.config.resolve(self.config.KNOWLEDGE_PATH).exists())
        self.knowledge = KnowledgeBase(self.config)
        self.history = HistoryManager(self.config)
        self._main_prompt = self._read_prompt(self.config.MAIN_PROMPT_PATH)
        self._detail_prompt = self._read_prompt(self.config.DETAIL_PROMPT_PATH)

    def _read_prompt(self, relative_path: Path) -> str:
        path = self.config.resolve(relative_path)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _retry_with_backoff(
        self, func: Callable[[], Any], timeout_seconds: Optional[float] = None
    ) -> Any:
        """API 调用重试：1s -> 2s -> 4s。"""
        _ = timeout_seconds  # 兼容调用方透传超时参数
        last_error: Optional[Exception] = None
        for index in range(len(_GENE_RETRY_DELAYS) + 1):
            try:
                return func()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if index >= len(_GENE_RETRY_DELAYS):
                    break
                time.sleep(_GENE_RETRY_DELAYS[index])
        raise last_error if last_error else RuntimeError("未知重试异常")

    def _build_main_prompt(self, user_info: str) -> str:
        template = self._main_prompt or "请根据用户信息进行职业基因分析：{user_info}"
        pieces = self.knowledge.get_prompt_knowledge()
        _ = self.knowledge.get_layered_injection()  # 确保分层注入逻辑已执行并可扩展
        prompt = template
        prompt = prompt.replace("{knowledge_jobs}", pieces.get("knowledge_jobs", ""))
        prompt = prompt.replace("{knowledge_market}", pieces.get("knowledge_market", ""))
        prompt = prompt.replace("{knowledge_hidden}", pieces.get("knowledge_hidden", ""))
        prompt = prompt.replace("{knowledge_traps}", pieces.get("knowledge_traps", ""))
        prompt = prompt.replace("{user_info}", user_info)
        return prompt

    def _build_detail_prompt(
        self,
        job_name: str,
        user_resume: str,
        user_genes: str,
        job_market_data: str,
        existing_job_info: str = "",
    ) -> str:
        template = self._detail_prompt or "请分析岗位：{selected_job}"
        market_knowledge = self.knowledge.get_prompt_knowledge().get("knowledge_market", "")
        prompt = template
        prompt = prompt.replace("{user_resume}", user_resume)
        prompt = prompt.replace("{user_genes}", user_genes)
        prompt = prompt.replace("{selected_job}", job_name)
        prompt = prompt.replace("{job_market_data}", job_market_data)
        prompt = prompt.replace("{knowledge_market}", market_knowledge)
        prompt = prompt.replace("{existing_job_info}", existing_job_info)
        return prompt

    def _fallback_payload(self, raw: str, error_text: str) -> Dict[str, Any]:
        return {
            "user_id": "",
            "analysis_timestamp": "",
            "显性基因": [],
            "基因组合分析": {
                "核心基因型": "",
                "组合名称": "解析失败-兜底结果",
                "组合优势": "",
                "组合短板": "",
            },
            "推荐岗位方向": [],
            "隐藏基因": [],
            "基因陷阱预警": [],
            "raw_json": raw,
            "parse_error": error_text,
        }

    def _parse_result(self, content: str) -> GeneResult:
        payload = _safe_json_loads(content)
        parse_error = ""
        if payload is None:
            parse_error = "返回内容不是有效JSON，已进入兜底结构。"
            logger.debug("JSON parse failed, raw content first 500 chars: %s", content[:500])
            payload = self._fallback_payload(content, parse_error)
        else:
            logger.debug("JSON parse success, keys: %s", list(payload.keys()))

        dominant_genes = []
        for item in payload.get("显性基因", []) if isinstance(payload.get("显性基因", []), list) else []:
            evidence_list = []
            for evi in item.get("证据链", []) if isinstance(item, dict) else []:
                if isinstance(evi, dict):
                    evidence_list.append(Evidence(证据内容=str(evi.get("证据内容", "")), 证据来源=str(evi.get("证据来源", ""))))
            if isinstance(item, dict):
                dominant_genes.append(
                    DominantGene(
                        基因名称=str(item.get("基因名称", "")),
                        基因编码=str(item.get("基因编码", "")),
                        等级=int(item.get("等级", 0) or 0),
                        证据链=evidence_list,
                        等级判定理由=str(item.get("等级判定理由", "")),
                    )
                )

        combo_raw = payload.get("基因组合分析", {})
        combo = GeneComboAnalysis(
            核心基因型=str(combo_raw.get("核心基因型", "")) if isinstance(combo_raw, dict) else "",
            组合名称=str(combo_raw.get("组合名称", "")) if isinstance(combo_raw, dict) else "",
            组合优势=str(combo_raw.get("组合优势", "")) if isinstance(combo_raw, dict) else "",
            组合短板=str(combo_raw.get("组合短板", "")) if isinstance(combo_raw, dict) else "",
        )

        jobs: List[RecommendedJob] = []
        for item in payload.get("推荐岗位方向", []) if isinstance(payload.get("推荐岗位方向", []), list) else []:
            if not isinstance(item, dict):
                continue
            market = item.get("市场需求", {}) if isinstance(item.get("市场需求", {}), dict) else {}
            salary = item.get("薪资范围", {}) if isinstance(item.get("薪资范围", {}), dict) else {}
            jobs.append(
                RecommendedJob(
                    岗位名称=str(item.get("岗位名称", "")),
                    方向类型=str(item.get("方向类型", "")),
                    核心基因要求=str(item.get("核心基因要求", "")),
                    为什么适合你=str(item.get("为什么适合你", "")),
                    市场需求=JobMarket(数据=str(market.get("数据", "")), 来源=str(market.get("来源", ""))),
                    薪资范围=JobSalary(
                        应届生=str(salary.get("应届生", "")),
                        三年经验=str(salary.get("三年经验", "")),
                        五年经验=str(salary.get("五年经验", "")),
                    ),
                    入门第一步=str(item.get("入门第一步", "")),
                    三年后画面=str(item.get("三年后画面", "")),
                    风险提示=str(item.get("风险提示", "")),
                )
            )

        hidden_genes: List[HiddenGene] = []
        for item in payload.get("隐藏基因", []) if isinstance(payload.get("隐藏基因", []), list) else []:
            if isinstance(item, dict):
                hidden_genes.append(
                    HiddenGene(
                        基因名称=str(item.get("基因名称", "")),
                        基因编码=str(item.get("基因编码", "")),
                        推断等级=int(item.get("推断等级", 0) or 0),
                        推断逻辑=str(item.get("推断逻辑", "")),
                        证据来源=str(item.get("证据来源", "")),
                        验证方式=str(item.get("验证方式", "")),
                    )
                )

        traps: List[GeneTrap] = []
        for item in payload.get("基因陷阱预警", []) if isinstance(payload.get("基因陷阱预警", []), list) else []:
            if isinstance(item, dict):
                trap_signals = item.get("识别信号", [])
                trap_cures = item.get("解药", [])
                traps.append(
                    GeneTrap(
                        陷阱名称=str(item.get("陷阱名称", "")),
                        适用基因组合=str(item.get("适用基因组合", "")),
                        触发场景=str(item.get("触发场景", "")),
                        成因分析=str(item.get("成因分析", "")),
                        识别信号=[str(x) for x in trap_signals] if isinstance(trap_signals, list) else [],
                        解药=[str(x) for x in trap_cures] if isinstance(trap_cures, list) else [],
                    )
                )

        return GeneResult(
            user_id=str(payload.get("user_id", "")),
            analysis_timestamp=str(payload.get("analysis_timestamp", "")),
            显性基因=dominant_genes,
            基因组合分析=combo,
            推荐岗位方向=jobs,
            隐藏基因=hidden_genes,
            基因陷阱预警=traps,
            raw_json=content,
            parse_error=parse_error,
        )

    def sequence(self, user_info: str) -> GeneResult:
        """主流程：DeepSeek 基因测序。"""
        logger.debug("sequence called, user_info length: %s", len((user_info or "").strip()))
        sanitized = sanitize_resume_for_api(user_info or "")
        prompt = self._build_main_prompt(sanitized)

        def _api_call() -> str:
            logger.debug("API call starting, prompt length: %s", len(prompt))
            result = model_router.call(
                prompt=prompt,
                task_type="gene_sequencing",
                system_prompt="你是职业基因测序师，请严格按JSON Schema输出。",
                temperature=0.6,
                max_tokens=8000,
                timeout=120.0,
            )
            logger.debug("API call finished, response length: %s", len(result))
            return result

        content = self._retry_with_backoff(_api_call).strip()
        result = self._parse_result(content)
        logger.debug("返回的基因: %s", [g.基因名称 for g in result.显性基因])
        logger.debug("返回的岗位: %s", [j.岗位名称 for j in result.推荐岗位方向])

        self.history.append(
            {
                "input": user_info,
                "result": result.to_dict(),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return result

    def get_job_detail(
        self,
        job_name: str,
        user_resume: str,
        user_genes: str,
        job_market_data: str = "",
        existing_job_info: str = "",
    ) -> str:
        """详情流程：智谱 GLM-4-Flash 岗位追问。"""
        logger.debug("get_job_detail called, job_name: %s", job_name)
        sanitized_resume = sanitize_resume_for_api(user_resume or "")
        sanitized_genes = sanitize_resume_for_api(user_genes or "")
        prompt = self._build_detail_prompt(
            job_name, sanitized_resume, sanitized_genes, job_market_data, existing_job_info
        )
        logger.debug("detail prompt length: %s", len(prompt))

        def _api_call() -> str:
            logger.debug("gene job detail API call starting...")
            result = model_router.call(
                prompt=prompt,
                task_type="simple_qa",
                system_prompt="你是职业基因追问顾问，请按模板输出深度分析。",
                temperature=0.7,
                max_tokens=4000,
                timeout=float(self.config.DETAIL_TIMEOUT_SECONDS),
            )
            logger.debug("gene job detail API call finished, length: %s", len(result))
            return result

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        timeout_sec = self.config.DETAIL_TIMEOUT_SECONDS
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_api_call)
                return future.result(timeout=timeout_sec).strip()
        except FuturesTimeout:
            logger.warning("get_job_detail timeout after %ss", timeout_sec)
            return "深度分析超时，请稍后重试。"
        except Exception as exc:
            logger.exception("get_job_detail failed: %s", repr(exc))
            return "我一时没回上来，能再说一遍吗？"


GENE_DIMENSIONS: List[str] = [
    "创造力",
    "共情力",
    "逻辑力",
    "适应力",
    "专注力",
    "表达力",
    "执行力",
    "协作力",
]

GENE_DIMENSIONS: List[str] = [
    "创造力",
    "共情力",
    "逻辑力",
    "适应力",
    "专注力",
    "表达力",
    "执行力",
    "协作力",
]

_GENE_CODE_TO_DIMENSIONS: Dict[str, List[tuple]] = {
    "CREATIVE": [("创造力", 1.0)],
    "SPATIAL": [("创造力", 0.55), ("逻辑力", 0.45)],
    "DATA": [("逻辑力", 0.65), ("专注力", 0.35)],
    "VERBAL": [("表达力", 1.0)],
    "LEAD": [("协作力", 0.75), ("执行力", 0.25)],
    "EMPATHY": [("共情力", 1.0)],
    "LOGIC": [("逻辑力", 1.0)],
    "HANDS": [("执行力", 0.7), ("专注力", 0.3)],
    "KINES": [("执行力", 0.45), ("适应力", 0.55)],
    "MUSIC": [("创造力", 0.5), ("适应力", 0.5)],
    "NATURE": [("适应力", 0.65), ("专注力", 0.35)],
    "DISCI": [("专注力", 0.6), ("执行力", 0.4)],
}

_GENE_NAME_TO_CODE: Dict[str, str] = {
    "空间思维": "SPATIAL",
    "数据敏感": "DATA",
    "语言表达": "VERBAL",
    "组织号召": "LEAD",
    "共情理解": "EMPATHY",
    "创造想象": "CREATIVE",
    "逻辑推演": "LOGIC",
    "动手实践": "HANDS",
    "身体动觉": "KINES",
    "音乐感知": "MUSIC",
    "自然感知": "NATURE",
    "自律执行": "DISCI",
}

_DIMENSION_GAP_FIXES: Dict[str, str] = {
    "创造力": "每天记录1个产品/内容想法，坚持7天能激活创意思维",
    "共情力": "每周做一次15分钟用户访谈，快速练出感知他人需求的能力",
    "逻辑力": "用结构化框架拆解1个真实案例，3天就能提升分析表达",
    "适应力": "主动接手1个陌生小任务，在变化中练出快速上手能力",
    "专注力": "用番茄钟专注25分钟打磨1个细节，7天养成深度工作习惯",
    "表达力": "每天写300字复盘或口播练习，2周表达会明显更清楚",
    "执行力": "把目标拆成3个可执行动作并当天完成，立刻建立推进感",
    "协作力": "主动承担1次小组协调角色，在配合中练出推动力",
}

_DIMENSION_TYPE_SCENE: Dict[str, tuple] = {
    "创造力": ("探索者", "从0到1、需要不断试错的场景"),
    "共情力": ("连接者", "需要理解他人、建立信任的场景"),
    "逻辑力": ("分析者", "需要拆解复杂问题、做判断的场景"),
    "适应力": ("应变者", "变化快、需要快速切换的场景"),
    "专注力": ("深耕者", "需要长期打磨、追求极致细节的场景"),
    "表达力": ("传递者", "需要说服、讲述、影响他人的场景"),
    "执行力": ("推进者", "需要把想法落地、拿到结果的场景"),
    "协作力": ("组织者", "需要协调多方、带动团队的场景"),
}

_JOB_PROFILES: List[Dict[str, Any]] = [
    {
        "job": "产品经理",
        "weights": {"创造力": 0.3, "适应力": 0.3, "逻辑力": 0.2, "表达力": 0.2},
        "detail": "需要把用户痛点转成可落地的产品方案，兼顾创意、逻辑与沟通。",
    },
    {
        "job": "内容运营",
        "weights": {"创造力": 0.35, "表达力": 0.35, "适应力": 0.2, "共情力": 0.1},
        "detail": "持续产出有传播力的内容，对创意、表达和热点嗅觉要求高。",
    },
    {
        "job": "用户运营",
        "weights": {"共情力": 0.3, "表达力": 0.3, "适应力": 0.2, "协作力": 0.2},
        "detail": "围绕用户生命周期做触达与留存，共情和沟通是核心。",
    },
    {
        "job": "数据分析师",
        "weights": {"逻辑力": 0.4, "专注力": 0.3, "执行力": 0.2, "适应力": 0.1},
        "detail": "从数据里找规律、讲清楚结论，逻辑与专注缺一不可。",
    },
    {
        "job": "开发工程师",
        "weights": {"逻辑力": 0.45, "专注力": 0.35, "执行力": 0.2},
        "detail": "用代码解决实际问题，需要稳定输出与深度专注。",
    },
    {
        "job": "研究员",
        "weights": {"逻辑力": 0.35, "专注力": 0.35, "创造力": 0.2, "执行力": 0.1},
        "detail": "在某一领域持续深挖，适合能沉下心做长期探索的人。",
    },
    {
        "job": "用户研究员",
        "weights": {"共情力": 0.35, "表达力": 0.25, "逻辑力": 0.2, "适应力": 0.2},
        "detail": "把用户真实需求翻译给团队，洞察与沟通同样重要。",
    },
    {
        "job": "心理咨询师",
        "weights": {"共情力": 0.45, "表达力": 0.25, "专注力": 0.2, "适应力": 0.1},
        "detail": "在对话中承接情绪、建立安全感，共情是最底层能力。",
    },
    {
        "job": "人力资源",
        "weights": {"共情力": 0.35, "表达力": 0.25, "协作力": 0.25, "执行力": 0.15},
        "detail": "连接人与组织，需要理解个体又能推动协作。",
    },
    {
        "job": "教育培训",
        "weights": {"共情力": 0.35, "表达力": 0.35, "协作力": 0.2, "执行力": 0.1},
        "detail": "把知识讲明白、让人愿意学，表达与共情是基本功。",
    },
    {
        "job": "项目经理",
        "weights": {"协作力": 0.35, "执行力": 0.3, "表达力": 0.2, "适应力": 0.15},
        "detail": "协调资源、推进进度，能把多方拧成一股绳。",
    },
    {
        "job": "销售",
        "weights": {"表达力": 0.35, "共情力": 0.25, "协作力": 0.2, "适应力": 0.2},
        "detail": "在沟通中建立信任并推动成交，表达与共情决定上限。",
    },
    {
        "job": "行政管理",
        "weights": {"执行力": 0.35, "协作力": 0.3, "专注力": 0.2, "表达力": 0.15},
        "detail": "保障组织日常运转，稳定执行与细致协调是关键。",
    },
    {
        "job": "管理咨询",
        "weights": {"逻辑力": 0.35, "适应力": 0.3, "表达力": 0.2, "协作力": 0.15},
        "detail": "快速理解业务、给出可执行建议，逻辑与适应力并重。",
    },
    {
        "job": "战略分析",
        "weights": {"逻辑力": 0.4, "适应力": 0.25, "创造力": 0.2, "专注力": 0.15},
        "detail": "在不确定中判断方向，需要结构化思考与前瞻视角。",
    },
    {
        "job": "创业者",
        "weights": {"创造力": 0.25, "适应力": 0.3, "执行力": 0.25, "逻辑力": 0.2},
        "detail": "从想法到落地全链路负责，适合能扛变化、敢推进的人。",
    },
]

_SURPRISE_JOB_DIMS: Dict[str, Dict[str, str]] = {
    "产品经理": {
        "专注力": "能专注打磨细节的人，反而能在产品迭代中做出差异化",
        "逻辑力": "结构化思考不是最高也没关系，但能把复杂问题讲清楚会很加分",
    },
    "内容运营": {
        "逻辑力": "内容不只是灵感，能搭框架的人更容易持续产出",
        "专注力": "能沉下心改稿的人，往往比只会追热点的人走得更远",
    },
    "数据分析师": {
        "表达力": "能把数据故事讲清楚，比只会跑数的人更容易被看见",
        "共情力": "理解业务方真实诉求，会让你的分析更有落地价值",
    },
    "用户研究员": {
        "专注力": "访谈后的归纳整理能力，决定了洞察深度",
        "执行力": "能把研究结论推动到落地，才是稀缺的研究员",
    },
    "项目经理": {
        "共情力": "懂人心、会协调冲突的项目经理，往往比只会排期的人更稳",
        "创造力": "遇到卡点能想出替代方案，是高级项目经理的隐藏技能",
    },
    "销售": {
        "逻辑力": "能讲清楚价值逻辑的销售，比只会套话术的人更长久",
        "专注力": "持续跟进客户细节的人，成交率往往更高",
    },
}


def _level_to_score(level: int) -> int:
    clamped = max(1, min(5, int(level or 3)))
    return clamped * 20


def _resolve_gene_code(gene: Dict[str, Any]) -> str:
    code = str(gene.get("基因编码", "")).strip().upper()
    if code:
        return code
    name = str(gene.get("基因名称", "")).strip()
    return _GENE_NAME_TO_CODE.get(name, "")


def extract_gene_scores_from_result(result: Dict[str, Any]) -> Dict[str, int]:
    """将测序结果中的显性基因转为 8 维度得分（0-100）。"""
    accumulators: Dict[str, List[float]] = {dim: [] for dim in GENE_DIMENSIONS}
    genes = result.get("显性基因", [])
    if isinstance(genes, list):
        for gene in genes:
            if not isinstance(gene, dict):
                continue
            code = _resolve_gene_code(gene)
            if not code:
                continue
            score = _level_to_score(int(gene.get("等级", 3) or 3))
            for dim, weight in _GENE_CODE_TO_DIMENSIONS.get(code, []):
                accumulators[dim].append(score * weight)

    gene_scores: Dict[str, int] = {}
    for dim in GENE_DIMENSIONS:
        values = accumulators[dim]
        if values:
            gene_scores[dim] = int(round(sum(values) / len(values)))
        else:
            gene_scores[dim] = 50
    return gene_scores


def _weighted_match(gene_scores: Dict[str, int], weights: Dict[str, float]) -> int:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return 0
    matched = sum(gene_scores.get(dim, 50) * weight for dim, weight in weights.items())
    return int(round(matched / total_weight))


def _pick_strengths(gene_scores: Dict[str, int], weights: Dict[str, float], limit: int = 3) -> List[Dict[str, Any]]:
    ranked = sorted(
        weights.keys(),
        key=lambda dim: (gene_scores.get(dim, 50), weights.get(dim, 0)),
        reverse=True,
    )
    return [{"dim": dim, "score": gene_scores.get(dim, 50)} for dim in ranked[:limit]]


def _pick_gaps(gene_scores: Dict[str, int], weights: Dict[str, float], limit: int = 2) -> List[Dict[str, Any]]:
    ranked = sorted(weights.keys(), key=lambda dim: gene_scores.get(dim, 50))
    return [{"dim": dim, "score": gene_scores.get(dim, 50)} for dim in ranked[:limit]]


def _build_fix_text(gaps: List[Dict[str, Any]]) -> str:
    if not gaps:
        return "保持现有节奏，持续积累项目经验即可。"
    primary = gaps[0]["dim"]
    return _DIMENSION_GAP_FIXES.get(primary, f"针对{primary}做专项小练习，7天就能看到变化")


def map_gene_to_jobs(gene_scores: Dict[str, int], top_n: int = 3) -> List[Dict[str, Any]]:
    """根据 8 维度基因得分匹配岗位。"""
    matches: List[Dict[str, Any]] = []
    for profile in _JOB_PROFILES:
        weights = profile["weights"]
        match_score = _weighted_match(gene_scores, weights)
        strengths = _pick_strengths(gene_scores, weights, limit=3)
        gaps = _pick_gaps(gene_scores, weights, limit=2)
        matches.append(
            {
                "job": profile["job"],
                "match": match_score,
                "strengths": strengths,
                "gaps": gaps,
                "fix": _build_fix_text(gaps),
                "detail": profile.get("detail", ""),
                "weights": weights,
            }
        )
    matches.sort(key=lambda item: item["match"], reverse=True)
    return matches[:top_n]


def build_gene_summary(gene_scores: Dict[str, int]) -> str:
    """生成基因一句话总结。"""
    top_dim = max(gene_scores.items(), key=lambda item: item[1])[0]
    persona, scene = _DIMENSION_TYPE_SCENE.get(top_dim, ("探索者", "需要发挥长处的场景"))
    return f"你是一个{top_dim}驱动的{persona}，最适合在{scene}中发挥"


def build_surprise_insight(gene_scores: Dict[str, int], job_matches: List[Dict[str, Any]]) -> str:
    """生成意外发现文案。"""
    if not job_matches:
        return "你的基因组合很独特，值得多尝试不同方向，找到最适合你的舞台。"

    top_job = job_matches[0]["job"]
    sorted_dims = sorted(gene_scores.items(), key=lambda item: item[1], reverse=True)
    top_dims = {dim for dim, _ in sorted_dims[:3]}
    job_weights = job_matches[0].get("weights", {})

    candidates = [
        dim
        for dim in job_weights.keys()
        if dim not in top_dims and gene_scores.get(dim, 50) <= sorted_dims[2][1]
    ]
    if not candidates:
        mid_dims = [dim for dim, score in sorted_dims[3:6]]
        candidates = [dim for dim in mid_dims if dim in job_weights]

    dim = candidates[0] if candidates else sorted_dims[-1][0]
    job_map = _SURPRISE_JOB_DIMS.get(top_job, {})
    insight = job_map.get(dim)
    if not insight:
        insight = f"在{top_job}岗位中，{dim}往往是决定你能走多远的隐藏变量"
    return f"你的{dim}虽然不是最高，但在{top_job}中其实是稀缺优势——{insight}"


def build_job_match_analysis(job_match: Dict[str, Any], gene_scores: Dict[str, int]) -> str:
    """生成单个岗位的详细匹配说明。"""
    lines = [f"**{job_match['job']}** 与你的基因匹配度 **{job_match['match']}%**", ""]
    lines.append(job_match.get("detail", ""))
    lines.append("")
    lines.append("**维度对比：**")
    for dim, weight in sorted(job_match.get("weights", {}).items(), key=lambda x: x[1], reverse=True):
        score = gene_scores.get(dim, 50)
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        lines.append(f"- {dim} {score}分（权重 {int(weight * 100)}%） `{bar}`")
    lines.append("")
    lines.append(f"**补救路线：** {job_match.get('fix', '')}")
    return "\n".join(lines)

import re

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api
from core.prompt_manager import prompt_manager


class GoldReport(BaseModel):
    raw_content: str = Field(description="LLM原始报告内容")
    natural_language_report: str = Field(description="提取后的自然语言报告")


class ReportGenerator(BaseAgent):
    AGENT_NAME = "report_generator"
    PROMPT_TEMPLATE = "gold_detector/reporter_prompt.txt"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def generate(self, resume_analysis: str, match_result: str) -> GoldReport:
        sanitized_analysis = sanitize_resume_for_api(resume_analysis)
        sanitized_match = sanitize_resume_for_api(match_result)
        retrieval_query = f"{sanitized_analysis}\n{sanitized_match}"
        prompt = prompt_manager.render_dynamic(
            self.PROMPT_TEMPLATE,
            query=retrieval_query,
            module="reporter",
            resume_analysis=sanitized_analysis,
            match_result=sanitized_match,
        )
        raw_content = model_router.call(
            prompt=prompt,
            task_type="comprehensive_eval",
            system_prompt="你是一位职业发展顾问。铁律：严禁编造！你写的每一个字都必须基于分析结果和简历原文。分析结果没提到的经历、技能，绝对不能自己添加。宁可报告短一点，也不能编造。",
        )
        natural_language_report = self._extract_natural_language_report(raw_content)
        return GoldReport(
            raw_content=raw_content,
            natural_language_report=natural_language_report,
        )

    def _extract_natural_language_report(self, raw_content: str) -> str:
        match = re.search(
            r'"natural_language_report"\s*:\s*"((?:[^"\\]|\\.)*)"',
            raw_content,
        )
        if match:
            return match.group(1).replace("\\n", "\n").replace('\\"', '"')
        return raw_content


report_generator = ReportGenerator()

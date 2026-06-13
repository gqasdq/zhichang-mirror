from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api
from core.prompt_manager import prompt_manager


class MatchResult(BaseModel):
    raw_content: str = Field(description="LLM原始匹配结果")


class JobMatcher(BaseAgent):
    AGENT_NAME = "job_matcher"
    PROMPT_TEMPLATE = "gold_detector/matcher_prompt.txt"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def match(self, resume_analysis: str, job_description: str) -> MatchResult:
        sanitized_analysis = sanitize_resume_for_api(resume_analysis)
        sanitized_jd = sanitize_resume_for_api(job_description)
        retrieval_query = f"{sanitized_jd}\n{sanitized_analysis}"
        prompt = prompt_manager.render_dynamic(
            self.PROMPT_TEMPLATE,
            query=retrieval_query,
            module="matcher",
            resume_analysis=sanitized_analysis,
            job_description=sanitized_jd,
        )
        response = model_router.call(
            prompt=prompt,
            task_type="complex_analysis",
            system_prompt="你是一位岗位匹配分析师，请输出清晰的匹配诊断。",
        )
        return MatchResult(raw_content=response)


job_matcher = JobMatcher()

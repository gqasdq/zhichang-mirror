from typing import Any, Dict

from agents.gold_detector.analyzer import resume_analyzer
from agents.gold_detector.reporter import report_generator
from engines.jd_matcher_v2 import JDMatcherV2
from engines.resume_quality_scorer import ResumeQualityScorer


class GoldDetectorService:
    def __init__(self) -> None:
        self._matcher = JDMatcherV2()
        self._quality_scorer = ResumeQualityScorer()

    def process(self, resume_text: str, job_description: str = "") -> Dict[str, Any]:
        analysis = resume_analyzer.analyze(resume_text)
        match_result = None
        quality_result = None

        if job_description and job_description.strip():
            match_result = self._matcher.match(analysis.raw_content, job_description)
        else:
            quality_result = self._quality_scorer.evaluate(analysis.raw_content)

        report = report_generator.generate(
            analysis.raw_content,
            match_result.raw_content if match_result else "无岗位信息，请仅基于简历分析",
        )
        return {
            "analysis": analysis.model_dump(),
            "match": match_result.model_dump() if match_result else None,
            "quality": quality_result.model_dump() if quality_result else None,
            "report": report.model_dump(),
        }


def get_gold_detector_service():
    return GoldDetectorService()

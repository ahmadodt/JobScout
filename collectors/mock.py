from __future__ import annotations

from collectors.base import Job, utc_now_iso


class MockCollector:
    name = "mock"

    def collect(self) -> list[Job]:
        collected_at = utc_now_iso()
        jobs = [
            (
                "AI Product Engineer",
                "Northstar Labs",
                "Remote",
                "Build internal LLM tools for product and operations teams.",
            ),
            (
                "LLM Application Developer",
                "SignalForge AI",
                "New York, NY",
                "Create retrieval-assisted applications for enterprise users.",
            ),
            (
                "Machine Learning Engineer, Generative AI",
                "Cedar Systems",
                "San Francisco, CA",
                "Train and evaluate models for document understanding workflows.",
            ),
            (
                "AI Solutions Architect",
                "HelioWorks",
                "Austin, TX",
                "Design customer-facing AI prototypes and production integrations.",
            ),
            (
                "Prompt Engineer",
                "Atlas Data Co.",
                "Remote",
                "Develop, test, and maintain prompt libraries for business users.",
            ),
            (
                "NLP Engineer",
                "BrightPath Analytics",
                "Boston, MA",
                "Improve text classification, extraction, and summarization systems.",
            ),
            (
                "AI Platform Engineer",
                "VectorWave",
                "Seattle, WA",
                "Operate model-serving infrastructure and evaluation pipelines.",
            ),
            (
                "Applied AI Engineer",
                "Nimbus Robotics",
                "Pittsburgh, PA",
                "Apply multimodal models to robotics support and diagnostics.",
            ),
            (
                "LLM Evaluation Specialist",
                "MeasureMind",
                "Remote",
                "Create benchmark suites and quality reports for language models.",
            ),
            (
                "Data Scientist, AI Search",
                "QueryQuest",
                "Chicago, IL",
                "Build search ranking experiments using embeddings and analytics.",
            ),
        ]

        return [
            Job(
                title=title,
                company=company,
                location=location,
                source=self.name,
                url=f"https://example.com/jobs/{index}",
                description=description,
                date_posted="2026-06-01",
                date_collected=collected_at,
            )
            for index, (title, company, location, description) in enumerate(jobs, start=1)
        ]

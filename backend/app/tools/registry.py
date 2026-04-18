from typing import Dict, List, Optional
from app.tools.base import BaseTool
from app.tools.anchor_chart_maker import AnchorChartMaker
from app.tools.concept_explainer import ConceptExplainer
from app.tools.direct_chat_responder import DirectChatResponder
from app.tools.note_maker import NoteMaker
from app.tools.concept_visualizer import ConceptVisualizer
from app.tools.mind_map import MindMap
from app.tools.debate_speech_generator import DebateSpeechGenerator
from app.tools.pronunciation_coach import PronunciationCoach
from app.tools.rhyme_rap_composer import RhymeRapComposer
from app.tools.flashcards import Flashcards
from app.tools.mock_test import MockTest
from app.tools.quiz_me import QuizMe
from app.tools.step_by_step_solver import StepByStepSolver
from app.tools.mnemonic_generator import MnemonicGenerator
from app.tools.summary_generator import SummaryGenerator
from app.tools.quick_compare import QuickCompare
from app.tools.quick_prompts import QuickPrompts
from app.tools.visual_story_builder import VisualStoryBuilder
from app.tools.podcast_maker import PodcastMaker
from app.tools.simulation_generator import SimulationGenerator
from app.tools.slide_deck_generator import SlideDeckGenerator
from app.tools.timeline_designer import TimelineDesigner


class ToolRegistry:
    """Central registry for all 20 educational tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_all()

    def _register_all(self):
        tools = [
            AnchorChartMaker(),
            ConceptExplainer(),
            ConceptVisualizer(),
            NoteMaker(),
            MindMap(),
            DebateSpeechGenerator(),
            PronunciationCoach(),
            RhymeRapComposer(),
            Flashcards(),
            MockTest(),
            QuizMe(),
            StepByStepSolver(),
            MnemonicGenerator(),
            SummaryGenerator(),
            QuickCompare(),
            QuickPrompts(),
            VisualStoryBuilder(),
            PodcastMaker(),
            SimulationGenerator(),
            SlideDeckGenerator(),
            TimelineDesigner(),
            DirectChatResponder(),
        ]
        for tool in tools:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Register a tool dynamically; supports large catalogs."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def schemas(self) -> List[dict]:
        return [t.get_schema() for t in self._tools.values()]

    def by_category(self) -> Dict[str, List[BaseTool]]:
        categories: Dict[str, List[BaseTool]] = {}
        for t in self._tools.values():
            cat = t.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(t)
        return categories

    def trigger_phrase_map(self) -> Dict[str, str]:
        """Maps trigger phrases to tool names for quick lookup."""
        mapping = {}
        for tool in self._tools.values():
            for phrase in tool.get_trigger_phrases():
                mapping[phrase.lower()] = tool.name
        return mapping

    def metadata_index(self) -> List[Dict[str, object]]:
        """Lightweight metadata index for dynamic tool routing."""
        result: List[Dict[str, object]] = []
        for tool in self._tools.values():
            schema = tool.get_schema()
            result.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category,
                    "required_params": schema.get("required_params", []),
                    "optional_params": schema.get("optional_params", []),
                    "trigger_phrases": schema.get("example_trigger_phrases", []),
                }
            )
        return result


# Singleton instance
registry = ToolRegistry()

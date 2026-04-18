from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class PodcastMaker(BaseTool):
    name = "podcast_maker"
    description = "Generate educational podcasts with narration and scripts"
    category = "creative"
    required_params = ["topic", "subject"]
    optional_params = ["duration_minutes", "podcast_style", "hosts", "target_audience"]
    param_defaults = {"duration_minutes": 10, "podcast_style": "educational_interview", "hosts": ["Host", "Expert"], "target_audience": "students"}

    def get_trigger_phrases(self):
        return ["podcast", "audio", "episode", "radio", "narration", "listen", "script"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        duration = params.get("duration_minutes", 10)
        hosts = params.get("hosts", ["Host", "Expert"])

        words_per_minute = 130
        total_words = duration * words_per_minute

        data = {
            "episode_title": f"Deep Dive: {topic} in {subject}",
            "subject": subject, "topic": topic,
            "duration_minutes": duration,
            "estimated_word_count": total_words,
            "show_notes": f"In this episode, we explore {topic} — one of the most important concepts in {subject}. Perfect for students at all levels.",
            "script": {
                "intro": {
                    "duration_seconds": 30,
                    "narration": f"Welcome to EduCast! Today we're diving deep into {topic}, a foundational concept in {subject}. I'm {hosts[0]}, joined by our expert {hosts[1] if len(hosts) > 1 else 'guest'}.",
                },
                "segment_1": {
                    "title": f"What is {topic}?",
                    "duration_seconds": duration * 15,
                    "dialogue": [
                        {"speaker": hosts[0], "text": f"So, can you explain {topic} for our listeners who are just starting out?"},
                        {"speaker": hosts[1] if len(hosts) > 1 else "Expert", "text": f"Absolutely! {topic} is essentially... [detailed explanation]"},
                        {"speaker": hosts[0], "text": "That's fascinating! And why does this matter for students?"},
                    ],
                },
                "segment_2": {
                    "title": "Real-World Applications",
                    "duration_seconds": duration * 20,
                    "dialogue": [
                        {"speaker": hosts[0], "text": f"Let's talk about where students actually see {topic} in real life..."},
                        {"speaker": hosts[1] if len(hosts) > 1 else "Expert", "text": "Great question! You'll find {topic} in..."},
                    ],
                },
                "quiz_break": {
                    "title": "Quick Quiz Break",
                    "duration_seconds": 60,
                    "question": f"Quick quiz: What is the main principle of {topic}? Pause and think... Answer coming up!",
                },
                "outro": {
                    "duration_seconds": 30,
                    "narration": f"That's all for today's episode on {topic}! Don't forget to practice and check the show notes for resources. Until next time!",
                },
            },
            "sound_cues": ["[INTRO MUSIC]", "[TRANSITION SOUND]", "[QUIZ BELL]", "[OUTRO MUSIC]"],
            "resources_mentioned": [f"{subject} textbook chapter on {topic}", f"Practice problems: {topic} worksheet"],
            "transcript_tags": ["#education", f"#{subject.replace(' ','')}", f"#{topic.replace(' ','')}"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})



export const TOOL_ICONS: Record<string, string> = {
  anchor_chart_maker: '📊',
  concept_explainer: '💡',
  concept_visualizer: '🎨',
  mind_map: '🗺️',
  debate_speech_generator: '🎤',
  pronunciation_coach: '🗣️',
  rhyme_rap_composer: '🎵',
  flashcards: '🃏',
  mock_test: '📝',
  quiz_me: '🧠',
  step_by_step_solver: '🔢',
  mnemonic_generator: '🧩',
  summary_generator: '📄',
  quick_compare: '⚖️',
  quick_prompts: '💭',
  visual_story_builder: '📖',
  podcast_maker: '🎙️',
  simulation_generator: '⚗️',
  slide_deck_generator: '🖥️',
  timeline_designer: '📅',
}

export const CATEGORY_META: Record<string, { label: string; color: string }> = {
  learning: { label: 'Learning', color: '#00c9a7' },
  assessment: { label: 'Assessment', color: '#3b82f6' },
  memory: { label: 'Memory', color: '#f59e0b' },
  communication: { label: 'Communication', color: '#a855f7' },
  creative: { label: 'Creative', color: '#ec4899' },
  structured: { label: 'Structured', color: '#f97316' },
}

export const QUICK_PILLS = [
  { label: 'Learning Persona',      msg: 'Show my learning persona and strengths',                icon: '👤' },
  { label: 'Learning Path',         msg: 'Create a personalised learning path for me',            icon: '📈' },
  { label: 'Concept Explainer',     msg: 'Explain the concept of derivatives in calculus',        icon: '💡' },
  { label: 'Summarize Notes',       msg: 'Summarize my notes on photosynthesis',                  icon: '📄' },
  { label: 'Create Flashcards',     msg: 'Create 10 flashcards for the French Revolution',        icon: '🃏' },
  { label: 'Mock Test',             msg: 'Give me a 20-question mock test on algebra',            icon: '📝' },
  { label: 'Mind Map',              msg: 'Build a mind map for quantum physics',                  icon: '🗺️' },
  { label: 'Quiz Me',               msg: "I'm struggling with calculus derivatives. Quiz me",     icon: '🧠' },
  { label: 'Compare Topics',        msg: 'Compare Newton\'s first law vs second law',             icon: '⚖️' },
  { label: 'Step-by-Step Solver',   msg: 'Solve this step by step: find the derivative of x^3',  icon: '🔢' },
  { label: 'Timeline',              msg: 'Create a timeline of World War II major events',        icon: '📅' },
  { label: 'Memory Trick',          msg: 'Give me a mnemonic to remember the planets',            icon: '🧩' },
]

export const EXAMPLE_CHAT_STARTERS = [
  "I'm struggling with calculus derivatives and need practice problems",
  "Explain photosynthesis like I'm 10 years old",
  "Compare mitosis vs meiosis side by side",
  "Give me a mock test on World War II",
  "Create flashcards for Spanish irregular verbs",
  "Build a mind map for machine learning",
  "I have an exam tomorrow on thermodynamics — help!",
  "Make a rap song to remember the water cycle",
]

export function formatToolName(name: string): string {
  return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

export function getConfidenceColor(c: number): string {
  if (c >= 0.8) return '#00c9a7'
  if (c >= 0.6) return '#f59e0b'
  return '#ef4444'
}

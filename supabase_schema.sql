-- ================================================================
-- EduOrchestrator V3 — Complete Supabase Schema
-- ================================================================
-- Run this in: Supabase Dashboard → SQL Editor → Run
-- ================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";


-- ================================================================
-- 1. STUDENT PROFILES  (linked to Supabase auth.users)
-- ================================================================
CREATE TABLE IF NOT EXISTS public.student_profiles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email               TEXT,
    full_name           TEXT,
    avatar_url          TEXT,
    learning_level      TEXT NOT NULL DEFAULT 'beginner'
                            CHECK (learning_level IN ('beginner','intermediate','advanced','expert')),
    emotional_state     TEXT NOT NULL DEFAULT 'neutral',
    teaching_style      TEXT NOT NULL DEFAULT 'direct',
    preferred_subjects  TEXT[]   NOT NULL DEFAULT '{}',
    tool_usage_stats    JSONB    NOT NULL DEFAULT '{}',
    total_sessions      INTEGER  NOT NULL DEFAULT 0,
    total_messages      INTEGER  NOT NULL DEFAULT 0,
    streak_days         INTEGER  NOT NULL DEFAULT 0,
    last_active_at      TIMESTAMPTZ,
    token_balance       INTEGER  NOT NULL DEFAULT 100,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_student_profiles_user_id ON public.student_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_student_profiles_last_active ON public.student_profiles(last_active_at DESC NULLS LAST);


-- ================================================================
-- 2. CONVERSATION SESSIONS
-- ================================================================
CREATE TABLE IF NOT EXISTS public.conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title           TEXT,
    primary_subject TEXT,
    message_count   INTEGER  NOT NULL DEFAULT 0,
    tools_used      TEXT[]   NOT NULL DEFAULT '{}',
    is_archived     BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.conversation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON public.conversation_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_subject ON public.conversation_sessions(primary_subject);


-- ================================================================
-- 3. CONVERSATION MESSAGES
-- ================================================================
CREATE TABLE IF NOT EXISTS public.conversation_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES public.conversation_sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,

    -- Orchestration metadata (assistant messages only)
    tool_used       TEXT,
    tool_params     JSONB,
    tool_response   JSONB,
    confidence      NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
    intent          TEXT,
    subject         TEXT,
    difficulty      TEXT,
    mood            TEXT,
    workflow_steps  TEXT[],
    latency_ms      INTEGER,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON public.conversation_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.conversation_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_tool_used ON public.conversation_messages(tool_used);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.conversation_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_fts ON public.conversation_messages
    USING GIN (to_tsvector('english', content));


-- ================================================================
-- 4. TOOL EXECUTION LOGS
-- ================================================================
CREATE TABLE IF NOT EXISTS public.tool_execution_logs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL REFERENCES public.conversation_sessions(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_id          UUID REFERENCES public.conversation_messages(id) ON DELETE SET NULL,

    tool_name           TEXT    NOT NULL,
    tool_category       TEXT,
    input_params        JSONB,
    output              JSONB,
    confidence          NUMERIC(4,3),
    fallback_tools      TEXT[],
    retry_count         INTEGER NOT NULL DEFAULT 0,
    success             BOOLEAN NOT NULL DEFAULT TRUE,
    error_message       TEXT,
    execution_time_ms   INTEGER,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_logs_user_id   ON public.tool_execution_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_tool_logs_tool_name ON public.tool_execution_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_logs_success   ON public.tool_execution_logs(success);
CREATE INDEX IF NOT EXISTS idx_tool_logs_created   ON public.tool_execution_logs(created_at DESC);


-- ================================================================
-- 5. TOOL REGISTRY  (static reference — seeded below)
-- ================================================================
CREATE TABLE IF NOT EXISTS public.tool_registry (
    id              SERIAL PRIMARY KEY,
    tool_name       TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    icon            TEXT,
    required_params TEXT[] NOT NULL DEFAULT '{}',
    optional_params TEXT[] NOT NULL DEFAULT '{}',
    trigger_phrases TEXT[] NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.tool_registry
    (tool_name, display_name, description, category, icon, required_params, optional_params, trigger_phrases)
VALUES
    ('anchor_chart_maker',      'Anchor Chart Maker',        'Structured visual charts for concept clarity',          'learning',       '📊', ARRAY['topic','subject'], ARRAY['grade_level','num_sections'],      ARRAY['anchor chart','visual chart','classroom chart']),
    ('concept_explainer',       'Concept Explainer',         'Explains concepts simply with examples',                'learning',       '💡', ARRAY['concept','subject'], ARRAY['difficulty','include_examples'],  ARRAY['explain','what is','tell me about','help me understand']),
    ('concept_visualizer',      'Concept Visualizer',        'Converts ideas into visual diagrams',                   'learning',       '🎨', ARRAY['concept','subject'], ARRAY['visualization_type'],            ARRAY['visualize','diagram','show me']),
    ('mind_map',                'Mind Map Builder',          'Connected idea maps for concept relationships',         'learning',       '🗺️', ARRAY['central_topic'],     ARRAY['subject','depth','branches'],    ARRAY['mind map','idea map','brainstorm']),
    ('debate_speech_generator', 'Debate & Speech Generator', 'Structured debate topics and speeches',                 'communication',  '🎤', ARRAY['topic'],             ARRAY['side','duration_minutes'],       ARRAY['debate','speech','argue','persuade']),
    ('pronunciation_coach',     'Pronunciation Coach',       'Guided pronunciation practice',                         'communication',  '🗣️', ARRAY['words_or_text','language'], ARRAY['difficulty'],            ARRAY['pronounce','pronunciation','how to say']),
    ('rhyme_rap_composer',      'Rhyme & Rap Composer',      'Topics as rhymes or rap for memorable learning',        'communication',  '🎵', ARRAY['topic','subject'],   ARRAY['style','length'],               ARRAY['rap','rhyme','song','poem','catchy']),
    ('flashcards',              'Flashcard Generator',       'Interactive flashcards for revision',                   'assessment',     '🃏', ARRAY['topic','subject'],   ARRAY['num_cards','difficulty'],        ARRAY['flashcard','memorize','recall','study cards']),
    ('mock_test',               'Mock Test Creator',         'Practice exams for speed and accuracy',                 'assessment',     '📝', ARRAY['subject','topics'],  ARRAY['num_questions','time_limit_minutes'], ARRAY['mock test','practice exam','exam prep']),
    ('quiz_me',                 'Quiz Me',                   'Quizzes to test knowledge',                             'assessment',     '🧠', ARRAY['topic','subject'],   ARRAY['difficulty','num_questions'],    ARRAY['quiz','quiz me','test me','practice problems']),
    ('step_by_step_solver',     'Step-by-Step Solver',       'Problems solved with clear explanations',               'assessment',     '🔢', ARRAY['problem','subject'], ARRAY['show_working'],                 ARRAY['solve','step by step','how do I','walk me through']),
    ('mnemonic_generator',      'Mnemonic Generator',        'Memory aids to improve recall',                         'memory',         '🧩', ARRAY['items_to_remember','subject'], ARRAY['mnemonic_type'],    ARRAY['mnemonic','memory trick','how to remember']),
    ('summary_generator',       'Summary Generator',         'Concise summaries of topics',                           'memory',         '📄', ARRAY['topic_or_text','subject'], ARRAY['length'],              ARRAY['summarize','summary','tldr','key points']),
    ('quick_compare',           'Quick Compare',             'Side-by-side topic comparison',                         'memory',         '⚖️', ARRAY['topic_a','topic_b'], ARRAY['subject'],                      ARRAY['compare','vs','versus','difference between']),
    ('quick_prompts',           'QuickPrompts',              'Creative prompts for brainstorming',                    'creative',       '💭', ARRAY['subject_or_theme'],  ARRAY['num_prompts'],                  ARRAY['prompt','brainstorm','give me ideas']),
    ('visual_story_builder',    'Visual Story Builder',      'Educational stories in structured panels',              'creative',       '📖', ARRAY['topic','subject'],   ARRAY['num_panels','story_type'],      ARRAY['story','visual story','comic','narrative']),
    ('podcast_maker',           'Podcast Maker',             'Educational podcasts with narration scripts',           'creative',       '🎙️', ARRAY['topic','subject'],   ARRAY['duration_minutes'],             ARRAY['podcast','audio','episode','script']),
    ('simulation_generator',    'Simulation Generator',      'Interactive simulations for complex concepts',          'structured',     '⚗️', ARRAY['concept','subject'], ARRAY['complexity'],                   ARRAY['simulate','simulation','interactive','virtual lab']),
    ('slide_deck_generator',    'Slide Deck Generator',      'Presentation slides for lessons',                       'structured',     '🖥️', ARRAY['topic','subject'],   ARRAY['num_slides','audience'],        ARRAY['slides','presentation','powerpoint']),
    ('timeline_designer',       'Timeline Designer',         'Events and sequences in timeline format',               'structured',     '📅', ARRAY['topic','subject'],   ARRAY['timeline_type'],                ARRAY['timeline','history','sequence','chronology'])
ON CONFLICT (tool_name) DO NOTHING;


-- ================================================================
-- 6. STUDENT ANALYTICS
-- ================================================================
CREATE TABLE IF NOT EXISTS public.student_analytics (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    total_tool_calls        INTEGER  NOT NULL DEFAULT 0,
    favourite_tool          TEXT,
    favourite_subject       TEXT,
    avg_confidence          NUMERIC(4,3),
    tools_breakdown         JSONB NOT NULL DEFAULT '{}',
    subjects_breakdown      JSONB NOT NULL DEFAULT '{}',
    difficulty_progression  JSONB NOT NULL DEFAULT '{}',
    weekly_activity         JSONB NOT NULL DEFAULT '{}',
    last_computed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_user_id ON public.student_analytics(user_id);


-- ================================================================
-- 7. TRIGGERS
-- ================================================================

-- updated_at helper
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

CREATE TRIGGER trg_student_profiles_updated_at
    BEFORE UPDATE ON public.student_profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON public.conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();


-- Auto-create student profile when a new Supabase user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.student_profiles (user_id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'avatar_url'
    )
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END; $$;

-- Attach trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- Auto-increment session message_count
CREATE OR REPLACE FUNCTION public.increment_session_message_count()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE public.conversation_sessions
    SET message_count = message_count + 1, updated_at = NOW()
    WHERE id = NEW.session_id;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_message_count
    AFTER INSERT ON public.conversation_messages
    FOR EACH ROW EXECUTE FUNCTION public.increment_session_message_count();


-- Track tools used per session
CREATE OR REPLACE FUNCTION public.track_session_tool()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tool_used IS NOT NULL THEN
        UPDATE public.conversation_sessions
        SET tools_used = ARRAY(SELECT DISTINCT unnest(tools_used || ARRAY[NEW.tool_used])),
            updated_at = NOW()
        WHERE id = NEW.session_id;
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_track_tool
    AFTER INSERT ON public.conversation_messages
    FOR EACH ROW WHEN (NEW.tool_used IS NOT NULL)
    EXECUTE FUNCTION public.track_session_tool();


-- Update student stats on new user message
CREATE OR REPLACE FUNCTION public.update_student_activity()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.role = 'user' THEN
        UPDATE public.student_profiles
        SET total_messages = total_messages + 1,
            last_active_at = NOW(),
            updated_at = NOW()
        WHERE user_id = NEW.user_id;
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_student_activity
    AFTER INSERT ON public.conversation_messages
    FOR EACH ROW EXECUTE FUNCTION public.update_student_activity();


-- Increment session count when a session is created
CREATE OR REPLACE FUNCTION public.increment_session_count()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE public.student_profiles
    SET total_sessions = total_sessions + 1, updated_at = NOW()
    WHERE user_id = NEW.user_id;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_session_count
    AFTER INSERT ON public.conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION public.increment_session_count();


-- ================================================================
-- 8. ROW LEVEL SECURITY
-- ================================================================
ALTER TABLE public.student_profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tool_execution_logs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_analytics     ENABLE ROW LEVEL SECURITY;

-- Drop existing policies before recreating
DO $$ BEGIN
    DROP POLICY IF EXISTS "service_role_student_profiles" ON public.student_profiles;
    DROP POLICY IF EXISTS "users_own_profile" ON public.student_profiles;
    DROP POLICY IF EXISTS "service_role_sessions" ON public.conversation_sessions;
    DROP POLICY IF EXISTS "users_own_sessions" ON public.conversation_sessions;
    DROP POLICY IF EXISTS "service_role_messages" ON public.conversation_messages;
    DROP POLICY IF EXISTS "users_own_messages" ON public.conversation_messages;
    DROP POLICY IF EXISTS "service_role_tool_logs" ON public.tool_execution_logs;
    DROP POLICY IF EXISTS "users_own_tool_logs" ON public.tool_execution_logs;
    DROP POLICY IF EXISTS "service_role_analytics" ON public.student_analytics;
    DROP POLICY IF EXISTS "users_own_analytics" ON public.student_analytics;
EXCEPTION WHEN others THEN NULL;
END $$;

-- Service role (FastAPI backend) — full access
CREATE POLICY "service_role_student_profiles" ON public.student_profiles FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_sessions"         ON public.conversation_sessions FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_messages"         ON public.conversation_messages FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_tool_logs"        ON public.tool_execution_logs FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_analytics"        ON public.student_analytics FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Authenticated users — own data only
CREATE POLICY "users_own_profile"    ON public.student_profiles      FOR ALL TO authenticated USING (user_id = auth.uid());
CREATE POLICY "users_own_sessions"   ON public.conversation_sessions  FOR ALL TO authenticated USING (user_id = auth.uid());
CREATE POLICY "users_own_messages"   ON public.conversation_messages  FOR ALL TO authenticated USING (user_id = auth.uid());
CREATE POLICY "users_own_tool_logs"  ON public.tool_execution_logs    FOR ALL TO authenticated USING (user_id = auth.uid());
CREATE POLICY "users_own_analytics"  ON public.student_analytics      FOR ALL TO authenticated USING (user_id = auth.uid());

-- Tool registry is public read
ALTER TABLE public.tool_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "public_tool_registry" ON public.tool_registry;
CREATE POLICY "public_tool_registry" ON public.tool_registry FOR SELECT TO anon, authenticated USING (TRUE);


-- ================================================================
-- 9. HELPER VIEWS
-- ================================================================
CREATE OR REPLACE VIEW public.v_session_summary AS
SELECT
    s.id            AS session_id,
    s.user_id,
    p.email,
    p.full_name,
    p.learning_level,
    s.title,
    s.primary_subject,
    s.message_count,
    s.tools_used,
    s.is_archived,
    s.created_at,
    s.updated_at,
    ROUND(EXTRACT(EPOCH FROM (s.updated_at - s.created_at)) / 60.0, 1) AS duration_minutes
FROM public.conversation_sessions s
LEFT JOIN public.student_profiles p ON p.user_id = s.user_id;


CREATE OR REPLACE VIEW public.v_tool_stats AS
SELECT
    tool_name,
    tool_category,
    COUNT(*)                                          AS total_calls,
    COUNT(*) FILTER (WHERE success = TRUE)            AS successes,
    COUNT(*) FILTER (WHERE success = FALSE)           AS failures,
    ROUND(AVG(confidence)::NUMERIC, 3)               AS avg_confidence,
    ROUND(AVG(execution_time_ms)::NUMERIC)           AS avg_latency_ms,
    COUNT(DISTINCT user_id)                           AS unique_users,
    MAX(created_at)                                   AS last_used_at
FROM public.tool_execution_logs
GROUP BY tool_name, tool_category
ORDER BY total_calls DESC;


CREATE OR REPLACE VIEW public.v_user_stats AS
SELECT
    p.user_id,
    p.email,
    p.full_name,
    p.learning_level,
    p.total_sessions,
    p.total_messages,
    p.streak_days,
    p.token_balance,
    p.last_active_at,
    COUNT(DISTINCT tl.tool_name) AS distinct_tools_used,
    ROUND(AVG(tl.confidence)::NUMERIC, 3) AS avg_confidence
FROM public.student_profiles p
LEFT JOIN public.tool_execution_logs tl ON tl.user_id = p.user_id
GROUP BY p.user_id, p.email, p.full_name, p.learning_level,
         p.total_sessions, p.total_messages, p.streak_days,
         p.token_balance, p.last_active_at;


-- ================================================================
-- 10. USEFUL FUNCTIONS
-- ================================================================

-- Recompute analytics for a user
CREATE OR REPLACE FUNCTION public.compute_analytics(p_user_id UUID)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_tools     JSONB;
    v_subjects  JSONB;
    v_fav_tool  TEXT;
    v_fav_subj  TEXT;
    v_avg_conf  NUMERIC;
BEGIN
    SELECT jsonb_object_agg(tool_name, cnt) INTO v_tools
    FROM (SELECT tool_name, COUNT(*) AS cnt FROM public.tool_execution_logs WHERE user_id = p_user_id GROUP BY tool_name) x;

    SELECT tool_name INTO v_fav_tool
    FROM public.tool_execution_logs WHERE user_id = p_user_id
    GROUP BY tool_name ORDER BY COUNT(*) DESC LIMIT 1;

    SELECT jsonb_object_agg(subject, cnt) INTO v_subjects
    FROM (SELECT subject, COUNT(*) AS cnt FROM public.conversation_messages WHERE user_id = p_user_id AND subject IS NOT NULL GROUP BY subject) x;

    SELECT subject INTO v_fav_subj
    FROM public.conversation_messages WHERE user_id = p_user_id AND subject IS NOT NULL
    GROUP BY subject ORDER BY COUNT(*) DESC LIMIT 1;

    SELECT AVG(confidence) INTO v_avg_conf FROM public.tool_execution_logs WHERE user_id = p_user_id;

    INSERT INTO public.student_analytics (user_id, total_tool_calls, favourite_tool, favourite_subject, avg_confidence, tools_breakdown, subjects_breakdown, last_computed_at)
    SELECT p_user_id, COUNT(*), v_fav_tool, v_fav_subj, v_avg_conf,
           COALESCE(v_tools,'{}'), COALESCE(v_subjects,'{}'), NOW()
    FROM public.tool_execution_logs WHERE user_id = p_user_id
    ON CONFLICT (user_id) DO UPDATE SET
        total_tool_calls   = EXCLUDED.total_tool_calls,
        favourite_tool     = EXCLUDED.favourite_tool,
        favourite_subject  = EXCLUDED.favourite_subject,
        avg_confidence     = EXCLUDED.avg_confidence,
        tools_breakdown    = EXCLUDED.tools_breakdown,
        subjects_breakdown = EXCLUDED.subjects_breakdown,
        last_computed_at   = NOW();
END; $$;


-- ================================================================
-- DONE ✅
--
-- Tables  : student_profiles, conversation_sessions,
--           conversation_messages, tool_execution_logs,
--           tool_registry (20 tools seeded), student_analytics
--
-- Triggers: auto-create profile on signup, message_count,
--           tool tracking, session count, student activity
--
-- Views   : v_session_summary, v_tool_stats, v_user_stats
--
-- RLS     : All tables secured; service_role full access,
--           users see only their own data
--
-- Key     : Linked to auth.users via user_id UUID (not text)
-- ================================================================

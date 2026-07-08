INSERT INTO prompt_templates (
    id, name, version, system_prompt, prompt_template,
    variables, owner_org, visibility, created_at, updated_at
) VALUES (
    gen_random_uuid(),
    'generate-html',
    '1.0.0',
    'You are an expert web developer. Output ONLY valid HTML code. No explanations.',
    'Create HTML based on: {{query}}. Output ONLY the code, nothing else.',
    '["query"]',
    'system',
    'private',
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;

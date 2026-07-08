UPDATE workflow_drafts
SET blocks = (
    jsonb_set(
        jsonb_set(
            blocks::jsonb,
            '{1,input_bindings}',
            '{"path": {"source": "literal", "value": "test_hello.html"}, "content": {"source": "step_output", "step_id": "step_1", "field": "response"}, "encoding": {"source": "literal", "value": "utf-8"}, "create_dirs": {"source": "literal", "value": "true"}}'
        ),
        '{1,config}',
        '{"base_path": "."}'
    )
)::json
WHERE id = 'a30cd15b-0d81-4168-a046-8ed929b3f97d';

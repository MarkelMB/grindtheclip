import json
import os

log_path = r'C:\Users\marke\.gemini\antigravity\brain\ed950239-8d93-417a-a352-922fe7b96800\.system_generated\logs\transcript_full.jsonl'

best_app_js = None

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('type') == 'PLANNER_RESPONSE':
                for tc in data.get('tool_calls', []):
                    if tc['function']['name'] in ['write_to_file', 'replace_file_content']:
                        args = tc['function'].get('arguments', {})
                        if isinstance(args, str):
                            args = json.loads(args)
                        target = args.get('TargetFile', '')
                        print(f"TargetFile: {target}")
            
            if data.get('type') == 'TOOL_RESPONSE':
                content = data.get('content', '')
                if 'Showing lines ' in content and 'app.js' in content:
                    print(f"Found view_file of app.js at step {data.get('step_index')}")
        except Exception as e:
            pass

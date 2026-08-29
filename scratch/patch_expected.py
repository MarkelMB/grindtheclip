import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """
        // Count players properly by looking at the last room state
        expectedPlayersForCoop = Object.keys(roomCharacters).length > 0 ? Object.keys(roomCharacters).length : 1; 
        // Wait, not all characters might be claimed. 
        // We should just use a global or pass it from backend. But we can assume it's just the number of players that were in the lobby.
        // Actually, we can fetch the players list from the server, but let's just use the length of the list before we clear it.
        // Or even better: expectedPlayersForCoop is passed from the server in `data.players_count`. Let's assume we modify server.py to send it.
"""
new_logic = """
        // Count unique players who claimed characters
        const uniqueSids = new Set(Object.values(roomCharacters));
        expectedPlayersForCoop = uniqueSids.size > 0 ? uniqueSids.size : 1;
"""

content = content.replace(old_logic.strip(), new_logic.strip())

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed expectedPlayersForCoop in app.js")

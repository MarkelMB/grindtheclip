import re

with open('server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update on_ready
old_ready = """        # Check if everyone is ready
        all_ready = len(rooms[room]['players']) > 0 and all(p['ready'] for p in rooms[room]['players'].values())
        if all_ready:
            socketio.emit('game_start_countdown', {'pack_name': rooms[room]['pack_name']}, room=room)"""

new_ready = """        # Check if everyone is ready
        all_ready = len(rooms[room]['players']) > 0 and all(p['ready'] for p in rooms[room]['players'].values())
        if all_ready:
            rooms[room]['coop_data'] = {
                'scores': [],
                'player_clips': {},
                'finished_count': 0,
                'total_expected': len(rooms[room]['players'])
            }
            socketio.emit('game_start_countdown', {'pack_name': rooms[room]['pack_name']}, room=room)"""

content = content.replace(old_ready, new_ready)

# 2. Update coop_submit
old_submit_init = """        if 'coop_data' not in rooms[room]:
            rooms[room]['coop_data'] = {
                'scores': [],
                'player_clips': {},
                'finished_count': 0
            }"""
new_submit_init = """        if 'coop_data' not in rooms[room]:
            rooms[room]['coop_data'] = {
                'scores': [],
                'player_clips': {},
                'finished_count': 0,
                'total_expected': len(rooms[room]['players'])
            }"""
content = content.replace(old_submit_init, new_submit_init)

old_submit_check = """        # Emit waiting update
        socketio.emit('coop_waiting_update', {
            'finished': room_data['finished_count'],
            'total': len(rooms[room]['players']),
            'last_finished': player_name
        }, room=room)
        
        # Check if all done
        if room_data['finished_count'] >= len(rooms[room]['players']):"""

new_submit_check = """        total_exp = room_data.get('total_expected', len(rooms[room]['players']))
        # Emit waiting update
        socketio.emit('coop_waiting_update', {
            'finished': room_data['finished_count'],
            'total': total_exp,
            'last_finished': player_name
        }, room=room)
        
        # Check if all done
        if room_data['finished_count'] >= total_exp:"""
content = content.replace(old_submit_check, new_submit_check)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched server.py successfully.")

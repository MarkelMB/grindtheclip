import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# find the first instance of character-select-modal
modal_start = content.find('<!-- Character Selection Modal')
if modal_start == -1:
    print("modal not found")
else:
    new_modal = """<!-- Character Selection Modal (Improved UX/UI) -->
    <div id="character-select-modal" class="modal" style="display:none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 9999; align-items: center; justify-content: center; backdrop-filter: blur(10px);">
        <div style="background: rgba(10,12,16,0.95); padding: 40px; border-radius: 20px; border: 2px solid var(--cyan); width: 450px; max-width: 90%; box-shadow: 0 0 40px rgba(0, 229, 255, 0.2); position: relative; overflow: hidden;">
            <!-- Decorational corners -->
            <div style="position: absolute; top: 0; left: 0; width: 30px; height: 30px; border-top: 3px solid var(--magenta); border-left: 3px solid var(--magenta);"></div>
            <div style="position: absolute; bottom: 0; right: 0; width: 30px; height: 30px; border-bottom: 3px solid var(--magenta); border-right: 3px solid var(--magenta);"></div>

            <h2 class="neon-text" style="color: var(--cyan); margin-bottom: 15px; font-size: 2rem; text-align: center;">🎬 Casting</h2>
            <p style="color: #aaa; margin-bottom: 30px; font-size: 1rem; text-align: center; line-height: 1.4;">¿A quién quieres doblar? Los personajes desmarcados usarán su voz original.</p>
            
            <div id="character-checkboxes" style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 35px; max-height: 300px; overflow-y: auto; padding-right: 15px;">
                <!-- Checkboxes will be injected here -->
            </div>
            
            <div style="display: flex; justify-content: center; gap: 20px;">
                <button class="btn btn-secondary" onclick="document.getElementById('character-select-modal').style.display='none'" style="padding: 12px 25px; font-size: 1.1rem; border-color: #555; cursor: pointer;">Volver</button>
                <button class="btn-pill btn-cyan" id="btn-start-dubbing" style="padding: 12px 30px; font-size: 1.2rem; cursor: pointer;">¡Acción! 🎥</button>
            </div>
        </div>
    </div>

    <!-- Background Music -->
    <audio id="menu-music" src="{{ url_for('static', filename='menu_music.mp3') }}" loop></audio>

    <script src="{{ url_for('static', filename='app.js') }}?v=11"></script>
</body>
</html>
"""
    new_content = content[:modal_start] + new_modal
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed!")

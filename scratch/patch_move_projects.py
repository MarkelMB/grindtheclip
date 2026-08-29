import os

# 1. Update index.html
html_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\templates\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

recent_projects_html = """
        <!-- Proyectos Recientes -->
        <div style="margin-top: 40px; text-align: left;">
            <h2 style="color: var(--cyan); margin-bottom: 20px; font-size: 1.5rem; text-shadow: 0 0 10px rgba(0,229,255,0.3);">Proyectos Recientes</h2>
            <div id="recent-projects-list" style="display: flex; flex-direction: column; gap: 15px; max-height: 300px; overflow-y: auto; padding-right: 10px;">
                <p style="color: #666; text-align: center; margin-top: 20px;">Cargando proyectos...</p>
            </div>
        </div>
"""

# Remove from view-creator-input
html = html.replace(recent_projects_html, "")

# Add to view-creator-mode
# Before: 
#             </div>
#         </div>
#     </div>
#
#     <!-- VIEW: Creator Input -->
# Let's target the end of view-creator-mode
html = html.replace(
    '            </div>\n        </div>\n    </div>\n\n    <!-- VIEW: Creator Input -->',
    '            </div>\n        </div>' + recent_projects_html + '\n    </div>\n\n    <!-- VIEW: Creator Input -->'
)

# And fix the Manual button to point to input but set a manual flag? The user asked previously to fix the Manual button going to the manual editor. Actually they just mentioned the URL issue.
# Let's fix the manual button to also use the IA input view but skip the IA part, or for now, just let's point it to view-creator-input.
html = html.replace("window.location.href='/editor'", "showView('view-creator-input')")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)


# 2. Update app.js
app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'
with open(app_js_path, 'r', encoding='utf-8') as f:
    appjs = f.read()

appjs = appjs.replace("if (viewId === 'view-creator-input')", "if (viewId === 'view-creator-mode')")

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(appjs)

print("Moved recent projects to view-creator-mode.")

import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add globals
globals_patch = """let autoSaveTimer = null;
let currentCreatorJobId = null;

// View Management"""

content = content.replace("// View Management", globals_patch)

# 2. Add loadRecentProjects and resumeProject
recent_projects_code = """
async function loadRecentProjects() {
    const list = document.getElementById('recent-projects-list');
    if (!list) return;
    try {
        const res = await fetch('/api/creator/projects');
        const data = await res.json();
        
        if (!data.projects || data.projects.length === 0) {
            list.innerHTML = '<p style="color: #666; text-align: center; margin-top: 20px;">No hay proyectos recientes.</p>';
            return;
        }
        
        list.innerHTML = '';
        data.projects.forEach(proj => {
            const dateStr = new Date(proj.updated_at * 1000).toLocaleString();
            const numLines = proj.lines ? proj.lines.length : 0;
            const el = document.createElement('div');
            el.style.cssText = 'background: rgba(20,25,35,0.8); border: 1px solid #2a3545; padding: 15px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s;';
            el.innerHTML = `
                <div>
                    <h3 style="color: #fff; margin: 0 0 5px 0; font-size: 1.1rem;">${proj.pack_name || 'Sin título'}</h3>
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">${numLines} escenas · Última edición: ${dateStr}</p>
                </div>
                <button class="btn-pill btn-cyan" onclick="resumeProject('${proj.job_id}')">Continuar</button>
            `;
            el.onmouseenter = () => el.style.background = 'rgba(30,40,55,0.9)';
            el.onmouseleave = () => el.style.background = 'rgba(20,25,35,0.8)';
            list.appendChild(el);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = '<p style="color: #ff5252; text-align: center; margin-top: 20px;">Error al cargar proyectos.</p>';
    }
}

async function resumeProject(jobId) {
    try {
        const res = await fetch(`/api/creator/result/${jobId}`);
        const data = await res.json();
        if (data.error) {
            alert("No se pudo cargar el proyecto.");
            return;
        }
        
        currentCreatorJobId = jobId;
        
        // Initialize editor state
        editorLines = data.result.lines || [];
        editorCharacters = data.result.characters || [];
        document.getElementById('editor-pack-name').value = data.pack_name || 'Sin título';
        
        // Ensure video is setup
        const video = document.getElementById('editor-video');
        video.src = data.video_url;
        
        showView('view-editor');
        setupTimeline();
        renderEditorLines();
        renderEditorCharacters();
        renderTimeline();
    } catch(e) {
        alert("Error cargando el proyecto.");
    }
}

async function autoSaveProject() {
    if (!currentCreatorJobId) return;
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    
    autoSaveTimer = setTimeout(async () => {
        try {
            const packName = document.getElementById('editor-pack-name').value.trim() || 'Sin título';
            const videoUrl = document.getElementById('editor-video').src;
            
            await fetch(`/api/creator/save/${currentCreatorJobId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pack_name: packName,
                    lines: editorLines,
                    characters: editorCharacters,
                    video_url: videoUrl
                })
            });
        } catch(e) {}
    }, 1000);
}
"""

content = content.replace("function showView(viewId) {", recent_projects_code + "\nfunction showView(viewId) {")

# 3. Hook loadRecentProjects to showView
showView_hook = """    document.getElementById(viewId).classList.add('active');
    if (viewId === 'view-creator-input') {
        loadRecentProjects();
    }"""
content = content.replace("    document.getElementById(viewId).classList.add('active');", showView_hook)

# 4. Set currentCreatorJobId on auto-build finish
auto_build_hook = """            currentCreatorJobId = currentAutoBuildJobId;
            const res = await fetch(`/api/creator/result/${currentAutoBuildJobId}`);"""
content = content.replace("const res = await fetch(`/api/creator/result/${currentAutoBuildJobId}`);", auto_build_hook)

# 5. Add autoSaveProject() to modifying functions
functions_to_hook = [
    ("function applyLineEdits() {", "autoSaveProject();\n}"),
    ("function addLineAtPlayhead() {", "autoSaveProject();\n}"),
    ("function deleteSelectedLine() {", "autoSaveProject();\n}"),
    ("function deleteLineById(id) {", "autoSaveProject();\n}"),
    ("function addCharacter() {", "autoSaveProject();\n}"),
    ("function removeCharacter(idx) {", "autoSaveProject();\n}"),
    ("function renameCharacter(idx, newName) {", "autoSaveProject();\n}")
]

# Quick regex to add autoSaveProject() at the end of these functions
# We'll just hook into the functions that re-render things like renderTimeline() or renderEditorLines()
content = content.replace("renderEditorLines();", "renderEditorLines();\n    autoSaveProject();")
content = content.replace("renderEditorCharacters();", "renderEditorCharacters();\n    autoSaveProject();")

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.js patched for projects logic")

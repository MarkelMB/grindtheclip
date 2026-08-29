"use strict";

const PALETTE = ["#22d3ee", "#e5636b", "#4caf7d", "#d9a441", "#c471ed", "#41c7d9", "#f27b9b", "#8bc34a"];

let project = {
    name: "untitled_" + Date.now(),
    title: "Nuevo Proyecto",
    video: null,
    local_video_path: null,
    characters: [],
    lines: [],
    authors: "",
    readme: ""
};

let activeCharacter = null;
let selectedLineId = null;
let pxPerSecond = 50; // Zoom level
let linePreviewTimer = null;
let autoSaveInterval = null;

const $ = id => document.getElementById(id);

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    // Media Loader
    $("btn-load-file").addEventListener("click", handleFileUpload);
    $("btn-load-yt").addEventListener("click", handleYTLoad);
    $("btn-remove-video").addEventListener("click", removeVideo);

    // Video Controls
    const player = $("main-player");
    player.addEventListener("timeupdate", onVideoTimeUpdate);
    player.addEventListener("loadedmetadata", onVideoLoaded);

    // Zoom
    $("zoom-slider").addEventListener("input", (e) => {
        pxPerSecond = parseInt(e.target.value);
        renderTimeline();
    });

    // Timeline Click Seek
    $("timeline-canvas").addEventListener("mousedown", (e) => {
        if (e.target && e.target.className && typeof e.target.className === 'string' && e.target.className.includes('handle')) return;
        if (e.target === $("timeline-canvas") && e.offsetY > $("timeline-canvas").clientHeight) return;
        const rect = $("timeline-canvas").getBoundingClientRect();
        const scrollLeft = $("timeline-canvas").scrollLeft;
        const x = e.clientX - rect.left + scrollLeft;
        const time = x / pxPerSecond;
        if (player.duration) {
            player.currentTime = Math.max(0, Math.min(time, player.duration));
        }
    });

    // Characters
    $("btn-add-char").addEventListener("click", addCharacter);
    $("new-char-name").addEventListener("keypress", (e) => { if (e.key === 'Enter') addCharacter(); });

    // Lines
    $("btn-add-line").addEventListener("click", addLineAtPlayhead);

    // Timeline Footer Range
    $("btn-set-start").addEventListener("click", () => { 
        $("export-start").value = player.currentTime.toFixed(2);
        updateExportTotal();
    });
    $("btn-set-end").addEventListener("click", () => { 
        $("export-end").value = player.currentTime.toFixed(2);
        updateExportTotal();
    });
    $("export-start").addEventListener("input", updateExportTotal);
    $("export-end").addEventListener("input", updateExportTotal);

    // Export
    $("btn-export-pack").addEventListener("click", exportPack);
    
    // Project Name
    $("project-name").addEventListener("change", (e) => { 
        project.title = e.target.value; 
        saveProjectState(true);
    });

    // Keyboard Shortcuts
    setupKeyboardShortcuts();

    // Auto-save timer (every 20 seconds)
    autoSaveInterval = setInterval(() => {
        saveProjectState(false);
    }, 20000);

    // Check if loading from AI Pipeline
    checkAILoad();
});

// --- Keyboard Shortcuts ---
function setupKeyboardShortcuts() {
    window.addEventListener("keydown", (e) => {
        // Ignore shortcuts if user is typing in an input or textarea
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
        if (activeTag === "input" || activeTag === "textarea" || activeTag === "select") {
            return;
        }

        const player = $("main-player");
        if (!player) return;

        switch (e.code) {
            case "Space":
                e.preventDefault();
                if (player.paused) {
                    player.play().catch(() => {});
                } else {
                    player.pause();
                }
                break;

            case "KeyN":
                e.preventDefault();
                addLineAtPlayhead();
                break;

            case "KeyI":
                if (selectedLineId) {
                    e.preventDefault();
                    const line = project.lines.find(l => l.id === selectedLineId);
                    if (line) {
                        line.start = Math.max(0, Math.min(player.currentTime, line.end - 0.1));
                        renderTimeline();
                        showSaveBadge("✂️ Inicio actualizado");
                    }
                }
                break;

            case "KeyO":
                if (selectedLineId) {
                    e.preventDefault();
                    const line = project.lines.find(l => l.id === selectedLineId);
                    if (line && player.duration) {
                        line.end = Math.min(player.duration, Math.max(line.start + 0.1, player.currentTime));
                        renderTimeline();
                        showSaveBadge("✂️ Fin actualizado");
                    }
                }
                break;

            case "Delete":
            case "Backspace":
                if (selectedLineId) {
                    e.preventDefault();
                    deleteLine(selectedLineId);
                }
                break;

            case "ArrowLeft":
                e.preventDefault();
                {
                    const step = e.shiftKey ? 0.1 : 1.0;
                    player.currentTime = Math.max(0, player.currentTime - step);
                }
                break;

            case "ArrowRight":
                e.preventDefault();
                {
                    const step = e.shiftKey ? 0.1 : 1.0;
                    player.currentTime = Math.min(player.duration || 9999, player.currentTime + step);
                }
                break;
        }
    });
}

function showSaveBadge(text) {
    const badge = $("save-badge");
    if (!badge) return;
    badge.innerText = text;
    badge.style.opacity = "1";
    badge.className = "badge badge-saved";
    setTimeout(() => {
        badge.innerText = "Guardado";
    }, 2500);
}

// --- Auto Save ---
async function saveProjectState(verbose = false) {
    if (!project.title || project.lines.length === 0) return;
    try {
        const badge = $("save-badge");
        if (badge) badge.innerText = "⏳ Guardando...";
        
        project.name = $("project-name").value || "untitled";
        await fetch(`/api/projects/${encodeURIComponent(project.name)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(project)
        });
        if (badge) badge.innerText = verbose ? "✅ Guardado" : "Guardado";
    } catch(e) {
        console.warn("Auto-save notice:", e);
    }
}

async function checkAILoad() {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get('job_id');
    const packName = params.get('pack_name');
    
    if (jobId) {
        $("media-loader-overlay").style.display = "none";
        
        if (packName) {
            $("project-name").value = packName;
            project.title = packName;
        }

        try {
            const res = await fetch('/api/creator/result/' + jobId);
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            if (data.result) {
                // Populate project data from AI result
                project.video = data.video_url;
                project.jobId = jobId;
                
                // Trim character names cleanly
                const lines = data.result.lines || [];
                lines.forEach(l => {
                    if (l.character) l.character = l.character.trim();
                });

                const uniqueChars = [...new Set(lines.map(l => l.character))];
                project.characters = uniqueChars.map((name, i) => ({
                    name: name,
                    color: PALETTE[i % PALETTE.length]
                }));

                if (project.characters.length > 0 && !activeCharacter) {
                    activeCharacter = project.characters[0].name;
                }

                project.lines = lines.map(l => ({
                    id: l.id || ("line_" + Math.random().toString(36).substr(2,9)),
                    character: (l.character || 'Personaje 1').trim(),
                    caption: l.caption || '',
                    start: parseFloat(l.start) || 0,
                    end: parseFloat(l.end) || 0,
                    confidence: l.confidence !== undefined ? parseFloat(l.confidence) : 0.9
                }));
            }
            
            $("main-player").src = project.video;
            
            // Wait for video metadata to render timeline properly
            $("main-player").onloadedmetadata = () => {
                onVideoLoaded();
                renderCharacters();
                renderTimeline();
            };
            
        } catch(err) {
            alert("Error al cargar proyecto IA: " + err.message);
            $("media-loader-overlay").style.display = "flex";
        }
    }
}

// --- Media Loading ---
async function handleFileUpload() {
    const file = $("video-file-input").files[0];
    if (!file) {
        alert("Selecciona un archivo de vídeo primero.");
        return;
    }
    const fd = new FormData();
    fd.append("video", file);
    loadMediaAPI(fd);
}

async function handleYTLoad() {
    const url = $("youtube-url-input").value.trim();
    if (!url) return;
    const fd = new FormData();
    fd.append("youtube_url", url);
    loadMediaAPI(fd);
}

async function loadMediaAPI(formData) {
    $("loader-status").style.display = "block";
    try {
        const res = await fetch("/api/editor/load_media", { method: "POST", body: formData });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        project.video = data.video_url;
        project.local_video_path = data.local_video_path;
        
        $("main-player").src = project.video;
        $("media-loader-overlay").style.display = "none";
    } catch(err) {
        $("loader-status").innerHTML = `<span style="color:var(--danger)">Error: ${err.message}</span>`;
    }
}

function removeVideo() {
    project.video = null;
    project.local_video_path = null;
    $("main-player").src = "";
    $("media-loader-overlay").style.display = "flex";
    $("loader-status").style.display = "none";
}

// --- Video Player ---
function onVideoLoaded() {
    const player = $("main-player");
    if (player && player.duration) {
        $("export-end").value = player.duration.toFixed(2);
        updateExportTotal();
        renderTimeline();
    }
}

function onVideoTimeUpdate() {
    const player = $("main-player");
    if (!player) return;
    const t = player.currentTime;
    
    // Update playhead
    const playhead = $("playhead");
    if (playhead) {
        playhead.style.left = (t * pxPerSecond) + "px";
    }

    // Handle line audio clip preview stop
    if (linePreviewTimer && player._previewEnd && t >= player._previewEnd) {
        player.pause();
        player._previewEnd = null;
        if (linePreviewTimer) {
            clearTimeout(linePreviewTimer);
            linePreviewTimer = null;
        }
    }
}

function formatTime(sec) {
    sec = Math.max(0, sec);
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toFixed(2).padStart(5, '0')}`;
}

// --- Audio Clip Preview ---
function previewLineAudio(line) {
    const player = $("main-player");
    if (!player || !line) return;
    
    selectedLineId = line.id;
    renderTimeline();

    // Jump player to line start and play until line end
    player.pause();
    player.currentTime = Math.max(0, line.start);
    player._previewEnd = line.end;
    
    player.play().catch(() => {});
}

// --- Characters ---
function addCharacter() {
    const nameInput = $("new-char-name");
    const name = nameInput.value.trim();
    if (!name || project.characters.find(c => c.name === name)) return;
    
    const color = PALETTE[project.characters.length % PALETTE.length];
    project.characters.push({ name, color });
    if (!activeCharacter) activeCharacter = name;
    
    nameInput.value = "";
    renderCharacters();
    renderTimeline();
}

function deleteCharacter(name) {
    project.characters = project.characters.filter(c => c.name !== name);
    if (activeCharacter === name) activeCharacter = project.characters.length ? project.characters[0].name : null;
    project.lines = project.lines.filter(l => l.character !== name);
    renderCharacters();
    renderTimeline();
}

function renderCharacters() {
    const list = $("characters-list");
    if (!list) return;
    list.innerHTML = "";
    project.characters.forEach(c => {
        const item = document.createElement("div");
        item.className = "char-item";
        if (c.name === activeCharacter) item.style.border = `1px solid ${c.color}`;
        
        item.innerHTML = `
            <div class="color-dot" style="background:${c.color}"></div>
            <div class="char-name" style="cursor:pointer" onclick="setActiveChar('${c.name}')">${c.name}</div>
            <button class="btn-delete-char" onclick="deleteCharacter('${c.name}')" title="Eliminar personaje">✖</button>
        `;
        list.appendChild(item);
    });
}

function setActiveChar(name) {
    activeCharacter = name;
    renderCharacters();
    renderTimeline();
    
    // Update playhead height to cover all tracks to the very bottom
    setTimeout(() => {
        const playhead = $("playhead");
        const tracksContainer = $("timeline-tracks-container");
        if (playhead && tracksContainer) {
            const h = Math.max(tracksContainer.scrollHeight + 40, $("timeline-canvas").clientHeight || 200);
            playhead.style.height = h + "px";
        }
    }, 50);
}

// --- Lines / Timeline ---
function addLineAtPlayhead() {
    if (!activeCharacter) return alert("Crea y selecciona un personaje primero.");
    const player = $("main-player");
    if (!player || !player.duration) return alert("Carga un vídeo primero.");
    
    const start = Math.round(player.currentTime * 100) / 100;
    const end = Math.round(Math.min(start + 2.0, player.duration) * 100) / 100;
    
    const text = prompt("Texto del diálogo:", "Nuevo diálogo");
    if (text === null) return;
    
    const newLine = {
        id: "line_" + Date.now(),
        character: activeCharacter,
        start: start,
        end: end,
        caption: text || "...",
        confidence: 1.0
    };

    project.lines.push(newLine);
    selectedLineId = newLine.id;
    renderTimeline();
    previewLineAudio(newLine);
}

function deleteLine(lineId) {
    project.lines = project.lines.filter(l => l.id !== lineId);
    if (selectedLineId === lineId) selectedLineId = null;
    renderTimeline();
}

function renderTimeline() {
    const player = $("main-player");
    const dur = player ? (player.duration || 0) : 0;
    
    // Clamp all line timestamps to video duration bounds
    if (dur > 0) {
        project.lines.forEach(l => {
            l.start = Math.max(0, Math.min(l.start, dur - 0.1));
            l.end = Math.max(l.start + 0.1, Math.min(l.end, dur));
        });
    }

    const canvasWidth = Math.max(800, dur * pxPerSecond);
    
    $("timeline-tracks-container").style.width = canvasWidth + "px";
    $("timeline-ruler").style.width = canvasWidth + "px";
    
    // Ruler
    const ruler = $("timeline-ruler");
    ruler.innerHTML = "";
    const step = 5;
    for(let t=0; t<=dur; t+=step) {
        const tick = document.createElement("div");
        tick.className = "ruler-tick";
        tick.style.left = (t * pxPerSecond) + "px";
        tick.textContent = formatTime(t);
        ruler.appendChild(tick);
    }
    
    // Tracks List (Left)
    const trackList = $("track-list");
    trackList.innerHTML = "";
    
    // Tracks Container (Canvas)
    const tracksContainer = $("timeline-tracks-container");
    tracksContainer.innerHTML = "";
    
    project.characters.forEach(c => {
        // Left header
        const th = document.createElement("div");
        th.className = "track-header" + (c.name === activeCharacter ? " active" : "");
        th.textContent = c.name;
        th.onclick = () => setActiveChar(c.name);
        trackList.appendChild(th);
        
        // Right track row
        const tr = document.createElement("div");
        tr.className = "timeline-track-row";
        tr.dataset.charName = c.name;
        
        // Clips for this character
        const charLines = project.lines.filter(l => (l.character || '').trim() === c.name.trim());
        charLines.forEach(line => {
            const clip = document.createElement("div");
            clip.className = "clip-block";
            const isSelected = line.id === selectedLineId;
            
            // Confidence border styling
            let borderStyle = isSelected ? `2px solid #ffffff` : `1px solid rgba(255,255,255,0.3)`;
            if (line.confidence !== undefined && line.confidence < 0.7) {
                borderStyle = isSelected ? `2px solid #ff5252` : `1.5px dashed #ffab40`;
            }

            clip.style.cssText = `
                left: ${line.start * pxPerSecond}px;
                width: ${Math.max(22, (line.end - line.start) * pxPerSecond)}px;
                background: ${c.color};
                border: ${borderStyle};
                box-shadow: ${isSelected ? '0 0 14px rgba(255,255,255,0.6)' : '0 2px 5px rgba(0,0,0,0.3)'};
            `;
            
            const confIcon = (line.confidence !== undefined && line.confidence < 0.7) ? '⚠️ ' : '';
            clip.title = `${line.character}: "${line.caption}" (${line.start.toFixed(2)}s - ${line.end.toFixed(2)}s)\nHaz clic para escuchar y editar. Arrastra para ajustar tiempos.`;
            clip.innerHTML = `
                <div class="clip-handle-l" onmousedown="startDrag(event, 'resize-l', '${line.id}')"></div>
                <div class="clip-text">${confIcon}${line.caption || '(vacío)'}</div>
                <div class="clip-handle-r" onmousedown="startDrag(event, 'resize-r', '${line.id}')"></div>
            `;

            let dragHappened = false;
            clip.onmousedown = (e) => {
                if (e.target.className.includes('handle')) return;
                dragHappened = false;
                startDrag(e, 'move', line.id);
                const markDrag = () => { dragHappened = true; window.removeEventListener('mousemove', markDrag); };
                window.addEventListener('mousemove', markDrag);
            };

            clip.onclick = (e) => {
                e.stopPropagation();
                if (!dragHappened) {
                    previewLineAudio(line);
                    editLine(line);
                }
            };

            tr.appendChild(clip);
        });
        
        tracksContainer.appendChild(tr);
    });

    // Update playhead line height to span all tracks down to the very bottom
    const playhead = $("playhead");
    if (playhead && tracksContainer) {
        const totalHeight = Math.max(tracksContainer.scrollHeight + 40, 300);
        playhead.style.height = totalHeight + "px";
    }
}

function updateExportTotal() {
    const s = parseFloat($("export-start").value) || 0;
    const e = parseFloat($("export-end").value) || 0;
    $("export-total").textContent = Math.max(0, e - s).toFixed(2);
}

function editLine(line) {
    const charSelect = $("modal-line-char");
    if (charSelect) {
        charSelect.innerHTML = "";
        project.characters.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.name;
            opt.textContent = c.name;
            if (c.name === line.character) opt.selected = true;
            charSelect.appendChild(opt);
        });
    }

    $("modal-line-text").value = line.caption || "";
    if ($("modal-line-start")) $("modal-line-start").value = line.start.toFixed(2);
    if ($("modal-line-end")) $("modal-line-end").value = line.end.toFixed(2);

    const modal = $("line-editor-modal");
    modal.style.display = "flex";

    // Wire Delete Button
    const btnDelete = $("btn-modal-delete");
    if (btnDelete) {
        btnDelete.onclick = () => {
            deleteLine(line.id);
            modal.style.display = "none";
        };
    }

    // Wire Save Button
    $("btn-modal-save").onclick = () => {
        if (charSelect && charSelect.value) line.character = charSelect.value;
        line.caption = $("modal-line-text").value.trim() || "...";
        if ($("modal-line-start")) line.start = parseFloat($("modal-line-start").value) || 0;
        if ($("modal-line-end")) line.end = parseFloat($("modal-line-end").value) || 0;
        
        modal.style.display = "none";
        renderTimeline();
    };

    // Wire Cancel Button
    $("btn-modal-cancel").onclick = () => {
        modal.style.display = "none";
    };
}

// --- Drag and Drop Logic ---
let dragObj = null;
function startDrag(e, type, lineId) {
    e.preventDefault();
    e.stopPropagation();
    const line = project.lines.find(l => l.id === lineId);
    dragObj = {
        type: type,
        line: line,
        startX: e.clientX,
        origStart: line.start,
        origEnd: line.end
    };
    document.addEventListener("mousemove", doDrag);
    document.addEventListener("mouseup", stopDrag);
}

function doDrag(e) {
    if (!dragObj) return;
    const player = $("main-player");
    const dur = player ? (player.duration || 0) : 0;
    const deltaSec = (e.clientX - dragObj.startX) / pxPerSecond;
    
    if (dragObj.type === 'move') {
        const span = dragObj.origEnd - dragObj.origStart;
        let newS = dragObj.origStart + deltaSec;
        newS = Math.max(0, Math.min(newS, dur - span));
        dragObj.line.start = Math.round(newS * 100) / 100;
        dragObj.line.end = Math.round((newS + span) * 100) / 100;

        // Check vertical track hover to switch character
        const trackRows = document.querySelectorAll('.timeline-track-row');
        trackRows.forEach(tr => {
            const rect = tr.getBoundingClientRect();
            if (e.clientY >= rect.top && e.clientY <= rect.bottom && tr.dataset.charName) {
                dragObj.line.character = tr.dataset.charName;
            }
        });
    } else if (dragObj.type === 'resize-l') {
        let newS = dragObj.origStart + deltaSec;
        newS = Math.max(0, Math.min(newS, dragObj.origEnd - 0.1));
        dragObj.line.start = Math.round(newS * 100) / 100;
    } else if (dragObj.type === 'resize-r') {
        let newE = dragObj.origEnd + deltaSec;
        newE = Math.min(dur, Math.max(newE, dragObj.origStart + 0.1));
        dragObj.line.end = Math.round(newE * 100) / 100;
    }
    renderTimeline();
}

function stopDrag() {
    dragObj = null;
    document.removeEventListener("mousemove", doDrag);
    document.removeEventListener("mouseup", stopDrag);
}

// --- Export ---
async function exportPack() {
    if (!project.video) return alert("Carga un vídeo primero.");
    if (project.lines.length === 0) return alert("Añade al menos una línea.");
    
    project.authors = $("meta-authors").value;
    project.readme = $("meta-readme").value;
    
    const player = $("main-player");
    const start = parseFloat($("export-start").value) || 0;
    const end = parseFloat($("export-end").value) || (player ? player.duration : 0);
    project.trim = { start, end };
    
    $("export-progress").style.display = "block";
    $("btn-export-pack").disabled = true;
    $("export-status-text").textContent = "Guardando proyecto y empaquetando para el juego...";
    $("export-fill").style.width = "50%";
    
    try {
        project.name = $("project-name").value || "untitled";
        await fetch(`/api/projects/${encodeURIComponent(project.name)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(project)
        });
        
        if (project.jobId) {
            const res = await fetch(`/api/creator/export`, { 
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    job_id: project.jobId,
                    pack_name: project.name,
                    lines: project.lines,
                    characters: project.characters
                })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
        } else {
            const res = await fetch(`/api/projects/${encodeURIComponent(project.name)}/export`, { method: "POST" });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
        }
        
        $("export-fill").style.width = "100%";
        $("export-status-text").textContent = "¡Completado! Serás redirigido al catálogo...";
        $("export-status-text").style.color = "var(--primary)";
        
        setTimeout(() => { window.location.href = "/"; }, 2000);
        
    } catch (err) {
        $("export-status-text").textContent = "Error: " + err.message;
        $("export-status-text").style.color = "var(--danger)";
        $("btn-export-pack").disabled = false;
    }
}

import os

filepath = r"static\editor.js"
code = '''"use strict";

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
let pxPerSecond = 50; // Zoom level

const $ = id => document.getElementById(id);

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    // Media Loader
    btn-load-file.addEventListener("click", handleFileUpload);
    btn-load-yt.addEventListener("click", handleYTLoad);
    btn-remove-video.addEventListener("click", removeVideo);

    // Video Controls
    main-player.addEventListener("timeupdate", onVideoTimeUpdate);
    main-player.addEventListener("loadedmetadata", onVideoLoaded);
    btn-play-pause.addEventListener("click", togglePlay);
    seek-bar.addEventListener("input", onSeekBarInput);

    // Zoom
    zoom-slider.addEventListener("input", (e) => {
        pxPerSecond = parseInt(e.target.value);
        renderTimeline();
    });

    // Characters
    btn-add-char.addEventListener("click", addCharacter);
    new-char-name.addEventListener("keypress", (e) => { if (e.key === 'Enter') addCharacter(); });

    // Lines
    btn-add-line.addEventListener("click", addLineAtPlayhead);

    // Timeline Footer
    btn-set-start.addEventListener("click", () => { 
        export-start.value = main-player.currentTime.toFixed(2);
        updateExportTotal();
    });
    btn-set-end.addEventListener("click", () => { 
        export-end.value = main-player.currentTime.toFixed(2);
        updateExportTotal();
    });
    export-start.addEventListener("input", updateExportTotal);
    export-end.addEventListener("input", updateExportTotal);

    // Export
    btn-export-pack.addEventListener("click", exportPack);
    
    // Project Name
    project-name.addEventListener("change", (e) => { project.title = e.target.value; });
});

// --- Media Loading ---
async function handleFileUpload() {
    const file = video-file-input.files[0];
    if (!file) {
        alert("Selecciona un archivo de video primero.");
        return;
    }
    const fd = new FormData();
    fd.append("video", file);
    loadMediaAPI(fd);
}

async function handleYTLoad() {
    const url = youtube-url-input.value.trim();
    if (!url) return;
    const fd = new FormData();
    fd.append("youtube_url", url);
    loadMediaAPI(fd);
}

async function loadMediaAPI(formData) {
    loader-status.style.display = "block";
    try {
        const res = await fetch("/api/editor/load_media", { method: "POST", body: formData });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        project.video = data.video_url;
        project.local_video_path = data.local_video_path;
        
        main-player.src = project.video;
        media-loader-overlay.style.display = "none";
    } catch(err) {
        loader-status.innerHTML = <span style="color:var(--danger)">Error: </span>;
    }
}

function removeVideo() {
    project.video = null;
    project.local_video_path = null;
    main-player.src = "";
    media-loader-overlay.style.display = "flex";
    loader-status.style.display = "none";
}

// --- Video Player ---
function onVideoLoaded() {
    seek-bar.max = main-player.duration;
    export-end.value = main-player.duration.toFixed(2);
    updateExportTotal();
    renderTimeline();
}

function onVideoTimeUpdate() {
    const t = main-player.currentTime;
    const d = main-player.duration || 0;
    seek-bar.value = t;
    time-display.textContent = ${formatTime(t)} / ;
    
    // Update playhead
    const playhead = playhead;
    playhead.style.left = (t * pxPerSecond) + "px";
}

function onSeekBarInput() {
    main-player.currentTime = seek-bar.value;
}

function togglePlay() {
    const v = main-player;
    if (v.paused) { v.play(); btn-play-pause.textContent = "⏸"; }
    else { v.pause(); btn-play-pause.textContent = "▶"; }
}

function formatTime(sec) {
    sec = Math.max(0, sec);
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return ${m}:;
}

// --- Characters ---
function addCharacter() {
    const nameInput = new-char-name;
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
    // Also remove lines for this character
    project.lines = project.lines.filter(l => l.character !== name);
    renderCharacters();
    renderTimeline();
}

function renderCharacters() {
    const list = characters-list;
    list.innerHTML = "";
    project.characters.forEach(c => {
        const item = document.createElement("div");
        item.className = "char-item";
        if (c.name === activeCharacter) item.style.border = 1px solid ;
        
        item.innerHTML = 
            <div class="color-dot" style="background:"></div>
            <div class="char-name" style="cursor:pointer" onclick="setActiveChar('')"></div>
            <button class="btn-delete-char" onclick="deleteCharacter('')">✖</button>
        ;
        list.appendChild(item);
    });
}

function setActiveChar(name) {
    activeCharacter = name;
    renderCharacters();
    renderTimeline(); // update track active state
}

// --- Lines / Timeline ---
function addLineAtPlayhead() {
    if (!activeCharacter) return alert("Crea y selecciona un personaje primero.");
    if (!main-player.duration) return alert("Carga un video primero.");
    
    const start = main-player.currentTime;
    const end = Math.min(start + 2.0, main-player.duration);
    
    const text = prompt("Texto de la línea:", "");
    if (text === null) return; // cancelled
    
    project.lines.push({
        id: "line_" + Date.now(),
        character: activeCharacter,
        start: start,
        end: end,
        caption: text || "..."
    });
    renderTimeline();
}

function renderTimeline() {
    const dur = main-player.duration || 0;
    const canvasWidth = Math.max(800, dur * pxPerSecond);
    
    timeline-canvas.style.width = canvasWidth + "px";
    
    // Ruler
    const ruler = timeline-ruler;
    ruler.innerHTML = "";
    const step = 5; // tick every 5 seconds
    for(let t=0; t<=dur; t+=step) {
        const tick = document.createElement("div");
        tick.className = "ruler-tick";
        tick.style.left = (t * pxPerSecond) + "px";
        tick.textContent = formatTime(t);
        ruler.appendChild(tick);
    }
    
    // Tracks List (Left)
    const trackList = track-list;
    trackList.innerHTML = "";
    
    // Tracks Container (Canvas)
    const tracksContainer = timeline-tracks-container;
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
        
        // Clips for this character
        const charLines = project.lines.filter(l => l.character === c.name);
        charLines.forEach(line => {
            const clip = document.createElement("div");
            clip.className = "clip-block";
            clip.style.left = (line.start * pxPerSecond) + "px";
            clip.style.width = ((line.end - line.start) * pxPerSecond) + "px";
            clip.style.background = c.color;
            clip.innerHTML = 
                <div class="clip-handle-l" onmousedown="startDrag(event, 'resize-l', '')"></div>
                <div class="clip-text"></div>
                <div class="clip-handle-r" onmousedown="startDrag(event, 'resize-r', '')"></div>
            ;
            clip.onmousedown = (e) => {
                if(e.target.className.includes('handle')) return;
                startDrag(e, 'move', line.id);
            };
            clip.ondblclick = () => editLine(line);
            tr.appendChild(clip);
        });
        
        tracksContainer.appendChild(tr);
    });
}

function updateExportTotal() {
    const s = parseFloat(export-start.value) || 0;
    const e = parseFloat(export-end.value) || 0;
    export-total.textContent = Math.max(0, e - s).toFixed(2);
}

function editLine(line) {
    modal-line-text.value = line.caption;
    line-editor-modal.style.display = "flex";
    
    btn-modal-save.onclick = () => {
        line.caption = modal-line-text.value;
        line-editor-modal.style.display = "none";
        renderTimeline();
    };
    btn-modal-cancel.onclick = () => {
        line-editor-modal.style.display = "none";
    };
}

// --- Drag and Drop Logic ---
let dragObj = null;
function startDrag(e, type, lineId) {
    e.preventDefault();
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
    const dur = main-player.duration || 0;
    const deltaSec = (e.clientX - dragObj.startX) / pxPerSecond;
    
    if (dragObj.type === 'move') {
        const span = dragObj.origEnd - dragObj.origStart;
        let newS = dragObj.origStart + deltaSec;
        newS = Math.max(0, Math.min(newS, dur - span));
        dragObj.line.start = newS;
        dragObj.line.end = newS + span;
    } else if (dragObj.type === 'resize-l') {
        let newS = dragObj.origStart + deltaSec;
        newS = Math.max(0, Math.min(newS, dragObj.origEnd - 0.1));
        dragObj.line.start = newS;
    } else if (dragObj.type === 'resize-r') {
        let newE = dragObj.origEnd + deltaSec;
        newE = Math.min(dur, Math.max(newE, dragObj.origStart + 0.1));
        dragObj.line.end = newE;
    }
    renderTimeline(); // In a pro app, only update the single DOM node for performance. Here re-render is fine.
}

function stopDrag() {
    dragObj = null;
    document.removeEventListener("mousemove", doDrag);
    document.removeEventListener("mouseup", stopDrag);
}

// --- Export ---
async function exportPack() {
    if (!project.video) return alert("Carga un video primero.");
    if (project.lines.length === 0) return alert("Añade al menos una línea.");
    
    project.authors = meta-authors.value;
    project.readme = meta-readme.value;
    
    const start = parseFloat(export-start.value) || 0;
    const end = parseFloat(export-end.value) || main-player.duration;
    project.trim = { start, end };
    
    export-progress.style.display = "block";
    btn-export-pack.disabled = true;
    export-status-text.textContent = "Guardando proyecto y empaquetando...";
    export-fill.style.width = "50%";
    
    try {
        // Save project first to our internal API
        project.name = project-name.value || "untitled";
        await fetch(/api/projects/, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(project)
        });
        
        // Trigger export
        const res = await fetch(/api/projects//export, { method: "POST" });
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);
        
        export-fill.style.width = "100%";
        export-status-text.textContent = "¡Completado! Serás redirigido...";
        export-status-text.style.color = "var(--primary)";
        
        setTimeout(() => { window.location.href = "/"; }, 2000);
        
    } catch (err) {
        export-status-text.textContent = "Error: " + err.message;
        export-status-text.style.color = "var(--danger)";
        btn-export-pack.disabled = false;
    }
}
'''

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)

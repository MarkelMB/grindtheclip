window.onerror = function(msg, url, lineNo, columnNo, error) {
    alert("JS Error: " + msg + "\nLine: " + lineNo + "\n" + (error ? error.stack : ""));
    return false;
};
window.addEventListener('unhandledrejection', function(event) {
    console.error("Unhandled Promise Rejection:", event.reason);
});
const socket = io({
    transports: ['polling'],
    upgrade: false,
    reconnection: true,
    reconnectionAttempts: 30,
    reconnectionDelay: 1000
});
let currentPack = '';
let clipsList = [];
let currentClipIndex = 0;
let hasBackingTrack = false;
let packHasVideo = false;

// Multiplayer & User Session Globals
let amIReady = false;
let currentRoom = null;
let myName = '';
let isMultiplayer = false;
let coopSubmitted = false;

// Supabase & User Profile Globals
let supabaseClient = null;
let currentUser = null;
let currentUserProfile = null;

function validateNickname(nick) {
    if (!nick || typeof nick !== 'string') {
        return { valid: false, error: 'El nick no puede estar vacío.' };
    }
    const trimmed = nick.trim();
    if (trimmed.length < 3 || trimmed.length > 16) {
        return { valid: false, error: 'El nick debe tener entre 3 y 16 caracteres.' };
    }
    const regex = /^[a-zA-Z0-9_-]+$/;
    if (!regex.test(trimmed)) {
        return { valid: false, error: 'Solo se permiten letras, números, _ y -' };
    }
    return { valid: true, nickname: trimmed };
}

function initSupabase() {
    try {
        const savedUrl = localStorage.getItem('gtc_supabase_url') || '';
        const savedKey = localStorage.getItem('gtc_supabase_key') || '';
        
        const urlInput = document.getElementById('setting-supabase-url');
        const keyInput = document.getElementById('setting-supabase-key');
        if (urlInput) urlInput.value = savedUrl;
        if (keyInput) keyInput.value = savedKey;

        if (window.supabase && typeof window.supabase.createClient === 'function' && savedUrl && savedKey) {
            supabaseClient = window.supabase.createClient(savedUrl, savedKey);
            console.log('[SUPABASE] Connected to Supabase backend.');
        } else {
            supabaseClient = null;
            console.log('[SUPABASE] Running in local/offline session mode.');
        }
    } catch (e) {
        console.warn('[SUPABASE] Initialization error:', e);
        supabaseClient = null;
    }
}

function switchAuthTab(tab) {
    const tabLogin = document.getElementById('auth-tab-login');
    const tabRegister = document.getElementById('auth-tab-register');
    const formLogin = document.getElementById('auth-form-login');
    const formRegister = document.getElementById('auth-form-register');
    const errBanner = document.getElementById('auth-error-banner');
    const succBanner = document.getElementById('auth-success-banner');

    if (errBanner) errBanner.style.display = 'none';
    if (succBanner) succBanner.style.display = 'none';

    if (tab === 'login') {
        if (tabLogin) tabLogin.classList.add('active');
        if (tabRegister) tabRegister.classList.remove('active');
        if (formLogin) formLogin.style.display = 'flex';
        if (formRegister) formRegister.style.display = 'none';
    } else {
        if (tabRegister) tabRegister.classList.add('active');
        if (tabLogin) tabLogin.classList.remove('active');
        if (formRegister) formRegister.style.display = 'flex';
        if (formLogin) formLogin.style.display = 'none';
    }
}

function liveCheckNickname(val) {
    const msg = document.getElementById('nick-validation-msg');
    if (!msg) return;
    const res = validateNickname(val);
    if (res.valid) {
        msg.innerText = '✓ Nick válido';
        msg.style.color = '#00e676';
    } else {
        msg.innerText = `⚠️ ${res.error}`;
        msg.style.color = '#ff1744';
    }
}

function getLocalAccounts() {
    try {
        const raw = localStorage.getItem('gtc_local_accounts');
        return raw ? JSON.parse(raw) : {};
    } catch(e) {
        return {};
    }
}

function saveLocalAccount(email, password, nickname) {
    const accounts = getLocalAccounts();
    accounts[email.toLowerCase()] = { email: email.toLowerCase(), password, nickname };
    localStorage.setItem('gtc_local_accounts', JSON.stringify(accounts));
}

function getLocalAccount(email) {
    const accounts = getLocalAccounts();
    return accounts[email.toLowerCase()] || null;
}

function loginAsGuest() {
    const guestNick = 'Jugador_' + Math.floor(1000 + Math.random() * 9000);
    const guestEmail = guestNick.toLowerCase() + '@local.game';
    currentUserProfile = { nickname: guestNick, email: guestEmail };
    saveLocalUserSession(currentUserProfile);
    setLoggedInUser(currentUserProfile);
    showView('view-start');
}

async function handleAuthSubmit(event, type) {
    event.preventDefault();
    const errBanner = document.getElementById('auth-error-banner');
    const succBanner = document.getElementById('auth-success-banner');
    if (errBanner) errBanner.style.display = 'none';
    if (succBanner) succBanner.style.display = 'none';

    if (type === 'register') {
        const nickInput = document.getElementById('reg-nickname').value;
        const email = document.getElementById('reg-email').value.trim().toLowerCase();
        const password = document.getElementById('reg-password').value;

        const valRes = validateNickname(nickInput);
        if (!valRes.valid) {
            if (errBanner) {
                errBanner.innerText = valRes.error;
                errBanner.style.display = 'block';
            }
            return;
        }
        const nickname = valRes.nickname;

        if (supabaseClient) {
            try {
                const { data, error } = await supabaseClient.auth.signUp({
                    email: email,
                    password: password,
                    options: { data: { nickname: nickname } }
                });
                if (error) throw error;

                currentUser = data.user;
                currentUserProfile = { nickname: nickname, email: email };
                saveLocalUserSession(currentUserProfile);
                setLoggedInUser(currentUserProfile);
            } catch (err) {
                if (errBanner) {
                    errBanner.innerText = `Error al registrarse: ${err.message}`;
                    errBanner.style.display = 'block';
                }
                return;
            }
        } else {
            saveLocalAccount(email, password, nickname);
            currentUserProfile = { nickname: nickname, email: email };
            saveLocalUserSession(currentUserProfile);
            setLoggedInUser(currentUserProfile);
        }

        if (succBanner) {
            succBanner.innerText = `¡Cuenta creada con éxito! Bienvenido, ${nickname}.`;
            succBanner.style.display = 'block';
        }
        setTimeout(() => {
            showView('view-start');
        }, 400);

    } else if (type === 'login') {
        const email = document.getElementById('login-email').value.trim().toLowerCase();
        const password = document.getElementById('login-password').value;

        if (supabaseClient) {
            try {
                const { data, error } = await supabaseClient.auth.signInWithPassword({
                    email: email,
                    password: password
                });
                if (error) throw error;

                currentUser = data.user;
                const metaNick = (data.user && data.user.user_metadata && data.user.user_metadata.nickname) ? data.user.user_metadata.nickname : email.split('@')[0];
                const cleanNick = validateNickname(metaNick).valid ? metaNick : 'Jugador';
                currentUserProfile = { nickname: cleanNick, email: email };
                saveLocalUserSession(currentUserProfile);
                setLoggedInUser(currentUserProfile);
            } catch (err) {
                if (errBanner) {
                    errBanner.innerText = `Error al iniciar sesión: ${err.message}`;
                    errBanner.style.display = 'block';
                }
                return;
            }
        } else {
            // Local mode: check stored account
            const localAccount = getLocalAccount(email);
            if (localAccount) {
                if (localAccount.password && localAccount.password !== password) {
                    if (errBanner) {
                        errBanner.innerText = 'Contraseña incorrecta.';
                        errBanner.style.display = 'block';
                    }
                    return;
                }
                currentUserProfile = { nickname: localAccount.nickname, email: email };
            } else {
                if (errBanner) {
                    errBanner.innerText = 'Este usuario/correo no está registrado. Por favor, haz clic en Registrase primero.';
                    errBanner.style.display = 'block';
                }
                return;
            }
            saveLocalUserSession(currentUserProfile);
            setLoggedInUser(currentUserProfile);
        }

        showView('view-start');
    }
}

function setLoggedInUser(profile) {
    if (!profile) return;
    myName = profile.nickname;
    
    const nickEl = document.getElementById('user-profile-nick');
    const emailEl = document.getElementById('user-profile-email');
    const joinNameEl = document.getElementById('join-name');

    if (nickEl) nickEl.innerText = profile.nickname;
    if (emailEl) emailEl.innerText = profile.email;
    if (joinNameEl) joinNameEl.value = profile.nickname;
}

function saveLocalUserSession(profile) {
    localStorage.setItem('gtc_user_session', JSON.stringify(profile));
}

function getLocalUserSession() {
    try {
        const raw = localStorage.getItem('gtc_user_session');
        return raw ? JSON.parse(raw) : null;
    } catch(e) {
        return null;
    }
}

async function handleLogout() {
    if (supabaseClient) {
        try {
            await supabaseClient.auth.signOut();
        } catch(e) { console.warn(e); }
    }
    currentUser = null;
    currentUserProfile = null;
    myName = '';
    localStorage.removeItem('gtc_user_session');
    
    const nickEl = document.getElementById('user-profile-nick');
    const emailEl = document.getElementById('user-profile-email');
    if (nickEl) nickEl.innerText = 'Invitado';
    if (emailEl) emailEl.innerText = 'Sin sesión iniciada';

    showView('view-auth');
}

async function checkAuthSession() {
    initSupabase();
    if (supabaseClient) {
        try {
            const { data } = await supabaseClient.auth.getSession();
            if (data && data.session && data.session.user) {
                currentUser = data.session.user;
                const metaNick = currentUser.user_metadata && currentUser.user_metadata.nickname ? currentUser.user_metadata.nickname : currentUser.email.split('@')[0];
                const cleanNick = validateNickname(metaNick).valid ? metaNick : 'Jugador';
                currentUserProfile = { nickname: cleanNick, email: currentUser.email };
                setLoggedInUser(currentUserProfile);
                showView('view-start');
                return;
            }
        } catch(e) {
            console.warn('[AUTH] Error checking Supabase session:', e);
        }
    }
    
    const localSession = getLocalUserSession();
    if (localSession && localSession.nickname && localSession.email) {
        currentUserProfile = localSession;
        setLoggedInUser(currentUserProfile);
        showView('view-start');
    } else {
        showView('view-auth');
    }
}


// Global AudioContext Initialization
let audioContext = new (window.AudioContext || window.webkitAudioContext)();
let originalBuffer = null;
let backingBuffer = null;
let sourceOriginal = null;
let sourceBacking = null;

let isPlaying = false;
let isRecording = false;
let playheadAnim = null;
let startTime = 0;

let userRecordings = []; // array of { blob: Blob, buffer: AudioBuffer }
let clipOriginalBuffers = []; // to keep track of lengths for final playback
let selectedCharacters = []; // array of selected character names
let coopFinalVideoUrl = null; // Store final video URL for downloading in coop

// ==========================================
// GAME SETTINGS SYSTEM
// ==========================================
const GTC_SETTINGS_KEY = 'gtc_game_settings_v1';
const defaultGtcSettings = {
    micDevice: 'default',
    micMonitor: false,
    micDsp: false,
    volMusic: 15,
    volSfx: 70,
    volGuide: 100,
    countdown: 3,
    autoReplay: true,
    scoreSensitivity: 'normal',
    bgWaves: true,
    theme: 'neon'
};

let gtcSettings = loadGtcSettings();

function loadGtcSettings() {
    try {
        const saved = localStorage.getItem(GTC_SETTINGS_KEY);
        if (saved) {
            return { ...defaultGtcSettings, ...JSON.parse(saved) };
        }
    } catch (e) {
        console.warn('Error loading settings:', e);
    }
    return { ...defaultGtcSettings };
}

function saveGtcSettings(settings) {
    try {
        localStorage.setItem(GTC_SETTINGS_KEY, JSON.stringify(settings));
    } catch (e) {
        console.warn('Error saving settings:', e);
    }
}

function applyGtcSettings() {
    // 1. Menu Music volume
    if (typeof menuMusic !== 'undefined' && menuMusic) {
        menuMusic.volume = (gtcSettings.volMusic / 100) * 0.3;
    }
    // 2. Background Waves
    const bgWaves = document.querySelector('.background-waves');
    if (bgWaves) {
        bgWaves.style.display = gtcSettings.bgWaves ? 'block' : 'none';
    }
    // 3. Theme Colors
    const root = document.documentElement;
    if (gtcSettings.theme === 'cyberpunk') {
        root.style.setProperty('--cyan', '#ffe600');
        root.style.setProperty('--cyan-dark', '#b3a200');
        root.style.setProperty('--magenta', '#9d00ff');
    } else if (gtcSettings.theme === 'matrix') {
        root.style.setProperty('--cyan', '#00ff66');
        root.style.setProperty('--cyan-dark', '#00993d');
        root.style.setProperty('--magenta', '#00cc44');
    } else {
        // Default Neon
        root.style.setProperty('--cyan', '#98e8e8');
        root.style.setProperty('--cyan-dark', '#6fb0b0');
        root.style.setProperty('--magenta', '#ff2a75');
    }
}

// Initial application of saved settings
setTimeout(applyGtcSettings, 100);

async function populateMicDevices() {
    const select = document.getElementById('setting-mic-device');
    if (!select) return;
    select.innerHTML = '<option value="default">Por defecto del sistema</option>';
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter(d => d.kind === 'audioinput');
        audioInputs.forEach((device, idx) => {
            const opt = document.createElement('option');
            opt.value = device.deviceId;
            opt.innerText = device.label || `Micrófono ${idx + 1}`;
            select.appendChild(opt);
        });
        if (gtcSettings.micDevice) {
            select.value = gtcSettings.micDevice;
        }
    } catch(e) {
        console.warn('Could not enumerate audio devices:', e);
    }
}

function openSettingsView() {
    playSound('click');
    document.getElementById('setting-vol-music').value = gtcSettings.volMusic;
    document.getElementById('val-vol-music').innerText = gtcSettings.volMusic + '%';
    
    document.getElementById('setting-vol-sfx').value = gtcSettings.volSfx;
    document.getElementById('val-vol-sfx').innerText = gtcSettings.volSfx + '%';
    
    document.getElementById('setting-vol-guide').value = gtcSettings.volGuide;
    document.getElementById('val-vol-guide').innerText = gtcSettings.volGuide + '%';
    
    document.getElementById('setting-mic-monitor').checked = gtcSettings.micMonitor;
    document.getElementById('setting-mic-dsp').checked = gtcSettings.micDsp;
    document.getElementById('setting-countdown').value = gtcSettings.countdown;
    document.getElementById('setting-autoreplay').checked = gtcSettings.autoReplay;
    const sensEl = document.getElementById('setting-score-sensitivity');
    if (sensEl) sensEl.value = gtcSettings.scoreSensitivity;
    document.getElementById('setting-bg-waves').checked = gtcSettings.bgWaves;
    document.getElementById('setting-theme').value = gtcSettings.theme;

    // Attach range listeners for live readout
    ['music', 'sfx', 'guide'].forEach(key => {
        const input = document.getElementById(`setting-vol-${key}`);
        const label = document.getElementById(`val-vol-${key}`);
        if (input && label) {
            input.oninput = () => {
                label.innerText = input.value + '%';
                if (key === 'music' && typeof menuMusic !== 'undefined' && menuMusic) {
                    menuMusic.volume = (parseInt(input.value) / 100) * 0.3;
                }
            };
        }
    });

    populateMicDevices();
    showView('view-settings');
}

function closeSettingsView() {
    playSound('click');
    stopMicTestLive();
    showView(lastActiveViewBeforeSettings || 'view-start');
}

function saveGtcSettingsUI() {
    gtcSettings.volMusic = parseInt(document.getElementById('setting-vol-music').value);
    gtcSettings.volSfx = parseInt(document.getElementById('setting-vol-sfx').value);
    gtcSettings.volGuide = parseInt(document.getElementById('setting-vol-guide').value);
    gtcSettings.micDevice = document.getElementById('setting-mic-device').value;
    gtcSettings.micMonitor = document.getElementById('setting-mic-monitor').checked;
    gtcSettings.micDsp = document.getElementById('setting-mic-dsp').checked;
    gtcSettings.countdown = parseInt(document.getElementById('setting-countdown').value);
    gtcSettings.autoReplay = document.getElementById('setting-autoreplay').checked;
    const saveSensEl = document.getElementById('setting-score-sensitivity');
    if (saveSensEl) gtcSettings.scoreSensitivity = saveSensEl.value;
    gtcSettings.bgWaves = document.getElementById('setting-bg-waves').checked;
    gtcSettings.theme = document.getElementById('setting-theme').value;

    const supabaseUrl = document.getElementById('setting-supabase-url')?.value.trim();
    const supabaseKey = document.getElementById('setting-supabase-key')?.value.trim();
    if (supabaseUrl !== undefined) localStorage.setItem('gtc_supabase_url', supabaseUrl || '');
    if (supabaseKey !== undefined) localStorage.setItem('gtc_supabase_key', supabaseKey || '');
    initSupabase();

    saveGtcSettings(gtcSettings);
    applyGtcSettings();
    stopMicTestLive();

    playSound('click');
    const toast = document.getElementById('settings-toast');
    if (toast) {
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2200);
    }
}

function resetGtcSettings() {
    gtcSettings = { ...defaultGtcSettings };
    saveGtcSettings(gtcSettings);
    applyGtcSettings();
    openSettingsView();
}

// Live Mic Tester
let micTestStream = null;
let micTestAnalyser = null;
let micTestAnimFrame = null;

async function toggleMicTestLive() {
    const btn = document.getElementById('btn-test-mic');
    const meter = document.getElementById('mic-test-meter');
    
    if (micTestStream) {
        stopMicTestLive();
        return;
    }

    try {
        const devId = document.getElementById('setting-mic-device').value;
        const constraints = {
            audio: {
                echoCancellation: document.getElementById('setting-mic-dsp').checked,
                noiseSuppression: document.getElementById('setting-mic-dsp').checked
            }
        };
        if (devId && devId !== 'default') {
            constraints.audio.deviceId = { exact: devId };
        }

        micTestStream = await navigator.mediaDevices.getUserMedia(constraints);
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const source = ctx.createMediaStreamSource(micTestStream);
        micTestAnalyser = ctx.createAnalyser();
        micTestAnalyser.fftSize = 256;
        source.connect(micTestAnalyser);

        if (btn) { btn.innerText = '⏹ Detener Prueba'; btn.style.background = '#ff1744'; btn.style.color = '#fff'; }

        const dataArray = new Uint8Array(micTestAnalyser.frequencyBinCount);
        const updateMeter = () => {
            if (!micTestAnalyser) return;
            micTestAnalyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const average = sum / dataArray.length;
            const percent = Math.min(100, Math.round((average / 128) * 100));
            if (meter) meter.style.width = percent + '%';
            micTestAnimFrame = requestAnimationFrame(updateMeter);
        };
        updateMeter();
    } catch(e) {
        alert('Error al acceder al micrófono: ' + e.message);
        stopMicTestLive();
    }
}

function stopMicTestLive() {
    if (micTestAnimFrame) cancelAnimationFrame(micTestAnimFrame);
    micTestAnimFrame = null;
    micTestAnalyser = null;
    if (micTestStream) {
        micTestStream.getTracks().forEach(t => t.stop());
        micTestStream = null;
    }
    const btn = document.getElementById('btn-test-mic');
    const meter = document.getElementById('mic-test-meter');
    if (btn) { btn.innerText = '🎤 Probar Micrófono'; btn.style.background = 'var(--cyan)'; btn.style.color = '#000'; }
    if (meter) meter.style.width = '0%';
}

// UI
const viewPacks = document.getElementById('view-packs');
const viewPlay = document.getElementById('view-play');
const packsGrid = document.getElementById('packs-grid');

const clipImage = document.getElementById('clip-image');
const sceneVideo = document.getElementById('scene-video');
const clipSubtitle = document.getElementById('clip-subtitle');
const clipCounterText = document.getElementById('clip-counter-text');

const btnListen = document.getElementById('btn-listen');
const btnRecord = document.getElementById('btn-record');
const btnNext = document.getElementById('btn-next');
const btnFinish = document.getElementById('btn-finish');
const btnWatch = document.getElementById('btn-watch');
const btnSave = document.getElementById('btn-save');
const finishedControls = document.getElementById('finished-controls');
const mainLayout = document.querySelector('.main-layout');
const btnExit = document.getElementById('btn-exit');

const canvas = document.getElementById('waveform-canvas');
const ctx = canvas.getContext('2d');
const playhead = document.getElementById('playhead');
const scoreOverlay = document.getElementById('score-overlay');
const scoreCard = document.getElementById('score-card');
const scoreRank = document.getElementById('score-rank');
const verdictText = document.getElementById('verdict-text');
const finalScore = document.getElementById('final-score');

const menuMusic = document.getElementById('menu-music');
menuMusic.volume = 0.15; // Low volume

// Sound Effects Synthesizer
function playSound(type) {
    if (!audioContext) return;
    if (audioContext.state === 'suspended') audioContext.resume();
    
    const sfxVolMultiplier = (typeof gtcSettings !== 'undefined' && gtcSettings) ? (gtcSettings.volSfx / 100) : 0.7;
    if (sfxVolMultiplier <= 0) return;
    
    const osc = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    osc.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    if (type === 'hover') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, audioContext.currentTime); // A4
        gainNode.gain.setValueAtTime(0.05 * sfxVolMultiplier, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.1);
        osc.start();
        osc.stop(audioContext.currentTime + 0.1);
    } else if (type === 'click') {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(880, audioContext.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(110, audioContext.currentTime + 0.1);
        gainNode.gain.setValueAtTime(0.1 * sfxVolMultiplier, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.1);
        osc.start();
        osc.stop(audioContext.currentTime + 0.1);
    } else if (type === 'transition') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(300, audioContext.currentTime);
        osc.frequency.exponentialRampToValueAtTime(600, audioContext.currentTime + 0.3);
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.05 * sfxVolMultiplier, audioContext.currentTime + 0.1);
        gainNode.gain.linearRampToValueAtTime(0.001, audioContext.currentTime + 0.4);
        osc.start();
        osc.stop(audioContext.currentTime + 0.4);
    }
}

// Fade out music helper
let musicFadeInterval = null;
function fadeOutMusic(durationMs = 1500) {
    if (menuMusic.paused) return;
    if (musicFadeInterval) clearInterval(musicFadeInterval);
    
    let startVolume = menuMusic.volume;
    let steps = 30;
    let stepTime = durationMs / steps;
    let volumeStep = startVolume / steps;
    
    musicFadeInterval = setInterval(() => {
        if (menuMusic.volume > volumeStep) {
            menuMusic.volume -= volumeStep;
        } else {
            menuMusic.pause();
            const defaultVol = (typeof gtcSettings !== 'undefined' && gtcSettings) ? (gtcSettings.volMusic / 100) * 0.3 : 0.15;
            menuMusic.volume = defaultVol;
            clearInterval(musicFadeInterval);
            musicFadeInterval = null;
        }
    }, stepTime);
}

function playMenuMusic() {
    if (musicFadeInterval) {
        clearInterval(musicFadeInterval);
        musicFadeInterval = null;
    }
    const targetVol = (typeof gtcSettings !== 'undefined' && gtcSettings) ? (gtcSettings.volMusic / 100) * 0.3 : 0.15;
    menuMusic.volume = targetVol;
    menuMusic.play().catch(e => console.log('Autoplay prevented'));
}

// Global UI Interaction Hooks
function hookUIInteractions() {
    const interactables = document.querySelectorAll('.btn, .btn-pill, .pack-card, .btn-menu, button, input[type="button"]');
    interactables.forEach(el => {
        // Prevent double hooking
        if (el.dataset.hooked) return;
        el.dataset.hooked = 'true';
        
        el.addEventListener('mouseenter', () => {
            if (!el.disabled) playSound('hover');
        });
        el.addEventListener('mousedown', () => {
            if (!el.disabled) playSound('click');
        });
    });
}

// Handle first interaction for audio autoplay policies
document.body.addEventListener('click', () => {
    if (audioContext.state === 'suspended') audioContext.resume();
    // Only play menu music if we are on the start menu, packs menu, or join menu
    const activeView = document.querySelector('.view.active');
    if (activeView && ['view-start', 'view-packs', 'view-join'].includes(activeView.id)) {
        if (menuMusic.paused) menuMusic.play().catch(e => console.log('Autoplay prevented'));
    }
});

let autoSaveTimer = null;
let currentCreatorJobId = null;

let isHost = false;
let multiplayerScoringMode = 'ia'; // 'ia' or 'voting'
let myVoteTargetComp = null;
let myVoteTargetCoop = null;
let isVotingCompleted = false;
let multiplayerGameMode = 'competitivo';
let roomCharacters = {}; // char_name -> sid
let claimedCharacters = []; // List of char names claimed by me
let allPackCharacters = [];
let coopVideoUrl = null;
let playersReadyForCoop = 0;
let expectedPlayersForCoop = 0;
let hostCoopClips = {}; // sid -> { index: blobUrl }


// View Management

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
            const dateStr = proj.updated_at ? new Date(proj.updated_at * 1000).toLocaleString() : 'Reciente';
            const numLines = proj.lines ? proj.lines.length : 0;
            const packTitle = proj.pack_name || proj.name || 'Sin título';
            const targetId = proj.job_id || proj.name;

            const el = document.createElement('div');
            el.style.cssText = 'background: rgba(20,25,35,0.85); border: 1px solid #2a3545; padding: 15px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s; margin-bottom: 10px;';
            
            el.innerHTML = `
                <div style="text-align: left;">
                    <h3 style="color: #fff; margin: 0 0 5px 0; font-size: 1.1rem;">${packTitle}</h3>
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">${numLines} diálogos · Última edición: ${dateStr}</p>
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button class="btn-pill btn-cyan" onclick="openProjectInEditor('${targetId}', '${encodeURIComponent(packTitle)}')">✏️ Modificar</button>
                    <button class="btn-pill" onclick="deleteRecentProject('${targetId}', '${encodeURIComponent(packTitle)}')" style="background: rgba(255,64,129,0.15); color: #ff4081; border: 1px solid #ff4081; padding: 8px 14px; font-weight: bold; cursor: pointer; border-radius: 8px;">🗑️</button>
                </div>
            `;
            el.onmouseenter = () => el.style.background = 'rgba(30,40,55,0.9)';
            el.onmouseleave = () => el.style.background = 'rgba(20,25,35,0.85)';
            list.appendChild(el);
        });
    } catch (e) {
        console.error("Error loading recent projects:", e);
        list.innerHTML = '<p style="color: #ff5252; text-align: center; margin-top: 20px;">Error al cargar proyectos.</p>';
    }
}

function openProjectInEditor(jobId, packName) {
    window.location.href = `/editor?job_id=${jobId}&pack_name=${packName}`;
}

async function deleteRecentProject(jobId, packNameDecoded) {
    const packName = decodeURIComponent(packNameDecoded);
    if (!confirm(`¿Eliminar el proyecto "${packName}"?`)) return;
    try {
        await fetch(`/api/projects/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
        loadRecentProjects();
    } catch(e) {
        alert("Error al eliminar el proyecto.");
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
        autoSaveProject();
        renderEditorCharacters();
        autoSaveProject();
        
        // Wait for video metadata to get real duration before rendering timeline
        const setupRender = () => {
            if (video.duration && isFinite(video.duration)) {
                editorVideoDuration = video.duration;
            }
            renderTimeline();
            renderLinesList();
        };
        if (video.readyState >= 1 && video.duration && isFinite(video.duration)) {
            editorVideoDuration = video.duration;
            renderTimeline();
            renderLinesList();
        } else {
            video.addEventListener('loadedmetadata', setupRender, { once: true });
            // Fallback: derive duration from last line end time
            if (editorLines.length > 0) {
                const maxEnd = Math.max(...editorLines.map(l => l.end || 0));
                if (maxEnd > 0) editorVideoDuration = maxEnd + 5;
            }
            renderTimeline();
            renderLinesList();
        }
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

function cleanGameLayoutAndState() {
    stopAudio();
    stopAfkChecker();
    isRecording = false;
    isPlaying = false;
    isCountdownActive = false;
    isStartingRecording = false;
    coopSubmitted = false;
    coopFinalVideoUrl = null;
    window._lastCompGameOverData = null;
    compWaitingPlayers = {};
    competitiveVideos = [];
    
    // Clear finished state layout
    if (typeof mainLayout !== 'undefined' && mainLayout) {
        mainLayout.classList.remove('finished-state');
    }
    
    // Hide score card & end controls
    if (typeof scoreCard !== 'undefined' && scoreCard) {
        scoreCard.classList.add('hidden');
        scoreCard.style.opacity = '';
        scoreCard.style.transform = '';
    }
    if (typeof finishedControls !== 'undefined' && finishedControls) {
        finishedControls.classList.add('hidden');
    }
    
    const scoreOverlay = document.getElementById('score-overlay');
    if (scoreOverlay) scoreOverlay.classList.add('hidden');

    const coopWaiting = document.getElementById('coop-waiting-overlay');
    if (coopWaiting) coopWaiting.style.display = 'none';

    const coopRanking = document.getElementById('coop-ranking-modal');
    if (coopRanking) coopRanking.style.display = 'none';

    const compLabel = document.getElementById('competitive-player-label');
    if (compLabel) compLabel.style.display = 'none';

    const btnPrevVideo = document.getElementById('btn-prev-video');
    if (btnPrevVideo) btnPrevVideo.style.display = 'none';

    const btnNextVideo = document.getElementById('btn-next-video');
    if (btnNextVideo) btnNextVideo.style.display = 'none';

    const panelButtons = document.querySelector('.panel-buttons');
    if (panelButtons) panelButtons.style.display = 'flex';

    if (typeof btnListen !== 'undefined' && btnListen) {
        btnListen.innerText = "▶ ESCUCHAR";
        btnListen.disabled = false;
    }
    if (typeof btnRecord !== 'undefined' && btnRecord) {
        btnRecord.innerText = "🎙 GRABAR";
        btnRecord.disabled = false;
    }
    if (typeof btnNext !== 'undefined' && btnNext) {
        btnNext.classList.remove('hidden');
        btnNext.disabled = true;
    }
    if (typeof btnFinish !== 'undefined' && btnFinish) {
        btnFinish.classList.add('hidden');
        btnFinish.disabled = true;
    }
}

let currentViewId = 'view-start';
let lastActiveViewBeforeSettings = 'view-start';
let afkCheckerTimer = null;
let lastUserActivityTime = Date.now();

function resetAfkActivity() {
    lastUserActivityTime = Date.now();
}

if (typeof window !== 'undefined') {
    ['click', 'keydown', 'mousemove', 'touchstart'].forEach(evtType => {
        window.addEventListener(evtType, resetAfkActivity, { passive: true });
    });
}

function startAfkChecker() {}
function stopAfkChecker() {}

// ReDub Feature: Instant Background Upload of takes
async function uploadSingleTakeInBackground(clipIndex, audioBlob) {
    if (!audioBlob || !currentRoom || !clipsList[clipIndex]) return;
    const clip = clipsList[clipIndex];
    const clipName = clip.name || clip.file || `clip_${clipIndex}.wav`;
    
    const formData = new FormData();
    formData.append('room', currentRoom);
    formData.append('sid', socket ? socket.id : '');
    formData.append('player_name', myName || '');
    formData.append('clip_name', clipName);
    formData.append('audio', audioBlob, `take_${clipIndex}.wav`);
    
    try {
        console.log(`[BACKGROUND UPLOAD] Uploading take for clip ${clipName}...`);
        await fetch('/api/upload_single_take', {
            method: 'POST',
            body: formData
        });
        console.log(`[BACKGROUND UPLOAD] Take for clip ${clipName} uploaded successfully!`);
    } catch(e) {
        console.warn(`[BACKGROUND UPLOAD] Error uploading take for ${clipName}:`, e);
    }
}

// ReDub Feature: Live Mic Volume Meter (AudioContext + AnalyserNode)
let _micAudioContext = null;
let _micAnalyser = null;
let _micStream = null;
let _micAnimFrame = null;

async function initMicVUMeter() {
    const statusLabel = document.getElementById('mic-status-label');
    const barFill = document.getElementById('vu-meter-bar-fill');
    if (!statusLabel || !barFill) return;

    try {
        if (!_micStream) {
            _micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        }
        
        if (!_micAudioContext) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            _micAudioContext = new AudioCtx();
            const source = _micAudioContext.createMediaStreamSource(_micStream);
            _micAnalyser = _micAudioContext.createAnalyser();
            _micAnalyser.fftSize = 128;
            source.connect(_micAnalyser);
        }

        if (_micAudioContext.state === 'suspended') {
            await _micAudioContext.resume();
        }

        const dataArray = new Uint8Array(_micAnalyser.frequencyBinCount);
        
        function updateMeter() {
            if (!_micAnalyser) return;
            _micAnalyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            let average = sum / dataArray.length;
            let percent = Math.min(100, Math.round((average / 128) * 100 * 1.5));
            
            if (barFill) {
                barFill.style.width = percent + '%';
            }
            if (statusLabel) {
                if (percent > 5) {
                    statusLabel.innerText = "🟢 Detectando voz (" + percent + "%)";
                    statusLabel.style.color = "#00e676";
                } else {
                    statusLabel.innerText = "⚪ Micro listo (Silencio)";
                    statusLabel.style.color = "#aaa";
                }
            }
            _micAnimFrame = requestAnimationFrame(updateMeter);
        }

        if (_micAnimFrame) cancelAnimationFrame(_micAnimFrame);
        updateMeter();

    } catch (err) {
        console.warn("[MIC VU] Could not access microphone:", err);
        if (statusLabel) {
            statusLabel.innerText = "⚠️ Permitir micro en el navegador";
            statusLabel.style.color = "#ff4081";
        }
    }
}

function showView(viewId) {
    currentViewId = viewId;
    if (viewId !== 'view-settings') {
        lastActiveViewBeforeSettings = viewId;
    }
    playSound('transition');
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    if (viewId === 'view-creator-mode') {
        loadRecentProjects();
    }
    if (viewId === 'view-lobby' || viewId === 'view-play') {
        setTimeout(initMicVUMeter, 300);
    }
}

let currentPlayMode = 'single'; // 'single' or 'multi'

// Start Menu logic
document.getElementById('btn-play-single').onclick = () => {
    currentPlayMode = 'single';
    showView('view-packs');
    playMenuMusic();
    loadPacks();
};

document.getElementById('btn-play-online').onclick = () => {
    showView('view-online-menu');
};



document.getElementById('btn-create-room').onclick = () => {
    currentPlayMode = 'multi';
    showView('view-packs');
    playMenuMusic();
    loadPacks();
};

document.getElementById('btn-join-room-menu').onclick = () => {
    showView('view-join');
};

document.getElementById('btn-back-from-packs').onclick = () => {
    if (currentPlayMode === 'multi') {
        showView('view-online-menu');
    } else {
        showView('view-start');
    }
};

async function loadPacks() {
    try {
        const userQuery = myName ? `&user=${encodeURIComponent(myName)}` : '';
        const res = await fetch(`/api/packs?t=${Date.now()}${userQuery}`);
        const packs = await res.json();
        
        packsGrid.innerHTML = '';
        if (!packs || packs.length === 0) {
            packsGrid.innerHTML = '<p style="color: #666; text-align: center; grid-column: 1/-1;">No hay escenas creadas todavía.</p>';
            return;
        }

        packs.forEach(pack => {
            const card = document.createElement('div');
            card.className = 'pack-card';
            card.style.position = 'relative';

            const img = document.createElement('img');
            if (pack.icon_url) {
                img.src = pack.icon_url;
                pack.cached_icon = pack.icon_url;
            } else {
                const svgData = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="100%" height="100%" fill="%231e222b"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="20" fill="%234bd1c2">${encodeURIComponent(pack.name.substring(0, 15))}</text></svg>`;
                img.src = `data:image/svg+xml;utf8,${svgData}`;
                pack.cached_icon = img.src;
            }
            img.alt = pack.name;
            card.appendChild(img);
            card.innerHTML += `<span>${pack.name}</span>`;

            // Delete pack button overlay
            const delBtn = document.createElement('button');
            delBtn.innerHTML = '🗑️';
            delBtn.title = 'Eliminar escena del catálogo';
            delBtn.style.cssText = 'position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.75); border: 1px solid #ff4081; color: #ff4081; border-radius: 50%; width: 32px; height: 32px; font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; justify-content: center; z-index: 10; transition: transform 0.2s;';
            delBtn.onmouseenter = () => delBtn.style.transform = 'scale(1.15)';
            delBtn.onmouseleave = () => delBtn.style.transform = 'scale(1.0)';
            
            delBtn.onclick = async (e) => {
                e.stopPropagation();
                if (confirm(`¿Seguro que quieres eliminar la escena "${pack.name}" de tu catálogo de escenas?`)) {
                    try {
                        const delRes = await fetch(`/api/packs/${encodeURIComponent(pack.name)}`, { method: 'DELETE' });
                        const delData = await delRes.json();
                        if (delData.error) alert("Error: " + delData.error);
                        else loadPacks();
                    } catch(err) {
                        alert("Error al eliminar la escena.");
                    }
                }
            };
            card.appendChild(delBtn);

            card.onclick = async () => {
                if (currentPlayMode === 'single') {
                    showView('view-play');
                    isMultiplayer = false;
                    fadeOutMusic();
                    selectPack(pack.name);
                } else {
                    window.currentPackIcon = pack.cached_icon;
                    await createMultiplayerRoom(pack.name);
                }
            };
            packsGrid.appendChild(card);
        });
        
        hookUIInteractions();
    } catch (e) {
        console.error('Error loading packs', e);
    }
}


// 2. Select Pack & Init
async function selectPack(packName) {
    currentPack = packName;
    const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/clips`);
    const data = await res.json();
    
    clipsList = data.clips;
    hasBackingTrack = data.has_backing_track;
    // Normalize clip format to always have .character and .name
    clipsList.forEach((clip, i) => {
        if (!clip.character && clip.name) {
            let parts = clip.name.split('_');
            clip.character = parts.length > 1 ? parts.slice(1).join('_').replace('.wav', '') : clip.name;
        }
        if (!clip.name && clip.character) {
            clip.name = `clip_${i}_${clip.character}.wav`;
        }
    });

    
    // Check for video
    try {
        let vRes = await fetch(`/media/${encodeURIComponent(packName)}/dub_video.mp4?t=` + Date.now(), {method: 'HEAD'});
        if (vRes.ok) {
            packHasVideo = true;
            window.currentPackVideo = `/media/${packName}/dub_video.mp4`;
        } else {
            let vRes2 = await fetch(`/media/${encodeURIComponent(packName)}/dub_video.ogv?t=` + Date.now(), {method: 'HEAD'});
            if (vRes2.ok) {
                packHasVideo = true;
                window.currentPackVideo = `/media/${packName}/dub_video.ogv`;
            } else {
                packHasVideo = false;
            }
        }
    } catch(e) { packHasVideo = false; }
    
    if (packHasVideo) {
        sceneVideo.src = window.currentPackVideo;
        sceneVideo.load();
    }
    
    if (clipsList.length === 0) {
        alert("Este pack no tiene clips vÃ¡lidos.");
        return;
    }
    
    if (audioContext.state === 'suspended') await audioContext.resume();
    
    if (hasBackingTrack) {
        const bgRes = await fetch(`/media/${encodeURIComponent(packName)}/_backing_track.mp3`);
        if (!bgRes.ok) {
            console.warn('Could not load backing track:', bgRes.status);
            backingBuffer = null;
        } else {
            const bgArray = await bgRes.arrayBuffer();
            try {
                backingBuffer = await audioContext.decodeAudioData(bgArray);
            } catch(e) {
                console.warn('Could not decode backing track:', e);
                backingBuffer = null;
            }
        }
    } else {
        backingBuffer = null;
    }
    
    cleanGameLayoutAndState();
    userRecordings = new Array(clipsList.length).fill(null);
    clipOriginalBuffers = new Array(clipsList.length).fill(null);
    currentClipIndex = 0;
    
    viewPacks.classList.remove('active');
    
    // Instead of directly showing the game view, show the character select modal
    const charModal = document.getElementById('character-select-modal');
    const checkboxesDiv = document.getElementById('character-checkboxes');
    checkboxesDiv.innerHTML = '';
    
    // Extract unique character names
    const uniqueChars = new Set();
    clipsList.forEach(clip => {
        let charName = clip.character;
        uniqueChars.add(charName);
    });
    
    uniqueChars.forEach(charName => {
        const label = document.createElement('label');
        label.style.display = 'flex';
        label.style.alignItems = 'center';
        label.style.padding = '10px 15px';
        label.style.background = 'rgba(255,255,255,0.05)';
        label.style.border = '1px solid rgba(255,255,255,0.1)';
        label.style.borderRadius = '8px';
        label.style.cursor = 'pointer';
        label.style.transition = 'all 0.2s';
        label.onmouseenter = () => label.style.background = 'rgba(0, 229, 255, 0.1)';
        label.onmouseleave = () => label.style.background = 'rgba(255,255,255,0.05)';
        label.innerHTML = `<input type="checkbox" value="${charName}" checked style="margin-right: 15px; transform: scale(1.2); accent-color: var(--cyan); cursor: pointer;"> <span style="color: white; font-size: 1.1rem;">${charName}</span>`;
        checkboxesDiv.appendChild(label);
    });
    
    charModal.style.display = 'flex';
}

function advanceToNextSelectedClip(currentIndex) {
    let index = currentIndex + 1;
    while (index < clipsList.length) {
        let charName = clipsList[index].character;
        if (selectedCharacters.includes(charName)) {
            currentClipIndex = index;
            loadClip(index);
            return;
        }
        index++;
    }
    // Reached the end
    calculateFinalScore();
}

document.getElementById('btn-start-dubbing').onclick = () => {
    const charModal = document.getElementById('character-select-modal');
    const checked = charModal.querySelectorAll('input[type="checkbox"]:checked');
    selectedCharacters = Array.from(checked).map(cb => cb.value);
    
    if (selectedCharacters.length === 0) {
        alert("¡Debes seleccionar al menos un personaje!");
        return;
    }
    
    cleanGameLayoutAndState();
    userRecordings = new Array(clipsList.length).fill(null);
    
    charModal.style.display = 'none';
    viewPlay.classList.add('active');
    sceneVideo.style.display = 'none';
    sceneVideo.classList.add('hidden');
    clipImage.style.display = 'block';
    
    if (!menuMusic.paused) {
        fadeOutMusic();
    }
    
    advanceToNextSelectedClip(-1);
};

function isLastSelectedClip(currentIndex) {
    for (let i = currentIndex + 1; i < clipsList.length; i++) {
        let charName = clipsList[i].character;
        if (!selectedCharacters || selectedCharacters.length === 0 || selectedCharacters.includes(charName)) {
            return false;
        }
    }
    return true;
}

// 3. Load Individual Clip
async function loadClip(index) {
    const clip = clipsList[index];
    let selectedClipsCount = 0;
    let currentSelectedIndex = 0;
    for (let i = 0; i < clipsList.length; i++) {
        let charName = clipsList[i].character;
        if (!selectedCharacters || selectedCharacters.length === 0 || selectedCharacters.includes(charName)) {
            selectedClipsCount++;
            if (i <= index) currentSelectedIndex++;
        }
    }
    clipCounterText.innerText = `Toma ${currentSelectedIndex} de ${selectedClipsCount}`;
    
    let charName = clip.character;
    const modeTitle = document.getElementById('play-mode-title');
    if (modeTitle) {
        const modeLabel = isMultiplayer ? (multiplayerGameMode === 'cooperativo' ? '🤝 COOPERATIVO' : '⚔️ COMPETITIVO') : '🎬 MODO SOLITARIO';
        modeTitle.innerText = `${modeLabel} · Personaje: ${charName}`;
    }

    if (clip.image) {
        clipImage.src = `/media/${encodeURIComponent(currentPack)}/${encodeURIComponent(clip.image_file)}`;
    } else {
        clipImage.src = window.currentPackIcon || '';
    }
    let textToDisplay = clip.text ? clip.subtitle : clip.name;
    document.querySelector('.subtitle').innerHTML = `<span style="color:var(--cyan)">[${charName}]</span> "${textToDisplay}"`;
    
    let sourceUrl = `/media/${encodeURIComponent(currentPack)}/${encodeURIComponent(clip.audio_file)}`;
    
    stopAudio();
    isRecording = false;
    isCountdownActive = false;
    isStartingRecording = false;
    if (btnRecord) btnRecord.innerText = "🎙️ Grabar Toma";
    if (btnListen) btnListen.innerText = "🔊 Escuchar Toma Guía";

    const btnPrevClip = document.getElementById('btn-prev-clip');
    if (btnPrevClip) {
        if (currentSelectedIndex > 1) {
            btnPrevClip.style.display = 'inline-block';
            btnPrevClip.onclick = () => {
                stopAudio();
                let prevIdx = index - 1;
                while (prevIdx >= 0) {
                    let cName = clipsList[prevIdx].character;
                    if (!selectedCharacters || selectedCharacters.length === 0 || selectedCharacters.includes(cName)) {
                        currentClipIndex = prevIdx;
                        loadClip(prevIdx);
                        return;
                    }
                    prevIdx--;
                }
            };
        } else {
            btnPrevClip.style.display = 'none';
        }
    }

    btnNext.disabled = true;
    btnWatch.disabled = true;
    playhead.style.left = '0px';
    
    btnListen.disabled = true;
    btnRecord.disabled = true;
    
    // Use cached buffer if already loaded (avoids redundant network fetch)
    if (clipOriginalBuffers[index]) {
        originalBuffer = clipOriginalBuffers[index];
        btnListen.disabled = false;
        btnRecord.disabled = false;
        btnNext.disabled = true;
        btnNext.classList.remove('hidden');
        btnFinish.classList.add('hidden');
        btnFinish.disabled = true;
        if (userRecordings[index]) {
            drawWaveform(originalBuffer, '#bc00ff');
            drawWaveform(userRecordings[index].buffer, '#00ffff', true);
            if (isLastSelectedClip(index)) {
                btnNext.classList.add('hidden');
                btnFinish.classList.remove('hidden');
                btnFinish.disabled = false;
            } else {
                btnNext.disabled = false;
            }
        } else {
            drawWaveform(originalBuffer, '#bc00ff');
        }
        // Preload next clip in background
        _preloadClip(index + 1);
        return;
    }

    // Fetch clip audio with error handling
    const audioUrl = `/media/${encodeURIComponent(currentPack)}/${encodeURIComponent(clip.audio_file)}`;
    try {
        const res = await fetch(audioUrl);
        if (!res.ok) {
            alert(`Error al cargar el audio del clip (${res.status}). Recarga la página o contacta con el anfitrión.`);
            btnListen.disabled = false;
            btnRecord.disabled = false;
            return;
        }
        const arrayBuffer = await res.arrayBuffer();
        try {
            originalBuffer = await audioContext.decodeAudioData(arrayBuffer);
        } catch(e) {
            console.error('decodeAudioData failed for', audioUrl, e);
            alert(`Error decodificando audio. El archivo puede estar corrupto o en formato no soportado.`);
            btnListen.disabled = false;
            btnRecord.disabled = false;
            return;
        }
    } catch(netErr) {
        console.error('Fetch failed for', audioUrl, netErr);
        alert(`Error de red al cargar el audio. Comprueba tu conexión o recarga la página.`);
        btnListen.disabled = false;
        btnRecord.disabled = false;
        return;
    }
    clipOriginalBuffers[index] = originalBuffer;
    // Kick off background preload of next clip immediately after loading current
    _preloadClip(index + 1);
    
    btnNext.disabled = true;
    btnNext.classList.remove('hidden');
    btnFinish.classList.add('hidden');
    btnFinish.disabled = true;
    
    btnListen.disabled = false;
    btnRecord.disabled = false;
    
    if (userRecordings[index]) {
        drawWaveform(originalBuffer, '#bc00ff');
        drawWaveform(userRecordings[index].buffer, '#00ffff', true);
        
        if (isLastSelectedClip(index)) {
            btnNext.classList.add('hidden');
            btnFinish.classList.remove('hidden');
            btnFinish.disabled = false;
        } else {
            btnNext.disabled = false;
        }
    } else {
        drawWaveform(originalBuffer, '#bc00ff');
    }
    
    btnListen.disabled = false;
    btnRecord.disabled = false;
}

/**
 * Background preload: silently fetch and decode the next clip's audio
 * so it's ready in cache before the user navigates to it.
 */
async function _preloadClip(index) {
    if (!clipsList || index < 0 || index >= clipsList.length) return;
    if (clipOriginalBuffers[index]) return; // already cached
    try {
        const clip = clipsList[index];
        const url = `/media/${encodeURIComponent(currentPack)}/${encodeURIComponent(clip.audio_file)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const buf = await res.arrayBuffer();
        clipOriginalBuffers[index] = await audioContext.decodeAudioData(buf);
    } catch(e) {
        // Preload failures are silent — the user will just get a fresh fetch if needed
        console.debug('Preload failed for clip', index, e);
    }
}

// Drawing Real Waveforms
function drawWaveform(buffer, color, overlay = false) {
    if (!overlay) ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const channelData = buffer.getChannelData(0);
    const step = Math.ceil(channelData.length / canvas.width);
    const amp = canvas.height / 2;
    
    ctx.fillStyle = color;
    ctx.beginPath();
    
    for (let i = 0; i < canvas.width; i++) {
        let min = 1.0;
        let max = -1.0;
        for (let j = 0; j < step; j++) {
            const datum = channelData[(i * step) + j]; 
            if (datum < min) min = datum;
            if (datum > max) max = datum;
        }
        
        let y = amp + (min * amp);
        let h = Math.max(1, (max - min) * amp);
        
        // Draw centered
        ctx.fillRect(i, y, 1, h);
    }
    
    // Draw middle line
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, canvas.height/2, canvas.width, 1);
}

function startPlayhead(duration) {
    startTime = audioContext.currentTime;
    cancelAnimationFrame(playheadAnim);
    
    function animate() {
        const elapsed = audioContext.currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1.0);
        playhead.style.left = (progress * 400) + 'px';
        
        if (progress < 1.0) {
            playheadAnim = requestAnimationFrame(animate);
        } else {
            stopAudio();
            btnListen.disabled = false;
            btnRecord.disabled = false;
        }
    }
    animate();
}

let recordAnalyser = null;
let recordDataArray = null;

function startPlayheadWithRecord(duration, analyser) {
    startTime = audioContext.currentTime;
    cancelAnimationFrame(playheadAnim);
    
    // Play guide audio at low volume if enabled
    const recordGuideVolSlider = document.getElementById('record-guide-vol-slider');
    const guideVol = recordGuideVolSlider ? (parseFloat(recordGuideVolSlider.value) / 100.0) : 0.20;
    if (guideVol > 0 && originalBuffer) {
        try {
            const guideSource = audioContext.createBufferSource();
            guideSource.buffer = originalBuffer;
            const guideGain = audioContext.createGain();
            guideGain.gain.value = guideVol;
            window.activeGuideGainNode = guideGain;
            guideSource.connect(guideGain);
            guideGain.connect(audioContext.destination);
            guideSource.start(0);
            sourceOriginal = guideSource;
        } catch(e) {
            console.warn("Guide audio play error:", e);
        }
    }
    
    // Clear canvas and draw purple base
    drawWaveform(originalBuffer, '#bc00ff');
    
    ctx.fillStyle = '#00ffff'; // Cyan for recording
    
    function animate() {
        const elapsed = audioContext.currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1.0);
        
        const currentX = Math.floor(progress * canvas.width);
        playhead.style.left = (progress * 400) + 'px';
        
        if (analyser) {
            analyser.getFloatTimeDomainData(recordDataArray);
            let max = 0;
            for(let i = 0; i < recordDataArray.length; i++) {
                if(Math.abs(recordDataArray[i]) > max) max = Math.abs(recordDataArray[i]);
            }
            
            const amp = canvas.height / 2;
            let h = Math.max(1, max * 2 * amp);
            ctx.fillRect(currentX, amp - (h/2), 2, h); // Draw cyan line centered
        }
        
        if (progress < 1.0 && isRecording) {
            playheadAnim = requestAnimationFrame(animate);
        } else {
            stopAudio();
            btnListen.disabled = false;
            btnRecord.disabled = false;
        }
    }
    animate();
}

function stopAudio() {
    if (playheadAnim) {
        cancelAnimationFrame(playheadAnim);
        playheadAnim = null;
    }
    if (sourceOriginal) { try { sourceOriginal.stop(); sourceOriginal.disconnect(); } catch(e){} sourceOriginal = null; }
    if (sourceBacking) { try { sourceBacking.stop(); sourceBacking.disconnect(); } catch(e){} sourceBacking = null; }
    
    if (window.playbackSources) {
        window.playbackSources.forEach(src => { try { src.stop(); src.disconnect(); } catch(e){} });
        window.playbackSources = [];
    }
    if (window.playbackTimeout) {
        clearTimeout(window.playbackTimeout);
        window.playbackTimeout = null;
    }
    if (packHasVideo && sceneVideo) {
        sceneVideo.pause();
        sceneVideo.style.display = 'none';
        sceneVideo.classList.add('hidden');
        clipImage.style.display = 'block';
    }
    isPlaying = false;

    // Reset button states
    if (btnListen) {
        btnListen.innerText = "▶ ESCUCHAR";
        btnListen.disabled = false;
    }
    if (btnRecord && !isRecording && !isCountdownActive && !isStartingRecording) {
        btnRecord.innerText = "🎙 GRABAR";
        btnRecord.disabled = false;
    }
}

/**
 * Helper to play video safely with a 250ms fallback timeout.
 * Prevents HTML5 video buffering/seeking promises from stalling or freezing recording/playback over network.
 */
function safePlayMedia(video, callback) {
    if (!video) { callback(); return; }
    let executed = false;
    const runOnce = () => {
        if (!executed) {
            executed = true;
            callback();
        }
    };
    const timer = setTimeout(runOnce, 250);
    try {
        const p = video.play();
        if (p && typeof p.then === 'function') {
            p.then(() => {
                clearTimeout(timer);
                runOnce();
            }).catch(err => {
                console.warn("Video play promise error:", err);
                clearTimeout(timer);
                runOnce();
            });
        } else {
            clearTimeout(timer);
            runOnce();
        }
    } catch(e) {
        console.warn("Video play call exception:", e);
        clearTimeout(timer);
        runOnce();
    }
}

btnListen.onclick = async () => {
    if (isRecording || isCountdownActive) return; // Cannot listen while recording
    
    // Toggle / Cancel playback if already playing
    if (isPlaying) {
        stopAudio();
        return;
    }
    
    if (audioContext.state === 'suspended') { try { await audioContext.resume(); } catch(e){} }
    isPlaying = true;
    btnListen.innerText = "⏹ DETENER";
    btnListen.disabled = false; // keep clickable to allow cancel!
    btnRecord.disabled = true;
    
    sourceOriginal = audioContext.createBufferSource();
    sourceOriginal.buffer = originalBuffer;
    
    // Guide volume setting
    const recordGuideVolSlider = document.getElementById('record-guide-vol-slider');
    const currentGuideVol = recordGuideVolSlider ? (parseFloat(recordGuideVolSlider.value) / 100.0) : 0.20;
    const guideGain = audioContext.createGain();
    guideGain.gain.value = currentGuideVol;
    window.activeGuideGainNode = guideGain;
    sourceOriginal.connect(guideGain);
    guideGain.connect(audioContext.destination);
    
    if (backingBuffer) {
        sourceBacking = audioContext.createBufferSource();
        sourceBacking.buffer = backingBuffer;
        sourceBacking.connect(guideGain);
    }
    
    if (packHasVideo) {
        sceneVideo.muted = true;
        sceneVideo.style.display = 'block';
        sceneVideo.classList.remove('hidden');
        clipImage.style.display = 'none';
        try { sceneVideo.currentTime = clipsList[currentClipIndex].timestamp || 0; } catch(e){}
        const startListen = () => {
            if (!isPlaying) return;
            if (sourceOriginal) sourceOriginal.start();
            if (backingBuffer && sourceBacking) sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0);
            startPlayhead(originalBuffer.duration);
        };
        safePlayMedia(sceneVideo, startListen);
    } else {
        sourceOriginal.start();
        if (backingBuffer) sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0);
        startPlayhead(originalBuffer.duration);
    }
};

let isCountdownActive = false;
let isStartingRecording = false;
let recordingTimer = null;
let activeMediaRecorder = null;

function resetRecordState() {
    isRecording = false;
    isCountdownActive = false;
    isStartingRecording = false;
    if (recordingTimer) {
        clearTimeout(recordingTimer);
        recordingTimer = null;
    }
    if (btnRecord) {
        btnRecord.innerText = "🎙 GRABAR";
        btnRecord.disabled = false;
    }
    if (btnListen && !isPlaying) {
        btnListen.disabled = false;
    }
}

btnRecord.onclick = async () => {
    // 1. If currently listening to original audio, stop listening
    if (isPlaying) {
        stopAudio();
    }
    
    // 2. If countdown is running -> Cancel countdown and return to idle
    if (isCountdownActive) {
        resetRecordState();
        if (clipSubtitle && clipsList && clipsList[currentClipIndex]) {
            const clip = clipsList[currentClipIndex];
            clipSubtitle.innerText = clip.text ? clip.subtitle : clip.name;
        }
        return;
    }

    // 3. If currently recording -> Stop recording and process take
    if (isRecording) {
        stopAudio();
        if (activeMediaRecorder && activeMediaRecorder.state === 'recording') {
            try {
                activeMediaRecorder.stop();
            } catch(e) {
                console.warn("Error stopping activeMediaRecorder:", e);
                resetRecordState();
            }
        } else {
            resetRecordState();
        }
        return;
    }

    // 4. Prevent double clicks while initializing mic
    if (isStartingRecording) return;

    // 5. Check Audio Buffer readiness
    if (!originalBuffer) {
        alert('Cargando el audio de la escena... Por favor inténtalo de nuevo en unos segundos.');
        return;
    }

    // 6. Check Browser WebRTC Support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Tu navegador o tipo de conexión (HTTP no segura) no permite el acceso al micrófono. Asegúrate de usar una conexión HTTPS o localhost.');
        return;
    }

    if (audioContext.state === 'suspended') { 
        try { await audioContext.resume(); } catch(e){} 
    }

function playCountdownBeep(isFinal = false) {
    if (!audioContext) return;
    if (audioContext.state === 'suspended') { try { audioContext.resume(); } catch(e){} }
    
    const now = audioContext.currentTime;
    const gain = audioContext.createGain();
    const sfxVol = (typeof gtcSettings !== 'undefined' && gtcSettings) ? (gtcSettings.volSfx / 100) : 0.7;
    
    if (!isFinal) {
        const osc = audioContext.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(1320, now + 0.12);
        
        gain.gain.setValueAtTime(0.3 * sfxVol, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
        
        osc.connect(gain);
        gain.connect(audioContext.destination);
        
        osc.start(now);
        osc.stop(now + 0.15);
    } else {
        const osc1 = audioContext.createOscillator();
        const osc2 = audioContext.createOscillator();
        
        osc1.type = 'triangle';
        osc1.frequency.setValueAtTime(1320, now);
        osc1.frequency.exponentialRampToValueAtTime(1760, now + 0.25);
        
        osc2.type = 'sawtooth';
        osc2.frequency.setValueAtTime(440, now);
        osc2.frequency.exponentialRampToValueAtTime(880, now + 0.25);
        
        gain.gain.setValueAtTime(0.4 * sfxVol, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        
        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(audioContext.destination);
        
        osc1.start(now);
        osc2.start(now);
        osc1.stop(now + 0.3);
        osc2.stop(now + 0.3);
    }
}

    // 7. Start Countdown if configured in Settings
    if (typeof gtcSettings !== 'undefined' && gtcSettings && gtcSettings.countdown > 0) {
        isCountdownActive = true;
        btnRecord.innerText = "⏹ CANCELAR";
        btnRecord.disabled = false;
        btnListen.disabled = true;

        const countdownOverlay = document.getElementById('countdown-overlay');
        const countdownNumber = document.getElementById('countdown-number');
        const countdownSubtext = document.getElementById('countdown-subtext');

        if (countdownOverlay) countdownOverlay.classList.remove('hidden');

        for (let c = gtcSettings.countdown; c > 0; c--) {
            if (!isCountdownActive) {
                if (countdownOverlay) countdownOverlay.classList.add('hidden');
                resetRecordState();
                return;
            }
            if (countdownNumber) {
                countdownNumber.innerText = c;
                countdownNumber.classList.remove('pop-anim');
                void countdownNumber.offsetWidth;
                countdownNumber.classList.add('pop-anim');
            }
            if (countdownSubtext) countdownSubtext.innerText = "¡PREPÁRATE PARA DOBLAR!";
            
            playCountdownBeep(false);
            await new Promise(r => setTimeout(r, 1000));
        }

        if (!isCountdownActive) {
            if (countdownOverlay) countdownOverlay.classList.add('hidden');
            resetRecordState();
            return;
        }

        if (countdownNumber) {
            countdownNumber.innerText = "¡YA!";
            countdownNumber.classList.remove('pop-anim');
            void countdownNumber.offsetWidth;
            countdownNumber.classList.add('pop-anim');
        }
        if (countdownSubtext) countdownSubtext.innerText = "🎙️ ¡GRABANDO!";
        
        playCountdownBeep(true);
        await new Promise(r => setTimeout(r, 400));
        
        if (countdownOverlay) countdownOverlay.classList.add('hidden');
        isCountdownActive = false;
    }

    isStartingRecording = true;
    btnListen.disabled = true;
    btnRecord.disabled = false;
    btnRecord.innerText = "⏹ PARAR GRABACIÓN";

    try {
        let micAudioConstraint = {
            echoCancellation: (gtcSettings ? !!gtcSettings.micDsp : false),
            noiseSuppression: (gtcSettings ? !!gtcSettings.micDsp : false),
            autoGainControl: (gtcSettings ? !!gtcSettings.micDsp : false)
        };
        if (gtcSettings && gtcSettings.micDevice && gtcSettings.micDevice !== 'default') {
            micAudioConstraint.deviceId = { ideal: gtcSettings.micDevice };
        }

        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraint });
        } catch(devErr) {
            console.warn("getUserMedia with custom mic failed, falling back to default mic:", devErr);
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }

        // Determine supported recorder MIME type
        let recMimeType = '';
        if (typeof MediaRecorder !== 'undefined') {
            if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) recMimeType = 'audio/webm;codecs=opus';
            else if (MediaRecorder.isTypeSupported('audio/webm')) recMimeType = 'audio/webm';
            else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) recMimeType = 'audio/ogg;codecs=opus';
            else if (MediaRecorder.isTypeSupported('audio/mp4')) recMimeType = 'audio/mp4';
        }

        const recOptions = recMimeType ? { mimeType: recMimeType } : {};
        const mediaRecorder = new MediaRecorder(stream, recOptions);
        activeMediaRecorder = mediaRecorder;
        const audioChunks = [];
        
        let monitorNode = null;
        if (gtcSettings && gtcSettings.micMonitor) {
            try {
                monitorNode = audioContext.createMediaStreamSource(stream);
                monitorNode.connect(audioContext.destination);
            } catch(e) { console.warn("Mic monitor connect error:", e); }
        }

        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            if (recordingTimer) {
                clearTimeout(recordingTimer);
                recordingTimer = null;
            }
            activeMediaRecorder = null;
            if (monitorNode) {
                try { monitorNode.disconnect(); } catch(e){}
            }
            stream.getTracks().forEach(t => t.stop());
            
            isRecording = false;
            isStartingRecording = false;
            isCountdownActive = false;
            
            if (audioChunks.length > 0) {
                const blobMime = mediaRecorder.mimeType || recMimeType || 'audio/webm';
                const blob = new Blob(audioChunks, { type: blobMime });
                try {
                    const arrayBuffer = await blob.arrayBuffer();
                    const decodedBuffer = await audioContext.decodeAudioData(arrayBuffer);
                    const wavBlob = bufferToWav(decodedBuffer);
                    
                    userRecordings[currentClipIndex] = { blob: wavBlob, buffer: decodedBuffer };
                    
                    drawWaveform(originalBuffer, '#bc00ff');
                    drawWaveform(decodedBuffer, '#00ffff', true);

                    // ReDub style: Instant background upload as soon as line recording finishes!
                    if (isMultiplayer && currentRoom && clipsList[currentClipIndex]) {
                        uploadSingleTakeInBackground(currentClipIndex, wavBlob || blob);
                    }
                } catch(e) {
                    console.warn("Recorded chunk decode error:", e);
                }
            }
            
            resetRecordState();

            if (isLastSelectedClip(currentClipIndex)) {
                btnNext.classList.add('hidden');
                btnFinish.classList.remove('hidden');
                btnFinish.disabled = false;
            } else {
                btnNext.disabled = false;
            }

            // Auto-replay setting
            if (gtcSettings && gtcSettings.autoReplay && userRecordings[currentClipIndex]) {
                setTimeout(() => {
                    if (!isPlaying && !isRecording) btnListen.click();
                }, 250);
            }
        };

        isRecording = true;
        isStartingRecording = false;

        const sourceStream = audioContext.createMediaStreamSource(stream);
        recordAnalyser = audioContext.createAnalyser();
        recordAnalyser.fftSize = 2048;
        sourceStream.connect(recordAnalyser);
        recordDataArray = new Float32Array(recordAnalyser.fftSize);

        if (backingBuffer) {
            sourceBacking = audioContext.createBufferSource();
            sourceBacking.buffer = backingBuffer;
            sourceBacking.connect(audioContext.destination);
        }

        const startPlaybackAndRecord = () => {
            if (!isRecording) return;
            try {
                if (mediaRecorder.state === 'inactive') mediaRecorder.start();
            } catch(e) { console.warn("mediaRecorder start error:", e); }
            
            if (backingBuffer && sourceBacking) {
                try { sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0); } catch(e){}
            }
            startPlayheadWithRecord(originalBuffer ? originalBuffer.duration : 5, recordAnalyser);
            
            recordingTimer = setTimeout(() => {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    try { mediaRecorder.stop(); } catch(e){}
                }
            }, (originalBuffer ? originalBuffer.duration : 5) * 1000);
        };

        if (packHasVideo && sceneVideo) {
            sceneVideo.muted = true;
            sceneVideo.style.display = 'block';
            sceneVideo.classList.remove('hidden');
            clipImage.style.display = 'none';
            try { sceneVideo.currentTime = clipsList[currentClipIndex].timestamp || 0; } catch(e){}
            safePlayMedia(sceneVideo, startPlaybackAndRecord);
        } else {
            startPlaybackAndRecord();
        }

    } catch (err) {
        console.error("Record click exception:", err);
        alert('No se pudo acceder al micrófono: ' + err.message);
        resetRecordState();
    }
};

btnNext.onclick = () => {
    advanceToNextSelectedClip(currentClipIndex);
};

btnFinish.onclick = () => {
    if (isMultiplayer) {
        // In Multiplayer (Coop or Competitive), immediately trigger submission/waiting screen
        // Do NOT show local finished controls or modify main layout prematurely!
        calculateFinalScore();
    } else {
        // Solo mode: transition UI to finished state and compute final score
        mainLayout.classList.add('finished-state');
        finishedControls.classList.remove('hidden');
        btnWatch.disabled = false;
        btnSave.disabled = false;
        
        document.querySelector('.control-panel').style.display = 'none';
        document.querySelector('.subtitle').style.display = 'none';
        document.querySelector('.waveform-container').style.display = 'none';
        
        document.querySelector('.center-content').style.width = '100%';
        document.querySelector('.center-content').style.maxWidth = '100%';
        
        setTimeout(() => {
            calculateFinalScore();
        }, 500);
    }
};


async function ensureAllOriginalBuffers() {
    const promises = [];
    for (let i = 0; i < clipsList.length; i++) {
        if (!clipOriginalBuffers[i]) {
            promises.push((async () => {
                try {
                    const res = await fetch(`/media/${encodeURIComponent(currentPack)}/${encodeURIComponent(clipsList[i].audio_file)}`);
                    if (!res.ok) { console.warn('Could not load clip', i, res.status); return; }
                    const arrayBuffer = await res.arrayBuffer();
                    clipOriginalBuffers[i] = await audioContext.decodeAudioData(arrayBuffer);
                } catch(e) {
                    console.warn('Could not decode clip', i, e);
                }
            })());
        }
    }
    await Promise.all(promises);
}

// 4. Watch Phase & Final Scoring
btnWatch.onclick = async () => {
    if (isPlaying || isRecording) return;
    isPlaying = true;
    await ensureAllOriginalBuffers();
    
    btnListen.disabled = true;
    btnRecord.disabled = true;
    btnNext.disabled = true;
    btnWatch.disabled = true;
    
    window.playbackSources = [];
    let maxTime = backingBuffer ? backingBuffer.duration : 0;
    
    if (backingBuffer) {
        sourceBacking = audioContext.createBufferSource();
        sourceBacking.buffer = backingBuffer;
        // Duck backing track slightly to eliminate any residual Demucs vocal bleed
        const backingGain = audioContext.createGain();
        backingGain.gain.value = 0.55;
        sourceBacking.connect(backingGain);
        backingGain.connect(audioContext.destination);
    }
    
    for (let i = 0; i < clipsList.length; i++) {
        const src = audioContext.createBufferSource();
        const clipChar = clipsList[i].character;
        const isPlayerChar = (selectedCharacters && selectedCharacters.includes(clipChar)) || 
                             (claimedCharacters && claimedCharacters.includes(clipChar));

        if (userRecordings[i] && userRecordings[i].buffer) {
            src.buffer = userRecordings[i].buffer;
        } else if (isPlayerChar) {
            // Player's character clip: play silent buffer so original voice NEVER leaks!
            src.buffer = audioContext.createBuffer(1, Math.max(100, Math.floor(audioContext.sampleRate * 0.5)), audioContext.sampleRate);
        } else {
            src.buffer = clipOriginalBuffers[i];
        }
        
        src.connect(audioContext.destination);
        window.playbackSources.push(src);
        
        const ts = clipsList[i].timestamp || 0;
        const clipDur = (src.buffer ? src.buffer.duration : (clipOriginalBuffers[i] ? clipOriginalBuffers[i].duration : 0));
        if (ts + clipDur > maxTime) {
            maxTime = ts + clipDur;
        }
    }
    
    if (packHasVideo) {
        sceneVideo.src = window.currentPackVideo;
        sceneVideo.muted = true; // Mute original video audio track!
        sceneVideo.style.display = 'block';
        sceneVideo.classList.remove('hidden');
        clipImage.style.display = 'none';
        sceneVideo.currentTime = 0;
        const startWatch = () => {
            if (backingBuffer) sourceBacking.start();
            for (let i = 0; i < clipsList.length; i++) {
                window.playbackSources[i].start(audioContext.currentTime + (clipsList[i].timestamp || 0));
            }
        };
        sceneVideo.play().then(startWatch).catch(e => {
            console.warn("Autoplay block or error:", e);
            startWatch();
        });
    } else {
        if (backingBuffer) sourceBacking.start();
        for (let i = 0; i < clipsList.length; i++) {
            window.playbackSources[i].start(audioContext.currentTime + (clipsList[i].timestamp || 0));
        }
    }
    
        // Wait for the whole scene to finish playing
    window.playbackTimeout = setTimeout(() => {
        isPlaying = false;
        if (packHasVideo) {
            sceneVideo.style.display = 'none';
            sceneVideo.classList.add('hidden');
            sceneVideo.classList.add('hidden');
            clipImage.style.display = 'block';
            sceneVideo.pause();
        }
        
        btnWatch.disabled = false;
        btnSave.disabled = false;
    }, maxTime * 1000);
};

async function calculateFinalScore() {
    const formData = new FormData();
    let idx = 0;
    for (let i = 0; i < clipsList.length; i++) {
        if (userRecordings[i] && userRecordings[i].blob) {
            // Only upload if it's my character (in coop) or if competitive/solo
            if (multiplayerGameMode !== 'cooperativo' || claimedCharacters.includes(clipsList[i].character)) {
                formData.append(`user_audio_${idx}`, userRecordings[i].blob, `user_${idx}.wav`);
                formData.append(`ref_audio_path_${idx}`, `${currentPack}/${clipsList[i].audio_file}`);
                formData.append(`char_name_${idx}`, clipsList[i].character);
                idx++;
            }
        }
    }
    formData.append('count', idx);

    if (isMultiplayer && multiplayerGameMode === 'cooperativo') {
        // COOP MODE: Send to server for mixing, then wait
        formData.append('room', currentRoom);
        formData.append('player_name', myName);
        formData.append('pack_name', currentPack);

        // Show waiting overlay BEFORE submit so the player sees it immediately
        const overlay = document.getElementById('coop-waiting-overlay');
        if (overlay) overlay.style.display = 'flex';

        const titleEl = document.getElementById('coop-waiting-title');
        if (titleEl) titleEl.innerText = "¡Toma Guardada! 🎬";
        const subTitleEl = document.getElementById('coop-waiting-subtitle');
        if (subTitleEl) subTitleEl.innerText = "Esperando a que todos los jugadores terminen de doblar...";

        coopSubmitted = true;  // Mark this player as submitted
        startCoopStatusPolling(); // Start HTTP polling fallback so remote players never get stuck

        try {
            await fetch('/api/coop_submit', { method: 'POST', body: formData });
        } catch(e) {
            console.error("Coop submit error:", e);
            alert("Error al enviar las tomas cooperativas. Reintentando...");
        }
        return; // Wait for socket events or polling fallback
    }

    // SOLO / COMPETITIVE MODE
    if (isMultiplayer && multiplayerGameMode === 'competitivo') {
        formData.append('room', currentRoom);
        formData.append('player_name', myName);
        formData.append('player_sid', socket.id);
        formData.append('pack_name', currentPack);
    }

    // In competitive mode we skip the score animation and go straight to a waiting screen
    const isCompetitive = isMultiplayer && multiplayerGameMode === 'competitivo';
    
    if (!isCompetitive) {
        // Solo / Coop: show score card as usual
        scoreCard.classList.remove('hidden');
        scoreRank.innerText = '?';
        verdictText.innerText = 'Calculando';
        verdictText.style.color = '#fff';
        finalScore.innerText = '0';
    } else {
        // Competitive: initialize waiting list with all known players without erasing existing progress
        if (!compWaitingPlayers) compWaitingPlayers = {};
        if (window._lastRoomPlayers && window._lastRoomPlayers.length > 0) {
            window._lastRoomPlayers.forEach(p => {
                const pName = p.name;
                if (pName && !compWaitingPlayers[pName]) {
                    compWaitingPlayers[pName] = {
                        name: pName,
                        sid: p.sid || pName,
                        score: p.score || 0,
                        scored: (p.score !== undefined && p.score !== null),
                        videoReady: !!pendingVideos[p.sid || pName] || !!pendingVideos[pName]
                    };
                }
            });
        }
        
        if (myName) {
            if (!compWaitingPlayers[myName]) {
                compWaitingPlayers[myName] = {
                    name: myName, sid: socket.id || myName, score: 0, scored: true, videoReady: !!(pendingVideos[socket.id] || pendingVideos[myName]), videoError: false
                };
            } else {
                compWaitingPlayers[myName].scored = true;
            }
        }

        if (window._lastCompGameOverData) {
            handleCompetitiveGameOver(window._lastCompGameOverData);
        } else {
            showCompWaitingScreen(null);
        }
    }
    
    let dots = 0;
    const calcInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        if (!isCompetitive) {
            verdictText.innerText = 'Calculando' + '.'.repeat(dots);
        }
    }, 400);
    
    try {
        // Upload retry mechanism for unstable / bad Wi-Fi
        let res;
        let retries = 3;
        while (retries > 0) {
            try {
                res = await fetch('/api/score_bulk', { method: 'POST', body: formData });
                if (res.ok) break;
            } catch(fetchErr) {
                console.warn(`[COMP] score_bulk upload failed over slow Wi-Fi, retrying (${retries} left)...`, fetchErr);
                retries--;
                if (retries === 0) throw fetchErr;
                await new Promise(r => setTimeout(r, 1500));
            }
        }
        
        const data = await res.json();
        
        clearInterval(calcInterval);
        if (data.error) throw new Error(data.error);
        
        let targetScore = data.score;
        if (typeof gtcSettings !== 'undefined' && gtcSettings) {
            if (gtcSettings.scoreSensitivity === 'permissive') {
                targetScore = Math.min(100, Math.round(targetScore * 1.15));
            } else if (gtcSettings.scoreSensitivity === 'strict') {
                targetScore = Math.max(0, Math.round(targetScore * 0.85));
            }
        }
        
        if (isCompetitive) {
            // Update waiting screen to show we finished
            updateCompWaiting(myName, true, targetScore);
            socket.emit('submit_score', { room: currentRoom, score: targetScore, player_name: myName });
            // Start HTTP polling fallback so remote players never get stuck
            startCompStatusPolling();
            // The server will emit competitive_game_over when all players finish
            return;
        }
        
        // Solo score animation
        finalScore.innerText = "0";
        scoreRank.style.opacity = "0";
        scoreRank.style.transition = "opacity 0.5s ease, transform 0.5s ease";
        scoreRank.style.transform = "scale(0.5)";
        
        let startTimestamp = null;
        const duration = 2000;
        
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            finalScore.innerText = Math.floor(easeOut * targetScore);
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                finalScore.innerText = targetScore;
                if (targetScore >= 95) { 
                    scoreRank.innerText = 'S'; scoreRank.style.color = '#00ffff'; verdictText.innerText = '¡NIVEL DIOS!'; verdictText.style.color = '#00ffff'; 
                } else if (targetScore >= 85) { 
                    scoreRank.innerText = 'A'; scoreRank.style.color = '#00e676'; verdictText.innerText = '¡EXCELENTE!'; verdictText.style.color = '#00e676'; 
                } else if (targetScore >= 70) { 
                    scoreRank.innerText = 'B'; scoreRank.style.color = '#ffea00'; verdictText.innerText = 'MUY BUENO'; verdictText.style.color = '#ffea00'; 
                } else if (targetScore >= 50) { 
                    scoreRank.innerText = 'C'; scoreRank.style.color = '#ff9100'; verdictText.innerText = 'ACEPTABLE'; verdictText.style.color = '#ff9100'; 
                } else { 
                    scoreRank.innerText = 'F'; scoreRank.style.color = '#ff1744'; verdictText.innerText = 'DESASTRE TOTAL'; verdictText.style.color = '#ff1744'; 
                }
                scoreRank.style.opacity = "1";
                scoreRank.style.transform = "scale(1)";
            }
        };
        window.requestAnimationFrame(step);
        
    } catch(e) {
        clearInterval(calcInterval);
        console.error(e);
    }
}

// ---- Competitive Waiting Screen ----
let compWaitingPlayers = {}; // name -> { name, sid, score, scored, videoReady }
let compTotalPlayers = 0;

function showCompWaitingScreen(initial) {
    let overlay = document.getElementById('comp-waiting-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'comp-waiting-overlay';
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.75); backdrop-filter: blur(4px);
            z-index: 9998; display: flex;
            flex-direction: column; align-items: center; justify-content: center;
        `;

        const card = document.createElement('div');
        card.style.cssText = `
            background: rgba(10,18,28,0.97);
            border: 2px solid var(--cyan, #98e8e8);
            border-radius: 20px;
            padding: 40px 50px;
            display: flex; flex-direction: column; align-items: center; gap: 20px;
            min-width: 380px; max-width: 560px;
            box-shadow: 0 0 40px rgba(152,232,232,0.2);
            animation: viewEnter 0.4s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
        `;
        
        const title = document.createElement('h2');
        title.style.cssText = "color: var(--cyan, #98e8e8); font-size: 2rem; margin: 0; text-align: center; text-shadow: 0 0 16px rgba(152,232,232,0.5);";
        title.innerText = '🎬 ¡Toma Guardada!';
        
        const sub2 = document.createElement('p');
        sub2.style.cssText = 'color: #b0bec5; font-size: 1rem; margin: 0; text-align: center;';
        sub2.innerText = 'Esperando a que todos los jugadores terminen de grabar...';

        const spinner = document.createElement('div');
        spinner.style.cssText = 'width: 40px; height: 40px; border: 3px solid rgba(152,232,232,0.2); border-top-color: var(--cyan, #98e8e8); border-radius: 50%; animation: spin 1s linear infinite;';

        const sub = document.createElement('p');
        sub.id = 'comp-waiting-sub';
        sub.style.cssText = 'color: var(--magenta, #ff2a75); font-weight: bold; font-size: 1.1rem; margin: 0; text-align: center;';
        sub.innerText = 'Vídeos listos: 0 / 0';
        
        const list = document.createElement('ul');
        list.id = 'comp-waiting-list';
        list.style.cssText = 'list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; min-width: 320px; width: 100%;';
        
        if (!document.getElementById('comp-spin-style')) {
            const style = document.createElement('style');
            style.id = 'comp-spin-style';
            style.innerText = '@keyframes spin { to { transform: rotate(360deg); } }';
            document.head.appendChild(style);
        }
        
        card.appendChild(title);
        card.appendChild(sub2);
        card.appendChild(spinner);
        card.appendChild(sub);
        card.appendChild(list);
        overlay.appendChild(card);
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    renderCompWaitingList();
}


function renderCompWaitingList() {
    const list = document.getElementById('comp-waiting-list');
    if (!list) return;
    list.innerHTML = '';
    
    // Deduplicate players strictly by player_name before rendering
    const uniquePlayers = {};
    Object.values(compWaitingPlayers).forEach(p => {
        if (p && p.name) {
            if (!uniquePlayers[p.name]) {
                uniquePlayers[p.name] = { ...p };
            } else {
                if (p.scored) uniquePlayers[p.name].scored = true;
                if (p.videoReady) uniquePlayers[p.name].videoReady = true;
                if (p.videoError) uniquePlayers[p.name].videoError = true;
                if (p.score) uniquePlayers[p.name].score = p.score;
            }
        }
    });

    const playerList = Object.values(uniquePlayers);
    playerList.forEach(p => {
        const li = document.createElement('li');
        li.style.cssText = `
            display: flex; align-items: center; justify-content: space-between;
            padding: 14px 20px; background: rgba(255,255,255,0.04); border-radius: 10px;
            border: 1px solid ${p.videoReady ? '#00e676' : (p.scored ? '#ffea00' : 'rgba(255,255,255,0.1)' )};
            transition: 0.3s;
        `;
        
        const left = document.createElement('span');
        left.style.cssText = 'color: #fff; font-size: 1rem; font-weight: bold;';
        left.innerText = p.name;
        
        const right = document.createElement('span');
        right.style.cssText = 'font-size: 1rem;';
        if (p.videoError) {
            right.style.color = '#ff5252';
            right.innerText = '❌ Error (sin vídeo)';
        } else if (p.videoReady) {
            right.style.color = '#00e676';
            right.innerText = '✅ Vídeo listo';
        } else if (p.scored) {
            right.style.color = '#ffea00';
            right.innerText = '⚙️ Procesando vídeo...';
        } else {
            right.style.color = '#b0bec5';
            right.innerText = '⏳ Jugando...';
        }
        
        li.appendChild(left);
        li.appendChild(right);
        list.appendChild(li);
    });
    
    // Update subtitle with accurate count
    const sub = document.getElementById('comp-waiting-sub');
    if (sub) {
        const scoredCount = playerList.filter(p => p.scored || p.videoReady).length;
        const total = playerList.length;
        sub.innerText = `Jugadores listos: ${scoredCount} / ${total}`;
    }

    // Auto-advance safety poll: if all unique players are ready, trigger status check immediately
    const scoredCount = playerList.filter(p => p.scored || p.videoReady).length;
    const totalCount = playerList.length;
    if (totalCount > 0 && scoredCount === totalCount && currentRoom) {
        fetch(`/api/competitive_status/${currentRoom}`)
            .then(r => r.json())
            .then(data => {
                if (data.status === 'done') {
                    handleCompetitiveGameOver(data);
                }
            }).catch(e => console.warn('[COMP] Auto-advance poll error:', e));
    }

    // NOTE: We do NOT auto-advance here.
    // The end screen is ONLY triggered by 'competitive_game_over' from the server.
    // This list is purely informational — it shows who has scored/rendered their video.

    // Show force-advance button for host after 60s of someone stuck
    const scored = Object.values(compWaitingPlayers).filter(p => p.scored || p.videoReady).length;
    const total = Object.keys(compWaitingPlayers).length;
    const card = document.querySelector('#comp-waiting-overlay > div');
    if (card && isHost && scored > 0 && scored < total) {
        if (!document.getElementById('comp-force-btn')) {
            const forceBtn = document.createElement('button');
            forceBtn.id = 'comp-force-btn';
            forceBtn.innerText = '⚡ Forzar resultado con los que terminaron';
            forceBtn.style.cssText = 'margin-top:10px; padding:10px 18px; background:rgba(255,64,129,0.15); border:1px solid #ff4081; color:#ff4081; border-radius:10px; cursor:pointer; font-size:0.9rem; transition:0.2s;';
            forceBtn.onclick = () => {
                forceBtn.disabled = true;
                forceBtn.innerText = 'Forzando...';
                fetch(`/api/force_advance/${currentRoom}`, {method: 'POST'})
                    .then(r => r.json())
                    .then(d => { if (d.error) { forceBtn.disabled=false; forceBtn.innerText='⚡ Forzar resultado'; } })
                    .catch(() => { forceBtn.disabled=false; forceBtn.innerText='⚡ Forzar resultado'; });
            };
            card.appendChild(forceBtn);
        }
    } else {
        const existing = document.getElementById('comp-force-btn');
        if (existing) existing.remove();
    }
}


function updateCompWaiting(name, scored, score) {
    // Update by sid (for ourselves) or by name (for others)
    let entry = compWaitingPlayers[socket.id]; // Try self first
    if (!entry) {
        entry = Object.values(compWaitingPlayers).find(p => p.name === name);
    }
    if (entry) {
        entry.scored = scored;
        if (score !== undefined) entry.score = score;
    }
    renderCompWaitingList();
}


btnSave.onclick = async () => {
    btnSave.disabled = true;
    btnSave.innerText = '⚙️ Generando vídeo MP4...';
    
    // In Coop mode, if video is already generated by server:
    if (isMultiplayer && multiplayerGameMode === 'cooperativo' && coopFinalVideoUrl) {
        const a = document.createElement('a');
        a.href = coopFinalVideoUrl;
        a.download = `GrindTheClip_${currentPack}_Coop.mp4`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        btnSave.disabled = false;
        btnSave.innerText = '💾 Guardar Vídeo Doblado';
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('pack_name', currentPack);
        let idx = 0;
        for (let i = 0; i < clipsList.length; i++) {
            if (userRecordings[i] && userRecordings[i].blob) {
                formData.append(`user_audio_${idx}`, userRecordings[i].blob, `user_${idx}.wav`);
                formData.append(`ref_audio_path_${idx}`, `${currentPack}/${clipsList[i].audio_file}`);
                formData.append(`char_name_${idx}`, clipsList[i].character);
                idx++;
            }
        }
        formData.append('count', idx);

        const res = await fetch('/api/singleplayer_mix', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.success && data.video_url) {
            const a = document.createElement('a');
            a.href = data.video_url;
            a.download = data.filename || `GrindTheClip_${currentPack}_Doblaje.mp4`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } else {
            alert("Error generando el vídeo final: " + (data.error || "Desconocido"));
        }
    } catch(e) {
        console.error("Error al guardar doblaje:", e);
        alert("Ocurrió un error procesando el vídeo final.");
    } finally {
        btnSave.disabled = false;
        btnSave.innerText = '💾 Guardar Vídeo Doblado';
    }
};

// Start of setupSocket and socket events that were lost
function setupSocket() {
    socket.on('error', (data) => {
        alert(data.message);
    });
    socket.on('mode_capacity_error', (data) => {
        alert(data.message);
    });
    socket.on('pack_catalog_updated', (data) => {
        console.log('[REALTIME CATALOG] Catalog updated on server:', data);
        if (typeof fetchPacks === 'function') {
            fetchPacks();
        }
    });
}

async function createMultiplayerRoom(packName) {
    let name = myName || (currentUserProfile ? currentUserProfile.nickname : '');
    if (!name) {
        alert("Debes iniciar sesión para crear una sala.");
        showView('view-auth');
        return;
    }
    
    try {
        const res = await fetch('/api/create_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pack_name: packName, mode: 'cooperativo' })
        });
        const data = await res.json();
        
        isMultiplayer = true;
        currentRoom = data.room_code;
        currentPack = packName;
        myName = name;
        isHost = true;
        
        // Fetch unique characters for this pack
        await fetchPackClips(); 
        
        document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
        showView('view-lobby');
        
        const tunnelEl = document.getElementById('lobby-tunnel-link');
        tunnelEl.style.display = 'block';
        tunnelEl.innerHTML = 'Generando enlace mágico...';
        
        // Start Cloudflare tunnel & register room code for online desktop app joins
        fetch('/api/start_tunnel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room: currentRoom, pack_name: packName })
        })
            .then(r => r.json())
            .then(d => {
                if (d.url) {
                    const fullLink = d.url;
                    tunnelEl.innerHTML = `
                        <div style="background: rgba(0, 229, 255, 0.1); border: 2px solid var(--cyan); border-radius: 12px; padding: 15px; margin-top: 15px; text-align: center;">
                            <p style="color: #fff; margin-bottom: 8px; font-weight: bold; font-size: 1.1rem;">🌐 SALA ONLINE ACTIVADA</p>
                            <p style="color: #aaa; margin-bottom: 12px; font-size: 0.95rem;">Tus amigos solo tienen que hacer clic en el enlace para entrar desde cualquier navegador o móvil:</p>
                            <button id="btn-copy-tunnel-link" onclick="navigator.clipboard.writeText('${fullLink}'); this.innerText='¡ENLACE COPIADO! ✓'; setTimeout(()=>this.innerText='📋 COPIAR ENLACE PARA DISCORD', 3000);" class="btn-pill btn-cyan" style="font-size: 1rem; padding: 10px 20px; cursor: pointer; font-weight: bold;">📋 COPIAR ENLACE PARA DISCORD</button>
                        </div>
                    `;
                } else if (d.error) {
                    tunnelEl.innerHTML = `Error túnel: ${d.error} <br><button onclick="createMultiplayerRoom('${packName}')" class="btn-pill btn-white" style="margin-top:5px;font-size:0.75rem;">Reintentar túnel</button>`;
                } else {
                    tunnelEl.innerHTML = 'Juego en red local.';
                }
            })
            .catch(err => {
                tunnelEl.innerHTML = `Error generando túnel: ${err.message}`;
            });
            
        // Enable mode selector for host
        const modeContainer = document.getElementById('lobby-mode-container');
        modeContainer.style.display = 'block';
        const modeSelect = document.getElementById('lobby-mode-select');
        modeSelect.style.display = 'block'; // Host can change it
        document.getElementById('lobby-mode-display').style.display = 'none';

        
        modeSelect.onchange = (e) => {
            socket.emit('change_mode', { room: currentRoom, mode: e.target.value });
        };
        
        socket.emit('join', { room: currentRoom, name: myName });
        
    } catch(e) {
        console.error(e);
        alert("Error al crear sala: " + e.message + "\nStack: " + e.stack);
    }
}


async function joinMultiplayerRoom() {
    const name = document.getElementById('join-name').value.trim();
    const code = document.getElementById('join-code').value.trim().toUpperCase();
    
    if (!name || !code) {
        alert("Rellena nombre y código");
        return;
    }
    
    try {
        let roomUrl = null;
        let roomPack = null;

        // 1. Check local server first
        const res = await fetch(`/api/check_room/${code}`);
        const data = await res.json();
        
        if (data.valid) {
            roomPack = data.pack_name;
        } else {
            // 2. Query central room registry to find the host's tunnel URL!
            try {
                const resRemote = await fetch(`/api/resolve_room_code/${code}`);
                const dataRemote = await resRemote.json();
                if (dataRemote.found && dataRemote.url) {
                    roomUrl = dataRemote.url;
                    roomPack = dataRemote.pack_name;
                } else {
                    alert(data.reason || "No se encontró ninguna sala activa con ese código.");
                    return;
                }
            } catch(e) {
                alert(data.reason || "Error buscando la sala remota.");
                return;
            }
        }
        
        // Connect socket to remote host's tunnel URL if cross-network
        if (roomUrl) {
            console.log(`[ONLINE] Conectando con la sala remota ${code} en: ${roomUrl}`);
            if (typeof io !== 'undefined') {
                if (socket) socket.disconnect();
                socket = io(roomUrl, { transports: ['polling', 'websocket'] });
                setupSocket();
            }
        }
        
        isMultiplayer = true;
        currentRoom = code;
        if (roomPack) currentPack = roomPack;
        myName = name;
        isHost = false;
        
        await fetchPackClips();
        fadeOutMusic();
        
        document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
        showView('view-lobby');
        
        document.getElementById('lobby-tunnel-link').style.display = 'none';
        
        const modeContainer = document.getElementById('lobby-mode-container');
        modeContainer.style.display = 'block';
        document.getElementById('lobby-mode-select').style.display = 'none';
        document.getElementById('lobby-mode-display').style.display = 'none';
        
        socket.emit('join', { room: currentRoom, name: myName });
        
    } catch(e) {
        console.error(e);
        alert("Error de conexión al buscar la sala: " + e.message);
    }
}

// ==========================================
// AUTO-UPDATER SYSTEM (2-SECOND HOT PATCH)
// ==========================================
async function checkAutoUpdates() {
    try {
        const res = await fetch('/api/check_update');
        const data = await res.json();
        if (data && data.update_available) {
            document.getElementById('update-ver-tag').innerText = data.version || '1.0.1';
            document.getElementById('update-changelog-text').innerText = data.changelog || 'Correcciones de errores aplicadas.';
            document.getElementById('update-notification-banner').style.display = 'block';
        }
    } catch(e) {
        console.log("Check update ping error:", e);
    }
}

async function applyAutoUpdateNow() {
    const bannerBtn = document.querySelector('#update-notification-banner button.btn-cyan');
    if (bannerBtn) bannerBtn.innerText = "⏳ Aplicando parche...";
    try {
        const res = await fetch('/api/apply_update', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || "No se pudo completar el parche automático.");
        }
    } catch(e) {
        alert("Error al aplicar la actualización: " + e.message);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkAutoUpdates, 2000);
});

async function fetchPackClips() {
    const r = await fetch(`/api/packs/${encodeURIComponent(currentPack)}/clips`);
    const d = await r.json();
    clipsList = d.clips || [];
    // Normalize clip format to always have .character and .name
    clipsList.forEach((clip, i) => {
        if (!clip.character && clip.name) {
            let parts = clip.name.split('_');
            clip.character = parts.length > 1 ? parts.slice(1).join('_').replace('.wav', '') : clip.name;
        }
        if (!clip.name && clip.character) {
            clip.name = `clip_${i}_${clip.character}.wav`;
        }
    });

    const chars = new Set();
    clipsList.forEach(c => {
        if(c.character) chars.add(c.character);
    });
    allPackCharacters = Array.from(chars);
}

function setReady() {
    const btn = document.getElementById('btn-ready');
    if (!btn) return;

    if (isMultiplayer && multiplayerGameMode === 'cooperativo' && (!claimedCharacters || claimedCharacters.length === 0)) {
        alert("⚠️ Debes elegir al menos un personaje antes de ponerte listo en el modo cooperativo.");
        return;
    }

    amIReady = !amIReady;
    if (amIReady) {
        btn.innerText = "✓ LISTO!";
        btn.classList.replace('btn-magenta', 'btn-cyan');
        btn.style.background = '#00ffcc'; // Greenish/Cyan
        btn.style.color = '#000';
    } else {
        btn.innerText = "¡ESTOY LISTO!";
        btn.classList.replace('btn-cyan', 'btn-magenta');
        btn.style.background = ''; // reset to default magenta
        btn.style.color = '';
    }
    socket.emit('toggle_ready', { room: currentRoom, ready: amIReady });
}

function leaveLobby() {
    stopCoopStatusPolling();
    stopCompStatusPolling();
    cleanGameLayoutAndState();
    hideRoomChatWidget();
    if (currentRoom) {
        socket.emit('leave_room', { room: currentRoom });
    }
    isMultiplayer = false;
    currentRoom = null;
    coopFinalVideoUrl = null;
    coopSubmitted = false;
    amIReady = false;
    
    // Reset ready button state
    const btn = document.getElementById('btn-ready');
    if (btn) {
        btn.disabled = false;
        btn.innerText = "¡ESTOY LISTO!";
        btn.classList.remove('btn-cyan');
        btn.classList.add('btn-magenta');
        btn.style.background = '';
        btn.style.color = '';
    }
    
    showView('view-online-menu');
    playMenuMusic();
}

btnExit.onclick = () => {
    stopCoopStatusPolling();
    stopCompStatusPolling();
    cleanGameLayoutAndState();
    if (currentRoom) {
        socket.emit('leave_room', {room: currentRoom});
    }
    const wasMultiplayer = isMultiplayer;
    currentRoom = null;
    isMultiplayer = false;
    coopSubmitted = false;
    coopFinalVideoUrl = null;
    
    // Completely reset game state
    if (sceneVideo) {
        sceneVideo.pause();
        sceneVideo.src = "";
    }
    stopAudio();
    if (typeof mediaRecorder !== 'undefined' && mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    isRecording = false;
    isPlaying = false;
    document.getElementById('coop-waiting-overlay').style.display = 'none';
    document.getElementById('coop-ranking-modal').style.display = 'none';
    mainLayout.classList.remove('finished-state');
    
    if (wasMultiplayer) {
        showView('view-online-menu');
    } else {
        showView('view-packs');
    }
    playMenuMusic();
};

const btnOptions = document.getElementById('btn-options');
if (btnOptions) {
    btnOptions.onclick = () => {
        openSettingsView();
    };
}

// ==========================================
// CREATOR: AUTO SCENE WORKSHOP
// ==========================================
// ===========================================
// EDITOR DE ESCENAS (TALLER DE ESCENAS)
// ===========================================

let creatorJobId = null;
let creatorResult = null;
let editorCharacters = [];
let editorLines = [];
let selectedLineId = null;
let editorVideoUrl = null;
let editorVideoDuration = 0;
let timelineZoom = 5;
const TRACK_LABEL_WIDTH = 130;
let displayedProgress = 0;

const CHAR_COLORS = ['#6c8cff','#e5636b','#4caf7d','#d9a441','#c471ed','#41c7d9','#ff7043','#66bb6a','#ab47bc','#5c6bc0'];

// ---- NAVEGACION ----



async function saveGeminiKeyFromModal() {
    const input = document.getElementById('gemini-key-input').value.trim();
    if (!input) { alert("Por favor introduce una Clave API válida."); return; }
    try {
        const res = await fetch('/api/save_gemini_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: input })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('gemini-key-modal').style.display = 'none';
            document.getElementById('btn-auto-create').click();
        } else {
            alert(data.error || "No se pudo guardar la clave API.");
        }
    } catch(e) {
        alert("Error guardando Clave API: " + e.message);
    }
}

document.getElementById('btn-auto-create').onclick = async () => {
    const userApiKey = (document.getElementById('creator-gemini-key') ? document.getElementById('creator-gemini-key').value.trim() : '');
    if (userApiKey) {
        try {
            await fetch('/api/save_gemini_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: userApiKey })
            });
        } catch(e) {
            console.warn("Could not save user Gemini key:", e);
        }
    } else {
        // Check if Gemini API key exists
        try {
            const rKey = await fetch('/api/check_gemini_key');
            const dKey = await rKey.json();
            if (!dKey.has_key) {
                const modalKey = document.getElementById('gemini-key-modal');
                if (modalKey) modalKey.style.display = 'flex';
                else alert("Por favor, introduce tu Clave API de Google Gemini en la casilla para usar el Taller de Escenas.");
                return;
            }
        } catch(e) {
            console.warn("Could not check gemini key:", e);
        }
    }

    const packName = document.getElementById('auto-pack-name').value.trim();
    const videoFile = document.getElementById('auto-video-upload').files[0];
    const youtubeUrl = document.getElementById('auto-youtube-url').value.trim();

    if (!packName) { alert('Escribe un nombre para la escena.'); return; }
    if (!videoFile && !youtubeUrl) { alert('Sube un video o pega un enlace de YouTube.'); return; }

    showView('view-creator-processing');

    const formData = new FormData();
    formData.append('pack_name', packName);
    if (videoFile) formData.append('video', videoFile);
    else formData.append('youtube_url', youtubeUrl);

    try {
        const res = await fetch('/api/creator/auto_build', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        creatorJobId = data.job_id;
        displayedProgress = 0;
        pollAutoProcessing();
    } catch(e) {
        alert('Error: ' + e.message);
        showView('view-creator-input');
    }
};

// ---- POLLING ----

async function pollAutoProcessing() {
    if (!creatorJobId) return;
    try {
        const res = await fetch('/api/creator/status/' + creatorJobId);
        const data = await res.json();
        const targetProgress = data.progress || 0;
        const statusText = data.status || 'Procesando...';
        document.getElementById('processing-status-text').innerText = statusText;
        smoothProgressTo(targetProgress);

        if (data.error) {
            alert('Error durante el procesamiento: ' + data.status);
            showView('view-creator-input');
            displayedProgress = 0;
            return;
        }

        if (data.progress >= 100) {
            displayedProgress = 100;
            document.getElementById('processing-progress-bar').style.width = '100%';
            document.getElementById('processing-percent').innerText = '100%';

            const packName = encodeURIComponent(document.getElementById('auto-pack-name').value.trim() || 'Mi Escena');
            setTimeout(() => {
                window.location.href = '/editor?job_id=' + creatorJobId + '&pack_name=' + packName;
            }, 1000);
        } else {
            setTimeout(pollAutoProcessing, 1200);
        }
    } catch(e) {
        console.error('Polling error:', e);
        setTimeout(pollAutoProcessing, 2000);
    }
}

function smoothProgressTo(target) {
    const bar = document.getElementById('processing-progress-bar');
    const pct = document.getElementById('processing-percent');
    if (!bar || !pct) return;
    if (target <= displayedProgress) return;
    displayedProgress = target;
    bar.style.width = target + '%';
    pct.innerText = target + '%';
}

// ---- PLAYHEAD ----

function updatePlayheadPosition() {
    const video = document.getElementById('editor-video');
    const ph = document.getElementById('timeline-playhead');
    if (!video || !ph) return;
    const pxPerSec = timelineZoom * 10;
    ph.style.left = (video.currentTime * pxPerSec) + 'px';
}

// ---- SELECCION DE LINEA ----

function selectLine(lineId) {
    selectedLineId = lineId;
    const line = editorLines.find(l => l.id === lineId);
    if (!line) { deselectLine(); return; }

    const lp = document.getElementById('line-edit-panel-wrap');
    if (lp) lp.style.display = 'block';

    document.getElementById('line-edit-caption').value = line.caption;
    document.getElementById('line-edit-start').value = line.start.toFixed(2);
    document.getElementById('line-edit-end').value = line.end.toFixed(2);

    // Jump video to line start
    const video = document.getElementById('editor-video');
    if (video && !isNaN(line.start)) video.currentTime = line.start;

    updateCharacterSelect(line.character);
    renderLinesList();
    renderTimeline();
}

function deselectLine() {
    selectedLineId = null;
    const lp = document.getElementById('line-edit-panel-wrap');
    if (lp) lp.style.display = 'none';
}

function applyLineEdits() {
    if (!selectedLineId) return;
    const line = editorLines.find(l => l.id === selectedLineId);
    if (!line) return;

    line.character = document.getElementById('line-edit-char').value;
    line.caption = document.getElementById('line-edit-caption').value;
    line.start = parseFloat(document.getElementById('line-edit-start').value) || 0;
    line.end = parseFloat(document.getElementById('line-edit-end').value) || 0;

    // If character not in list, add it
    if (!editorCharacters.find(c => c.name === line.character)) {
        editorCharacters.push({ name: line.character, color: CHAR_COLORS[editorCharacters.length % CHAR_COLORS.length] });
        renderCharactersPanel();
    }

    renderLinesList();
    renderTimeline();
}

// ---- GESTION DE LINEAS ----

function addLineAtPlayhead() {
    const video = document.getElementById('editor-video');
    const currentTime = video ? video.currentTime : 0;
    const charName = editorCharacters.length > 0 ? editorCharacters[0].name : 'Personaje 1';

    const newLine = {
        id: Math.random().toString(36).substr(2,9),
        character: charName,
        caption: 'Nuevo dialogo',
        start: Math.round(currentTime * 100) / 100,
        end: Math.round((currentTime + 3) * 100) / 100
    };
    editorLines.push(newLine);
    editorLines.sort((a, b) => a.start - b.start);
    selectLine(newLine.id);
    renderLinesList();
    renderTimeline();
}

function deleteSelectedLine() {
    if (!selectedLineId) return;
    if (!confirm('Eliminar esta linea?')) return;
    editorLines = editorLines.filter(l => l.id !== selectedLineId);
    deselectLine();
    renderLinesList();
    renderTimeline();
}

function renderLinesList() {
    const container = document.getElementById('editor-lines-list');
    const counter = document.getElementById('lines-count');
    if (!container) return;
    if (counter) counter.textContent = editorLines.length;

    container.innerHTML = '';
    const sorted = [...editorLines].sort((a, b) => a.start - b.start);
    sorted.forEach(line => {
        const ch = editorCharacters.find(c => c.name === line.character);
        const color = ch ? ch.color : '#666';
        const isSelected = line.id === selectedLineId;
        const el = document.createElement('div');
        el.style.cssText = `display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;cursor:pointer;border:1px solid ${isSelected ? '#00bcd4' : '#1e3040'};background:${isSelected ? '#1a2f3a' : '#0d1117'};`;
        el.innerHTML = `
            <div style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;"></div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:0.7rem;color:#546e7a;">${line.character} · ${line.start.toFixed(1)}s - ${line.end.toFixed(1)}s</div>
                <div style="font-size:0.8rem;color:#cfd8dc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${line.caption || '(sin texto)'}</div>
            </div>
            <button onclick="event.stopPropagation();deleteLineById('${line.id}')" style="background:none;border:none;color:#546e7a;cursor:pointer;font-size:0.9rem;padding:2px 4px;">&#10005;</button>
        `;
        el.onclick = () => selectLine(line.id);
        container.appendChild(el);
    });
}

function deleteLineById(id) {
    editorLines = editorLines.filter(l => l.id !== id);
    if (selectedLineId === id) deselectLine();
    renderLinesList();
    renderTimeline();
}

// ---- GESTION DE PERSONAJES ----

function renderCharactersPanel() {
    const container = document.getElementById('editor-sidebar-chars');
    if (!container) return;
    container.innerHTML = '';
    editorCharacters.forEach((ch, i) => {
        const el = document.createElement('div');
        el.style.cssText = 'display:flex;align-items:center;padding:6px 8px;border-radius:6px;gap:8px;background:rgba(255,255,255,0.03);margin-bottom:4px;';
        el.innerHTML = `
            <div style="width:12px;height:12px;border-radius:50%;background:${ch.color};flex-shrink:0;"></div>
            <span style="flex:1;font-size:0.88rem;color:#fff;font-weight:bold;">${ch.name}</span>
            <button onclick="removeCharacter(${i})" title="Eliminar personaje" style="width:26px;height:26px;border-radius:4px;border:1px solid #ff4081;background:rgba(255,64,129,0.15);color:#ff4081;cursor:pointer;font-size:0.85rem;display:flex;align-items:center;justify-content:center;flex-shrink:0;">🗑️</button>
        `;
        container.appendChild(el);
    });
    updateCharacterSelect();
}

function addCharacter() {
    const name = document.getElementById('new-char-name').value.trim();
    if (!name) return;
    if (editorCharacters.find(c => c.name === name)) { alert('Ese personaje ya existe.'); return; }
    editorCharacters.push({ name: name, color: CHAR_COLORS[editorCharacters.length % CHAR_COLORS.length] });
    document.getElementById('new-char-name').value = '';
    renderCharactersPanel();
    renderTimeline();
}

function removeCharacter(idx) {
    if (idx < 0 || idx >= editorCharacters.length) return;
    const name = editorCharacters[idx].name;
    const charLines = editorLines.filter(l => l.character === name);
    if (charLines.length > 0) {
        if (!confirm(`¿Eliminar al personaje "${name}" y sus ${charLines.length} líneas de diálogo de la línea de tiempo?`)) return;
        editorLines = editorLines.filter(l => l.character !== name);
    }
    editorCharacters.splice(idx, 1);
    if (selectedLineId && !editorLines.some(l => l.id === selectedLineId)) {
        deselectLine();
    }
    renderCharactersPanel();
    renderLinesList();
    renderTimeline();
}

function renameCharacter(idx, newName) {
    const oldName = editorCharacters[idx].name;
    editorCharacters[idx].name = newName;
    // Update all lines that had the old name
    editorLines.forEach(l => { if (l.character === oldName) l.character = newName; });
    renderCharactersPanel();
    renderLinesList();
    renderTimeline();
}

function updateCharacterSelect(selectedChar) {
    const sel = document.getElementById('line-edit-char');
    if (!sel) return;
    sel.innerHTML = '';
    editorCharacters.forEach(ch => {
        const opt = document.createElement('option');
        opt.value = ch.name;
        opt.textContent = ch.name;
        if (selectedChar && ch.name === selectedChar) opt.selected = true;
        sel.appendChild(opt);
    });
    // Allow typing a new character name
    if (selectedChar && !editorCharacters.find(c => c.name === selectedChar)) {
        const opt = document.createElement('option');
        opt.value = selectedChar;
        opt.textContent = selectedChar + ' (nuevo)';
        opt.selected = true;
        sel.appendChild(opt);
    }
}

function getCharColor(charName) {
    const ch = editorCharacters.find(c => c.name === charName);
    return ch ? ch.color : '#607d8b';
}

// ---- TIMELINE ----

let isDraggingTimelineBlock = false;
let draggedLineId = null;
let dragStartX = 0;
let dragStartY = 0;
let origLineStart = 0;
let origLineEnd = 0;

function renderTimeline() {
    const scrollArea = document.getElementById('timeline-scroll-area');
    const ruler = document.getElementById('timeline-ruler');
    const tracks = document.getElementById('timeline-tracks');
    const charsPane = document.getElementById('timeline-chars-pane');
    if (!ruler || !tracks || !charsPane || !scrollArea) return;

    const video = document.getElementById('editor-video');
    if (video && video.duration && isFinite(video.duration) && video.duration > 0) {
        editorVideoDuration = video.duration;
    }
    if (!editorVideoDuration || editorVideoDuration <= 0) {
        const maxEnd = editorLines.reduce((max, l) => Math.max(max, l.end || 0), 10);
        editorVideoDuration = Math.max(maxEnd, 10);
    }

    // Clamp all line timestamps to video duration bounds
    editorLines.forEach(l => {
        l.start = Math.max(0, Math.min(l.start, editorVideoDuration - 0.1));
        l.end = Math.max(l.start + 0.1, Math.min(l.end, editorVideoDuration));
    });

    const pxPerSec = timelineZoom * 10;
    const totalWidth = Math.max(editorVideoDuration * pxPerSec, 800);

    // Ruler
    ruler.innerHTML = '';
    ruler.style.width = totalWidth + 'px';
    ruler.style.minWidth = totalWidth + 'px';
    const interval = pxPerSec >= 50 ? 1 : pxPerSec >= 20 ? 5 : 10;
    for (let t = 0; t <= editorVideoDuration; t += interval) {
        const mark = document.createElement('div');
        mark.style.cssText = `position:absolute;left:${t*pxPerSec}px;top:0;height:100%;border-left:1px solid #1e3040;padding-left:3px;font-size:0.62rem;color:#546e7a;user-select:none;`;
        const mins = Math.floor(t / 60);
        const secs = Math.floor(t % 60);
        mark.textContent = `${mins}:${secs.toString().padStart(2,'0')}`;
        ruler.appendChild(mark);
    }

    ruler.onclick = (e) => {
        const rect = ruler.getBoundingClientRect();
        const time = Math.max(0, (e.clientX - rect.left + scrollArea.scrollLeft) / pxPerSec);
        if (video) video.currentTime = time;
    };

    // Tracks
    tracks.innerHTML = '';
    tracks.style.width = totalWidth + 'px';
    tracks.style.minWidth = totalWidth + 'px';

    // Playhead
    const ph = document.createElement('div');
    ph.id = 'timeline-playhead';
    ph.style.cssText = 'position:absolute;top:0;bottom:0;width:2px;background:#00e5ff;z-index:10;pointer-events:none;box-shadow:0 0 8px #00e5ff;';
    ph.style.left = (video ? video.currentTime * pxPerSec : 0) + 'px';
    tracks.appendChild(ph);

    charsPane.innerHTML = '';

    const charsToShow = editorCharacters.length > 0 ? editorCharacters : [{ name: 'Sin personaje', color: '#607d8b' }];
    charsToShow.forEach((ch, trackIdx) => {
        const charLabel = document.createElement('div');
        charLabel.style.cssText = `height:44px;display:flex;align-items:center;padding:0 8px;border-bottom:1px solid #1e3040;gap:6px;`;
        charLabel.innerHTML = `<div style="width:8px;height:8px;border-radius:50%;background:${ch.color};flex-shrink:0;"></div><span style="font-size:0.75rem;color:#b0bec5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${ch.name}</span>`;
        charsPane.appendChild(charLabel);

        const track = document.createElement('div');
        track.dataset.charName = ch.name;
        track.dataset.trackIndex = trackIdx;
        track.style.cssText = `height:44px;position:relative;border-bottom:1px solid #1a2030;`;

        const charLines = editorLines.filter(l => l.character === ch.name);
        charLines.forEach(line => {
            const left = line.start * pxPerSec;
            const width = Math.max((line.end - line.start) * pxPerSec, 24);
            const isSelected = line.id === selectedLineId;

            const el = document.createElement('div');
            el.className = 'timeline-line-block';
            el.style.cssText = `position:absolute;left:${left}px;width:${width}px;top:6px;height:32px;background:${ch.color};border-radius:6px;color:#000;font-size:0.68rem;font-weight:bold;line-height:32px;padding:0 6px 0 8px;cursor:grab;box-shadow:${isSelected ? '0 0 0 2px #fff,0 0 12px rgba(255,255,255,0.5)' : '0 2px 4px rgba(0,0,0,0.4)'};opacity:0.92;transition:opacity 0.1s, box-shadow 0.1s; display:flex; justify-content:space-between; align-items:center; user-select:none; z-index:2;`;
            el.title = `${line.character}: "${line.caption}" (${line.start.toFixed(1)}s - ${line.end.toFixed(1)}s)\nArrastra horizontalmente para mover de tiempo o verticalmente para cambiar personaje`;
            el.innerHTML = `
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; pointer-events:none;">${line.caption || '(vacío)'}</span>
            `;

            // Click to select
            el.onclick = (e) => {
                e.stopPropagation();
                selectLine(line.id);
            };

            // Drag & Drop logic (horizontal for time shift, vertical for character track shift)
            el.onpointerdown = (e) => {
                if (e.target.tagName.toLowerCase() === 'button') return;
                e.stopPropagation();
                el.setPointerCapture(e.pointerId);
                el.style.cursor = 'grabbing';
                el.style.zIndex = '50';
                isDraggingTimelineBlock = true;
                draggedLineId = line.id;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                origLineStart = line.start;
                origLineEnd = line.end;
                selectLine(line.id);

                const duration = origLineEnd - origLineStart;

                const onPointerMove = (moveEvt) => {
                    if (!isDraggingTimelineBlock || draggedLineId !== line.id) return;
                    const deltaX = moveEvt.clientX - dragStartX;
                    const deltaTime = deltaX / pxPerSec;
                    let newStart = Math.max(0, Math.min(origLineStart + deltaTime, editorVideoDuration - duration));
                    let newEnd = newStart + duration;

                    line.start = Math.round(newStart * 100) / 100;
                    line.end = Math.round(newEnd * 100) / 100;

                    // Vertical track hover check (change character)
                    const trackElements = document.querySelectorAll('#timeline-tracks > div');
                    trackElements.forEach(tEl => {
                        const r = tEl.getBoundingClientRect();
                        if (moveEvt.clientY >= r.top && moveEvt.clientY <= r.bottom && tEl.dataset.charName) {
                            line.character = tEl.dataset.charName;
                        }
                    });

                    // Real-time update detail inputs
                    const startInput = document.getElementById('line-edit-start');
                    const endInput = document.getElementById('line-edit-end');
                    if (startInput) startInput.value = line.start.toFixed(2);
                    if (endInput) endInput.value = line.end.toFixed(2);
                    const charSelect = document.getElementById('line-edit-char');
                    if (charSelect && line.character) charSelect.value = line.character;

                    renderTimeline();
                };

                const onPointerUp = (upEvt) => {
                    try { el.releasePointerCapture(upEvt.pointerId); } catch(err){}
                    el.style.cursor = 'grab';
                    el.style.zIndex = '2';
                    isDraggingTimelineBlock = false;
                    draggedLineId = null;
                    window.removeEventListener('pointermove', onPointerMove);
                    window.removeEventListener('pointerup', onPointerUp);
                    renderLinesList();
                    renderTimeline();
                    autoSaveProject();
                };

                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp);
            };

            el.onmouseover = () => { if (!isDraggingTimelineBlock) el.style.opacity = '1'; };
            el.onmouseout = () => { if (!isDraggingTimelineBlock) el.style.opacity = '0.92'; };
            track.appendChild(el);
        });

        tracks.appendChild(track);
    });
}

// ---- SALIR DEL EDITOR ----

function editorRemoveVideo() {
    const v = document.getElementById('editor-video');
    if (v) { v.src = ''; v.load(); }
    editorVideoUrl = null;
    editorVideoDuration = 0;
}

function exitEditor() {
    if (editorLines.length > 0) {
        if (!confirm('Seguro que quieres salir? Los cambios no guardados se perderan.')) return;
    }
    showView('view-start');
    selectedLineId = null;
    editorLines = [];
    editorCharacters = [];
    editorVideoDuration = 0;
    deselectLine();
}

// ---- EXPORTAR ----

async function exportPack() {
    const packNameEl = document.getElementById('editor-pack-name');
    const packName = packNameEl ? packNameEl.value.trim() : '';
    if (!packName) { alert('Escribe un nombre para la escena.'); return; }
    if (editorLines.length === 0) { alert('No hay lineas de dialogo para exportar.'); return; }
    if (!creatorJobId) { alert('Error: no hay un trabajo activo. Vuelve a crear la escena desde el principio.'); return; }

    const statusEl = document.getElementById('export-status');
    const btn = document.getElementById('btn-export-pack');

    if (btn) { btn.textContent = 'Exportando...'; btn.disabled = true; }
    if (statusEl) { statusEl.style.display = 'block'; statusEl.textContent = 'Procesando el pack...'; }

    try {
        const res = await fetch('/api/creator/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_id: creatorJobId,
                pack_name: packName,
                lines: editorLines,
                characters: editorCharacters
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        if (statusEl) statusEl.textContent = 'Pack creado con exito!';
        if (btn) { btn.textContent = 'Exportado!'; btn.disabled = false; }
        setTimeout(() => {
            alert('La escena "' + packName + '" se ha creado correctamente. Ya puedes jugarla desde el catalogo de escenas.');
            if (btn) { btn.textContent = 'Export pack'; }
            showView('view-packs');
        }, 1200);
    } catch(e) {
        if (statusEl) statusEl.textContent = 'Error: ' + e.message;
        if (btn) { btn.textContent = 'Export pack'; btn.disabled = false; }
        alert('Error al exportar: ' + e.message);
    }
}

// Fetch network info for multiplayer
fetch('/api/network_info')
    .then(r => r.json())
    .then(data => {
        const el = document.getElementById('network-ip-display');
        if(el && data.local_ips && data.local_ips.length > 0) {
            let html = "";
            data.local_ips.forEach(ip => {
                html += 'https://' + ip + ':' + data.port + '<br>';
            });
            el.innerHTML = html;
        }
    })
    .catch(e => console.error('Error fetching network info', e));


    

// ---------------- MULTIPLAYER HANDLERS ----------------
socket.on('room_update', (data) => {
    multiplayerGameMode = data.mode;
    multiplayerScoringMode = data.scoring_mode || 'ia';
    window._lastRoomPlayers = data.players; // Cache for competitive waiting screen
    showRoomChatWidget();
    
    // Update mode badge for ALL players (host and guests)
    const modeBadge = document.getElementById('lobby-mode-badge');
    if (modeBadge) {
        modeBadge.style.display = 'block';
        if (data.mode === 'cooperativo') {
            modeBadge.style.background = 'rgba(0,229,255,0.15)';
            modeBadge.style.border = '2px solid #00e5ff';
            modeBadge.style.color = '#00e5ff';
            modeBadge.innerText = '🤝 COOPERATIVO — Cada jugador elige sus personajes';
        } else {
            modeBadge.style.background = 'rgba(255,64,129,0.15)';
            modeBadge.style.border = '2px solid #ff4081';
            modeBadge.style.color = '#ff4081';
            modeBadge.innerText = '⚔️ COMPETITIVO — Todos doblan todos los personajes';
        }
    }

    // Update scoring mode container & badge for host and guests
    const scoringContainer = document.getElementById('lobby-scoring-container');
    const scoringSelect = document.getElementById('lobby-scoring-select');
    const scoringBadge = document.getElementById('lobby-scoring-badge');

    if (scoringContainer) scoringContainer.style.display = 'block';
    
    if (isHost) {
        if (scoringSelect) {
            scoringSelect.style.display = 'block';
            scoringSelect.value = multiplayerScoringMode;
            scoringSelect.onchange = function() {
                socket.emit('change_scoring_mode', { room: currentRoom, scoring_mode: this.value });
            };
        }
        if (scoringBadge) scoringBadge.style.display = 'none';
    } else {
        if (scoringSelect) scoringSelect.style.display = 'none';
        if (scoringBadge) {
            scoringBadge.style.display = 'block';
            if (multiplayerScoringMode === 'voting') {
                scoringBadge.style.background = 'rgba(255,64,129,0.15)';
                scoringBadge.style.border = '2px solid #ff4081';
                scoringBadge.style.color = '#ff4081';
                scoringBadge.innerText = '🗳️ VOTACIÓN DE JUGADORES — Elección por votos';
            } else {
                scoringBadge.style.background = 'rgba(0,229,255,0.15)';
                scoringBadge.style.border = '2px solid #00e5ff';
                scoringBadge.style.color = '#00e5ff';
                scoringBadge.innerText = '🤖 PUNTUACIÓN IA — Evaluación automática por precisión';
            }
        }
    }
    
    multiplayerScoreSensitivity = data.score_sensitivity || 'normal';
    multiplayerPlaybackMode = 'premiere'; // Fixed: always premiere (host controls)


    // Sync the host dropdown value if we are host
    if (isHost) {
        const sel = document.getElementById('lobby-mode-select');
        if (sel) sel.value = data.mode;
    }

    
    const playersDiv = document.getElementById('lobby-players');
    if(playersDiv) {
        playersDiv.innerHTML = '';
        data.players.forEach(p => {
            const pdiv = document.createElement('div');
            pdiv.style.padding = '10px';
            pdiv.style.marginBottom = '5px';
            pdiv.style.background = p.ready ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 255, 255, 0.05)';
            pdiv.style.border = p.ready ? '1px solid #00e676' : '1px solid #2a3f54';
            pdiv.style.borderRadius = '5px';
            
            let html = `<strong style="color: ${p.ready ? '#00e676' : '#fff'}">${p.name}</strong> `;
            if(p.ready) html += ' - LISTO';
            pdiv.innerHTML = html;
            playersDiv.appendChild(pdiv);

            // Synchronize compWaitingPlayers if competitive waiting screen is active
            if (compWaitingPlayers) {
                let entry = compWaitingPlayers[p.sid] || Object.values(compWaitingPlayers).find(cp => cp.name === p.name);
                if (entry) {
                    if (p.score !== undefined && p.score !== null) {
                        entry.scored = true;
                        entry.score = p.score;
                    }
                }
            }
        });

        if (document.getElementById('comp-waiting-overlay')?.style.display === 'flex') {
            renderCompWaitingList();
        }
    }
    
    // Update chars if coop
    claimedCharacters = [];
    if(data.characters) {
        Object.keys(data.characters).forEach(charName => {
            if (data.characters[charName] === myName) {
                claimedCharacters.push(charName);
            }
        });
    }
    
    if (multiplayerGameMode === 'cooperativo') {
        const charsContainer = document.getElementById('lobby-chars-container');
        const charsList = document.getElementById('lobby-chars-list');
        if (charsContainer && charsList && allPackCharacters) {
            charsContainer.style.display = 'block';
            charsList.innerHTML = '';
            
            allPackCharacters.forEach(c => {
                const row = document.createElement('div');
                row.style.display = 'flex';
                row.style.alignItems = 'center';
                row.style.justifyContent = 'space-between';
                row.style.padding = '8px 12px';
                row.style.background = '#121a24';
                row.style.borderRadius = '6px';
                row.style.marginBottom = '6px';
                
                const nameSpan = document.createElement('span');
                nameSpan.innerText = c;
                nameSpan.style.color = '#fff';
                
                const btnClaim = document.createElement('button');
                btnClaim.className = 'btn-pill';
                
                if (data.characters && data.characters[c]) {
                    if (data.characters[c] === myName) {
                        btnClaim.innerText = 'Tuyo';
                        btnClaim.style.background = '#00e5ff';
                        btnClaim.style.color = '#000';
                        btnClaim.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: false});
                    } else {
                        const ownerName = data.characters[c];
                        btnClaim.innerText = ownerName || 'Ocupado';
                        btnClaim.disabled = true;
                        btnClaim.style.background = '#37474f';
                        btnClaim.style.color = '#fff';
                    }
                } else {
                    btnClaim.innerText = 'Elegir';
                    btnClaim.style.background = '#ff4081';
                    btnClaim.style.color = '#fff';
                    btnClaim.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: true});
                }
                
                row.appendChild(nameSpan);
                row.appendChild(btnClaim);
                charsList.appendChild(row);
            });
        }
    } else {
        const charsContainer = document.getElementById('lobby-chars-container');
        if (charsContainer) charsContainer.style.display = 'none';
    }

    // Ready button styling and state update
    const btnReady = document.getElementById('btn-ready');
    if (btnReady) {
        if (multiplayerGameMode === 'cooperativo' && (!claimedCharacters || claimedCharacters.length === 0)) {
            if (amIReady) {
                amIReady = false;
            }
            btnReady.innerText = "⚠️ ELIGE PERSONAJE";
            btnReady.style.background = "#37474f";
            btnReady.style.color = "#aaa";
        } else {
            btnReady.style.background = amIReady ? "#00ffcc" : "";
            btnReady.style.color = amIReady ? "#000" : "";
            btnReady.innerText = amIReady ? "✓ LISTO!" : "¡ESTOY LISTO!";
        }
    }
});

socket.on('game_start_countdown', async (data) => {
    try {
        // Reset and pre-populate compWaitingPlayers for competitive waiting screen
        compWaitingPlayers = {};
        if (window._lastRoomPlayers && Array.isArray(window._lastRoomPlayers)) {
            window._lastRoomPlayers.forEach(p => {
                const sid = p.sid || p.name;
                compWaitingPlayers[sid] = {
                    name: p.name,
                    sid: sid,
                    score: 0,
                    scored: false,
                    videoReady: false,
                    videoError: false
                };
            });
        }

        // Show a loading/countdown indicator
        const btn = document.getElementById('btn-ready');
        if(btn) btn.innerText = "⏳ PREPARANDO JUEGO...";
        
        const packName = data.pack_name;
        
        // 1. Check for video
        try {
            let vRes = await fetch(`/media/${encodeURIComponent(packName)}/dub_video.mp4?t=` + Date.now(), {method: 'HEAD'});
            if (vRes.ok) {
                packHasVideo = true;
                window.currentPackVideo = `/media/${encodeURIComponent(packName)}/dub_video.mp4`;
            } else {
                let vRes2 = await fetch(`/media/${encodeURIComponent(packName)}/dub_video.ogv?t=` + Date.now(), {method: 'HEAD'});
                if (vRes2.ok) {
                    packHasVideo = true;
                    window.currentPackVideo = `/media/${encodeURIComponent(packName)}/dub_video.ogv`;
                } else {
                    packHasVideo = false;
                }
            }
        } catch(e) {
            console.warn('Video check failed:', e);
            packHasVideo = false;
        }
        
        if (packHasVideo) {
            sceneVideo.src = window.currentPackVideo;
            sceneVideo.load();
        }
        
        // 2. Fetch pack info for backing track
        try {
            const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/clips`);
            if (res.ok) {
                const packData = await res.json();
                hasBackingTrack = packData.has_backing_track;
            } else {
                hasBackingTrack = false;
            }
        } catch(e) {
            console.warn('Pack info fetch failed:', e);
            hasBackingTrack = false;
        }
        
        if (audioContext.state === 'suspended') {
            try { await audioContext.resume(); } catch(e) {}
        }
        
        if (hasBackingTrack) {
            try {
                const bgRes = await fetch(`/media/${encodeURIComponent(packName)}/_backing_track.mp3`);
                if (bgRes.ok) {
                    const bgArray = await bgRes.arrayBuffer();
                    backingBuffer = await audioContext.decodeAudioData(bgArray);
                } else {
                    backingBuffer = null;
                }
            } catch(e) {
                console.warn('Could not load backing track:', e);
                backingBuffer = null;
            }
        } else {
            backingBuffer = null;
        }
        
        userRecordings = new Array(clipsList.length).fill(null);
        clipOriginalBuffers = new Array(clipsList.length).fill(null);
        currentClipIndex = 0;
        
        // 3. Set characters to dub
        if (multiplayerGameMode === 'cooperativo') {
            selectedCharacters = claimedCharacters;
            if (!selectedCharacters || selectedCharacters.length === 0) {
                alert("No has elegido ningún personaje. Dubbearás todos los personajes.");
                selectedCharacters = allPackCharacters;
                claimedCharacters = allPackCharacters;
            }
        } else {
            selectedCharacters = allPackCharacters;
            claimedCharacters = allPackCharacters;
        }
        
        // 4. Start game UI with clean layout & empty recordings
        cleanGameLayoutAndState();
        startAfkChecker();
        userRecordings = new Array(clipsList.length).fill(null);
        clipOriginalBuffers = new Array(clipsList.length).fill(null);
        currentClipIndex = 0;
        
        showView('view-play');
        sceneVideo.style.display = 'none';
        sceneVideo.classList.add('hidden');
        clipImage.style.display = 'block';
        
        if (!menuMusic.paused) {
            fadeOutMusic();
        }
        
        // 5. Load first clip
        advanceToNextSelectedClip(-1);
    } catch(err) {
        console.error("Error in game_start_countdown handler:", err);
        showView('view-play');
        advanceToNextSelectedClip(-1);
    }
});

// Bind ready button
document.getElementById('btn-ready').onclick = setReady;

// Utility function to convert AudioBuffer to WAV Blob
function bufferToWav(abuffer, len) {
    var numOfChan = abuffer.numberOfChannels,
        length = len || abuffer.length * numOfChan * 2 + 44,
        buffer = new ArrayBuffer(length),
        view = new DataView(buffer),
        channels = [], i, sample,
        offset = 0,
        pos = 0;

    function setUint16(data) {
        view.setUint16(pos, data, true);
        pos += 2;
    }

    function setUint32(data) {
        view.setUint32(pos, data, true);
        pos += 4;
    }

    setUint32(0x46464952);
    setUint32(length - 8);
    setUint32(0x45564157);
    setUint32(0x20746d66);
    setUint32(16);
    setUint16(1);
    setUint16(numOfChan);
    setUint32(abuffer.sampleRate);
    setUint32(abuffer.sampleRate * 2 * numOfChan);
    setUint16(numOfChan * 2);
    setUint16(16);
    setUint32(0x61746164);
    setUint32(length - pos - 4);

    for (i = 0; i < abuffer.numberOfChannels; i++)
        channels.push(abuffer.getChannelData(i));

    while (pos < length) {
        for (i = 0; i < numOfChan; i++) {
            sample = Math.max(-1, Math.min(1, channels[i][offset]));
            sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
            view.setInt16(pos, sample, true);
            pos += 2;
        }
        offset++;
    }

    return new Blob([buffer], {type: "audio/wav"});
}


// COOP MULTIPLAYER SYNC
socket.on('coop_waiting_update', (data) => {
    const text = document.getElementById('coop-waiting-text');
    if (text) {
        text.innerText = `${data.finished} / ${data.total} Jugadores Listos`;
    }
    const playersListEl = document.getElementById('coop-waiting-players-list');
    if (playersListEl && data.players) {
        playersListEl.innerHTML = '';
        data.players.forEach(p => {
            const row = document.createElement('div');
            row.style.display = 'flex';
            row.style.justifyContent = 'space-between';
            row.style.alignItems = 'center';
            row.style.padding = '8px 12px';
            row.style.borderRadius = '6px';
            row.style.background = p.status === 'finished' ? 'rgba(0, 230, 118, 0.15)' : 'rgba(255, 255, 255, 0.05)';
            row.style.border = p.status === 'finished' ? '1px solid #00e676' : '1px solid rgba(255,255,255,0.1)';
            
            const isDone = p.status === 'finished';
            row.innerHTML = `
                <span style="color: ${isDone ? '#00e676' : '#fff'}; font-weight: bold;">${p.name}</span>
                <span style="color: ${isDone ? '#00e676' : '#ff4081'}; font-size: 0.9rem;">${isDone ? '✅ Terminado' : '🔴 Grabando...'}</span>
            `;
            playersListEl.appendChild(row);
        });
    }
});

socket.on('coop_processing', (data) => {
    const titleEl = document.getElementById('coop-waiting-title');
    if (titleEl) titleEl.innerText = "🎬 Procesando Escena Grupal";
    const subTitleEl = document.getElementById('coop-waiting-subtitle');
    if (subTitleEl) subTitleEl.innerText = data.message || "Mezclando doblajes de todos los jugadores...";
    startCoopStatusPolling();
});

let coopStatusPollTimer = null;

function stopCoopStatusPolling() {
    if (coopStatusPollTimer) {
        clearInterval(coopStatusPollTimer);
        coopStatusPollTimer = null;
    }
}

function startCoopStatusPolling() {
    stopCoopStatusPolling();
    if (!currentRoom) return;
    
    coopStatusPollTimer = setInterval(async () => {
        try {
            const res = await fetch(`/api/coop_status/${currentRoom}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'done' && data.ranking) {
                stopCoopStatusPolling();
                handleCoopGameOver(data);
            } else if (data.status === 'error') {
                stopCoopStatusPolling();
                handleCoopGameOver(data);
            } else if (data.status === 'processing') {
                const text = document.getElementById('coop-waiting-text');
                if (text && data.finished !== undefined && data.total !== undefined) {
                    text.innerText = `${data.finished} / ${data.total} Jugadores Listos`;
                }
                const playersListEl = document.getElementById('coop-waiting-players-list');
                if (playersListEl && data.players) {
                    playersListEl.innerHTML = '';
                    data.players.forEach(p => {
                        const row = document.createElement('div');
                        row.style.display = 'flex';
                        row.style.justifyContent = 'space-between';
                        row.style.alignItems = 'center';
                        row.style.padding = '8px 12px';
                        row.style.borderRadius = '6px';
                        row.style.background = p.status === 'finished' ? 'rgba(0, 230, 118, 0.15)' : 'rgba(255, 255, 255, 0.05)';
                        row.style.border = p.status === 'finished' ? '1px solid #00e676' : '1px solid rgba(255,255,255,0.1)';
                        
                        const isDone = p.status === 'finished';
                        row.innerHTML = `
                            <span style="color: ${isDone ? '#00e676' : '#fff'}; font-weight: bold;">${p.name}</span>
                            <span style="color: ${isDone ? '#00e676' : '#ff4081'}; font-size: 0.9rem;">${isDone ? '✅ Terminado' : '🔴 Grabando...'}</span>
                        `;
                        playersListEl.appendChild(row);
                    });
                }
            }
        } catch(e) {
            console.warn("Coop status poll error:", e);
        }
    }, 2000);
}

function showCoopVotingModal(data) {
    const modal = document.getElementById('coop-voting-modal');
    const grid = document.getElementById('coop-voting-players-grid');
    const statusMsg = document.getElementById('coop-voting-status-msg');
    if (!modal || !grid) return;

    grid.innerHTML = '';
    if (statusMsg) statusMsg.style.display = myVoteTargetCoop ? 'block' : 'none';

    const ranking = data.ranking || [];
    ranking.forEach(r => {
        const pName = r.name || r.player_name;
        const card = document.createElement('div');
        card.style.cssText = `
            background: #111318; border: 2px solid ${pName === myName ? '#444' : 'var(--magenta)'};
            border-radius: 12px; padding: 15px; display: flex; flex-direction: column;
            align-items: center; gap: 8px; text-align: center;
        `;

        card.innerHTML = `
            <div style="font-size: 1.8rem;">🎭</div>
            <div style="color: #fff; font-weight: bold; font-size: 1.1rem;">${pName}</div>
        `;

        if (pName === myName) {
            card.innerHTML += `<span style="color: #ff80ab; font-size: 0.8rem; font-style: italic;">(Tú - No puedes votarte)</span>`;
        } else {
            const btn = document.createElement('button');
            btn.className = 'btn-pill';
            const hasVotedThis = (myVoteTargetCoop === pName);
            btn.style.cssText = `padding: 8px 18px; font-size: 0.9rem; font-weight: bold; background: ${hasVotedThis ? '#00e676' : 'var(--magenta)'}; color: ${hasVotedThis ? '#000' : '#fff'}; margin-top: 5px; cursor: pointer; border: none;`;
            btn.innerText = hasVotedThis ? '✓ Votado' : '🗳️ VOTAR';
            btn.disabled = !!myVoteTargetCoop;

            btn.onclick = () => {
                myVoteTargetCoop = pName;
                socket.emit('submit_vote', { room: currentRoom, voter: myName, target: pName });
                showCoopVotingModal(data);
            };
            card.appendChild(btn);
        }
        grid.appendChild(card);
    });

    modal.style.display = 'flex';
}

function renderCoopRankingPanel(ranking) {
    const rankList = document.getElementById('comp-rank-list');
    if (!rankList) return;
    rankList.innerHTML = '';

    const medal = ['🥇', '🥈', '🥉'];
    const isVotingMode = (multiplayerScoringMode === 'voting');

    ranking.forEach((r, i) => {
        const item = document.createElement('li');
        item.style.cssText = `
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 14px; border-radius: 10px; transition: 0.2s;
            background: rgba(255,255,255,0.04);
            border: 1px solid ${i===0 ? '#FFD700' : i===1 ? '#C0C0C0' : i===2 ? '#CD7F32' : 'rgba(255,255,255,0.08)'};
        `;

        const pName = r.name || r.player_name;
        const scoreLabel = isVotingMode && isVotingCompleted 
            ? `${r.votes || 0} 🗳️ <small style="color:#888;">(IA: ${r.score} pts)</small>` 
            : `${r.score} pts`;

        item.innerHTML = `
            <span style="color: #fff; font-weight: bold; font-size: 1rem;">${medal[i] || '#' + (i+1)} ${pName}</span>
            <span style="color: var(--cyan); font-weight: bold; font-size: 1rem;">${scoreLabel}</span>
        `;
        rankList.appendChild(item);
    });
}

function handleCoopGameOver(data) {
    stopCoopStatusPolling();
    stopAfkChecker();
    isGameFinished = true;
    
    const overlay = document.getElementById('coop-waiting-overlay');
    if (overlay) overlay.style.display = 'none';

    if (data.error) {
        alert("Error al mezclar la escena cooperativa: " + data.error);
        return;
    }

    if (data.video_url) {
        coopFinalVideoUrl = data.video_url;
    }

    // Build competitiveVideos array for Coop Mode so Phase 1 & Phase 2 render seamlessly
    const rawList = data.ranking || data.scores || window._lastCoopRanking || [];
    if (rawList.length > 0) {
        competitiveVideos = rawList.map(r => {
            const pName = r.name || r.player_name;
            const pSid = r.sid || r.player_sid || pName;
            const charName = r.character || (typeof lobbyCharacters !== 'undefined' && lobbyCharacters ? Object.keys(lobbyCharacters).find(c => lobbyCharacters[c] === pName) : '') || '';
            return {
                player_name: pName,
                player_sid: pSid,
                character: charName,
                score: r.score || 0,
                votes: r.votes !== undefined ? r.votes : 0,
                video_url: coopFinalVideoUrl
            };
        });
    } else if (typeof lobbyPlayers !== 'undefined' && lobbyPlayers && lobbyPlayers.length > 0) {
        competitiveVideos = lobbyPlayers.map(p => {
            const pName = typeof p === 'string' ? p : p.name;
            const charName = (typeof lobbyCharacters !== 'undefined' && lobbyCharacters ? Object.keys(lobbyCharacters).find(c => lobbyCharacters[c] === pName) : '') || '';
            return {
                player_name: pName,
                player_sid: pName,
                character: charName,
                score: 0,
                votes: 0,
                video_url: coopFinalVideoUrl
            };
        });
    }

    if (data.isVotingFinished || isVotingCompleted) {
        switchCompEndPhase(2);
    } else {
        switchCompEndPhase(1);
    }
}

socket.on('coop_game_over', (data) => {
    handleCoopGameOver(data);
});


// =========================================================
// COMPETITIVE END SCREEN
// Completely self-contained. Does NOT reuse game UI elements.
// =========================================================

let competitiveVideos = [];
let currentCompVideoIndex = -1;
let pendingVideos = {};
let compEndScreenReady = false;
let _premiereActive = false;
let currentCompEndPhase = 1; // 1 = Host Presentation, 2 = Leaderboard & Free Play
let userVotedSid = null;

// Helper: in multiplayer, host ALWAYS controls. Guests are always locked.
function isHostController() {
    return !isMultiplayer || !currentRoom || isHost;
}
// Emit a sync event to all room members (host only calls this)
function emitVideoSync(payload) {
    if (!isMultiplayer || !currentRoom) return;
    socket.emit('host_video_sync', Object.assign({ room: currentRoom }, payload));
}

function getOrCreateCompEndScreen() {
    let overlay = document.getElementById('comp-end-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'comp-end-overlay';
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: #0a0c10; z-index: 9999; display: none;
        flex-direction: column; align-items: center; justify-content: space-between;
        padding: 15px 20px; box-sizing: border-box; overflow-y: auto;
    `;

    // ===== PHASE 1 CONTAINER (Drawing 1: Host Synchronized Presentation Stage) =====
    const phase1 = document.createElement('div');
    phase1.id = 'comp-phase-1';
    phase1.style.cssText = 'width: 100%; max-width: 1100px; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; position: relative; gap: 10px;';

    // Top player name header
    const p1Header = document.createElement('div');
    p1Header.id = 'comp-p1-header';
    p1Header.style.cssText = "color: #ff4081; font-family: 'Permanent Marker', cursive; font-size: 2.5rem; text-shadow: 2px 2px 0px rgba(0,0,0,0.8); text-align: center; margin-top: 5px;";
    p1Header.innerText = 'Nombre del Jugador';

    // Host / Guest sync badge
    const p1SyncBadge = document.createElement('div');
    p1SyncBadge.id = 'comp-p1-sync-badge';
    p1SyncBadge.style.cssText = 'font-size: 0.85rem; font-weight: bold; letter-spacing: 1px; border-radius: 20px; padding: 4px 16px; margin-top: -5px;';

    // Main Video Player Area
    const p1VideoWrap = document.createElement('div');
    p1VideoWrap.style.cssText = 'position: relative; max-width: 720px; width: 100%; display: flex; justify-content: center; align-items: center;';

    const compVideo = document.createElement('video');
    compVideo.id = 'comp-video-player';
    compVideo.controls = true;
    compVideo.style.cssText = 'width: 100%; max-height: 52vh; border-radius: 12px; border: 2px solid #ff4081; background: #000; display: block;';

    // Guest overlay for Phase 1 to prevent non-hosts from scrubbing video
    const guestOverlay = document.createElement('div');
    guestOverlay.id = 'comp-guest-overlay';
    guestOverlay.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: transparent; display: none; z-index: 2; border-radius: 12px; pointer-events: auto;';

    p1VideoWrap.appendChild(compVideo);
    p1VideoWrap.appendChild(guestOverlay);

    // Bottom Player Selector Row (Drawing 1 bottom bar)
    const p1BottomBar = document.createElement('div');
    p1BottomBar.id = 'comp-p1-bottom-bar';
    p1BottomBar.style.cssText = 'width: 100%; max-width: 850px; background: rgba(18,26,36,0.9); border: 2px solid #2a3f54; border-radius: 16px; padding: 12px 20px; display: flex; align-items: center; justify-content: center; gap: 15px; overflow-x: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5);';

    // Host 'Siguiente' button on right side of Phase 1
    const p1NextBtn = document.createElement('button');
    p1NextBtn.id = 'comp-p1-btn-next';
    p1NextBtn.innerText = 'Siguiente ➔';
    p1NextBtn.style.cssText = 'position: absolute; right: 0; top: 50%; transform: translateY(-50%); background: linear-gradient(135deg, #00e676, #00bcd4); color: #000; border: none; border-radius: 30px; padding: 14px 28px; font-size: 1.1rem; font-weight: bold; cursor: pointer; box-shadow: 0 0 20px rgba(0,230,118,0.4); transition: 0.2s; z-index: 10;';
    p1NextBtn.onclick = () => {
        if (!isHostController()) return;
        emitVideoSync({ action: 'goto_phase2' });
        switchCompEndPhase(2);
    };

    phase1.appendChild(p1Header);
    phase1.appendChild(p1SyncBadge);
    phase1.appendChild(p1VideoWrap);
    phase1.appendChild(p1BottomBar);
    phase1.appendChild(p1NextBtn);


    // ===== PHASE 2 CONTAINER (Drawing 2: Leaderboard + Free Video Player) =====
    const phase2 = document.createElement('div');
    phase2.id = 'comp-phase-2';
    phase2.style.cssText = 'width: 100%; max-width: 1100px; height: 100%; display: none; flex-direction: column; align-items: center; justify-content: space-between; gap: 15px;';

    // Winner Banner
    const p2WinnerBanner = document.createElement('h1');
    p2WinnerBanner.id = 'comp-p2-winner-banner';
    p2WinnerBanner.style.cssText = "font-family: 'Permanent Marker', cursive; font-size: 2.8rem; color: #00e676; text-shadow: 0 0 20px rgba(0,230,118,0.5); text-align: center; margin: 5px 0;";
    p2WinnerBanner.innerText = '¡X ha ganado!';

    // Phase 2 Main Layout (Left: Leaderboard, Right: Video Player)
    const p2Content = document.createElement('div');
    p2Content.style.cssText = 'width: 100%; flex: 1; display: flex; gap: 20px; align-items: stretch; min-height: 0;';

    // Left Leaderboard Panel
    const p2Leaderboard = document.createElement('div');
    p2Leaderboard.id = 'comp-p2-leaderboard';
    p2Leaderboard.style.cssText = 'width: 320px; min-width: 280px; background: rgba(18,26,36,0.9); border: 2px solid #2a3f54; border-radius: 16px; padding: 18px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto;';

    // Right Video Player Area for Free Play & Download
    const p2RightWrap = document.createElement('div');
    p2RightWrap.style.cssText = 'flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; background: rgba(10,14,20,0.6); border-radius: 16px; padding: 15px; border: 1px solid #1e2a3a;';

    const p2VideoLabel = document.createElement('div');
    p2VideoLabel.id = 'comp-p2-video-label';
    p2VideoLabel.style.cssText = 'color: #00e5ff; font-weight: bold; font-size: 1.3rem;';
    p2VideoLabel.innerText = 'Selecciona un vídeo del ranking';

    const p2VideoWrap = document.createElement('div');
    p2VideoWrap.style.cssText = 'width: 100%; max-width: 600px;';

    const p2VideoPlayer = document.createElement('video');
    p2VideoPlayer.id = 'comp-p2-video-player';
    p2VideoPlayer.controls = true;
    p2VideoPlayer.style.cssText = 'width: 100%; border-radius: 12px; border: 2px solid #00e5ff; background: #000; max-height: 42vh;';

    p2VideoWrap.appendChild(p2VideoPlayer);

    const p2DownloadBtn = document.createElement('button');
    p2DownloadBtn.id = 'comp-p2-btn-download';
    p2DownloadBtn.innerText = 'Descargar Vídeo 💾';
    p2DownloadBtn.style.cssText = 'background: #ff4081; color: #fff; border: none; border-radius: 25px; padding: 10px 24px; font-size: 1rem; font-weight: bold; cursor: pointer; transition: 0.2s;';

    p2RightWrap.appendChild(p2VideoLabel);
    p2RightWrap.appendChild(p2VideoWrap);
    p2RightWrap.appendChild(p2DownloadBtn);

    p2Content.appendChild(p2Leaderboard);
    p2Content.appendChild(p2RightWrap);

    // Bottom Right: Return to Main Menu Button
    const p2BottomRow = document.createElement('div');
    p2BottomRow.style.cssText = 'width: 100%; display: flex; justify-content: flex-end; padding-top: 5px;';

    const p2LobbyBtn = document.createElement('button');
    p2LobbyBtn.id = 'comp-p2-btn-lobby';
    p2LobbyBtn.innerText = '🏠 Volver al Menú Principal';
    p2LobbyBtn.style.cssText = 'background: rgba(255,255,255,0.08); color: #fff; border: 1px solid #2a3f54; border-radius: 25px; padding: 12px 30px; font-size: 1rem; font-weight: bold; cursor: pointer; transition: 0.2s;';
    p2LobbyBtn.onclick = () => {
        if (isMultiplayer && currentRoom && isHost) {
            emitVideoSync({ action: 'return_to_main_menu' });
        }
        closeCompEndScreenAndReturn();
    };
    p2BottomRow.appendChild(p2LobbyBtn);

    phase2.appendChild(p2WinnerBanner);
    phase2.appendChild(p2Content);
    phase2.appendChild(p2BottomRow);

    overlay.appendChild(phase1);
    overlay.appendChild(phase2);
    document.body.appendChild(overlay);

    // Phase 1 Video play/pause/seek listeners (Host broadcasts to guests)
    compVideo.addEventListener('play', () => {
        if (!isMultiplayer || !currentRoom || !isHost || currentCompEndPhase !== 1) return;
        emitVideoSync({ action: 'play', index: currentCompVideoIndex, time: compVideo.currentTime });
    });
    compVideo.addEventListener('pause', () => {
        if (!isMultiplayer || !currentRoom || !isHost || currentCompEndPhase !== 1) return;
        emitVideoSync({ action: 'pause', index: currentCompVideoIndex, time: compVideo.currentTime });
    });
    compVideo.addEventListener('seeked', () => {
        if (!isMultiplayer || !currentRoom || !isHost || currentCompEndPhase !== 1) return;
        emitVideoSync({ action: 'seek', index: currentCompVideoIndex, time: compVideo.currentTime });
    });

    return overlay;
}

function switchCompEndPhase(phaseNum) {
    currentCompEndPhase = phaseNum;
    const overlay = getOrCreateCompEndScreen();
    overlay.style.display = 'flex';

    const phase1 = document.getElementById('comp-phase-1');
    const phase2 = document.getElementById('comp-phase-2');

    if (phaseNum === 1) {
        if (phase1) phase1.style.display = 'flex';
        if (phase2) phase2.style.display = 'none';
        renderCompPhase1();
    } else {
        if (phase1) phase1.style.display = 'none';
        if (phase2) phase2.style.display = 'flex';
        const v1 = document.getElementById('comp-video-player');
        if (v1) v1.pause();
        renderCompPhase2();
    }
}

function getPlayerVideoUrl(item) {
    if (multiplayerGameMode === 'cooperativo') {
        if (coopFinalVideoUrl && coopFinalVideoUrl !== '__error__') return coopFinalVideoUrl;
        if (item && item.video_url && item.video_url !== '__error__') return item.video_url;
        if (currentRoom) {
            return `/uploads/room_${currentRoom}/final_video.mp4`;
        }
        return null;
    }
    if (!item) return null;
    const pName = item.player_name || item.name;
    const pSid = item.player_sid || item.sid;
    if (item.video_url && item.video_url !== '__error__') return item.video_url;
    if (pName && pendingVideos[pName] && pendingVideos[pName] !== '__error__') return pendingVideos[pName];
    if (pSid && pendingVideos[pSid] && pendingVideos[pSid] !== '__error__') return pendingVideos[pSid];
    if (pName && currentRoom) {
        const slug = pName.replace(/[^a-zA-Z0-9_\-]/g, '_');
        return `/uploads/room_${currentRoom}_player_${slug}/final_${slug}.mp4`;
    }
    return null;
}

function renderCompPhase1() {
    if (!competitiveVideos || competitiveVideos.length === 0) return;
    if (currentCompVideoIndex < 0 || currentCompVideoIndex >= competitiveVideos.length) {
        currentCompVideoIndex = 0;
    }

    const isCoop = (multiplayerGameMode === 'cooperativo');
    const currentItem = competitiveVideos[currentCompVideoIndex] || {};
    const isSyncedSession = isMultiplayer && currentRoom;
    const amGuest = isSyncedSession && !isHost;

    // Header title
    const header = document.getElementById('comp-p1-header');
    if (header) {
        if (isCoop) {
            header.innerText = `Escena Grupal: ${currentPack || 'Cooperativo'}`;
        } else {
            header.innerText = currentItem.player_name || 'Escena';
        }
    }

    // Sync badge
    const badge = document.getElementById('comp-p1-sync-badge');
    if (badge) {
        if (amGuest) {
            badge.innerText = '📺 El host controla la reproducción';
            badge.style.background = 'rgba(0,229,255,0.1)';
            badge.style.color = '#00e5ff';
        } else if (isSyncedSession) {
            badge.innerText = '👑 HOST — Tú controlas la reproducción';
            badge.style.background = 'rgba(255,64,129,0.2)';
            badge.style.color = '#ff4081';
        } else {
            badge.innerText = '';
        }
    }

    // Next button for host
    const nextBtn = document.getElementById('comp-p1-btn-next');
    if (nextBtn) {
        nextBtn.style.display = isHostController() ? 'block' : 'none';
    }

    // Video Player & Guest Lock
    const compVideo = document.getElementById('comp-video-player');
    const guestOverlay = document.getElementById('comp-guest-overlay');

    if (amGuest) {
        if (compVideo) compVideo.controls = false;
        if (guestOverlay) guestOverlay.style.display = 'block';
    } else {
        if (compVideo) compVideo.controls = true;
        if (guestOverlay) guestOverlay.style.display = 'none';
    }

    // Load Video URL (In Coop mode, video is single coopFinalVideoUrl)
    const realUrl = getPlayerVideoUrl(currentItem);
    let missingCard = document.getElementById('comp-video-missing-card');
    const p1VideoWrap = compVideo ? compVideo.parentNode : null;

    if (!realUrl || realUrl === '__error__') {
        if (compVideo) {
            compVideo.pause();
            compVideo.style.display = 'none';
        }
        if (!missingCard && p1VideoWrap) {
            missingCard = document.createElement('div');
            missingCard.id = 'comp-video-missing-card';
            missingCard.style.cssText = `
                display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
                width: 100%; height: 280px; background: rgba(20,12,18,0.92); border: 2px dashed #ff5252;
                border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 0 20px rgba(255,82,82,0.2);
            `;
            missingCard.innerHTML = `
                <div style="font-size: 2.8rem;">⚠️</div>
                <div style="color: #ff5252; font-weight: bold; font-size: 1.2rem;">Vídeo No Disponible</div>
                <div style="color: #b0bec5; font-size: 0.9rem; max-width: 420px; line-height: 1.4;">
                    No se pudo cargar el vídeo final de la escena.
                </div>
            `;
            p1VideoWrap.appendChild(missingCard);
        } else if (missingCard) {
            missingCard.style.display = 'flex';
        }
    } else {
        if (missingCard) missingCard.style.display = 'none';
        if (compVideo) {
            compVideo.style.display = 'block';
            const targetAbsUrl = new URL(realUrl, window.location.origin).href;
            if (compVideo.src !== targetAbsUrl) {
                compVideo.pause();
                compVideo.src = realUrl;
                compVideo.load();
            }
        }
    }

    // Render Bottom Selector Bar (Drawing 1 bottom bar)
    const bottomBar = document.getElementById('comp-p1-bottom-bar');
    if (bottomBar) {
        bottomBar.innerHTML = '';
        if (!competitiveVideos || competitiveVideos.length === 0) {
            bottomBar.style.display = 'none';
        } else {
            bottomBar.style.display = 'flex';
            competitiveVideos.forEach((v, idx) => {
            const isSelected = (idx === currentCompVideoIndex);
            const isSelf = (v.player_name === myName || v.player_sid === socket.id);

            const card = document.createElement('div');
            card.style.cssText = `
                display: flex; flex-direction: column; align-items: center; gap: 4px;
                padding: 8px 14px; border-radius: 12px;
                background: ${isSelected && !isCoop ? 'rgba(0,229,255,0.15)' : 'rgba(255,255,255,0.04)'};
                border: 2px solid ${isSelected && !isCoop ? 'var(--cyan)' : 'rgba(255,255,255,0.1)'};
                cursor: ${isHostController() && !isCoop ? 'pointer' : 'default'}; transition: 0.2s;
            `;

            if (isHostController() && !isCoop) {
                card.onclick = () => selectCompPhase1Player(idx);
            }

            const avatar = document.createElement('div');
            avatar.style.cssText = `
                width: 44px; height: 44px; border-radius: 50%;
                background: linear-gradient(135deg, var(--cyan), var(--magenta));
                display: flex; align-items: center; justify-content: center;
                font-weight: bold; font-size: 1.1rem; color: #000;
            `;
            avatar.innerText = (v.player_name || '?').substring(0, 2).toUpperCase();

            const nameSpan = document.createElement('span');
            nameSpan.style.cssText = `color: ${isSelected && !isCoop ? 'var(--cyan)' : '#fff'}; font-size: 0.85rem; font-weight: bold; text-align: center;`;
            const charText = v.character ? ` (${v.character})` : '';
            nameSpan.innerText = `${v.player_name}${charText}`;

            card.appendChild(avatar);
            card.appendChild(nameSpan);

            // Voting Button (if scoring mode is 'voting' or 'votos')
            if (multiplayerScoringMode === 'voting' || multiplayerScoringMode === 'votos') {
                const voteBtn = document.createElement('button');
                voteBtn.className = 'btn-pill';
                voteBtn.style.cssText = 'padding: 4px 12px; font-size: 0.8rem; font-weight: bold; margin-top: 4px; border: none; transition: 0.2s;';
                const pName = v.player_name;
                const isSelf = (pName === myName || v.player_sid === socket.id);

                if (isSelf) {
                    voteBtn.innerText = 'Tú';
                    voteBtn.disabled = true;
                    voteBtn.style.background = 'rgba(255,255,255,0.1)';
                    voteBtn.style.color = '#777';
                } else if (userVotedSid === pName || userVotedSid === v.player_sid) {
                    voteBtn.innerText = '✓ Votado';
                    voteBtn.style.background = '#00e676';
                    voteBtn.style.color = '#000';
                } else {
                    voteBtn.innerText = 'VOTAR 🗳️';
                    voteBtn.style.background = 'var(--magenta)';
                    voteBtn.style.color = '#fff';
                    voteBtn.style.cursor = 'pointer';
                    voteBtn.onclick = (e) => {
                        e.stopPropagation();
                        userVotedSid = pName;
                        socket.emit('submit_vote', { room: currentRoom, voter: myName, target: pName });
                        voteBtn.innerText = '✓ Votado';
                        voteBtn.style.background = '#00e676';
                        voteBtn.style.color = '#000';
                    };
                }
                card.appendChild(voteBtn);
            }

            bottomBar.appendChild(card);
        });
        }
    }
}

function selectCompPhase1Player(index) {
    if (index < 0 || index >= competitiveVideos.length) return;
    currentCompVideoIndex = index;
    if (isHostController()) {
        emitVideoSync({ action: 'select', index: index });
    }
    renderCompPhase1();
}

function renderCompPhase2() {
    if (!competitiveVideos || competitiveVideos.length === 0) return;

    const isCoop = (multiplayerGameMode === 'cooperativo');
    const isVotingMode = (multiplayerScoringMode === 'voting' || multiplayerScoringMode === 'votos');

    // Find winner (highest votes or highest AI score)
    const sorted = [...competitiveVideos].sort((a, b) => {
        const valA = isVotingMode ? (a.votes !== undefined ? a.votes : (a.score || 0)) : (a.score || 0);
        const valB = isVotingMode ? (b.votes !== undefined ? b.votes : (b.score || 0)) : (b.score || 0);
        return valB - valA;
    });
    const winner = sorted[0];

    const winnerBanner = document.getElementById('comp-p2-winner-banner');
    if (winnerBanner && winner) {
        if (isCoop) {
            winnerBanner.innerText = `🏆 ¡${winner.player_name} es el MVP de la escena!`;
        } else {
            winnerBanner.innerText = `🏆 ¡${winner.player_name} ha ganado!`;
        }
    }

    // Left Leaderboard list
    const leaderboard = document.getElementById('comp-p2-leaderboard');
    if (leaderboard) {
        leaderboard.innerHTML = '';
        sorted.forEach((item, rankIdx) => {
            const row = document.createElement('div');
            const isWinner = rankIdx === 0;
            row.style.cssText = `
                display: flex; align-items: center; justify-content: space-between;
                padding: 10px 14px; border-radius: 10px;
                background: ${isWinner ? 'rgba(0,230,118,0.12)' : 'rgba(255,255,255,0.04)'};
                border: 1px solid ${isWinner ? '#00e676' : 'rgba(255,255,255,0.1)'};
            `;

            const rankEmoji = rankIdx === 0 ? '🥇' : rankIdx === 1 ? '🥈' : rankIdx === 2 ? '🥉' : `#${rankIdx + 1}`;

            const leftInfo = document.createElement('div');
            leftInfo.style.cssText = 'display: flex; align-items: center; gap: 8px;';

            let scoreDisplay = '';
            if (isVotingMode) {
                const votesCount = item.votes !== undefined ? item.votes : (item.score || 0);
                const aiScore = item.rawScore || item.score || 0;
                scoreDisplay = `🗳️ ${votesCount} Voto${votesCount == 1 ? '' : 's'} (${aiScore} pts IA)`;
            } else {
                scoreDisplay = `⭐ ${item.score || 0} Puntos IA`;
            }

            const charSub = item.character ? `<span style="color: #aaa; font-size: 0.78rem;"> (${escapeHtml(item.character)})</span>` : '';
            leftInfo.innerHTML = `
                <span style="font-size: 1.2rem;">${rankEmoji}</span>
                <div>
                    <div style="color: #fff; font-weight: bold; font-size: 0.9rem;">${escapeHtml(item.player_name)}${charSub}</div>
                    <div style="color: ${isWinner ? '#00e676' : '#00e5ff'}; font-size: 0.78rem; font-weight: bold;">${scoreDisplay}</div>
                </div>
            `;

            const playBtn = document.createElement('button');
            playBtn.className = 'btn-pill';
            playBtn.innerText = '▶ Ver';
            playBtn.style.cssText = 'padding: 4px 12px; font-size: 0.8rem; background: var(--cyan); color: #000; font-weight: bold;';
            playBtn.onclick = () => loadPhase2FreeVideo(item);

            row.appendChild(leftInfo);
            row.appendChild(playBtn);
            leaderboard.appendChild(row);
        });
    }

    // Auto-select winner's video initially in Phase 2
    if (winner) {
        loadPhase2FreeVideo(winner);
    }
}

function loadPhase2FreeVideo(item) {
    const label = document.getElementById('comp-p2-video-label');
    const player = document.getElementById('comp-p2-video-player');
    const dlBtn = document.getElementById('comp-p2-btn-download');

    if (label) {
        if (multiplayerGameMode === 'cooperativo') {
            label.innerText = item.character ? `Escena Grupal — Doblado por ${item.player_name} (${item.character})` : `Escena Grupal — Doblado por ${item.player_name}`;
        } else {
            label.innerText = `Vídeo de ${item.player_name}`;
        }
    }

    const realUrl = getPlayerVideoUrl(item);
    let missingCard = document.getElementById('comp-p2-missing-card');

    if (!realUrl || realUrl === '__error__') {
        if (player) {
            player.pause();
            player.style.display = 'none';
        }
        if (!missingCard && player && player.parentNode) {
            missingCard = document.createElement('div');
            missingCard.id = 'comp-p2-missing-card';
            missingCard.style.cssText = `
                display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
                width: 100%; height: 200px; background: rgba(20,12,18,0.9); border: 2px dashed #ff5252;
                border-radius: 12px; padding: 15px; text-align: center;
            `;
            missingCard.innerHTML = `
                <div style="font-size: 2.2rem;">⚠️</div>
                <div style="color: #ff5252; font-weight: bold; font-size: 1rem;">Sin Vídeo Grabado</div>
                <div style="color: #888; font-size: 0.82rem;">Este jugador no pudo generar su vídeo.</div>
            `;
            player.parentNode.appendChild(missingCard);
        } else if (missingCard) {
            missingCard.style.display = 'flex';
        }
        if (dlBtn) {
            dlBtn.disabled = true;
            dlBtn.style.opacity = '0.5';
            dlBtn.style.cursor = 'not-allowed';
        }
    } else {
        if (missingCard) missingCard.style.display = 'none';
        if (player) {
            player.style.display = 'block';
            const targetAbsUrl = new URL(realUrl, window.location.origin).href;
            if (player.src !== targetAbsUrl) {
                player.pause();
                player.src = realUrl;
                player.load();
                player.play().catch(() => {});
            }
        }
        if (dlBtn) {
            dlBtn.disabled = false;
            dlBtn.style.opacity = '1';
            dlBtn.style.cursor = 'pointer';
            dlBtn.onclick = () => {
                const a = document.createElement('a');
                a.href = realUrl;
                a.download = `GrindTheClip_${item.player_name}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            };
        }
    }
}

function closeCompEndScreenAndReturn() {
    console.log('[CLEANUP] Returning to main menu and resetting room state...');

    // 1. Hide overlay
    const overlay = document.getElementById('comp-end-overlay');
    if (overlay) overlay.style.display = 'none';

    // 2. Hide all other modals and overlays
    ['comp-waiting-overlay', 'coop-waiting-overlay', 'coop-ranking-modal', 'coop-voting-modal', 'character-select-modal', 'room-chat-widget'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    // 3. Stop and unload all video and audio players
    const playersToStop = [
        document.getElementById('comp-video-player'),
        document.getElementById('comp-p2-video-player'),
        document.getElementById('scene-video'),
        document.getElementById('coop-final-video')
    ];
    playersToStop.forEach(vid => {
        if (vid) {
            try {
                vid.pause();
                vid.currentTime = 0;
                vid.removeAttribute('src');
                vid.load();
            } catch(e){}
        }
    });

    // 4. Hide sceneVideo if inside #view-play
    const sceneVideoEl = document.getElementById('scene-video');
    if (sceneVideoEl) sceneVideoEl.classList.add('hidden');

    // 5. Stop polling timers
    stopCompStatusPolling();
    if (typeof compWaitingSafetyTimer !== 'undefined' && compWaitingSafetyTimer) {
        clearTimeout(compWaitingSafetyTimer);
    }

    // 6. Reset multiplayer state and leave room
    competitiveVideos = [];
    pendingVideos = {};
    compWaitingPlayers = {};
    currentCompVideoIndex = -1;
    userVotedSid = null;

    if (isMultiplayer && currentRoom) {
        try { socket.emit('leave_room', { room: currentRoom }); } catch(e){}
        currentRoom = null;
        isMultiplayer = false;
        isHost = false;
    }

    // 7. Activate main menu view
    showView('view-start');
}

// Backward compatibility helper
function loadCompVideo(index) {
    selectCompPhase1Player(index);
}

function renderCompRankingPanel() {
    if (currentCompEndPhase === 2) {
        renderCompPhase2();
    }
}

// ---- Competitive status HTTP polling fallback ----
let compStatusPollTimer = null;

function stopCompStatusPolling() {
    if (compStatusPollTimer) {
        clearInterval(compStatusPollTimer);
        compStatusPollTimer = null;
    }
}

function startCompStatusPolling() {
    if (compStatusPollTimer) return;
    console.log('[COMP] Starting status poll for room:', currentRoom);
    compStatusPollTimer = setInterval(async () => {
        if (!currentRoom || !isMultiplayer) {
            stopCompStatusPolling();
            return;
        }
        try {
            const res = await fetch(`/api/competitive_status/${currentRoom}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'done' && data.scores) {
                handleCompetitiveGameOver(data);
            } else if (data.status === 'waiting') {
                if (data.submitted && Array.isArray(data.submitted)) {
                    data.submitted.forEach(subName => {
                        if (!compWaitingPlayers[subName]) {
                            compWaitingPlayers[subName] = { name: subName, sid: subName, score: 0, scored: true, videoReady: false };
                        } else {
                            compWaitingPlayers[subName].scored = true;
                            if (data.scores && data.scores[subName] !== undefined) {
                                compWaitingPlayers[subName].score = data.scores[subName];
                            }
                        }
                    });
                    renderCompWaitingList();
                }
            }
        } catch(e) {
            console.warn('[COMP] Status poll error:', e);
        }
    }, 1500);
}

function handleCompetitiveGameOver(data) {
    if (!data || !data.scores) return;
    console.log('[COMP] handleCompetitiveGameOver triggered with scores:', data.scores);
    window._lastCompGameOverData = data;
    stopCompStatusPolling();
    stopAfkChecker();

    currentCompVideoIndex = 0;
    compTotalPlayers = data.scores.length;

    compWaitingPlayers = {};
    data.scores.forEach(r => {
        const pName = r.name || r.player_name;
        const pSid = r.sid || pName;
        const url = pendingVideos[pSid] || pendingVideos[pName];
        compWaitingPlayers[pName] = {
            name: pName,
            sid: pSid,
            score: r.score,
            scored: true,
            videoReady: !!url,
            videoError: url === '__error__'
        };
    });

    competitiveVideos = data.scores.map(r => {
        const pName = r.name || r.player_name;
        const pSid = r.sid || pName;
        const url = pendingVideos[pSid] || pendingVideos[pName] || null;
        return {
            player_name: pName,
            player_sid: pSid,
            score: r.score,
            video_url: url,
            hasError: url === '__error__'
        };
    });

    if (compWaitingSafetyTimer) clearTimeout(compWaitingSafetyTimer);

    const waitOverlay = document.getElementById('comp-waiting-overlay');
    if (waitOverlay) waitOverlay.style.display = 'none';

    switchCompEndPhase(1);
}

// ---- Socket Handlers ----

let compWaitingSafetyTimer = null;

socket.on('competitive_game_over', (data) => {
    handleCompetitiveGameOver(data);
});

socket.on('comp_waiting_update', (data) => {
    if (!compWaitingPlayers) compWaitingPlayers = {};
    const pName = data.player_name;
    if (pName) {
        if (!compWaitingPlayers[pName]) {
            compWaitingPlayers[pName] = { name: pName, sid: data.player_sid || pName, score: 0, scored: false, videoReady: false };
        }
        compWaitingPlayers[pName].scored = true;
        if (data.score !== undefined) compWaitingPlayers[pName].score = data.score;
        if (data.player_sid) compWaitingPlayers[pName].sid = data.player_sid;
    }
    
    if (data.submitted_players && Array.isArray(data.submitted_players)) {
        data.submitted_players.forEach(subName => {
            if (!compWaitingPlayers[subName]) {
                compWaitingPlayers[subName] = { name: subName, sid: subName, score: 0, scored: true, videoReady: false };
            } else {
                compWaitingPlayers[subName].scored = true;
            }
        });
    }
    
    renderCompWaitingList();
});

socket.on('player_video_ready', (data) => {
    console.log('[COMP] player_video_ready received:', data);
    const finalUrl = data.video_url || '__error__';
    const pName = data.player_name;
    const pSid = data.player_sid;

    if (pSid) pendingVideos[pSid] = finalUrl;
    if (pName) pendingVideos[pName] = finalUrl;

    if (pName) {
        if (!compWaitingPlayers[pName]) {
            compWaitingPlayers[pName] = { name: pName, sid: pSid || pName, score: 0, scored: true, videoReady: false };
        }
        compWaitingPlayers[pName].scored = true;
        compWaitingPlayers[pName].videoReady = finalUrl !== '__error__';
        compWaitingPlayers[pName].videoError = finalUrl === '__error__';
    }

    if (competitiveVideos && competitiveVideos.length > 0) {
        const index = competitiveVideos.findIndex(p => p.player_name === pName || p.player_sid === pSid);
        if (index !== -1) {
            competitiveVideos[index].video_url = finalUrl;
            competitiveVideos[index].hasError = finalUrl === '__error__';
        }
    }

    renderCompWaitingList();

    if (typeof currentCompEndPhase !== 'undefined' && currentCompEndPhase === 1) {
        renderCompPhase1();
    }
});

// ---- Video Sync Handler ----
// Host emits host_video_sync → server rebroadcasts as video_sync to whole room.
// Host ignores its own echo. Guests apply all commands.
// NOTE: In Phase 2, all remote playback commands are IGNORED so each player has 100% independent playback!
socket.on('video_sync', (data) => {
    if (isHost || currentCompEndPhase === 2) return; // Host ignores echo, and Phase 2 is 100% local free exploration!

    const compVideo = document.getElementById('comp-video-player');
    const action = data.action;

    // ---- COMPETITIVE SYNC ----
    if (action === 'select') {
        if (!competitiveVideos || competitiveVideos.length === 0) return;
        const index = data.index;
        if (index < 0 || index >= competitiveVideos.length) return;
        currentCompVideoIndex = index;
        if (currentCompEndPhase === 1) {
            renderCompPhase1();
        }

    } else if (action === 'play') {
        if (!compVideo || currentCompEndPhase !== 1) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;
        compVideo.play().catch(() => {});

    } else if (action === 'pause') {
        if (!compVideo || currentCompEndPhase !== 1) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;
        compVideo.pause();

    } else if (action === 'seek') {
        if (!compVideo || currentCompEndPhase !== 1) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;

    } else if (action === 'goto_phase2') {
        switchCompEndPhase(2);

    } else if (action === 'return_to_lobby' || action === 'return_to_main_menu') {
        closeCompEndScreenAndReturn();

    // ---- COOP SYNC ----
    } else if (action === 'coop_play') {
        if (!compVideo) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;
        compVideo.play().catch(() => {});

    } else if (action === 'coop_pause') {
        if (!compVideo) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;
        compVideo.pause();

    } else if (action === 'coop_seek') {
        if (!compVideo) return;
        if (data.time !== undefined) compVideo.currentTime = data.time;
    }
});

// Dynamic host transfer handler
socket.on('host_changed', (data) => {
    console.log(`[HOST CHANGED] New host assigned: ${data.host_name}`);
    if (myName === data.host_name || (socket && socket.id === data.host_sid)) {
        isHost = true;
    } else {
        isHost = false;
    }
    if (competitiveVideos && competitiveVideos.length > 0 && currentCompVideoIndex >= 0) {
        loadCompVideo(currentCompVideoIndex);
    }
});

// Voting completed handler (for both competitive and coop modes)
socket.on('voting_completed', (data) => {
    console.log('[VOTING COMPLETED]', data);
    isVotingCompleted = true;

    const coopVoteModal = document.getElementById('coop-voting-modal');
    if (coopVoteModal) coopVoteModal.style.display = 'none';

    if (multiplayerGameMode === 'cooperativo' || data.mode === 'cooperativo') {
        window._lastCoopRanking = data.ranking;
        handleCoopGameOver({ video_url: coopFinalVideoUrl, ranking: data.ranking, isVotingFinished: true });
    } else {
        competitiveVideos = data.scores || data.ranking;
        currentCompVideoIndex = 0;
        renderCompRankingPanel();
    }
});

// Keyboard shortcut for deleting selected timeline line blocks in Scene Editor
window.addEventListener('keydown', (e) => {
    if (typeof currentViewId !== 'undefined' && (currentViewId === 'view-editor' || currentViewId === 'view-creator-editor')) {
        if ((e.key === 'Delete' || e.key === 'Backspace') && selectedLineId) {
            const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
            if (activeTag !== 'input' && activeTag !== 'textarea' && activeTag !== 'select') {
                e.preventDefault();
                deleteLineById(selectedLineId);
            }
        }
    }
});

// ===== INICIO: Restaurar sesión de usuario =====
checkAuthSession();

// ==========================================
// FLOATING MULTIPLAYER TEXT CHAT WIDGET LOGIC
// ==========================================
let isChatMinimized = false;
let chatUnreadCount = 0;

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function initRoomChat() {
    const header = document.getElementById('room-chat-header');
    const body = document.getElementById('room-chat-body');
    const footer = document.getElementById('room-chat-footer');
    const toggleBtn = document.getElementById('btn-toggle-chat');
    const input = document.getElementById('room-chat-input');
    const sendBtn = document.getElementById('btn-send-chat');

    if (!header || !input || !sendBtn) return;

    header.onclick = () => {
        isChatMinimized = !isChatMinimized;
        if (isChatMinimized) {
            body.style.display = 'none';
            footer.style.display = 'none';
            toggleBtn.innerText = '▲';
        } else {
            body.style.display = 'flex';
            footer.style.display = 'flex';
            toggleBtn.innerText = '▼';
            chatUnreadCount = 0;
            updateChatUnreadBadge();
        }
    };

    const doSend = () => {
        const msg = input.value.trim();
        if (!msg || !currentRoom) return;
        socket.emit('send_chat_message', { room: currentRoom, message: msg });
        input.value = '';
    };

    sendBtn.onclick = (e) => {
        if (e) e.preventDefault();
        doSend();
    };
    input.onkeydown = (e) => {
        e.stopPropagation();
        if (e.key === 'Enter') {
            e.preventDefault();
            doSend();
        }
    };
}

function showRoomChatWidget() {
    const widget = document.getElementById('room-chat-widget');
    if (widget && isMultiplayer && currentRoom) {
        widget.style.display = 'flex';
    }
}

function hideRoomChatWidget() {
    const widget = document.getElementById('room-chat-widget');
    if (widget) {
        widget.style.display = 'none';
        const body = document.getElementById('room-chat-body');
        if (body) body.innerHTML = '<div style="color: #666; font-style: italic; text-align: center; margin-top: 20px;">¡Comienza a chatear con los jugadores de la sala!</div>';
    }
    chatUnreadCount = 0;
    updateChatUnreadBadge();
}

function updateChatUnreadBadge() {
    const badge = document.getElementById('room-chat-unread-badge');
    if (badge) {
        if (chatUnreadCount > 0 && isChatMinimized) {
            badge.style.display = 'inline-block';
            badge.innerText = chatUnreadCount;
        } else {
            badge.style.display = 'none';
        }
    }
}

function playChatSound() {
    try {
        if (!audioContext) return;
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, audioContext.currentTime);
        osc.frequency.exponentialRampToValueAtTime(400, audioContext.currentTime + 0.12);
        gain.gain.setValueAtTime(0.08, audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.12);
        osc.connect(gain);
        gain.connect(audioContext.destination);
        osc.start();
        osc.stop(audioContext.currentTime + 0.12);
    } catch(e){}
}

socket.on('chat_message_received', (data) => {
    const body = document.getElementById('room-chat-body');
    if (!body) return;

    if (body.querySelector('div[style*="font-style: italic"]')) {
        body.innerHTML = '';
    }

    const isSelf = data.sid === (socket ? socket.id : null);
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `background: rgba(255,255,255,0.05); padding: 6px 10px; border-radius: 8px; word-break: break-word; border-left: 3px solid ${isSelf ? 'var(--magenta)' : 'var(--cyan)'};`;

    msgDiv.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom: 2px;">
            <strong style="color: ${isSelf ? 'var(--magenta)' : 'var(--cyan)'}; font-size: 0.8rem;">${escapeHtml(data.sender)}</strong>
            <span style="color: #666; font-size: 0.72rem;">${data.time || ''}</span>
        </div>
        <div style="color: #eee; font-size: 0.82rem;">${escapeHtml(data.message)}</div>
    `;

    body.appendChild(msgDiv);
    body.scrollTop = body.scrollHeight;

    if (isChatMinimized) {
        chatUnreadCount++;
        updateChatUnreadBadge();
        playChatSound();
    }
});

window.addEventListener('DOMContentLoaded', () => {
    initRoomChat();
    
    const slider = document.getElementById('record-guide-vol-slider');
    const valSpan = document.getElementById('record-guide-vol-val');
    if (slider) {
        slider.oninput = (e) => {
            const val = e.target.value;
            if (valSpan) valSpan.innerText = `${val}%`;
            if (window.activeGuideGainNode) {
                window.activeGuideGainNode.gain.value = parseFloat(val) / 100.0;
            }
        };
    }
});
initRoomChat();

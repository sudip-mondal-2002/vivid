const form = document.getElementById('uploadForm');
const progress = document.getElementById('progress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const result = document.getElementById('result');
const originalImage = document.getElementById('originalImage');
const resultImage = document.getElementById('resultImage');
const downloadBtn = document.getElementById('downloadBtn');
const error = document.getElementById('error');
const errorText = document.getElementById('errorText');
const fileInput = document.getElementById('file');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const submitBtn = document.getElementById('submitBtn');

let taskId = null;
let simulatedPercent = 0;
let simTimer = null;
let pollRetries = 0;
const MAX_POLL_RETRIES = 120; // 2 minutes max

// Smooth animated progress - creeps forward even when backend is slow
function startSimulatedProgress(startAt, maxAt) {
    simulatedPercent = startAt;
    clearInterval(simTimer);
    simTimer = setInterval(() => {
        if (simulatedPercent < maxAt) {
            // Slow down as we approach max
            const remaining = maxAt - simulatedPercent;
            const increment = Math.max(0.2, remaining * 0.03);
            simulatedPercent = Math.min(simulatedPercent + increment, maxAt);
            progressFill.style.width = `${Math.round(simulatedPercent)}%`;
        }
    }, 500);
}

function stopSimulatedProgress() {
    clearInterval(simTimer);
}

function setProgress(percent, text) {
    stopSimulatedProgress();
    simulatedPercent = percent;
    progressFill.style.width = `${percent}%`;
    if (text) progressText.textContent = text;
}

// File input change handler
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'cr2') {
            fileInput.value = '';
            fileName.textContent = 'No file selected';
            fileSize.textContent = '.CR2 files only';
            showError('Only Canon CR2 RAW files are supported.');
            return;
        }
        error.classList.add('hidden');
        fileName.textContent = file.name;
        const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
        fileSize.textContent = `${sizeMB} MB \u2022 CR2`;
    } else {
        fileName.textContent = 'No file selected';
        fileSize.textContent = '.CR2 files only';
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const file = fileInput.files[0];
    if (!file) return;
    
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'cr2') {
        showError('Only Canon CR2 RAW files are supported.');
        return;
    }
    
    const preset = document.getElementById('preset').value;
    const format = document.getElementById('format').value;
    
    // Reset UI
    error.classList.add('hidden');
    result.classList.add('hidden');
    progress.classList.remove('hidden');
    pollRetries = 0;
    setProgress(0, 'Getting upload URL...');
    submitBtn.disabled = true;
    
    try {
        // Get pre-signed URL
        startSimulatedProgress(0, 8);
        const uploadRes = await fetch('/upload', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: file.name, preset, format})
        });
        
        if (!uploadRes.ok) {
            const errBody = await uploadRes.text();
            throw new Error(`Upload init failed: ${errBody || uploadRes.status}`);
        }
        const {task_id, upload_url} = await uploadRes.json();
        taskId = task_id;
        
        // Upload to S3 with progress simulation
        setProgress(10, 'Uploading image...');
        startSimulatedProgress(10, 25);
        
        const s3Res = await fetch(upload_url, {
            method: 'PUT',
            headers: {'Content-Type': 'application/octet-stream'},
            body: file
        });
        
        if (!s3Res.ok) throw new Error('S3 upload failed');
        
        // Start polling with simulated progress (cold start can take 10-30s)
        setProgress(25, 'Waiting for processor...');
        startSimulatedProgress(25, 90);
        setTimeout(poll, 2000); // Give Lambda a moment to trigger
        
    } catch (err) {
        showError(err.message);
    }
});

async function poll() {
    pollRetries++;
    if (pollRetries > MAX_POLL_RETRIES) {
        showError('Processing timed out. Please try again.');
        return;
    }
    
    try {
        const res = await fetch(`/status/${taskId}`);
        if (!res.ok) {
            // Status file might not exist yet during cold start
            if (pollRetries < 10) {
                progressText.textContent = 'Starting processor...';
                setTimeout(poll, 2000);
                return;
            }
            throw new Error('Status check failed');
        }
        
        const status = await res.json();
        
        // Update progress from backend (override simulation if backend is ahead)
        const backendPercent = status.percent || 0;
        if (backendPercent > simulatedPercent) {
            simulatedPercent = backendPercent;
            progressFill.style.width = `${backendPercent}%`;
        }
        
        // Show backend message
        if (status.message) {
            progressText.textContent = status.message;
        }
        
        if (status.stage === 'complete') {
            setProgress(95, 'Loading result...');
            
            const resultRes = await fetch(`/result/${taskId}`);
            if (!resultRes.ok) throw new Error('Failed to get result');
            
            const {download_url, original_url} = await resultRes.json();
            
            // Preload images before showing result
            const loadPromises = [];
            
            if (original_url) {
                loadPromises.push(new Promise((resolve) => {
                    originalImage.onload = resolve;
                    originalImage.onerror = resolve;
                    originalImage.src = original_url;
                }));
            }
            
            loadPromises.push(new Promise((resolve) => {
                resultImage.onload = resolve;
                resultImage.onerror = resolve;
                resultImage.src = download_url;
            }));
            
            // Store URL for blob download
            downloadBtn.dataset.url = download_url;
            
            await Promise.all(loadPromises);
            
            setProgress(100, 'Done!');
            
            // Short delay so user sees 100%
            setTimeout(() => {
                progress.classList.add('hidden');
                result.classList.remove('hidden');
                submitBtn.disabled = false;
                // Scroll result into view on mobile
                result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 400);
            
        } else if (status.stage === 'error') {
            throw new Error(status.message || 'Processing failed');
        } else {
            // Pending or processing - keep polling
            const delay = status.stage === 'pending' ? 2000 : 1500;
            setTimeout(poll, delay);
        }
    } catch (err) {
        showError(err.message);
    }
}

// Force download via blob fetch (cross-origin presigned URLs don't support <a download>)
downloadBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const url = downloadBtn.dataset.url;
    if (!url) return;
    
    try {
        downloadBtn.style.pointerEvents = 'none';
        downloadBtn.textContent = 'Downloading...';
        
        const res = await fetch(url);
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = blobUrl;
        const fmt = document.getElementById('format').value || 'jpg';
        a.download = `vivid-enhanced.${fmt}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
    } catch (err) {
        // Fallback: open in new tab
        window.open(url, '_blank');
    } finally {
        downloadBtn.style.pointerEvents = '';
        downloadBtn.innerHTML = '<span class="material-icons-round text-lg">download</span> Download Enhanced Image';
    }
});

function showError(msg) {
    stopSimulatedProgress();
    errorText.textContent = msg;
    error.classList.remove('hidden');
    progress.classList.add('hidden');
    submitBtn.disabled = false;
    // Scroll error into view
    error.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

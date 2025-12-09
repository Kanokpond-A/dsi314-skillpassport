lucide.createIcons();

const API_URL = "http://localhost:8000/api/v3/ucb/from-pdf";
const HISTORY_API_URL = "http://localhost:8000/api/v3/ucb/history";
const JOBS_API_URL = "http://localhost:8000/api/v3/jobs";

// --- DOM Elements ---
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const candidateListEl = document.getElementById('candidate-list');
const comparisonContainer = document.getElementById('comparison-container');
const placeholderCard = document.getElementById('placeholder-card');
const scoreValDisplay = document.getElementById('score-val');
const scoreSlider = document.getElementById('score-slider');
const searchInput = document.getElementById('search-input');
const resultCountLabel = document.getElementById('results-count-label');

// Job Context Elements
const jobSelect = document.getElementById('job-select');
const jobTitleInput = document.getElementById('job-title-input');
const jobDescInput = document.getElementById('job-desc-input');
const jobEditorArea = document.getElementById('job-editor-area');

// State Variables
let fileQueue = [];
let analyzedCandidates = []; 

// ==================================================
// 1. File Upload Logic
// ==================================================
dropArea.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    addFilesToQueue(e.target.files);
    processQueue(); 
});

dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.style.borderColor = 'var(--primary)'; dropArea.style.background = '#EFF6FF'; });
dropArea.addEventListener('dragleave', (e) => { dropArea.style.borderColor = '#E2E8F0'; dropArea.style.background = '#F8FAFC'; });
dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dropArea.style.borderColor = '#E2E8F0'; dropArea.style.background = '#F8FAFC';
    addFilesToQueue(e.dataTransfer.files);
    processQueue();
});

function addFilesToQueue(files) {
    if (!files || files.length === 0) return;
    for (let file of files) {
        if (file.type === 'application/pdf') {
            if (!fileQueue.some(f => f.name === file.name)) {
                fileQueue.push(file);
                renderCandidateListItem({ 
                    candidate_info: { name: "Analyzing...", email: file.name }, 
                    score: { final_score: 0 } 
                }, true); 
            }
        }
    }
}

// ==================================================
// 2. Batch Analysis (AI Connection)
// ==================================================
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function processQueue() {
    const jobDesc = jobDescInput.value || ""; 

    while (fileQueue.length > 0) {
        const file = fileQueue.shift();
        let success = false;
        let attempt = 0;

        while (!success && attempt < 3) {
            attempt++;
            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('job_description', jobDesc);

                const response = await fetch(API_URL, { method: 'POST', body: formData });

                if (response.ok) {
                    const result = await response.json();
                    result.filename = file.name;
                    
                    // เพิ่มเข้าตัวแปรหลัก
                    analyzedCandidates.push(result);
                    applyFilters(); 
                    
                    if (analyzedCandidates.length === 1) {
                        toggleComparison(result);
                    }
                    success = true;
                    if (fileQueue.length > 0) await delay(3000);

                } else {
                    console.warn(`Retry attempt ${attempt}...`);
                    await delay(3000); 
                }
            } catch (error) {
                console.error(error);
                if (attempt >= 3) success = true; 
                else await delay(3000);
            }
        }
    }
}

// ==================================================
// 3. Rendering Functions
// ==================================================
function renderCandidateListItem(data, isPlaceholder = false) {
    const info = data.parsed_resume?.candidate_info || data.candidate_info || {};
    const score = data.score?.final_score || 0;
    const name = info.name || (isPlaceholder ? "Analyzing..." : "Unknown Candidate");
    const subtitle = isPlaceholder ? data.candidate_info.email : (info.email || data.filename);

    let scoreClass = 'low';
    if (score >= 80) scoreClass = 'high';
    else if (score >= 50) scoreClass = 'medium';

    const item = document.createElement('div');
    item.className = `candidate-item ${isPlaceholder ? 'pulse' : ''}`;
    if (!isPlaceholder) {
        item.onclick = () => toggleComparison(data);
        if (document.getElementById(`compare-${data.db_id || data.filename}`)) {
            item.classList.add('active');
        }
    }

    const avatarLetter = name.charAt(0).toUpperCase();
    let avatarClass = '';
    if (score < 50) avatarClass = 'red';
    else if (score < 80) avatarClass = 'yellow';

    item.innerHTML = `
        <div class="c-avatar ${avatarClass}">${isPlaceholder ? '<i data-lucide="loader-2" class="spin"></i>' : avatarLetter}</div>
        <div class="c-info">
            <div class="c-name">${name}</div>
            <div class="c-role">${subtitle}</div>
        </div>
        <div class="c-score ${scoreClass}">${isPlaceholder ? '...' : Math.round(score) + '%'}</div>
    `;
    candidateListEl.appendChild(item);
}

function toggleComparison(data) {
    const cardId = `compare-${data.db_id || data.filename}`;
    const existingCard = document.getElementById(cardId);
    if (existingCard) {
        existingCard.remove();
    } else {
        renderComparisonCard(data);
    }
    applyFilters();
    checkPlaceholder();
}

function renderComparisonCard(data) {
    const resume = data.parsed_resume || {};
    const analysis = data.score?.analysis || {};
    const info = resume.candidate_info || {};
    const score = data.score?.final_score || 0;
    
    const matched = analysis.matched_criteria || [];
    const gaps = analysis.missing_gaps || [];

    const cardId = `compare-${data.db_id || data.filename}`;
    let ringClass = 'high';
    if (score < 80) ringClass = 'medium';
    if (score < 50) ringClass = 'low';

    // สร้าง URL สำหรับเปิดไฟล์ PDF
    const viewResumeUrl = `http://localhost:8000/static/resumes/${data.filename}`;

    const card = document.createElement('div');
    card.className = 'compare-card';
    card.id = cardId;
    card.style.animation = 'slideInRight 0.3s ease-out';

    card.innerHTML = `
        <div class="compare-header">
            <div class="match-ring ${ringClass}">${Math.round(score)}%</div>
            <div class="c-details">
                <h3>${info.name || 'Unknown'}</h3>
                <p>${info.phone || info.email || 'No Contact'}</p>
            </div>
            <button class="btn-icon" onclick="toggleComparison({db_id: '${data.db_id}', filename: '${data.filename}'})"><i data-lucide="x"></i></button>
        </div>
        
        <div class="compare-body">
            <div class="attr-group">
                <label>✅ Top Matched</label>
                <div class="tags">
                    ${matched.length > 0 
                        ? matched.slice(0, 5).map(m => `<span class="tag green">${m}</span>`).join('')
                        : '<span class="text-muted" style="font-size:0.8rem">No strong match</span>'}
                </div>
            </div>

            <div class="attr-group">
                <label>⚠️ Gaps</label>
                <ul class="gap-list">
                    ${gaps.length > 0
                        ? gaps.slice(0, 3).map(g => `<li>${g}</li>`).join('')
                        : '<li>No major gaps found</li>'}
                </ul>
            </div>

            <div class="info-row">
                <span>Exp</span> <strong>${analysis.years_of_experience || 0} Years</strong>
            </div>
            <div class="info-row" style="border-bottom:none; display:block; padding-top:0.5rem;">
                <span style="font-size:0.75rem; color:#64748B;">AI Summary:</span>
                <p style="font-size:0.8rem; margin-top:0.2rem; color:#334155;">"${(analysis.summary_comment || '').substring(0, 120)}..."</p>
            </div>
        </div>
        <div class="compare-footer">
            <button class="btn-full" onclick="window.open('${viewResumeUrl}', '_blank')">
                View Resume
            </button>
        </div>
    `;

    comparisonContainer.insertBefore(card, placeholderCard);
    lucide.createIcons();
}

function checkPlaceholder() {
    const cards = comparisonContainer.querySelectorAll('.compare-card');
    placeholderCard.style.display = cards.length > 0 ? 'none' : 'flex';
}

// ==================================================
// 4. Filtering & Search
// ==================================================
scoreSlider.addEventListener('input', (e) => {
    scoreValDisplay.textContent = e.target.value + '%';
    applyFilters();
});
searchInput.addEventListener('input', () => applyFilters());

function applyFilters() {
    candidateListEl.innerHTML = ''; 
    const minScore = parseInt(scoreSlider.value);
    const keyword = searchInput.value.toLowerCase();

    const filtered = analyzedCandidates.filter(c => {
        const score = c.score?.final_score || 0;
        const name = (c.parsed_resume?.candidate_info?.name || '').toLowerCase();
        return score >= minScore && name.includes(keyword);
    });

    resultCountLabel.innerHTML = `<i data-lucide="users"></i> Results (${filtered.length})`;

    filtered.forEach(c => renderCandidateListItem(c));
    fileQueue.forEach(f => renderCandidateListItem({ 
        candidate_info: { name: "Analyzing...", email: f.name }, 
        score: { final_score: 0 } 
    }, true));
    
    lucide.createIcons();
}

function resetFilters() {
    searchInput.value = '';
    scoreSlider.value = 0;
    scoreValDisplay.textContent = "0%";
    applyFilters();
}

// ==================================================
// 5. Job Context Manager
// ==================================================
function showNewJobForm() {
    jobSelect.value = "";
    jobTitleInput.value = "";
    jobDescInput.value = "";
    jobEditorArea.style.display = "block";
    jobTitleInput.focus();
}

function hideJobForm() {
    jobEditorArea.style.display = "none";
}

function loadJobDescription() {
    const selectedVal = jobSelect.value;
    if (!selectedVal) {
        jobEditorArea.style.display = "none";
        return;
    }
    const job = JSON.parse(decodeURIComponent(selectedVal));
    jobTitleInput.value = job.title;
    jobDescInput.value = job.description;
    jobEditorArea.style.display = "block";
}

async function saveJobProfile() {
    const title = jobTitleInput.value.trim();
    const description = jobDescInput.value.trim();

    if (!title || !description) {
        alert("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน"); return;
    }

    const saveBtn = document.querySelector('button[onclick="saveJobProfile()"]');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '⏳ Saving...';
    saveBtn.disabled = true;

    try {
        const res = await fetch(JOBS_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description })
        });
        
        if (res.ok) {
            alert("✅ Saved!");
            await fetchJobProfiles();
        } else {
            alert("❌ Failed: " + await res.text());
        }
    } catch (e) {
        alert("❌ Error: " + e.message);
    } finally {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
}

async function fetchJobProfiles() {
    console.log("🔄 Fetching Job Profiles...");
    try {
        const res = await fetch(JOBS_API_URL);
        if(!res.ok) return;

        const jobs = await res.json();
        jobSelect.innerHTML = '<option value="">-- Create New / Select --</option>';
        
        if (Array.isArray(jobs)) {
            jobs.forEach(job => {
                const option = document.createElement('option');
                option.value = encodeURIComponent(JSON.stringify(job));
                option.textContent = job.title;
                jobSelect.appendChild(option);
            });
        }
    } catch (e) { 
        console.error("Error fetching jobs:", e); 
    }
}

// ==================================================
// 6. History Manager (ดึงข้อมูลเก่า)
// ==================================================
async function loadCandidateHistory() {
    console.log("📚 Loading history...");
    try {
        const res = await fetch(HISTORY_API_URL);
        if (!res.ok) throw new Error("API Failed");
        
        const historyList = await res.json();
        console.log(`📚 Found ${historyList.length} records.`);

        historyList.forEach(item => {
            if (item.raw_data) {
                const candidateData = item.raw_data;
                // เติม ID และชื่อไฟล์กลับเข้าไป
                candidateData.db_id = item.db_id;
                candidateData.filename = item.filename;
                
                // กันซ้ำ
                const exists = analyzedCandidates.some(c => c.db_id === item.db_id);
                if (!exists) {
                    analyzedCandidates.push(candidateData);
                }
            }
        });
        applyFilters(); // วาดหน้าจอใหม่
    } catch (e) {
        console.error("❌ Error loading history:", e);
    }
}

// ==================================================
// 7. Initialize App
// ==================================================
window.addEventListener('DOMContentLoaded', () => {
    fetchJobProfiles();      // 1. โหลดรายชื่องาน
    loadCandidateHistory();  // 2. โหลดประวัติผู้สมัคร
});
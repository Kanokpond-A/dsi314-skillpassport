lucide.createIcons();

// --- API Endpoints ---
const API_URL = "http://localhost:8000/api/v3/ucb/from-pdf";
const HISTORY_API_URL = "http://localhost:8000/api/v3/ucb/history";
const JOBS_API_URL = "http://localhost:8000/api/v3/jobs";

// --- DOM Elements ---
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const candidateListEl = document.getElementById('candidate-list'); 
const candidateTbody = document.getElementById('candidate-tbody'); 
const scoreValDisplay = document.getElementById('score-val');
const scoreSlider = document.getElementById('score-slider');
const searchInput = document.getElementById('search-input');
const resultCountLabel = document.getElementById('results-count-label');
const poolCountLabel = document.getElementById('pool-count');

// Job Context Elements
const jobSelect = document.getElementById('job-select');
const jobTitleInput = document.getElementById('job-title-input');
const jobDescInput = document.getElementById('job-desc-input');
const jobEditorArea = document.getElementById('job-editor-area');

// State Variables
let fileQueue = [];
let analyzedCandidates = []; 
let comparisonList = []; 
let myChart = null; // ตัวแปรเก็บกราฟ

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
            const alreadyExists = analyzedCandidates.some(c => c.filename === file.name);
            const alreadyInQueue = fileQueue.some(f => f.name === file.name);
            if (alreadyExists || alreadyInQueue) {
                alert(`⚠️ ไฟล์ "${file.name}" มีอยู่ในระบบแล้ว`);
                continue;
            }
            fileQueue.push(file);
        }
    }
    applyFilters(); 
}

// ==================================================
// 2. Batch Analysis
// ==================================================
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// script.js

// ==================================================
// 2. Batch Analysis (Logic การคิวและประมวลผล)
// ==================================================

async function processQueue() {
    // 1. เช็ค JD ก่อน (ตามที่คุณเคยขอไว้)
    const jobDesc = jobDescInput.value || ""; 
    if (!jobDesc || jobDesc.trim().length === 0) {
        alert("⚠️ กรุณาเลือก Job Description (หรือสร้างใหม่) ก่อนอัปโหลด Resume ครับ!");
        fileQueue = []; // ล้างคิว
        renderSidebarItem(analyzedCandidates); // รีเฟรชหน้าจอ
        return; 
    }

    // 2. เริ่มวนลูปไฟล์ในคิว
    // เราจะไม่ใช้ while loop แบบเดิมที่ blocking แต่จะใช้ Logic แบบทีละไฟล์
    // เพื่อให้เราควบคุม UI ได้แม่นยำครับ
    
    if (fileQueue.length === 0) return; // ถ้าคิวว่างก็จบ

    // 3. สั่ง Render Sidebar เพื่อให้เห็นว่า "Analyzing..." (ไฟล์อยู่ใน fileQueue)
    renderSidebarItem(analyzedCandidates);

    // 4. ดึงไฟล์แรกออกมาทำ (แต่ยังไม่ลบออกจาก Array นะ เพื่อให้ UI ยังโชว์อยู่)
    const file = fileQueue[0]; 
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_description', jobDesc);

    try {
        console.log(`🚀 Sending ${file.name} to AI...`);
        
        const res = await fetch(API_URL, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error("Server Error");

        const data = await res.json();

        // ... (หลังจากดึง jobDesc แล้ว) ...
        const jobDesc = jobDescInput.value || "";

        // 🔥 1. ดึงชื่อตำแหน่งงาน (Job Title) จากช่อง Input
        const currentJobTitle = jobTitleInput.value || "General Candidate";

        // ... (ในส่วน FormData) ...
        const formData = new FormData();
        formData.append('file', file);
        formData.append('job_description', jobDesc);

        // 🔥 2. ส่งชื่อตำแหน่งงานไปด้วย
        formData.append('job_title', currentJobTitle);
        
        // ✅ สำเร็จ:
        // 1. เพิ่มข้อมูลลงใน Analyzed List
        // (เช็ค db_id ให้ชัวร์)
        const candidateData = data; 
        if (data.db_id) candidateData.db_id = data.db_id;
        
        analyzedCandidates.push(candidateData);
        
        // 2. ลบไฟล์ออกจากคิว (เพราะเสร็จแล้ว)
        fileQueue.shift();

        // 3. อัปเดตหน้าจอทั้งหมด
        applyFilters(); // ตัวนี้จะไปเรียก renderSidebarItem และ renderCandidateTable ให้เอง

    } catch (err) {
        console.error("❌ Error analyzing:", err);
        alert(`Failed to analyze ${file.name}`);
        
        // ❌ พลาด: ก็ลบออกจากคิวเหมือนกัน (ไม่งั้นจะค้าง)
        fileQueue.shift();
        renderSidebarItem(analyzedCandidates);
    }

    // 5. เรียกตัวเองซ้ำ (Recursion) เพื่อทำไฟล์ถัดไปในคิว
    if (fileQueue.length > 0) {
        setTimeout(processQueue, 500); // พัก 0.5 วิ แล้วทำต่อ
    }
}

// ==================================================
// ฟังก์ชัน Render Sidebar (ปรับปรุงให้โชว์สถานะโหลด)
// ==================================================
function renderSidebarItem(candidates = []) {
    const listEl = document.getElementById('candidate-list');
    const countLabel = document.getElementById('results-count-label');
    
    listEl.innerHTML = '';
    
    // 1. ส่วนแสดงไฟล์ที่ "เสร็จแล้ว" (Analyzed Candidates)
    // (แสดงแบบย้อนหลัง ล่าสุดอยู่บน)
    const reversedList = [...candidates].reverse(); 
    
    reversedList.forEach(c => {
        const info = c.parsed_resume?.candidate_info || {};
        const score = c.score?.final_score || 0;
        const scoreColor = score >= 80 ? '#16A34A' : (score >= 50 ? '#EAB308' : '#64748B');
        
        const div = document.createElement('div');
        div.className = 'candidate-item';
        div.innerHTML = `
            <div class="c-avatar small" style="width:28px; height:28px; font-size:0.8rem; background:#F1F5F9; color:#475569;">
                ${(info.name||'U').charAt(0).toUpperCase()}
            </div>
            <div class="c-info" style="flex:1;">
                <div class="c-name" style="font-size:0.85rem; font-weight:600;">${info.name || 'Unknown'}</div>
                <div style="font-size:0.7rem; color:#94A3B8;">Matched: ${Math.round(score)}%</div>
            </div>
            <div class="c-score" style="font-size:0.8rem; font-weight:700; color:${scoreColor};">
                ${Math.round(score)}%
            </div>
        `;
        div.onclick = () => toggleCompare(c.db_id, true);
        listEl.appendChild(div);
    });

    // 2. ส่วนแสดงไฟล์ที่ "กำลังประมวลผล" (Queue) 🔥 ไฮไลท์สำคัญ 🔥
    fileQueue.forEach(f => {
        const div = document.createElement('div');
        div.className = 'candidate-item pulse'; // ใช้ Class Animation ที่เราแก้ใน CSS
        div.innerHTML = `
            <div style="width:28px; height:28px; display:flex; align-items:center; justify-content:center;">
                <i data-lucide="loader-2" class="loading-spinner" style="color:#2563EB;"></i>
            </div>
            <div class="c-info" style="margin-left:8px;">
                <div style="font-size:0.85rem; color:#2563EB;">Analyzing...</div>
                <div style="font-size:0.7rem; color:#64748B;">${f.name}</div>
            </div>
        `;
        listEl.prepend(div); // เอาไว้บนสุดเสมอ
    });

    // อัปเดตตัวเลขจำนวน (รวมทั้งที่เสร็จแล้วและกำลังทำ)
    const total = candidates.length + fileQueue.length;
    if (countLabel) countLabel.innerHTML = `<i data-lucide="users"></i> Uploaded (${total})`;
    
    lucide.createIcons();
}

// ==================================================
// 3. Render Table (Bottom - Candidate Pool)
// ==================================================
function renderCandidateTable(candidates) {
    candidateTbody.innerHTML = '';
    // ... (ส่วนเช็ค candidates ว่าง เหมือนเดิม) ...
    if (!candidates.length) {
        candidateTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px; color:#94a3b8;">No candidates found.</td></tr>';
        return;
    }

    candidates.forEach(c => {
        // ... (ตัวแปร info, score, skills เหมือนเดิม) ...
        const info = c.parsed_resume.candidate_info || {};
        const score = c.score?.final_score || 0;
        const skills = c.parsed_resume.skills?.hard_skills || [];
        const isSelected = comparisonList.includes(c.db_id);
        const scoreClass = score >= 80 ? 'high' : (score >= 50 ? 'medium' : 'low');

        // 🔥 เช็คสถานะ Shortlist 🔥
        const starIcon = c.isShortlisted 
            ? `<i data-lucide="star" style="width:14px; height:14px; fill:#EAB308; color:#EAB308; margin-right:6px;"></i>` 
            : '';

        const tr = document.createElement('tr');
        if (isSelected) tr.classList.add('selected');
        if (c.isShortlisted) tr.style.background = '#F0FDF4'; // ไฮไลท์แถวสีเขียวอ่อนๆ

        tr.innerHTML = `
            <td style="text-align:center;">
                <input type="checkbox" class="checkbox-custom" ${isSelected ? 'checked' : ''} onchange="toggleCompare(${c.db_id}, this.checked)">
            </td>
            <td>
                <div style="font-weight:600; color:#0F172A; display:flex; align-items:center;">
                    ${starIcon} ${info.name || 'Unknown'}
                </div>
                <div style="font-size:0.8rem; color:#64748B;">${c.job_title}</div>
            </td>
            <td><span class="c-score ${scoreClass}">${Math.round(score)}%</span></td>
            <td>${c.score?.analysis?.years_of_experience || 0} Yrs</td>
            <td>
                <div style="display:flex; gap:4px; flex-wrap:wrap; max-width:250px;">
                    ${skills.slice(0, 3).map(s => `<span class="tag-skill">${s}</span>`).join('')}
                </div>
            </td>
            <td>
                <button class="btn-delete-item" onclick="deleteCandidate(event, ${c.db_id})"><i data-lucide="trash-2" width="16"></i></button>
            </td>
        `;
        candidateTbody.appendChild(tr);
    });
    
    if(poolCountLabel) poolCountLabel.textContent = candidates.length;
    lucide.createIcons();
}

// ==================================================
// 4. Comparison Logic (Top - Cards)
// ==================================================
function toggleCompare(dbId, isChecked) {
    if (isChecked) {
        if (comparisonList.length >= 4) {
            alert("⚠️ Compare max 4 candidates only.");
            applyFilters(); // Reset checkbox
            return;
        }
        if (!comparisonList.includes(dbId)) comparisonList.push(dbId);
    } else {
        comparisonList = comparisonList.filter(id => id !== dbId);
    }
    applyFilters(); 
}

function clearComparison() {
    comparisonList = [];
    applyFilters();
}

function renderComparisonSection() {
    const container = document.getElementById('comparison-container');
    const countLabel = document.getElementById('compare-count');
    
    // ... (ส่วนเช็ค container ว่าง เหมือนเดิม) ...
    if (!container) return;
    container.innerHTML = '';
    
    const selected = analyzedCandidates.filter(c => comparisonList.includes(c.db_id));
    if (countLabel) countLabel.textContent = selected.length;

    if (!selected.length) {
        container.innerHTML = `<div class="empty-placeholder"><i data-lucide="arrow-down-circle" size="48" style="color:#cbd5e1; margin-bottom:12px;"></i><p>Select candidates from table.</p></div>`;
        lucide.createIcons();
        return;
    }

    selected.forEach(c => {
        // ... (ดึงตัวแปร info, score, matches, gaps เหมือนเดิม) ...
        const info = c.parsed_resume.candidate_info || {};
        const score = c.score?.final_score || 0;
        const analysis = c.score?.analysis || {};
        const matches = analysis.matched_criteria || [];
        const gaps = analysis.missing_gaps || [];
        let scoreColor = score >= 80 ? '#16A34A' : (score >= 50 ? '#EAB308' : '#EF4444');

        // 🔥 ตรวจสอบสถานะ Shortlist เพื่อเตรียมสีปุ่ม 🔥
        const isShort = c.isShortlisted === true;
        const btnStyle = isShort 
            ? 'background-color:#16A34A; color:white; border-color:#16A34A;' 
            : '';
        const btnText = isShort 
            ? '<i data-lucide="check" width="14"></i> Shortlisted' 
            : '<i data-lucide="star" width="14"></i> Shortlist';
        const btnClass = isShort ? 'btn-card shortlist active' : 'btn-card shortlist';

        const card = document.createElement('div');
        card.className = 'compare-card';
        
        // ใส่ HTML (สังเกตตรงปุ่ม onclick ส่ง c.db_id ไปด้วย)
        card.innerHTML = `
            <button class="btn-close-card" onclick="toggleCompare(${c.db_id}, false)"><i data-lucide="x" width="16"></i></button>
            
            <div class="col-info">
                <div class="info-header">
                    <div class="card-avatar">${(info.name||'U').charAt(0).toUpperCase()}</div>
                    <div>
                        <h3 style="margin:0; font-size:1rem; font-weight:700;">${info.name}</h3>
                        <p style="margin:0; font-size:0.8rem; color:#64748B;">${c.job_title}</p>
                    </div>
                </div>
                <div class="info-details">
                    <div><i data-lucide="mail" width="14"></i> ${info.email || '-'}</div>
                    <div><i data-lucide="phone" width="14"></i> ${info.phone || '-'}</div>
                    <div class="badge-exp"><i data-lucide="clock" width="14"></i> ${analysis.years_of_experience || 0} Years</div>
                </div>
            </div>

            <div class="col-list">
                <div class="list-header green"><i data-lucide="check-circle-2" width="14"></i> Top Matched</div>
                <ul class="detail-list">
                    ${matches.length > 0 ? matches.slice(0, 3).map(m => `<li class="detail-item match"><i data-lucide="check" width="14"></i> <span>${m}</span></li>`).join('') : '<li style="color:#94a3b8;font-size:0.8rem">- No matches -</li>'}
                </ul>
            </div>

            <div class="col-list">
                <div class="list-header orange"><i data-lucide="alert-circle" width="14"></i> Gaps</div>
                <ul class="detail-list">
                    ${gaps.length > 0 ? gaps.slice(0, 3).map(g => `<li class="detail-item gap"><i data-lucide="alert-triangle" width="14"></i> <span>${g}</span></li>`).join('') : '<li style="color:#94a3b8;font-size:0.8rem">- No gaps -</li>'}
                </ul>
            </div>

            <div class="col-action">
                <div class="score-big" style="color:${scoreColor}">${Math.round(score)}%</div>
                <div class="btn-stack">
                    <button class="btn-card" onclick="openResumeModal('http://localhost:8000/static/resumes/${c.filename}', '${info.name}')">
                        <i data-lucide="file-text" width="14"></i> Resume
                    </button>
                    <button class="btn-card primary" onclick="openAnalysisModal(${c.db_id})">
                        <i data-lucide="bar-chart-2" width="14"></i> Analysis
                    </button>
                    
                    <button class="${btnClass}" style="${btnStyle}" onclick="toggleShortlist(this, ${c.db_id})">
                        ${btnText}
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
    lucide.createIcons();
}

// ==========================================
// ⭐ ฟังก์ชันจัดการ Shortlist (Logic ใหม่)
// ==========================================
function toggleShortlist(btn, dbId) {
    // 1. หาตัว Candidate ใน Memory
    const candidate = analyzedCandidates.find(c => c.db_id === dbId);
    if (!candidate) return;

    // 2. สลับสถานะ (Toggle Boolean)
    // ถ้ายังไม่มีค่า isShortlisted ให้เริ่มเป็น false
    candidate.isShortlisted = !candidate.isShortlisted;

    // 3. อัปเดตปุ่มทันที (เพื่อความลื่นไหล)
    updateShortlistButtonVisual(btn, candidate.isShortlisted);

    // 4. อัปเดตตารางด้านล่าง (ให้มีดาวขึ้น)
    renderCandidateTable(analyzedCandidates.filter(c => {
        // กรองตาม Logic Filter เดิม (เพื่อให้หน้าจอไม่กระตุก)
        const minScore = parseInt(scoreSlider.value);
        const keyword = searchInput.value.toLowerCase();
        const score = c.score?.final_score || 0;
        const name = (c.parsed_resume?.candidate_info?.name || '').toLowerCase();
        return score >= minScore && name.includes(keyword);
    }));

    // TODO: ถ้ามี API Backend ให้ยิง Save ตรงนี้
    // saveShortlistStatus(dbId, candidate.isShortlisted); 
}

// ฟังก์ชันช่วยปรับสีปุ่ม (แยกออกมาให้เรียกใช้ซ้ำได้)
function updateShortlistButtonVisual(btn, isActive) {
    if (isActive) {
        btn.classList.add('active'); // เพิ่ม Class ให้ CSS จัดการ
        btn.innerHTML = '<i data-lucide="check" width="14"></i> Shortlisted';
        btn.style.backgroundColor = '#16A34A';
        btn.style.color = 'white';
        btn.style.borderColor = '#16A34A';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '<i data-lucide="star" width="14"></i> Shortlist';
        btn.style.backgroundColor = 'white';
        btn.style.color = '#334155';
        btn.style.borderColor = '#E2E8F0';
    }
    lucide.createIcons();
}

// ==================================================
// 5. Analysis Modal & Animated Chart (Updated)
// ==================================================
function openAnalysisModal(dbId) {
    const candidate = analyzedCandidates.find(c => c.db_id === dbId);
    if (!candidate) return;

    const modal = document.getElementById('analysis-modal');
    const info = candidate.parsed_resume.candidate_info || {};
    
    // 1. เติมข้อมูล Text
    document.getElementById('ana-name').textContent = info.name || "Unknown Candidate";
    document.getElementById('ana-role').textContent = candidate.job_title || "Applied Position";
    document.getElementById('ana-avatar').textContent = (info.name || 'U').charAt(0).toUpperCase();
    
    const analysis = candidate.score.analysis || {};
    document.getElementById('ana-summary').textContent = analysis.summary_comment || "No summary available.";

    // 2. แสดง Modal
    modal.classList.add('show');

    // 3. เตรียม Canvas (Reset เพื่อป้องกันกราฟซ้อน)
    const chartBox = document.querySelector('.ana-chart-box');
    chartBox.innerHTML = '<canvas id="skillsChart"></canvas>';
    
    // 4. ดึงข้อมูลคะแนน (ตรวจสอบค่า null/undefined ให้เป็น 50)
    const caps = candidate.score.capabilities?.breakdown || {};
    const pots = candidate.score.potential?.breakdown || {};

    const dataValues = [
        caps.skill_match || 50,       // Skills
        caps.duration_score || 50,    // Experience
        caps.project_scale || 50,     // Scale
        caps.standards || 50,         // Standards
        pots.leadership || 50,        // Leadership (ตอนนี้ Backend ส่งมาแล้ว)
        pots.career_growth || 50      // Growth
    ];

    // 5. วาดกราฟ
    const ctx = document.getElementById('skillsChart').getContext('2d');

    // สร้าง Gradient สีฟ้าสวยๆ
    const gradient = ctx.createRadialGradient(150, 150, 0, 150, 150, 150);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.6)');   // สีฟ้าเข้มตรงกลาง
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.05)');  // จางออกขอบนอก

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Skills', 'Experience', 'Scale', 'Standards', 'Leadership', 'Growth'],
            datasets: [{
                label: 'Competency',
                data: dataValues,
                backgroundColor: gradient,
                borderColor: '#2563EB',
                borderWidth: 2,
                pointBackgroundColor: '#FFFFFF',
                pointBorderColor: '#2563EB',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.4 // เส้นโค้งมน
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1500,
                easing: 'easeOutElastic' // อนิเมชันเด้งดึ๋ง
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(226, 232, 240, 0.8)' },
                    grid: { 
                        color: 'rgba(226, 232, 240, 0.4)', 
                        circular: true // ✅ เส้นตารางวงกลม
                    },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    ticks: { display: false }, // ซ่อนตัวเลขแกน
                    pointLabels: { 
                        font: { size: 12, weight: '700', family: "'Inter', sans-serif" }, 
                        color: '#475569' 
                    }
                }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function closeAnalysisModal() {
    document.getElementById('analysis-modal').classList.remove('show');
}

// ==================================================
// 6. Filtering & Init
// ==================================================
// --- DOM Elements (เพิ่ม sortSelect) ---
const sortSelect = document.getElementById('sort-select'); // ✅ เพิ่มตัวนี้

// ... (EventListener ของ Slider และ Search Input เหมือนเดิม) ...

function applyFilters() {
    const minScore = parseInt(scoreSlider.value);
    const keyword = searchInput.value.toLowerCase().trim();
    const sortMode = sortSelect.value; // ✅ รับค่าโหมดการเรียง

    // 1. Filter (กรองข้อมูล)
    let filtered = analyzedCandidates.filter(c => {
        // กรองคะแนน
        const score = c.score?.final_score || 0;
        if (score < minScore) return false;

        // กรอง Keyword (ชื่อ หรือ สกิล)
        if (keyword) {
            const name = (c.parsed_resume?.candidate_info?.name || '').toLowerCase();
            const skills = (c.parsed_resume?.skills?.hard_skills || []).map(s => s.toLowerCase());
            
            // เช็คว่า Keyword ตรงกับ "ชื่อ" หรือ "สกิลตัวใดตัวหนึ่ง" หรือไม่
            const matchName = name.includes(keyword);
            const matchSkill = skills.some(s => s.includes(keyword)); // ✅ ค้นหาสกิลได้แล้ว
            
            return matchName || matchSkill;
        }

        return true;
    });

    // 2. Sort (เรียงลำดับ) - ✅ Logic ใหม่
    filtered.sort((a, b) => {
        const scoreA = a.score?.final_score || 0;
        const scoreB = b.score?.final_score || 0;
        const nameA = (a.parsed_resume?.candidate_info?.name || '').toLowerCase();
        const nameB = (b.parsed_resume?.candidate_info?.name || '').toLowerCase();
        const expA = a.score?.analysis?.years_of_experience || 0;
        const expB = b.score?.analysis?.years_of_experience || 0;

        switch (sortMode) {
            case 'score_asc': 
                return scoreA - scoreB; // คะแนนน้อยไปมาก
            case 'name_asc':
                return nameA.localeCompare(nameB); // ชื่อ ก-ฮ
            case 'name_desc':
                return nameB.localeCompare(nameA); // ชื่อ ฮ-ก
            case 'exp_desc':
                return expB - expA; // ประสบการณ์มากไปน้อย
            case 'score_desc':
            default:
                return scoreB - scoreA; // คะแนนมากไปน้อย (Default)
        }
    });

    // 3. Render
    renderSidebarItem(filtered);
    renderCandidateTable(filtered);
    
    // (Optional) ถ้าอยากให้รายการ Comparison เปลี่ยนตามด้วย ให้เรียก renderComparisonSection() 
    // แต่ปกติ Comparison มักจะ Fix ไว้ตามที่ user เลือก จึงอาจไม่ต้องเรียกตรงนี้ก็ได้
}

function resetFilters() {
    searchInput.value = '';
    scoreSlider.value = 0;
    scoreValDisplay.textContent = "0%";
    sortSelect.value = "score_desc"; // ✅ Reset การเรียงด้วย
    applyFilters();
}

// ==================================================
// 7. Job Context & Utils
// ==================================================
function hideJobForm() { jobEditorArea.style.display = "none"; }

// ฟังก์ชันสำหรับสั่งยืดกล่องข้อความ
function autoResize(element) {
    element.style.height = 'auto'; // รีเซ็ตความสูงก่อนคำนวณ
    element.style.height = element.scrollHeight + 'px'; // ตั้งความสูงเท่ากับเนื้อหา
}

// ผูก Event ว่า "ถ้ามีการพิมพ์ (input)" ให้เรียกใช้ฟังก์ชันยืดกล่อง
const jdTextArea = document.getElementById('job-desc-input');
if (jdTextArea) {
    jdTextArea.addEventListener('input', function() {
        autoResize(this);
    });
}

function showNewJobForm() { 
    jobSelect.value = ""; 
    jobTitleInput.value = ""; 
    jobDescInput.value = ""; 
    jobEditorArea.style.display = "block"; 
    jobTitleInput.focus(); 
    jobDescInput.style.height = '120px'; 
}

function loadJobDescription() {
    const selectedVal = jobSelect.value;
    if (!selectedVal) { jobEditorArea.style.display = "none"; return; }
    const job = JSON.parse(decodeURIComponent(selectedVal));
    jobTitleInput.value = job.title; 
    jobDescInput.value = job.description;

    jobEditorArea.style.display = "block";

    autoResize(jobDescInput);
}

async function saveJobProfile() {
    const title = jobTitleInput.value.trim(); const description = jobDescInput.value.trim();
    if (!title || !description) return alert("⚠️ Please fill all fields");
    try {
        const res = await fetch(JOBS_API_URL, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({title, description}) });
        if (res.ok) { alert("✅ Saved!"); await fetchJobProfiles(); }
    } catch (e) { console.error(e); }
}

async function fetchJobProfiles() {
    try {
        const res = await fetch(JOBS_API_URL);
        if(!res.ok) return;
        const jobs = await res.json();
        jobSelect.innerHTML = '<option value="">-- Create New / Select --</option>';
        jobs.forEach(job => {
            const option = document.createElement('option');
            option.value = encodeURIComponent(JSON.stringify(job));
            option.textContent = job.title;
            jobSelect.appendChild(option);
        });
    } catch (e) { console.error(e); }
}

async function loadCandidateHistory() {
    try {
        const res = await fetch(HISTORY_API_URL);
        if (!res.ok) throw new Error("API Failed");
        const historyList = await res.json();
        historyList.forEach(item => {
            if (item.raw_data) {
                const candidateData = item.raw_data;
                candidateData.db_id = item.db_id;
                candidateData.filename = item.filename;
                if (!analyzedCandidates.some(c => c.db_id === item.db_id)) analyzedCandidates.push(candidateData);
            }
        });
        applyFilters(); 
    } catch (e) { console.error("History Error:", e); }
}

async function deleteCandidate(event, dbId, filename) {
    event.stopPropagation();
    if (!confirm(`Delete "${filename}"?`)) return;
    try {
        const res = await fetch(`http://localhost:8000/api/v3/ucb/history/${dbId}`, { method: 'DELETE' });
        if (res.ok) {
            analyzedCandidates = analyzedCandidates.filter(c => c.db_id !== dbId);
            comparisonList = comparisonList.filter(id => id !== dbId);
            applyFilters();
        }
    } catch (e) { console.error(e); }
}

function openResumeModal(url, candidateName) {
    const modal = document.getElementById('resume-modal');
    modal.querySelector('#modal-title').textContent = `📄 Resume: ${candidateName}`;
    modal.querySelector('iframe').src = url;
    modal.classList.add('show');
}
function closeResumeModal() {
    const modal = document.getElementById('resume-modal');
    modal.classList.remove('show');
    setTimeout(() => { modal.querySelector('iframe').src = ""; }, 300);
}
document.addEventListener('keydown', (e) => { 
    if (e.key === "Escape") { closeResumeModal(); closeAnalysisModal(); } 
});

window.addEventListener('DOMContentLoaded', () => { fetchJobProfiles(); loadCandidateHistory(); });

function toggleSection(panelId, iconId) {
    const panel = document.getElementById(panelId);
    const icon = document.getElementById(iconId);
    
    if (!panel) return;

    if (panel.style.display === 'none' || panel.style.display === '') {
        // สั่งเปิด
        panel.style.display = 'block';
        if (icon) icon.style.transform = 'rotate(0deg)';
    } else {
        // สั่งปิด
        panel.style.display = 'none';
        if (icon) icon.style.transform = 'rotate(-90deg)';
    }
}
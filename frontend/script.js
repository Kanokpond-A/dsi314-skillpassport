// === (A) ตั้งค่า URL ของ Backend ===
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

// === ตัวแปรสำหรับเก็บ instance ของกราฟ ===
let scoreChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {

    // === 1. อ้างอิงถึง Element ต่างๆ ===
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('file-upload');
    const fileNameDisplay = document.getElementById('file-name-display');
    const convertButton = document.getElementById('convert-button');
    const clearButton = document.getElementById('clear-button');

    const loadingState = document.getElementById('loading-state');
    const resultContainer = document.getElementById('result-container');
    const errorContainer = document.getElementById('error-container');

    let selectedFile = null;
    const originalFileText = fileNameDisplay.innerHTML;
    let lastParsedData = null;

    // === เรียกใช้ hideAllStates() ตอนเริ่มต้น ===
    hideAllStates();

    // === 2. เพิ่ม Event Listeners ===
    fileUploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelection);
    clearButton.addEventListener('click', clearAll);
    convertButton.addEventListener('click', handleConversion);

    // --- Drag & Drop Listeners ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileUploadArea.addEventListener(eventName, preventDefaults, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        fileUploadArea.addEventListener(eventName, () => fileUploadArea.classList.add('highlight'), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        fileUploadArea.addEventListener(eventName, () => fileUploadArea.classList.remove('highlight'), false);
    });
    fileUploadArea.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelection();
        }
    });

    // === 3. ฟังก์ชันหลักในการทำงาน ===

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function handleFileSelection() {
        selectedFile = fileInput.files[0];
        lastParsedData = null;
        if (selectedFile) {
            fileNameDisplay.innerHTML = `<span class="file-selected">ไฟล์ที่เลือก:</span> ${selectedFile.name}`;
            convertButton.disabled = false;
        } else {
            clearAll();
        }
        resultContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        resultContainer.innerHTML = '';
        errorContainer.innerHTML = '';
    }

    function clearAll() {
        fileInput.value = '';
        selectedFile = null;
        lastParsedData = null;
        fileNameDisplay.innerHTML = originalFileText;
        convertButton.disabled = true;
        hideAllStates();
    }

    function hideAllStates() {
        loadingState.style.display = 'none';
        resultContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        resultContainer.innerHTML = '';
        errorContainer.innerHTML = '';

        if (scoreChartInstance) {
            scoreChartInstance.destroy();
            scoreChartInstance = null;
        }
    }

    // === 4. ฟังก์ชันเชื่อมต่อ Backend ===
    async function handleConversion() {
        if (!selectedFile) {
            renderError('กรุณาเลือกไฟล์ก่อนดำเนินการ');
            return;
        }

        hideAllStates();
        loadingState.style.display = 'flex';
        convertButton.disabled = true;
        clearButton.disabled = true;

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            // STEP 1: Parse
            const parseResponse = await fetch(`${API_BASE_URL}/parse-resume`, {
                method: 'POST',
                body: formData,
            });
            if (!parseResponse.ok) {
                const err = await parseResponse.json().catch(() => ({ detail: `Server error during parse (${parseResponse.status})` }));
                throw new Error(err.detail || 'ไม่สามารถประมวลผลไฟล์ Resume ได้');
            }
            const parsedData = await parseResponse.json();
            lastParsedData = parsedData;

            // STEP 2: Score
            const scoreResponse = await fetch(`${API_BASE_URL}/score-hr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(parsedData)
            });
            if (!scoreResponse.ok) {
                 const err = await scoreResponse.json().catch(() => ({ detail: `Server error during score (${scoreResponse.status})` }));
                throw new Error(err.detail || 'ไม่สามารถคำนวณคะแนนได้');
            }
            const hrData = await scoreResponse.json();

            // STEP 3: Render
            renderSuccess(hrData, selectedFile.name);

        } catch (error) {
            console.error("Conversion Error:", error);
            renderError(error.message || 'การเชื่อมต่อกับเซิร์ฟเวอร์ล้มเหลว');
            lastParsedData = null;
        } finally {
            loadingState.style.display = 'none';
            convertButton.disabled = false;
            clearButton.disabled = false;
        }
    }

    // === 5. ฟังก์ชันแสดงผลลัพธ์ (แก้ไข Summary, เรียก Chart) ===
    function renderSuccess(data, sourceFileName) {
        hideAllStates();
        resultContainer.style.display = 'block';

        let breakdownHtml = '<p class="result-text">ไม่มีข้อมูล Breakdown</p>';
        if (data.breakdown && data.breakdown.length > 0) {
            const sortedBreakdown = [...data.breakdown].sort((a, b) => (a.skill || '').localeCompare(b.skill || ''));
            breakdownHtml = sortedBreakdown.map(item => `
                <div class="result-breakdown-item">
                    <span class="item-skill">${item.skill || 'N/A'}</span>
                    <span class="item-level level-${String(item.level || 'n/a').toLowerCase().replace(' ', '-')}">${item.level || 'N/A'}</span>
                </div>
            `).join('');
        }

        let summaryHtml = '<p class="result-text">ไม่มีข้อมูลสรุปผล</p>';
        if (data.summary && typeof data.summary === 'object') {
             const matched = data.summary.matched_skills?.length > 0 ? data.summary.matched_skills.join(', ') : '-';
             const missing = data.summary.missing_skills?.length > 0 ? data.summary.missing_skills.join(', ') : '-';
             const matchPercent = data.summary.matched_percent ?? 'N/A';
             summaryHtml = `
                 <p class="result-text"><strong>Skill Match:</strong> ${matchPercent}%</p>
                 <p class="result-text"><strong>Matched Skills:</strong> ${matched}</p>
                 <p class="result-text"><strong>Missing Must-Have Skills:</strong> ${missing}</p>
             `;
        }

        const html = `
            <div class="result-card">
                <div> <h2 class="result-title">${data.name || 'ไม่พบชื่อ'}</h2> <p class="result-subtitle">สรุปข้อมูลจาก: ${sourceFileName}</p> </div>
                <div class="result-summary-grid">
                    <div class="summary-box"> <span class="summary-title">Score</span> <span class="summary-value score-${String(data.level || 'n/a').toLowerCase().replace(' ', '-')}">${data.score === 0 ? 0 : (data.score || 'N/A')}</span> </div>
                    <div class="summary-box"> <span class="summary-title">Level</span> <span class="summary-value">${data.level || 'N/A'}</span> </div>
                </div>
                <div class="result-section"> <h3 class="result-section-title">สรุปผล (Summary)</h3> ${summaryHtml} </div>
                <div class="result-section chart-section"> <h3 class="result-section-title">ส่วนประกอบคะแนน (Score Components)</h3> <div class="chart-container"> <canvas id="scoreComponentChart"></canvas> </div> <p id="chart-no-data" class="chart-error hidden">ไม่มีข้อมูลสำหรับสร้างกราฟส่วนประกอบคะแนน</p> </div>
                <div class="result-section"> <h3 class="result-section-title">Breakdown</h3> <div class="result-breakdown-list"> ${breakdownHtml} </div> </div>
                <div class="result-actions"> <button id="download-pdf-button" class="download-button"> ดาวน์โหลด UCB (PDF) </button> <p id="pdf-error-message" class="pdf-error"></p> </div>
            </div>
        `;
        resultContainer.innerHTML = html;

        // --- ผูก Event Listener ---
        const downloadBtn = document.getElementById('download-pdf-button');
        if (downloadBtn) { downloadBtn.addEventListener('click', handlePdfDownload); }
        const pdfErrorMsg = document.getElementById('pdf-error-message');
        if (pdfErrorMsg) { pdfErrorMsg.textContent = ''; }

        // --- เรียกสร้างกราฟ ---
        const scoreComponentsData = data.score_components;
        createScoreChart(scoreComponentsData); // 👈 เรียกฟังก์ชัน Radar Chart
    }


    // === (แก้ไข) ฟังก์ชันสร้างกราฟ (Radar Chart) ===
    function createScoreChart(scoreComponents) {
        const chartSection = document.querySelector('.chart-section');
        const canvas = document.getElementById('scoreComponentChart');
        const noDataMsg = document.getElementById('chart-no-data');

        if (!canvas || !chartSection || !noDataMsg) {
            console.error("Required elements for chart not found.");
            return;
        }
        const ctx = canvas.getContext('2d');

        if (scoreChartInstance) {
            scoreChartInstance.destroy();
            scoreChartInstance = null;
        }

        // --- ตรวจสอบข้อมูล ---
        if (!scoreComponents || typeof scoreComponents !== 'object' || Object.keys(scoreComponents).length < 3) { // Radar needs >= 3
            console.warn("Score components data is missing or invalid for radar chart. Chart not created.");
            chartSection.style.display = 'block';
            canvas.style.display = 'none';
            noDataMsg.classList.remove('hidden');
            return;
        } else {
             chartSection.style.display = 'block';
             canvas.style.display = 'block';
             noDataMsg.classList.add('hidden');
        }

        // --- เตรียมข้อมูล (บังคับลำดับ) ---
        const desiredOrder = ["Experience", "Skills Match", "Contact Info", "Title Match"];
        const labelMapping = {
            "Skills Match": "Skills",
            "Experience": "Experience",
            "Title Match": "Title",
            "Contact Info": "Contacts"
        };
        const labels = [];
        const dataValues = [];
        desiredOrder.forEach(key => {
            if (scoreComponents.hasOwnProperty(key)) {
                 labels.push(labelMapping[key] || key);
                 const value = scoreComponents[key] || 0;
                 dataValues.push(Math.max(0, Math.min(1, value)) * 100);
            } else {
                 // ใส่ค่า 0 ถ้าไม่มี Key (เพื่อให้ Radar ยังคงรูป)
                 labels.push(labelMapping[key] || key);
                 dataValues.push(0);
                 console.warn(`Key "${key}" not found in scoreComponents data. Assuming 0.`);
            }
        });
        // ตรวจสอบขั้นต่ำ 3 แกนอีกครั้ง (เผื่อบาง Key หายไปหมด)
         if (labels.length < 3) {
              console.warn("Not enough valid components (<3) for radar chart after ordering/filtering.");
              chartSection.style.display = 'block';
              canvas.style.display = 'none';
              noDataMsg.classList.remove('hidden');
              return;
         }

        // --- สร้างกราฟ Radar (พร้อม Style ที่ปรับปรุงแล้ว) ---
        scoreChartInstance = new Chart(ctx, {
            type: 'radar', // 👈 Type เป็น radar
            data: {
                labels: labels, // 👈 ใช้ Labels ที่จัดลำดับแล้ว
                datasets: [{
                    label: 'คะแนนองค์ประกอบ (%)',
                    data: dataValues, // 👈 ใช้ Data ที่จัดลำดับแล้ว
                    fill: true,
                    backgroundColor: 'rgba(54, 162, 235, 0.3)',
                    borderColor: 'rgb(54, 162, 235)',
                    pointBackgroundColor: 'rgb(54, 162, 235)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(54, 162, 235)',
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                elements: { line: { borderWidth: 2 } },
                scales: {
                    r: { // 👈 ตั้งค่าแกนรัศมี
                        beginAtZero: true, min: 0, max: 100,
                        ticks: {
                            stepSize: 20, backdropColor: 'rgba(255, 255, 255, 0.75)',
                            color: '#666', font: { size: 10 },
                            callback: function(value) { if (value % 20 === 0) { return value + "%"; } return ''; }
                        },
                        pointLabels: { font: { size: 12, weight: '500' }, color: '#333' },
                        angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
                        grid: { color: 'rgba(0, 0, 0, 0.08)' }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: function(context) { // Tooltip สำหรับ Radar
                        let label = context.dataset.label || ''; if (label) label += ': ';
                        // ใน Radar ค่าจะอยู่ใน context.raw หรือ context.parsed.r
                        if (context.raw !== null) label += parseFloat(context.raw).toFixed(1) + '%';
                        return label;
                    }}}
                }
            }
        });
    }
    // === สิ้นสุดฟังก์ชันสร้างกราฟ ===


    // === 6. ฟังก์ชันดาวน์โหลด PDF (เหมือนเดิม) ===
    async function handlePdfDownload() {
        if (!lastParsedData) {
            console.error('No data available for PDF generation!');
             const pdfErrorMsg = document.getElementById('pdf-error-message');
             if (pdfErrorMsg) pdfErrorMsg.textContent = 'ข้อมูลไม่พร้อมสร้าง PDF';
            return;
        }
        const downloadBtn = document.getElementById('download-pdf-button');
        const pdfErrorMsg = document.getElementById('pdf-error-message');
        if (pdfErrorMsg) pdfErrorMsg.textContent = '';
        downloadBtn.disabled = true;
        downloadBtn.textContent = 'กำลังสร้าง PDF...';
        try {
            const pdfResponse = await fetch(`${API_BASE_URL}/ucb-pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lastParsedData)
            });
            if (!pdfResponse.ok) {
                let errorDetail = `ไม่สามารถสร้างไฟล์ PDF ได้ (Status: ${pdfResponse.status})`;
                try {
                    const errorJson = await pdfResponse.json(); errorDetail = errorJson.detail || errorDetail;
                } catch (e) { try { const errorText = await pdfResponse.text(); if(errorText) errorDetail = errorText.substring(0, 100); } catch (e2) {} }
                throw new Error(errorDetail);
            }
            const blob = await pdfResponse.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none'; a.href = url;
            const fileName = (lastParsedData && lastParsedData.name) ? `${lastParsedData.name}_UCB_Report.pdf` : 'Candidate_UCB_Report.pdf';
            a.download = fileName; document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); a.remove();
        } catch (error) {
            console.error('PDF Download Error:', error);
            if (pdfErrorMsg) {
                if (error instanceof TypeError && error.message === "Failed to fetch") { pdfErrorMsg.textContent = 'เกิดข้อผิดพลาด: ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้'; }
                else { pdfErrorMsg.textContent = `เกิดข้อผิดพลาด: ${error.message}`; }
            }
        } finally {
            if(downloadBtn) { downloadBtn.disabled = false; downloadBtn.textContent = 'ดาวน์โหลด UCB (PDF)'; }
        }
    }

    // === 7. ฟังก์ชัน renderError (เหมือนเดิม) ===
    function renderError(message) {
        hideAllStates();
        errorContainer.style.display = 'block';
        errorContainer.innerHTML = `<div class="error-box"><p class="error-title">เกิดข้อผิดพลาด</p><p>${message}</p></div>`;
    }
});

window.addEventListener('scroll', () => {
  const header = document.querySelector('header');
  if (window.scrollY > 10) header.classList.add('scrolled');
  else header.classList.remove('scrolled');
});

const data = {
  // Recharts example
  stroke: '#5C6BF4',
  fill: 'rgba(92,107,244,0.2)',
  dot: { r: 4, fill: '#5C6BF4' }
};
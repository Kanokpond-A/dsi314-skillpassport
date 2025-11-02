// === (A) ตั้งค่า URL ของ Backend ===
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

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
        // ซ่อนผลลัพธ์เก่า/Error เมื่อเลือกไฟล์ใหม่
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
            console.error("Conversion Error:", error); // แสดง Error ใน Console
            renderError(error.message || 'การเชื่อมต่อกับเซิร์ฟเวอร์ล้มเหลว');
            lastParsedData = null;
        } finally {
            loadingState.style.display = 'none';
            convertButton.disabled = false;
            clearButton.disabled = false;
        }
    }

    // === 5. ฟังก์ชันแสดงผลลัพธ์ (เหมือนเดิม) ===
    function renderSuccess(data, sourceFileName) {
        hideAllStates();
        resultContainer.style.display = 'block';

        let breakdownHtml = '<p class="result-text">ไม่มีข้อมูล Breakdown</p>';
        if (data.breakdown && data.breakdown.length > 0) {
            breakdownHtml = data.breakdown.map(item => `
                <div class="result-breakdown-item">
                    <span class="item-skill">${item.skill || 'N/A'}</span>
                    <span class="item-level level-${String(item.level || 'n/a').toLowerCase().replace(' ', '-')}">${item.level || 'N/A'}</span>
                </div>
            `).join('');
        }

        const html = `
            <div class="result-card">
                <div>
                    <h2 class="result-title">${data.name || 'ไม่พบชื่อ'}</h2>
                    <p class="result-subtitle">สรุปข้อมูลจาก: ${sourceFileName}</p>
                </div>
                <div class="result-summary-grid">
                    <div class="summary-box">
                        <span class="summary-title">Score</span>
                        <span class="summary-value score-${String(data.level || 'n/a').toLowerCase().replace(' ', '-')}">${data.score === 0 ? 0 : (data.score || 'N/A')}</span>
                    </div>
                    <div class="summary-box">
                        <span class="summary-title">Level</span>
                        <span class="summary-value">${data.level || 'N/A'}</span>
                    </div>
                </div>
                <div class="result-section">
                    <h3 class="result-section-title">สรุปผล (Summary)</h3>
                    <p class="result-text">${data.summary || 'ไม่มีสรุปผล'}</p>
                </div>
                <div class="result-section">
                    <h3 class="result-section-title">Breakdown</h3>
                    <div class="result-breakdown-list">
                        ${breakdownHtml}
                    </div>
                </div>
                <div class="result-actions">
                    <button id="download-pdf-button" class="download-button">
                        ดาวน์โหลด UCB (PDF)
                    </button>
                    <!-- (เพิ่ม) พื้นที่สำหรับแสดงข้อความ Error ของการดาวน์โหลด -->
                    <p id="pdf-error-message" class="pdf-error"></p>
                </div>
            </div>
        `;
        resultContainer.innerHTML = html;

        const downloadBtn = document.getElementById('download-pdf-button');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', handlePdfDownload);
        }
         // (เพิ่ม) ซ่อนข้อความ Error เก่าๆ ของ PDF
        const pdfErrorMsg = document.getElementById('pdf-error-message');
        if (pdfErrorMsg) pdfErrorMsg.textContent = '';
    }


    // === 6. ฟังก์ชันดาวน์โหลด PDF (แก้ไข Error Handling) ===
    async function handlePdfDownload() {
        if (!lastParsedData) {
            console.error('No data available for PDF generation!');
            // (เพิ่ม) แสดงข้อผิดพลาดใกล้ๆ ปุ่ม
             const pdfErrorMsg = document.getElementById('pdf-error-message');
             if (pdfErrorMsg) pdfErrorMsg.textContent = 'ข้อมูลไม่พร้อมสร้าง PDF';
            return;
        }

        const downloadBtn = document.getElementById('download-pdf-button');
        const pdfErrorMsg = document.getElementById('pdf-error-message'); // อ้างอิงพื้นที่แสดง Error
        if (pdfErrorMsg) pdfErrorMsg.textContent = ''; // ล้าง Error เก่า

        downloadBtn.disabled = true;
        downloadBtn.textContent = 'กำลังสร้าง PDF...';

        try {
            const pdfResponse = await fetch(`${API_BASE_URL}/ucb-pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lastParsedData)
            });

            if (!pdfResponse.ok) {
                // พยายามอ่าน Error จาก Backend (ถ้ามี)
                let errorDetail = `ไม่สามารถสร้างไฟล์ PDF ได้ (Status: ${pdfResponse.status})`;
                try {
                    // ลองอ่านเป็น JSON ก่อน
                    const errorJson = await pdfResponse.json();
                    errorDetail = errorJson.detail || errorDetail;
                } catch (e) {
                    try {
                         // ถ้าไม่ใช่ JSON ลองอ่านเป็น Text
                         const errorText = await pdfResponse.text();
                         if(errorText) errorDetail = errorText.substring(0, 100); // เอาแค่ส่วนแรกๆ
                    } catch (e2) { /* ไม่สนใจ Error ตอนอ่าน Text */ }
                }
                throw new Error(errorDetail);
            }

            // ถ้าสำเร็จ ดาวน์โหลดตามปกติ
            const blob = await pdfResponse.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            const fileName = (lastParsedData && lastParsedData.name) ? `${lastParsedData.name}_UCB_Report.pdf` : 'Candidate_UCB_Report.pdf';
            a.download = fileName;
            document.body.appendChild(a);
            a.click();

            window.URL.revokeObjectURL(url);
            a.remove();

        } catch (error) {
            console.error('PDF Download Error:', error);
            // --- 👇 (แก้ไข) แสดง Error ใกล้ปุ่ม แทนการเรียก renderError ---
            if (pdfErrorMsg) {
                // ตรวจสอบว่าเป็น Network Error หรือไม่
                if (error instanceof TypeError && error.message === "Failed to fetch") {
                     pdfErrorMsg.textContent = 'เกิดข้อผิดพลาด: ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้';
                } else {
                     pdfErrorMsg.textContent = `เกิดข้อผิดพลาด: ${error.message}`;
                }
            }
            // --- 👆 สิ้นสุดการแก้ไข ---
        } finally {
            // คืนค่าปุ่มให้กดได้เสมอ ไม่ว่าจะสำเร็จหรือล้มเหลว
            if(downloadBtn) {
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'ดาวน์โหลด UCB (PDF)';
            }
        }
    }


    // === 7. ฟังก์ชัน renderError (เหมือนเดิม) ===
    function renderError(message) {
        hideAllStates();
        errorContainer.style.display = 'block';
        errorContainer.innerHTML = `
            <div class="error-box">
                <p class="error-title">เกิดข้อผิดพลาด</p>
                <p>${message}</p>
            </div>
        `;
    }
});

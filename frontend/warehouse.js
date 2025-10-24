// warehouse.js
console.log("Warehouse JavaScript loaded.");

// --- Configuration ---
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1'; // หรือ URL ของ Backend ที่ Deploy ไว้

// --- Global State ---
let allCandidatesData = []; // เก็บข้อมูลทั้งหมดที่ดึงมาจาก API
let filteredCandidatesData = []; // เก็บข้อมูลหลังจากใช้ Filter

document.addEventListener('DOMContentLoaded', () => {
    console.log("Warehouse DOM fully loaded and parsed.");

    // --- Element References ---
    const loadingIndicator = document.getElementById('loading-indicator');
    const messageContainer = document.getElementById('message-container');
    const tableBody = document.getElementById('results-table-body');
    const resultsCountEl = document.getElementById('results-count');
    const compareSelectA = document.getElementById('compare-candidate-a');
    const compareSelectB = document.getElementById('compare-candidate-b');
    const compareDetailsA = document.getElementById('compare-a-details');
    const compareDetailsB = document.getElementById('compare-b-details');

    // Filter elements
    const searchBox = document.getElementById('search-box');
    const scoreRangeMin = document.getElementById('score-range-min');
    const scoreRangeMax = document.getElementById('score-range-max');
    const scoreRangeLabel = document.getElementById('score-range-label'); // สำหรับแสดงช่วงคะแนน
    const sortBySelect = document.getElementById('sort-by');
    const refreshButton = document.getElementById('refresh-button');
    const exportCsvButton = document.getElementById('export-csv-button');


    // --- Initial Load ---
    fetchData(); // โหลดข้อมูลเมื่อหน้าเว็บโหลดเสร็จ

    // --- Event Listeners ---
    refreshButton.addEventListener('click', () => {
        // ใช้ fetchData() เพื่อบังคับโหลดใหม่จาก Server
        fetchData();
    });
    // ใช้ debounce เพื่อลดการ filter ตอนกำลังพิมพ์
    searchBox.addEventListener('input', debounce(applyFiltersAndSort, 300));
    scoreRangeMin.addEventListener('input', updateScoreRangeLabel);
    scoreRangeMax.addEventListener('input', updateScoreRangeLabel);
    // ใช้ 'change' เพื่อ filter ตอนปล่อยเมาส์ หรือเปลี่ยนค่าเสร็จ
    scoreRangeMin.addEventListener('change', applyFiltersAndSort);
    scoreRangeMax.addEventListener('change', applyFiltersAndSort);

    sortBySelect.addEventListener('change', applyFiltersAndSort);
    exportCsvButton.addEventListener('click', exportTableToCSV);
    compareSelectA.addEventListener('change', () => updateCompareView('a', compareSelectA.value));
    compareSelectB.addEventListener('change', () => updateCompareView('b', compareSelectB.value));

    // ฟังก์ชันอัปเดต Label ช่วงคะแนน
    function updateScoreRangeLabel() {
        scoreRangeLabel.textContent = `${scoreRangeMin.value}-${scoreRangeMax.value}`;
    }
    updateScoreRangeLabel(); // เรียกครั้งแรก


    // --- Core Functions ---

    // 1. ดึงข้อมูลจาก Backend
    async function fetchData() {
        showLoading(true);
        showMessage(''); // ล้างข้อความเก่า
        try {
            console.log("Fetching data from API...");
            // เรียก API GET /resumes
            const response = await fetch(`${API_BASE_URL}/resumes`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
            }
            allCandidatesData = await response.json();
            console.log("Data received:", allCandidatesData);

            if (!Array.isArray(allCandidatesData)) {
                 throw new Error("Invalid data format received from server.");
            }

            // กรอง/เรียงลำดับ และแสดงผลครั้งแรก
            applyFiltersAndSort();
            showMessage(`โหลดข้อมูล ${allCandidatesData.length} รายการสำเร็จ`, 'success');

        } catch (error) {
            console.error("Error fetching data:", error);
            showMessage(`เกิดข้อผิดพลาดในการโหลดข้อมูล: ${error.message}`, 'error');
            allCandidatesData = [];
            filteredCandidatesData = [];
            renderAll(); // แสดงผลหน้าว่างๆ
        } finally {
            showLoading(false);
        }
    }

    // 2. ใช้ Filter และ Sort ตามที่ผู้ใช้เลือก
    function applyFiltersAndSort() {
        console.log("Applying filters and sort...");
        const searchTerm = searchBox.value.toLowerCase().trim();
        // ตรวจสอบค่า Min/Max ไม่ให้ผิดพลาด
        let minScore = parseInt(scoreRangeMin.value, 10);
        let maxScore = parseInt(scoreRangeMax.value, 10);
        if (isNaN(minScore) || minScore < 0) minScore = 0;
        if (isNaN(maxScore) || maxScore > 100) maxScore = 100;
        if (minScore > maxScore) [minScore, maxScore] = [maxScore, minScore]; // สลับถ้า min > max

        const sortBy = sortBySelect.value;

        // --- Filtering ---
        filteredCandidatesData = allCandidatesData.filter(candidate => {
            // กรองด้วยคะแนน
            const score = candidate?.fit_score ?? candidate?.score ?? 0;
            if (score < minScore || score > maxScore) return false;

            // กรองด้วย Search term (เช็ค ชื่อไฟล์/candidate_id, headline, skills, gaps)
            if (searchTerm) {
                const searchableText = [
                    candidate?.candidate_id || '', // ใช้ candidate_id แทนชื่อไฟล์
                    candidate?.headline || '',
                    (candidate?.skills?.normalized || []).join(' '),
                    (candidate?.gaps || []).join(' ')
                ].join(' ').toLowerCase();
                if (!searchableText.includes(searchTerm)) {
                    return false;
                }
            }
            // สามารถเพิ่ม Filter Must-have skills ตรงนี้ได้

            return true; // ผ่านทุก Filter
        });

        // --- Sorting ---
        filteredCandidatesData.sort((a, b) => {
            const scoreA = a?.fit_score ?? a?.score ?? 0;
            const scoreB = b?.fit_score ?? b?.score ?? 0;
            const fileA = (a?.candidate_id || '').toLowerCase(); // ใช้ candidate_id
            const fileB = (b?.candidate_id || '').toLowerCase();
            const headlineA = (a?.headline || '').toLowerCase();
            const headlineB = (b?.headline || '').toLowerCase();

            switch (sortBy) {
                case 'score_asc':     return scoreA - scoreB;
                case 'file_asc':      return fileA.localeCompare(fileB);
                case 'file_desc':     return fileB.localeCompare(fileA);
                case 'headline_asc':  return headlineA.localeCompare(headlineB);
                case 'headline_desc': return headlineB.localeCompare(headlineA);
                case 'score_desc': // Default
                default:             return scoreB - scoreA;
            }
        });

        console.log(`Filtering complete. ${filteredCandidatesData.length} candidates remaining.`);
        resultsCountEl.textContent = filteredCandidatesData.length; // อัปเดตจำนวนผลลัพธ์
        exportCsvButton.disabled = filteredCandidatesData.length === 0; // เปิด/ปิดปุ่ม Export

        // --- Render results ---
        renderAll(); // แสดงผลตารางและ Dropdown ใหม่
    }

    // 3. ฟังก์ชันหลักในการ Render UI ทั้งหมด
    function renderAll() {
        renderTable(filteredCandidatesData);
        updateCompareDropdowns(filteredCandidatesData);
        // ล้าง Compare View ถ้า Dropdown เปลี่ยน
        updateCompareView('a', compareSelectA.value);
        updateCompareView('b', compareSelectB.value);
    }


    // 4. แสดงผลตาราง 'All Results'
    function renderTable(data) {
        console.log("Rendering results table...");
        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="px-4 py-3 text-sm text-gray-500 text-center">ไม่พบข้อมูลที่ตรงกับเงื่อนไข</td></tr>';
            return;
        }

        tableBody.innerHTML = data.map(candidate => `
            <tr class="hover:bg-gray-700">
                <td class="px-4 py-2 text-sm text-gray-300 truncate max-w-xs" title="${candidate.candidate_id || ''}">${candidate.candidate_id || 'N/A'}</td>
                <td class="px-4 py-2 text-sm text-indigo-400 font-medium">${candidate?.fit_score ?? candidate?.score ?? 'N/A'}</td>
                <td class="px-4 py-2 text-sm text-gray-300 truncate max-w-sm" title="${candidate.headline || ''}">${candidate.headline || '-'}</td>
                <td class="px-4 py-2 text-sm text-gray-400 truncate max-w-xs" title="${(candidate?.skills?.normalized || []).join(', ')}">${(candidate?.skills?.normalized || []).slice(0, 5).join(', ') + ((candidate?.skills?.normalized || []).length > 5 ? '...' : '')}</td>
                <td class="px-4 py-2 text-sm text-red-400 truncate max-w-xs" title="${(candidate?.gaps || []).join(', ')}">${(candidate?.gaps || []).join(', ')}</td>
            </tr>
        `).join('');
    }

    // 5. อัปเดตตัวเลือกใน Dropdown ของ 'Compare Candidates'
    function updateCompareDropdowns(data) {
         console.log("Updating compare dropdowns...");
        // เก็บค่าที่เลือกไว้ก่อน
        const selectedA = compareSelectA.value;
        const selectedB = compareSelectB.value;

        const optionsHtml = data.map(c =>
            // ใช้ candidate_id เป็น value และแสดงใน text
            `<option value="${c.candidate_id || ''}">${c.candidate_id || 'N/A'} (${c?.fit_score ?? c?.score ?? 'N/A'})</option>`
        ).join('');

        const placeholderA = '<option value="">-- เลือก Candidate A --</option>';
        const placeholderB = '<option value="">-- เลือก Candidate B --</option>';

        compareSelectA.innerHTML = placeholderA + optionsHtml;
        compareSelectB.innerHTML = placeholderB + optionsHtml;

        // คืนค่าที่เลือกไว้ ถ้ายังมีอยู่ใน List ใหม่
        if (data.some(c => c.candidate_id === selectedA)) {
            compareSelectA.value = selectedA;
        }
        if (data.some(c => c.candidate_id === selectedB)) {
            compareSelectB.value = selectedB;
        }
    }

    // 6. อัปเดตส่วนแสดงรายละเอียด เมื่อเลือก Candidate ใน Compare Section
    function updateCompareView(panel, candidateId) {
         console.log(`Updating compare panel ${panel} for ID: ${candidateId}`);
        const detailsContainer = panel === 'a' ? compareDetailsA : compareDetailsB;
        detailsContainer.innerHTML = ''; // ล้างข้อมูลเก่า

        if (!candidateId) {
            detailsContainer.innerHTML = '<p class="text-gray-500">เลือก Candidate เพื่อดูรายละเอียด</p>';
            return;
        }

        // หาข้อมูลเต็มๆ ของ Candidate จาก allCandidatesData (ไม่ใช่ตัวที่ filter แล้ว)
        const candidate = allCandidatesData.find(c => c.candidate_id === candidateId);

        if (!candidate) {
            detailsContainer.innerHTML = '<p class="text-red-400">Error: ไม่พบข้อมูล Candidate</p>';
            return;
        }

        // แสดงรายละเอียด
        const score = candidate?.fit_score ?? candidate?.score ?? 'N/A';
        const headline = candidate?.headline || '-';
        const reasons = candidate?.reasons || [];
        const gaps = candidate?.gaps || [];
        const skills = candidate?.skills?.normalized || [];
        const contacts = candidate?.contacts || {};

        // ทำ Redaction ที่ Frontend (ถ้า Backend ไม่ได้ทำมาให้)
        const redactedContacts = Object.entries(contacts).reduce((acc, [key, value]) => {
            const PII_KEYS_LOWER = ['email', 'phone', 'location', 'address', 'linkedin', 'github', 'line', 'facebook'];
            acc[key] = PII_KEYS_LOWER.includes(key.toLowerCase()) ? '•••' : value;
            return acc;
        }, {});


        detailsContainer.innerHTML = `
            <h4>Fit Score: <span class="font-medium text-indigo-400">${score}</span></h4>
            <p><strong>Headline:</strong> ${headline}</p>
            <div><strong>Reasons:</strong> ${reasons.length > 0 ? `<ul>${reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : '<span>-</span>'}</div>
            <div><strong>Gaps:</strong> ${gaps.length > 0 ? gaps.join(', ') : '-'}</div>
            <div><strong>Skills (Normalized):</strong> ${skills.length > 0 ? skills.join(', ') : '-'}</div>
            <div><strong>Contacts (Redacted):</strong> <pre>${JSON.stringify(redactedContacts, null, 2)}</pre></div>
            <details class="mt-2 text-xs">
                <summary class="cursor-pointer text-gray-500 hover:text-gray-400">ดู Raw JSON</summary>
                <pre class="mt-1">${JSON.stringify(candidate, null, 2)}</pre>
            </details>
            <div class="border-t border-red-500/30 pt-3 mt-4">
                <h4 class="text-sm font-medium text-red-400">Danger Zone</h4>
                <button data-candidate-id="${candidateId}" class="delete-button">
                    ลบไฟล์สำหรับ ${candidateId}
                </button>
            </div>
        `;

        // เพิ่ม Event Listener ให้ปุ่มลบที่เพิ่งสร้าง
        detailsContainer.querySelector('.delete-button').addEventListener('click', handleDelete);
    }

    // 7. จัดการการกดปุ่มลบ
    async function handleDelete(event) {
        const button = event.currentTarget;
        const candidateId = button.getAttribute('data-candidate-id');

        if (!candidateId) return;

        // ยืนยันก่อนลบ
        if (!confirm(`ต้องการลบข้อมูลทั้งหมดของ Candidate "${candidateId}" ใช่หรือไม่? การกระทำนี้ไม่สามารถย้อนกลับได้`)) {
            return;
        }

        console.log(`Attempting to delete candidate: ${candidateId}`);
        button.disabled = true;
        button.textContent = 'Deleting...';
        showMessage(''); // ล้างข้อความเก่า

        try {
            // เรียก API DELETE /resume/{file_id}
            const response = await fetch(`${API_BASE_URL}/resume/${encodeURIComponent(candidateId)}`, {
                method: 'DELETE',
            });

            // ตรวจสอบ Response (204 No Content ถือว่าสำเร็จ)
            if (!response.ok && response.status !== 204) {
                let errorDetail = `Failed to delete (Status: ${response.status})`;
                 try { const errJson = await response.json(); errorDetail = errJson.detail || errorDetail; } catch(e){}
                throw new Error(errorDetail);
            }

            console.log(`Successfully deleted candidate: ${candidateId}`);
            showMessage(`ลบข้อมูลสำหรับ ${candidateId} สำเร็จ กำลังโหลดข้อมูลใหม่...`, 'success');

            // --- โหลดข้อมูลใหม่ทั้งหมดจาก Server หลังลบสำเร็จ ---
            await fetchData(); // วิธีนี้ชัวร์ที่สุด


        } catch (error) {
            console.error('Delete Error:', error);
            showMessage(`เกิดข้อผิดพลาดในการลบ ${candidateId}: ${error.message}`, 'error');
            button.disabled = false; // คืนสภาพปุ่มถ้า Error
            button.textContent = `ลบไฟล์สำหรับ ${candidateId}`;
        }
    }


    // 8. Export ข้อมูลในตารางปัจจุบันเป็น CSV
    function exportTableToCSV() {
        if (filteredCandidatesData.length === 0) {
            showMessage("ไม่มีข้อมูลสำหรับ Export", "warning");
            return;
        }
        console.log("Exporting data to CSV...");
        // Headers ตรงกับตาราง
        const headers = ["File", "Fit Score", "Headline", "Skills", "Gaps"];
        const csvRows = [headers.join(',')];

        filteredCandidatesData.forEach(candidate => {
            const values = [
                `"${(candidate.candidate_id || '').replace(/"/g, '""')}"`, // ใส่ "" ครอบ และ escape "
                candidate?.fit_score ?? candidate?.score ?? '',
                `"${(candidate.headline || '').replace(/"/g, '""')}"`,
                `"${(candidate?.skills?.normalized || []).join('; ').replace(/"/g, '""')}"`, // ใช้ ; คั่นใน list
                `"${(candidate?.gaps || []).join('; ').replace(/"/g, '""')}"`
            ];
            csvRows.push(values.join(','));
        });

        downloadCSV(csvRows.join('\n'), 'candidate_warehouse_export.csv');
        console.log("CSV export initiated.");
    }

    // ฟังก์ชันช่วยดาวน์โหลด CSV
    function downloadCSV(csvString, filename) {
        const blob = new Blob([`\uFEFF${csvString}`], { type: 'text/csv;charset=utf-8;' }); // เพิ่ม BOM สำหรับ Excel
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url); // Clean up
    }


    // --- Utility Functions ---
    // แสดง/ซ่อน Loading Indicator และ Disable/Enable Form
    function showLoading(isLoading) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
        const formElements = [searchBox, scoreRangeMin, scoreRangeMax, sortBySelect, refreshButton, exportCsvButton, compareSelectA, compareSelectB];
        formElements.forEach(el => { if(el) el.disabled = isLoading; });
    }

    // แสดงข้อความสถานะ (Info, Success, Warning, Error)
    function showMessage(message, type = 'info') {
        messageContainer.textContent = message;
        // ใช้ Tailwind classes สำหรับสีพื้นหลังและตัวอักษร
        messageContainer.className = `my-4 p-3 rounded-md text-sm font-semibold ${
            type === 'error' ? 'bg-red-900/30 text-red-300 border border-red-500/50' :
            type === 'success' ? 'bg-green-900/30 text-green-300 border border-green-500/50' :
            type === 'warning' ? 'bg-yellow-900/30 text-yellow-300 border border-yellow-500/50' :
            'bg-blue-900/30 text-blue-300 border border-blue-500/50' // Default info
        }`;
        messageContainer.style.display = message ? 'block' : 'none';
    }

    // ฟังก์ชัน Debounce ช่วยหน่วงเวลาการเรียกฟังก์ชัน (สำหรับ Search Box)
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

}); // End DOMContentLoaded
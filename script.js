document.addEventListener('DOMContentLoaded', () => {
    
    // === 1. อ้างอิงถึง Element ต่างๆ ในหน้า HTML ด้วย ID ===
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('file-upload');
    const fileNameDisplay = document.getElementById('file-name-display');
    const convertButton = document.getElementById('convert-button');
    const clearButton = document.getElementById('clear-button');

    // ส่วนของพื้นที่แสดงผลลัพธ์
    const outputContainer = document.getElementById('output-container');
    const loadingState = document.getElementById('loading-state');
    const resultContainer = document.getElementById('result-container');
    const errorContainer = document.getElementById('error-container');

    // ตัวแปรสำหรับเก็บไฟล์ที่เลือก และข้อความเริ่มต้น
    let selectedFile = null;
    const originalFileText = fileNameDisplay.innerHTML;

    // === 2. เพิ่ม Event Listeners (ตัวดักจับเหตุการณ์) ===

    // --- ทำให้พื้นที่อัปโหลดคลิกได้ ---
    fileUploadArea.addEventListener('click', () => {
        fileInput.click(); // สั่งให้ input ที่ซ่อนอยู่ทำงาน
    });

    // --- จัดการไฟล์เมื่อผู้ใช้เลือกเสร็จ ---
    fileInput.addEventListener('change', handleFileSelection);

    // --- จัดการปุ่ม "ล้างข้อมูล" ---
    clearButton.addEventListener('click', clearAll);

    // --- จัดการปุ่ม "แปลง" (ส่งข้อมูลให้ Backend) ---
    convertButton.addEventListener('click', handleConversion);

    // --- เพิ่มความสามารถในการลากและวาง (Drag & Drop) ---
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
        if (selectedFile) {
            // ถ้ามีไฟล์, แสดงชื่อไฟล์ และเปิดใช้งานปุ่ม "แปลง"
            fileNameDisplay.innerHTML = `<span class="font-semibold text-green-600">ไฟล์ที่เลือก:</span> ${selectedFile.name}`;
            convertButton.disabled = false;
        } else {
            clearAll();
        }
    }

    function clearAll() {
        fileInput.value = '';
        selectedFile = null;
        fileNameDisplay.innerHTML = originalFileText;
        convertButton.disabled = true;
        hideAllStates();
    }

    function hideAllStates() {
        loadingState.classList.add('hidden');
        resultContainer.classList.add('hidden');
        errorContainer.classList.add('hidden');
    }

    function handleConversion() {
        if (!selectedFile) {
            renderError('กรุณาเลือกไฟล์ก่อนดำเนินการ');
            return;
        }

        hideAllStates();
        loadingState.classList.remove('hidden');
        convertButton.disabled = true;
        clearButton.disabled = true;

        const formData = new FormData();
        formData.append('file', selectedFile);

        // ส่ง Request ไปยัง Python Flask Server
        fetch('http://127.0.0.1:5000/upload', {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => Promise.reject(err));
            }
            return response.json();
        })
        .then(data => {
            renderSuccess(data);
        })
        .catch(error => {
            renderError(error.error || 'การเชื่อมต่อกับเซิร์ฟเวอร์ล้มเหลว');
        })
        .finally(() => {
            loadingState.classList.add('hidden');
            convertButton.disabled = false;
            clearButton.disabled = false;
        });
    }

    // === 4. ฟังก์ชันสำหรับแสดงผลลัพธ์บนหน้าเว็บ ===

    function renderSuccess(data) {
        hideAllStates();
        resultContainer.classList.remove('hidden');
        const html = `
            <div class="border border-slate-200 rounded-xl p-6 space-y-6 animate-fade-in">
                <div>
                    <h2 class="text-2xl font-bold text-indigo-700">${data.name || 'ไม่พบชื่อ'}</h2>
                    <p class="text-sm text-slate-500">สรุปข้อมูลจาก: ${data.source_file || 'N/A'}</p>
                </div>
                <div class="border-t border-slate-200 pt-4">
                    <h3 class="font-semibold text-slate-800 mb-3">ข้อมูลติดต่อ</h3>
                    <div class="space-y-2 text-slate-600">
                        <p><strong>อีเมล:</strong> ${data.contacts?.email || 'ไม่มีข้อมูล'}</p>
                        <p><strong>โทรศัพท์:</strong> ${data.contacts?.phone || 'ไม่มีข้อมูล'}</p>
                    </div>
                </div>
            </div>
        `;
        resultContainer.innerHTML = html;
    }

    function renderError(message) {
        hideAllStates();
        errorContainer.classList.remove('hidden');
        errorContainer.innerHTML = `
            <div class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md" role="alert">
                <p class="font-bold">เกิดข้อผิดพลาด</p>
                <p>${message}</p>
            </div>
        `;
    }
});

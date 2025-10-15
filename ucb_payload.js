// Reference to HTML elements
const fileInput = document.getElementById('file-upload');
const transformButton = document.getElementById('convert-button');

// add Event Listener for Transform button
transformButton.addEventListener('click', function() {
    // ตรวจสอบว่ามีไฟล์ถูกเลือกหรือไม่
    const file = fileInput.files[0];
    if (!file) {
        alert('กรุณาเลือกไฟล์ก่อน');
        return;
    }

    // เรียกใช้ฟังก์ชันแปลงข้อมูล
    transformFile(file);
});

// ฟังก์ชันสำหรับแปลงข้อมูลจากไฟล์
function transformFile(file) {
    // นี่คือส่วนที่คุณจะเขียน Logic การแปลงข้อมูล
    // ในขั้นตอนนี้ เราจะแสดงแค่ชื่อไฟล์ที่ถูกอัปโหลด
    // การแปลงข้อมูลจากไฟล์จริงๆ (เช่น .pdf, .docx) จะต้องใช้ไลบรารีเพิ่มเติม
    
    const fileName = file.name;
    const fileType = file.type;
    
    alert(`กำลังแปลงไฟล์: ${fileName}\nประเภทไฟล์: ${fileType}`);

    // *หมายเหตุ: หากต้องการแปลงไฟล์ .docx หรือ .pdf จริงๆ*
    // คุณจะต้องใช้ไลบรารี JavaScript ที่สามารถอ่านเนื้อหาจากไฟล์ไบนารีได้
    // ตัวอย่างเช่น:
    // - สำหรับ PDF: ใช้ไลบรารีอย่าง `pdf.js`
    // - สำหรับ DOCX: ใช้ไลบรารีอย่าง `mammoth.js`
    
    // โค้ดในส่วนนี้จะมีความซับซ้อนขึ้นอยู่กับประเภทไฟล์ที่คุณต้องการแปลง
    // ในขั้นแรกนี้ การแสดงแค่ข้อมูลพื้นฐานของไฟล์ก็เพียงพอแล้วครับ
    
    // แสดงผลลัพธ์บนหน้าเว็บ (สมมติว่ามี Element สำหรับแสดงผล)
    // const outputElement = document.createElement('div');
    // outputElement.textContent = `ข้อมูลจากไฟล์ ${fileName} ถูกแปลงแล้ว`;
    // document.body.appendChild(outputElement);
}
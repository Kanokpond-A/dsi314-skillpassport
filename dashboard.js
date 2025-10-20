// js/dashboard.js

// รอให้หน้าเว็บ (HTML) โหลดเสร็จเรียบร้อยก่อน
document.addEventListener('DOMContentLoaded', () => {
    
    // === 1. ตรวจสอบสถานะการ Login ===
    setupAuthenticationUI();

});

function setupAuthenticationUI() {
    // 1. ค้นหา Token ใน LocalStorage
    const token = localStorage.getItem('userToken');
    
    // 2. อ้างอิงไปยังตำแหน่งที่เราจะใส่ปุ่มใน Header
    const authContainer = document.getElementById('auth-links-container');

    if (!authContainer) {
        console.error('ไม่พบ auth-links-container ใน HTML!');
        return;
    }

    if (token) {
        // --- 3.A ถ้ามี Token (Login อยู่) ---
        // เราจะสร้างปุ่ม "ออกจากระบบ" และอาจจะแสดงชื่อผู้ใช้
        
        // (ตัวเลือกเสริม) ดึงข้อมูลผู้ใช้มาแสดง
        fetchUserProfile(token); 
        
        // สร้างปุ่ม Logout
        authContainer.innerHTML = `
            <li><a href="#" id="logout-button-header">ออกจากระบบ</a></li>
        `;
        
        // เพิ่ม Event Listener ให้ปุ่ม Logout ใหม่
        const logoutButton = document.getElementById('logout-button-header');
        if (logoutButton) {
            logoutButton.addEventListener('click', (e) => {
                e.preventDefault(); // ป้องกันการ Refresh หน้า
                handleLogout();
            });
        }

    } else {
        // --- 3.B ถ้าไม่มี Token (เป็น Guest) ---
        // เราจะสร้างปุ่ม "เข้าสู่ระบบ" และ "ลงทะเบียน"
        
        authContainer.innerHTML = `
            <li><a href="login.html">เข้าสู่ระบบ</a></li>
            <li><a href="register.html" class="nav-button">ลงทะเบียน</a></li> 
        `;
        // (เราใช้ .nav-button จาก style.css เดิมของคุณ)
    }
}

function handleLogout() {
    // ลบ Token ออกจาก LocalStorage
    localStorage.removeItem('userToken');
    
    // (ทางเลือก) แจ้งเตือนผู้ใช้
    alert('ออกจากระบบสำเร็จ');
    
    // รีเฟรชหน้าเพื่อให้ UI อัปเดตเป็น "เข้าสู่ระบบ"
    window.location.reload();
}

async function fetchUserProfile(token) {
    // ฟังก์ชันนี้จะทำงาน *เฉพาะ* เมื่อผู้ใช้ Login อยู่
    try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/users/me', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            // ถ้า Token หมดอายุ หรือไม่ถูกต้อง
            throw new Error('Session หมดอายุ');
        }

        const user = await response.json();
        console.log('ข้อมูลผู้ใช้:', user);
        
        // (ตัวอย่าง) คุณสามารถใช้ข้อมูลนี้ไปแสดงผล
        // เช่น: document.getElementById('user-email-display').textContent = user.email;

    } catch (error) {
        // ถ้าเกิดปัญหา, อาจจะหมายความว่า Token เก่า
        // ให้บังคับ Logout เลย
        console.error(error.message);
        handleLogout();
    }
}
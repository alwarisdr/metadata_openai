วิธีใช้งาน
**ในเครื่องต้องลง Python ก่อนนะครับ (ถ้าทำไฟล์ .exe กินเนื้อที่เยอะ ใช้เวลานาน)
วิธีติดตั้ง Python : https://www.facebook.com/groups/820449589702580/permalink/853676156379923

1. หลังจากดาวน์โหลดไฟล์มาแล้ว unzip ออกมาจะได้ folder :metadata (แนะนำให้เอาไว้ที่ c:\metadata หรือ d:\metadata เพื่อสะดวกในการพิมพ์คำสั่ง หรือชำนาญแล้วก็แล้วแต่สะดวก)
2. เปิด Command Prompt (Windows + R แล้วพิมพ์ cmd) > เลือก Run as Administrator ด้วยนะครับ
3. ในหน้าต่าง Command Prompt ให้พิมพ์ cd metadata แล้วกด enter ที่คีย์บอร์ด
4. จะได้ c:\metadata เสร็จแล้วให้พิมพ์คำสั่ง 
	1. python -m venv venv แล้วกด Enter
	2. venv\scripts\activate แล้วกด Enter
	3. pip install -r requirements.txt แล้วกด Enter
	4. python app.py แล้วกด Enter
5. ถ้าเครื่องเราพร้อมใช้งาน จะมี url : http://127.0.0.1:5000/ ซึ่งเป็น Server จำลองในเครื่องเรา ให้ Copy แล้วไปแปะที่ช่อง URL ของ Browser เพื่อเริ่มใช้งานได้เลย
6. ในหน้าจอใช้งาน 
	- เอา OpenAI API Key มาใส่ในช่อง แล้วกด Save API Key
	- เลือกวิธีการอัพโหลด เช่น 1 ไฟล์, หลายไฟล์ และ โฟลเดอร์
	- กดปุ่ม วิเคราะห์รูปภาพและฝังคีย์เวิร์ด
	- จะขึ้น Process... รอจนกว่าจะขึ้น Done ...
***ทำเสร็จแล้วให้ย้ายรูปและไฟล์ metadata.csv ไปไว้ที่อื่นทุกครั้งหลังทำงานเสร็จ (เพราะโปรแกรมจะสร้างไฟล์ metadata.csv ใหม่มาทับไฟล์เดิม

API Key ไปเอาได้ที่นี่ https://platform.openai.com/api-keys

ติดปัญหาสอบถามได้ที่ inbox ในเพจ https://www.facebook.com/ai.influencer.th

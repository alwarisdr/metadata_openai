import os
import pandas as pd
from flask import Flask, render_template, request, send_file, jsonify, url_for, session
from PIL import Image
from PIL.ExifTags import TAGS
import piexif
import piexif.helper
from openai import OpenAI
import csv
from werkzeug.utils import secure_filename
import openai
import base64
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # ควรเปลี่ยนเป็นค่าที่ซับซ้อนและเก็บเป็นความลับ

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Global variables
processing_complete = False
csv_path = ''

def get_openai_client():
    if 'openai_api_key' in session:
        return OpenAI(api_key=session['openai_api_key'])
    return None

def generate_title_from_description(description):
    client = get_openai_client()
    if not client:
        return "API Key Not Set"
    
    prompt = f"Create a short title (not exceeding 150 characters) based on this description: {description}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates titles."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()[:150]

def save_metadata_to_image(image_path, title, subjects, tags):
    try:
        # Load existing exif data
        exif_dict = piexif.load(image_path)
        
        # Prepare new metadata
        user_comment = piexif.helper.UserComment.dump(subjects, encoding="unicode")
        exif_dict['0th'][piexif.ImageIFD.XPTitle] = title.encode('utf-16le')
        exif_dict['Exif'][piexif.ExifIFD.UserComment] = user_comment
        exif_dict['0th'][piexif.ImageIFD.XPKeywords] = tags.encode('utf-16le')
        
        # Convert exif dict to bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # Insert exif bytes into the image file
        piexif.insert(exif_bytes, image_path)
        
        print(f"Metadata saved successfully for {image_path}")
    except Exception as e:
        print(f"Error saving metadata for {image_path}: {e}")

def read_metadata_from_image(image_path):
    try:
        exif_dict = piexif.load(image_path)
        title = exif_dict['0th'].get(piexif.ImageIFD.XPTitle, b'').decode('utf-16le', 'ignore').rstrip('\x00')
        subjects = piexif.helper.UserComment.load(exif_dict['Exif'].get(piexif.ExifIFD.UserComment, b'')).decode('utf-8')
        tags = exif_dict['0th'].get(piexif.ImageIFD.XPKeywords, b'').decode('utf-16le', 'ignore').rstrip('\x00')
        return title, subjects, tags
    except Exception as e:
        print(f"Error reading metadata from {image_path}: {e}")
        return "", "", ""

def generate_content_from_filename(filename):
    try:
        client = get_openai_client()
        if not client:
            return "API Key Not Set", "No subjects available", "image, unspecified, content, visual, media"
        
        prompt = f"""
        Filename: {filename}

        Generate metadata for a stock photo:

        1. Title: A concise, SEO-friendly title (≤100 characters).
        2. Subjects: A 4-5 sentence detailed description.
        3. Tags: 49 single-word keywords, comma-separated.  
        - First 10 must include all key terms from the title.  
        - The remaining 39 should be highly relevant but not plural.  
        - Select at least 30 distinct important words to ensure variety.
        - No paired words.  
        - Ensure maximum discoverability.  

        Format your response exactly as follows:  
        Title: [Your title here]  
        Subjects: [Your subjects here]  
        Tags: [Your tags here] 
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates SEO-optimized image metadata for stock photography platforms."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # ✅ แสดงข้อมูลเครดิตที่ใช้ (Token Usage)
        if hasattr(response, 'usage'):
            print(f"Tokens used - Input: {response.usage.prompt_tokens}, Output: {response.usage.completion_tokens}, Total: {response.usage.total_tokens}")
        else:
            print("Token usage data not available.")

        print(f"Raw API response: {response.choices[0].message.content}")

       
        
        title = "Untitled Image"
        subjects = "No subjects available"
        tags = "image, unspecified, content, visual, media"
        
        for line in response.choices[0].message.content.split('\n'):
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("subjects:"):
                subjects = line.split(":", 1)[1].strip()
            elif line.lower().startswith("tags:"):
                tags = line.split(":", 1)[1].strip()
        
        if not title or title == "Untitled Image":
            if subjects:
                title = generate_title_from_description(subjects)
        
        # Extract keywords from title
        title_keywords = [word.strip().lower() for word in title.replace(',', '').split() if len(word) >= 3]

        # Process tags
        tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
        tag_list = list(set(tag_list))  # Remove duplicates
        tag_list = [tag for tag in tag_list if len(tag) >= 3]  # Remove very short tags

        # Ensure 10 title-based keywords are included
        final_tags = title_keywords[:10] + [tag for tag in tag_list if tag not in title_keywords]
        tags = ', '.join(final_tags[:49])  # Limit to 49 tags
        
        return title, subjects, tags
    except Exception as e:
        print(f"Error generating content for {filename}: {e}")
        return "Error Image", "Failed to process image", "error, processing, failed, image, issue"

def select_category(filename, title, subjects, tags):
    client = get_openai_client()
    if not client:
        return "0"
    
    categories = [
        "1. Animals", "2. Buildings and Architecture", "3. Business", "4. Drinks",
        "5. The Environment", "6. States of Mind", "7. Food", "8. Graphic Resources",
        "9. Hobbies and Leisure", "10. Industry", "11. Landscapes", "12. Lifestyle",
        "13. People", "14. Plants and Flowers", "15. Culture and Religion", "16. Science",
        "17. Social Issues", "18. Sports", "19. Technology", "20. Transport", "21. Travel"
    ]
    categories_str = ", ".join(categories)
    
    prompt = f"""
    Based on the following image metadata, select the most appropriate category from the list below:

    Filename: {filename}
    Title: {title}
    Subjects: {subjects}
    Tags: {tags}

    Categories:
    {categories_str}

    Please respond with only the number of the category (e.g., "13" for People) that best fits the image.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that selects categories for images."},
            {"role": "user", "content": prompt}
        ]
    )
    
    category_number = response.choices[0].message.content.strip()
    
    try:
        category_number = int(category_number)
        if 1 <= category_number <= 21:
            return str(category_number)
        else:
            return "0"  # Default value if out of range
    except ValueError:
        return "0"  # Default value if not a valid number

def encode_image(image_path):
    """ แปลงไฟล์ภาพเป็น Base64 """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def resize_image(input_path, output_path, max_size=(512, 512), quality=85):
    """ ลดขนาดไฟล์ก่อนส่งให้ AI วิเคราะห์ """
    with Image.open(input_path) as img:
        img.thumbnail(max_size)
        img.save(output_path, "JPEG", quality=quality)
    return output_path  # คืนค่าพาธไฟล์ที่ถูกย่อ

def analyze_image_with_vision(image_path):

    try:
        """ ลดขนาดภาพก่อนส่งไปยัง OpenAI Vision API """
        resized_path = "resized_" + os.path.basename(image_path)
        resized_path = resize_image(image_path, resized_path)
        print(f"ลดขนาดภาพ image path เป็น 512x512 พิกเซล ตำแหน่งอยู่ที่ {resized_path}")

        if resized_path:
            print(f"✅ ลดขนาดภาพเสร็จสิ้น! ไฟล์ใหม่: {resized_path}")
        else:
            print("❌ ลดขนาดภาพล้มเหลว")

        """ ส่งภาพที่ย่อแล้วไปยัง OpenAI Vision API """
        image_base64 = encode_image(resized_path)
        print("แปลง image path เป็น image_base64")

        client = get_openai_client()
        if not client:
            return "API Key Not Set", "No subjects available", "image, unspecified"

        prompt = f"""
        Analyze this image and generate metadata for microstock:

        1. Title: A concise, SEO-friendly stock photo title (≤100 characters).
        2. Subjects: A detailed 3 sentence description.
        3. Tags: 49 single-word keywords, comma-separated.
        - First 10 must include all key terms from the title.
        - The remaining 39 should be highly relevant but not plural.
        - Select at least 30 distinct important words to ensure variety.  
        - No paired words.
        - Ensure maximum discoverability.

        **Format output as follows:**  
        Title: [Your title here]  
        Subjects: [Your subjects here]  
        Tags: [Your tags here]
        """
        
        with open(resized_path, "rb") as image_file:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI that generates image metadata, including titles, descriptions, and SEO-optimized tags for stock photography platforms."},
                    {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url":f"data:image/jpeg;base64,{image_base64}"}}
                        ],
                    } 
                ],
                max_tokens=300
            )
        
        print(response.choices[0])

        # ✅ แสดงข้อมูลเครดิตที่ใช้ (Token Usage)
        if hasattr(response, 'usage'):
            print(f"Tokens used - Input: {response.usage.prompt_tokens}, Output: {response.usage.completion_tokens}, Total: {response.usage.total_tokens}")
        else:
            print("Token usage data not available.")

        # ดึงผลลัพธ์จาก AI
        print(f"Raw API response: {response.choices[0].message.content}")
        raw_content = response.choices[0].message.content

        # ใช้ Regex ลบ ** และ "Title:" ออก
        clean_content = re.sub(r"\*\*(.*?)\*\*", r"\1", raw_content)  # ลบ Markdown **bold**
        print(f"Cleaned API response: {clean_content}")
        
        result = response.choices[0].message.content.strip().split('\n')
        title, subjects, tags = "Untitled Image", "No subjects available", "image, unspecified"
        
        for line in result:
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("subjects:"):
                subjects = line.split(":", 1)[1].strip()
            elif line.lower().startswith("tags:"):
                tags = line.split(":", 1)[1].strip()

        # หลังจากใช้งานเสร็จแล้ว ลบไฟล์ resized
        if os.path.exists(resized_path):
            os.remove(resized_path)
            print(f"🗑️ ลบไฟล์ {resized_path} สำเร็จ")
        
        return title, subjects, tags
    except Exception as e:
        print(f"Error analyzing image with Vision API: {e}")
        return "Error Image", "Failed to process image", "error, processing, failed, image, issue"

def generate_metadata_with_vision(image_path):

    try :
        print(f"ประมวลผลภาพ {image_path} ด้วย OpenAI Vision API")
        filename = os.path.basename(image_path)
        title, subjects, tags, = analyze_image_with_vision(image_path)
        category = select_category(filename, title, subjects, tags)

        save_metadata_to_image(image_path, title, subjects, tags)
            
        read_title, read_subjects, read_tags = read_metadata_from_image(image_path)
        print(f"Verified metadata for {image_path}:")
        print(f"Title: {read_title}")
        print(f"Subjects: {read_subjects}")
        print(f"Tags: {read_tags}")
        print(f"Category: {category}")
            
        return title, subjects, tags, category
    except Exception as e:
        print(f"Error generating metadata for {image_path}: {e}")
        return "Error Image", "Failed to process image", "error, processing, failed, image, issue"

def generate_metadata(image_path):
    try:
        filename = os.path.basename(image_path)
        title, subjects, tags = generate_content_from_filename(filename)
        category = select_category(filename, title, subjects, tags)
        
        save_metadata_to_image(image_path, title, subjects, tags)
        
        read_title, read_subjects, read_tags = read_metadata_from_image(image_path)
        print(f"Verified metadata for {image_path}:")
        print(f"Title: {read_title}")
        print(f"Subjects: {read_subjects}")
        print(f"Tags: {read_tags}")
        print(f"Category: {category}")
        
        return title, subjects, tags, category
    except Exception as e:
        print(f"Error generating metadata for {image_path}: {e}")
        return "Error Image", "Failed to process image", "error, processing, failed, image, issue", "0"

def rename_file_with_title(file_path, title):
    try:
        directory = os.path.dirname(file_path)
        file_extension = os.path.splitext(file_path)[1]
        new_filename = secure_filename(title) + file_extension
        new_file_path = os.path.join(directory, new_filename)
        
        counter = 1
        while os.path.exists(new_file_path):
            new_filename = f"{secure_filename(title)}_{counter}{file_extension}"
            new_file_path = os.path.join(directory, new_filename)
            counter += 1
        
        os.rename(file_path, new_file_path)
        print(f"File renamed from {file_path} to {new_file_path}")
        return new_file_path
    except Exception as e:
        print(f"Error renaming file {file_path}: {e}")
        return file_path

@app.route('/', methods=['GET', 'POST'])
def index():
    global processing_complete, csv_path
    if request.method == 'POST':
        if 'openai_api_key' in request.form:
            session['openai_api_key'] = request.form['openai_api_key']
            return jsonify({'status': 'success', 'message': 'API key บันทึกเรียบร้อยแล้ว'})

        if 'openai_api_key' not in session:
            return jsonify({'status': 'error', 'message': 'กรุณาใส่ OpenAI API key ก่อน'})

        upload_type = request.form.get('upload_type')
        
        if upload_type == 'single':
            file = request.files['single_image']
            if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                #title, subjects, tags, category = generate_metadata(file_path)
                title, subjects, tags, category = generate_metadata_with_vision(file_path)
                new_file_path = rename_file_with_title(file_path, title)
                return jsonify({'status': 'success', 'message': f'ไฟล์ {filename} ถูกประมวลผลและเปลี่ยนชื่อเป็น {os.path.basename(new_file_path)}'})
            
        elif upload_type in ['multiple', 'folder']:
            uploaded_files = request.files.getlist("multiple_images" if upload_type == 'multiple' else "image_folder")
            
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'metadata.csv')
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(['Filename', 'Title', 'Keywords', 'Category', 'Releases'])

                for file in uploaded_files:
                    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)
                        print(f"กำลังประมวลผลรูปภาพ: {filename}")

                        #title, subjects, tags, category = generate_metadata(file_path)
                        title, subjects, tags, category = generate_metadata_with_vision(file_path)
                        new_file_path = rename_file_with_title(file_path, title)
                        new_filename = os.path.basename(new_file_path)
                        
                        csv_writer.writerow([new_filename, title, tags, category, ''])
                        print(f"สร้างและบันทึก Metadata สำหรับ {new_filename}: Title: {title}, Tags: {tags}, Category: {category}")

            print(f"สร้างไฟล์ CSV Metadata ที่ {csv_path}")
            processing_complete = True
            return jsonify({'status': 'processing', 'message': 'อัปโหลดไฟล์และเริ่มการประมวลผลแล้ว'})
        
        return jsonify({'status': 'error', 'message': 'ประเภทการอัปโหลดไม่ถูกต้องหรือไม่ได้เลือกไฟล์'})
    
    return render_template('index.html')

@app.route('/status')
def status():
    global processing_complete
    if processing_complete:
        return jsonify({'status': 'done', 'download_url': url_for('download_csv')})
    else:
        return jsonify({'status': 'processing'})

@app.route('/download_csv')
def download_csv():
    global csv_path
    return send_file(csv_path, as_attachment=True, download_name='metadata.csv')

if __name__ == '__main__':
    app.run(debug=True)
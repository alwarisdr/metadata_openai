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
        Based on this filename: {filename}
        Generate the following information:
        1. Title: A short, descriptive title (7 words or less)
        2. Subjects: A detailed description (2-3 sentences)
        3. Tags: Generate 20-30 relevant keywords for SEO, optimized for imstocker ranking. Follow these guidelines:
           - Include a mix of specific and general terms related to the image
           - Use both singular and plural forms of nouns
           - Include synonyms and related concepts
           - Add some descriptive adjectives
           - Include terms related to style, mood, or technique if applicable
           - Consider including location or cultural references if relevant
           - Avoid overly generic terms like "image" or "picture"
           - Separate keywords with commas
        
        Please format your response exactly as follows:
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
        
        # Process tags
        tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
        tag_list = list(set(tag_list))  # Remove duplicates
        tag_list = [tag for tag in tag_list if len(tag) >= 3]  # Remove very short tags
        tags = ', '.join(tag_list[:30])  # Limit to 30 tags
        
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
                title, subjects, tags, category = generate_metadata(file_path)
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

                        title, subjects, tags, category = generate_metadata(file_path)
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
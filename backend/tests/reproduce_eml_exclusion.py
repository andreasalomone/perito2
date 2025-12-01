import os
import shutil
import logging
from email.message import EmailMessage
from email.policy import default
import pathlib
import sys

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.document_processor import process_eml_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_dummy_eml(file_path):
    msg = EmailMessage(policy=default)
    msg['Subject'] = 'Test Email with Attachments'
    msg['From'] = 'sender@example.com'
    msg['To'] = 'recipient@example.com'
    msg.set_content('This is the body of the email.')

    # Add a valid attachment (text)
    msg.add_attachment(b'This is a text attachment.', filename='valid.txt', maintype='text', subtype='plain')

    # Add a valid GIF attachment (minimal 1x1 GIF)
    # 1x1 pixel transparent GIF
    valid_gif_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    msg.add_attachment(valid_gif_data, filename='valid.gif', maintype='image', subtype='gif')
    
    # Add another invalid attachment (mp4)
    msg.add_attachment(b'fake_mp4_content', filename='video.mp4', maintype='video', subtype='mp4')

    with open(file_path, 'wb') as f:
        f.write(msg.as_bytes())

def test_eml_exclusion():
    upload_folder = 'tests/temp_uploads'
    eml_path = os.path.join(upload_folder, 'test.eml')
    
    # Cleanup and setup
    if os.path.exists(upload_folder):
        shutil.rmtree(upload_folder)
    os.makedirs(upload_folder)

    try:
        create_dummy_eml(eml_path)
        
        logger.info(f"Created dummy EML at {eml_path}")
        
        # Process the EML file
        results = process_eml_file(eml_path, upload_folder)
        
        # Check results
        filenames = [r.get('filename') for r in results]
        logger.info(f"Extracted filenames: {filenames}")
        
        found_txt = any('valid.txt' in str(f) for f in filenames)
        found_gif = any('valid.gif' in str(f) for f in filenames)
        found_mp4 = any('video.mp4' in str(f) for f in filenames)
        
        if found_txt:
            logger.info("PASS: Valid text attachment found.")
        else:
            logger.error("FAIL: Valid text attachment NOT found.")
            
        # For reproduction, we EXPECT the GIF to be found (because we haven't fixed it yet).
        # But the goal of the test is to verify the FIX.
        # So we will assert that it is NOT found, which should FAIL now.
        if not found_gif:
            logger.info("PASS: Valid GIF attachment NOT found (correctly excluded).")
        else:
            logger.error("FAIL: Valid GIF attachment FOUND (should be excluded).")
            
        if not found_mp4:
            logger.info("PASS: Invalid MP4 attachment NOT found (correctly excluded).")
        else:
            logger.error("FAIL: Invalid MP4 attachment FOUND (should be excluded).")
            
        # Check file system
        # Modified to check upload_folder directly as per current implementation
        files_on_disk = list(pathlib.Path(upload_folder).glob('*'))
        logger.info(f"Files on disk: {[f.name for f in files_on_disk]}")
        
        disk_gif = any(f.name == 'valid.gif' for f in files_on_disk)
        if not disk_gif:
                logger.info("PASS: GIF file NOT found on disk.")
        else:
                logger.error("FAIL: GIF file FOUND on disk.")

    finally:
        # Cleanup
        if os.path.exists(upload_folder):
            shutil.rmtree(upload_folder)

if __name__ == "__main__":
    test_eml_exclusion()

import os
import json
from google import genai
import PIL.Image

def test_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("No GEMINI_API_KEY found.")
        return
        
    client = genai.Client(api_key=api_key)
    img_path = r"d:\Sai Kiran\projects\pms3.0\pms\uploads\temp_timetable_time_table_DS.jpeg"
    
    if not os.path.exists(img_path):
        print("Image not found:", img_path)
        return
        
    img = PIL.Image.open(img_path)
    
    prompt = """
    Analyze this university timetable image.
    Extract the subjects for each period (usually 1 to 7) for Monday to Saturday.
    Also, extract the precise time duration for each of the 7 periods. Provide time strictly in 24-hour format (e.g., '13:00 - 13:50', not '1:00 - 1:50' or '1:00 PM').
    
    Return ONLY a raw JSON mapping with the following exact structure, with no markdown formatting, no backticks, just the JSON string:
    {
        "parsed_data": {
            "Monday": ["Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5", "Sub 6", "Sub 7"],
            "Tuesday": ["...", "...", "...", "...", "...", "...", "..."],
            "Wednesday": ["...", "...", "...", "...", "...", "...", "..."],
            "Thursday": ["...", "...", "...", "...", "...", "...", "..."],
            "Friday": ["...", "...", "...", "...", "...", "...", "..."],
            "Saturday": ["...", "...", "...", "...", "...", "...", "..."]
        },
        "timings": [
            "09:00 - 10:00",
            "10:00 - 10:50",
            "11:00 - 11:50",
            "11:50 - 12:40",
            "13:30 - 14:20",
            "14:20 - 15:10",
            "15:10 - 16:00"
        ]
    }
    Note: If a period says "Break" or "Lunch" or is empty, use an empty string "" for the subject.
    Make sure to exclude explicit break/lunch columns from the 'parsed_data' array if they are not actual class periods. We only want the 7 class periods.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, prompt]
        )
        print("RAW RESPONSE:")
        print(response.text)
        
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        print("\nPARSED SUCCESS:")
        print(json.dumps(data, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(r"d:\Sai Kiran\projects\pms3.0\pms\.env")
    test_gemini()

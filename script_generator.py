import os
import json
import re
from typing import List, Dict

class ScriptGenerator:
    def __init__(self, openai_api_key: str = None, gemini_api_key: str = None, ollama_url: str = "http://localhost:11434", use_ollama: bool = False, ollama_model: str = "llama3"):
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.ollama_url = ollama_url
        self.use_ollama = use_ollama
        self.ollama_model = ollama_model
        
        if self.openai_api_key:
            import openai
            openai.api_key = self.openai_api_key
            self.openai_module = openai
            
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.genai_module = genai
            except ImportError:
                print("Warning: google.generativeai not found or deprecated.")
                self.genai_module = None

    def ensure_service_running(self):
        """Checks if Ollama is running, and starts it if not."""
        import requests
        import subprocess
        import time
        import sys

        try:
            requests.get(self.ollama_url, timeout=2)
            # print("✅ Ollama is already running.")
            return True
        except:
            print("⚠️ Ollama not detected. Attempting to start...")
            try:
                # Start Ollama in a separate process
                if sys.platform == "win32":
                    subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Wait for it to initialize
                print("⏳ Waiting for Ollama to start (max 30s)...")
                for i in range(30):
                    try:
                        requests.get(self.ollama_url, timeout=1)
                        print("✅ Ollama started successfully!")
                        return True
                    except:
                        time.sleep(1)
                        if i % 5 == 0:
                            print(f"   ...waiting {i}s")
                
                print("❌ Failed to start Ollama automatically.")
                return False
            except FileNotFoundError:
                print("❌ 'ollama' command not found. Is it installed?")
                return False
            except Exception as e:
                print(f"❌ Error starting Ollama: {e}")
                return False

    def generate_script(self, topic: str) -> List[Dict[str, str]]:
        """
        Generates a documentary script with visual keywords based on the topic.
        Returns a list of segments: [{'text': '...', 'keywords': '...'}]
        """
        system_prompt = """
        You are a professional documentary scriptwriter. 
        Create a compelling, dramatic script for a video essay about the given topic.
        
        Output Format: JSON object with a "segments" key containing a list of objects.
        Example:
        {
            "segments": [
                {
                    "text": "The script text...",
                    "keywords": ["specific visual query", "broader visual query", "safe abstract query"]
                }
            ]
        }
        
        Requirements:
        - The script should be engaging, well-paced, and factual.
        - "keywords" MUST be a list of 3 strings:
          1. A highly specific visual description of the scene.
          2. A broader, simpler visual concept.
          3. A generic, safe background concept (e.g. "abstract technology background").
        - Do not include scene numbers or directions in the "text" field.
        - Generate about 5-8 segments for a 1-2 minute video.
        """
        
        user_prompt = f"Topic: {topic}"

        try:
            if self.openai_api_key:
                return self._generate_openai(system_prompt, user_prompt)
            elif self.gemini_api_key:
                return self._generate_gemini(system_prompt, user_prompt)
            elif self.use_ollama:
                if self.ensure_service_running():
                    return self._generate_ollama(system_prompt, user_prompt)
                else:
                    raise ValueError("Ollama is not running and could not be started.")
            else:
                raise ValueError("No API Key provided for Script Generation and Ollama is disabled.")
        except Exception as e:
            print(f"Script Generation Error: {e}")
            return []

    def generate_quiz_questions(self, topic="General Knowledge", amount=5) -> List[Dict]:
        """
        Generates quiz questions using LLM.
        """
        system_prompt = """
        You are a quiz generator. Generate unique, interesting, and diverse multiple-choice questions.
        
        Output Format: JSON object with a "questions" key containing a list of objects.
        Example:
        {
            "questions": [
                {
                    "q": "What is the capital of France?",
                    "a": "Paris",
                    "options": ["Paris", "London", "Berlin", "Madrid"],
                    "difficulty": "easy"
                }
            ]
        }
        
        Requirements:
        - 'options' MUST be a list of 4 strings, INCLUDING the correct answer.
        - 'a' MUST be exactly one of the strings in 'options'.
        - 'difficulty' should be 'easy', 'medium', or 'hard'.
        - Ensure questions are factually correct.
        """
        
        user_prompt = f"Generate {amount} questions about {topic}."
        
        try:
            if self.use_ollama:
                self.ensure_service_running()
                return self._generate_ollama_quiz(system_prompt, user_prompt)
            elif self.openai_api_key:
                # Reuse openai generation but need to parse specifically? 
                # _generate_openai returns parsed JSON, so if prompt asks for "questions" list, it should work.
                result = self._generate_openai(system_prompt, user_prompt)
                return result.get("questions", [])
            else:
                return []
        except Exception as e:
            print(f"Quiz Generation Error: {e}")
            return []

    def generate_couple_questions(self, amount=5, gender="neutral", category="general") -> List[Dict]:
        """
        Generates 'Couples Quiz' style questions.
        gender: 'male' (questions about Him), 'female' (questions about Her), or 'neutral'.
        category: 'general', 'deep', 'spicy', 'funny', 'hard', etc.
        """
        
        focus_instruction = ""
        example_q = "What is their favorite movie?"
        example_a = "The Matrix"
        
        if gender.lower() == "male":
            focus_instruction = "IMPORTANT: All questions MUST be about HIM (e.g., 'What is his...', 'Does he prefer...'). Do NOT use 'her' or 'she'."
            example_q = "What is his dream car?"
            example_a = "Ferrari"
        elif gender.lower() == "female":
            focus_instruction = "IMPORTANT: All questions MUST be about HER (e.g., 'What is her...', 'Does she prefer...'). Do NOT use 'him' or 'he'."
            example_q = "What is her favorite flower?"
            example_a = "Rose"
            
        # Category specific context
        cat_instruction = ""
        if category.lower() == "deep":
            cat_instruction = "Focus on emotional connection, future goals, fears, and values. Questions that make them think deeply."
        elif category.lower() == "spicy":
            cat_instruction = "Focus on romance, physical attraction, and cheeky/flirty topics. Keep it safe for YouTube (PG-13) but fun/suggestive."
        elif category.lower() == "funny":
            cat_instruction = "Focus on embarrassing moments, funny habits, and weird quirks. Make them laugh."
        elif category.lower() == "hard":
            cat_instruction = "Focus on obscure details (e.g., exact birth time, license plate, specific favorites). Things only a true partner would know."
        else:
            cat_instruction = "Focus on general relationship knowledge, favorites, and habits."

        system_prompt = f"""
        You are a fun couples quiz generator. Generate engaging questions for couples to test how well they know each other.
        
        Output Format: JSON object with a "questions" key containing a list of objects.
        Example:
        {{
            "questions": [
                {{
                    "q": "{example_q}",
                    "a": "{example_a}",
                    "options": ["{example_a}", "Option B", "Option C", "Option D"],
                    "difficulty": "easy"
                }}
            ]
        }}
        
        Requirements:
        - {focus_instruction}
        - Theme: {category.upper()}
        - {cat_instruction}
        - Avoid generic trivia. Focus on knowing the partner.
        - 'options' MUST be a list of 4 strings.
        - 'a' MUST be one of the strings in 'options'.
        - 'difficulty' should be 'easy'.
        - Generate diverse questions to avoid repetition.
        """
        
        user_prompt = f"Generate {amount} {category} couples quiz questions about {gender if gender != 'neutral' else 'partners'}."
        
        try:
            if self.use_ollama:
                self.ensure_service_running()
                return self._generate_ollama_quiz(system_prompt, user_prompt)
            elif self.openai_api_key:
                result = self._generate_openai(system_prompt, user_prompt)
                return result.get("questions", [])
            else:
                return []
        except Exception as e:
            print(f"Couples Quiz Generation Error: {e}")
            return []

    def _generate_ollama_quiz(self, system_prompt, user_prompt):
        # Re-using _generate_ollama logic but ensuring we get the 'questions' list
        result = self._generate_ollama(system_prompt, user_prompt)
        if isinstance(result, dict) and "questions" in result:
            return result["questions"]
        elif isinstance(result, list):
            return result
        return []

    def generate_chart_data(self, context_text: str) -> Dict:
        """
        Generates realistic chart data based on the context text using LLM.
        """
        system_prompt = """
        You are a data analyst for a documentary.
        Generate realistic (or historically accurate if applicable) data points for a chart based on the given context text.
        
        Output Format: JSON object.
        {
            "title": "Chart Title",
            "x_label": "Label for X Axis (e.g., Year, Time)",
            "y_label": "Label for Y Axis (e.g., Value, Stock Price)",
            "type": "line",  # or "bar"
            "data": [
                {"label": "X1", "value": 10},
                {"label": "X2", "value": 20}
            ]
        }
        Requirements:
        - Provide 5-10 data points.
        - The trend must match the narrative (e.g., "plummet" -> values go down).
        - If exact numbers are not in text, infer realistic ones.
        """
        
        user_prompt = f"Context: {context_text}"
        
        try:
            if self.openai_api_key:
                return self._generate_openai_chart(system_prompt, user_prompt)
            elif self.gemini_api_key:
                return self._generate_gemini_chart(system_prompt, user_prompt)
            elif self.use_ollama:
                self.ensure_service_running()
                return self._generate_ollama_chart(system_prompt, user_prompt)
            else:
                # Fallback if no API key
                return self._generate_fallback_chart_data(context_text)
        except Exception as e:
            print(f"Chart Data Generation Error: {e}")
            return self._generate_fallback_chart_data(context_text)

    def _generate_fallback_chart_data(self, text: str) -> Dict:
        """Fallback data generation if LLM fails."""
        text_lower = text.lower()
        is_crash = "plummet" in text_lower or "crash" in text_lower or "drop" in text_lower
        
        points = []
        import random
        base = 100
        for i in range(5):
            if is_crash:
                val = base - (i * 15) + random.randint(-5, 5)
            else:
                val = base + (i * 15) + random.randint(-5, 5)
            points.append({"label": f"T{i+1}", "value": max(0, val)})
            
        return {
            "title": "Trend Analysis",
            "x_label": "Time",
            "y_label": "Value",
            "type": "line",
            "data": points
        }

    def _generate_openai_chart(self, system_prompt, user_prompt):
        import openai
        client = openai.OpenAI(api_key=self.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return self._parse_json_dict(content)

    def _generate_gemini_chart(self, system_prompt, user_prompt):
        if not self.genai_module:
            raise ImportError("Google Generative AI module not available.")
        model = self.genai_module.GenerativeModel('gemini-pro')
        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        return self._parse_json_dict(response.text)

    def _parse_json_dict(self, content):
        try:
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            return data
        except:
            return {}

    def _generate_ollama(self, system_prompt, user_prompt):
        """Generates script using Ollama local API."""
        import requests
        
        url = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": "json" # Force JSON mode if supported by model/Ollama version
        }
        
        try:
            print(f"Sending request to Ollama ({self.ollama_model})... This may take several minutes (Timeout: 15 mins).")
            # Increased timeout to 900s (15 minutes) for slower hardware
            response = requests.post(url, json=payload, timeout=900)
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            return self._parse_json(content)
        except Exception as e:
            print(f"Ollama Error: {e}")
            # Try non-chat endpoint if chat fails? No, usually chat is better for instruction.
            return []

    def _generate_ollama_chart(self, system_prompt, user_prompt):
        """Generates chart data using Ollama."""
        import requests
        
        url = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": "json"
        }
        
        try:
            print(f"Generating chart with Ollama...")
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            return self._parse_json_dict(content)
        except Exception as e:
            print(f"Ollama Chart Error: {e}")
            return {}

    def extract_image_search_term(self, text: str) -> str:
        """
        Extracts a single, simple search term for finding an image.
        """
        system_prompt = "You are an image search assistant. Extract the single most important noun or subject from the text for finding a relevant photo. Output ONLY the word or short phrase. Do not include 'image of' or similar."
        user_prompt = f"Text: {text}\nSearch Term:"
        
        try:
            if self.use_ollama:
                self.ensure_service_running()
                import requests
                url = f"{self.ollama_url}/api/chat"
                payload = {
                    "model": self.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    content = response.json().get("message", {}).get("content", "").strip()
                    # Cleanup quotes and extra text
                    content = content.replace('"', '').replace("'", "").split('\n')[0]
                    return content
            elif self.openai_api_key:
                import openai
                client = openai.OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Keyword Extraction Error: {e}")
        
        # Fallback: simple heuristic
        # Return the longest word starting with capital letter (usually proper noun)
        words = [w.strip("?,.!") for w in text.split()]
        capitals = [w for w in words if w and w[0].isupper() and len(w) > 3]
        if capitals:
            return capitals[0]
        # Or just the longest word
        return max(words, key=len) if words else "question"

    def _extract_keywords_ollama(self, text: str) -> str:
        """Extracts visual keywords using Ollama."""
        system_prompt = "You are a visual research assistant. Extract 2-4 visual keywords for finding stock footage that matches the given text. Output ONLY the keywords."
        user_prompt = f"Text: {text}\nKeywords:"
        
        import requests
        url = f"{self.ollama_url}/api/generate" # Use generate for simple completion
        payload = {
            "model": self.ollama_model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "").strip().replace('"', '')
        except:
            pass
        return ""

    def process_text(self, text: str) -> List[Dict[str, str]]:
        """
        Parses raw text into script segments and extracts keywords.
        Supports structured scripts with 'Narrator:' and '[Visuals:...]' tags.
        """
        if self.use_ollama:
            self.ensure_service_running()

        import re
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        segments = []
        current_segment = {"text": "", "visuals": ""}
        
        # Check if this is a structured script (contains "Narrator:" or "[Visuals")
        is_structured = any("Narrator:" in line or "[Visuals" in line for line in lines)
        
        if is_structured:
            for line in lines:
                # 1. Visual Cues
                if line.startswith("[Visuals") or line.startswith("[Visual"):
                    # Extract content inside brackets or after colon
                    content = line.replace("[Visuals:", "").replace("[Visuals", "").replace("]", "").strip()
                    current_segment["visuals"] = content
                    
                # 2. Narrator Blocks
                elif line.startswith("Narrator:"):
                    # If we have pending text, save it first
                    if current_segment["text"]:
                        segments.append(current_segment)
                        current_segment = {"text": "", "visuals": ""}
                    
                    content = line.replace("Narrator:", "").strip()
                    current_segment["text"] = content
                    
                # 3. Timestamps / Metadata (Skip)
                elif line.startswith("[") and ("00:" in line or "The Hook" in line or "End Screen" in line):
                    continue
                    
                # 4. Chapters / Headers
                elif line.startswith("Chapter") or line.startswith("Conclusion"):
                    # Treat as part of narration or start new segment?
                    # Let's start new segment for clear pause
                    if current_segment["text"]:
                        segments.append(current_segment)
                        current_segment = {"text": "", "visuals": ""}
                    current_segment["text"] = line
                    
                # 5. Continuation Text
                else:
                    if current_segment["text"]:
                        current_segment["text"] += " " + line
                    else:
                        # Maybe a loose line, treat as text
                        current_segment["text"] = line

            # Append last segment
            if current_segment["text"]:
                segments.append(current_segment)
                
        else:
            # Fallback to simple paragraph splitter for unstructured text
            current_text = ""
            for line in lines:
                if len(current_text) + len(line) < 150:
                    current_text += " " + line
                else:
                    if current_text:
                        segments.append({"text": current_text.strip(), "visuals": ""})
                    current_text = line
            if current_text:
                segments.append({"text": current_text.strip(), "visuals": ""})
            
        # Generate final output with keywords
        result = []
        for s in segments:
            # Use visual description for keywords if available, else text
            source_for_keywords = s["visuals"] if s["visuals"] else s["text"]
            keywords = self._extract_keywords(source_for_keywords)
            
            # Clean text for TTS (remove brackets, parens, and common script prefixes)
            clean_text = s["text"]
            clean_text = re.sub(r'\[.*?\]', '', clean_text)
            clean_text = re.sub(r'\(.*?\)', '', clean_text)
            clean_text = re.sub(r'^(Narrator|Voiceover|Host|Scene \d+):', '', clean_text, flags=re.IGNORECASE)
            clean_text = clean_text.strip()
            
            if clean_text:
                result.append({"text": clean_text, "keywords": keywords})
            
        return result

    def _extract_keywords(self, text: str) -> str:
        """Extracts search keywords from text using Ollama (if enabled) or spaCy."""
        if self.use_ollama:
            kws = self._extract_keywords_ollama(text)
            if kws:
                return kws
                
        try:
            import spacy
            # Load model lazily
            if not hasattr(self, 'nlp'):
                self.nlp = spacy.load("en_core_web_sm")
            
            doc = self.nlp(text)
            
            # 1. Try to find Proper Nouns (PROPN)
            propns = [token.text for token in doc if token.pos_ == "PROPN"]
            if propns:
                # Use unique proper nouns, preserving order
                seen = set()
                unique_propns = [x for x in propns if not (x in seen or seen.add(x))]
                return " ".join(unique_propns[:3])
            
            # 2. If no proper nouns, find Nouns (NOUN)
            nouns = [token.text for token in doc if token.pos_ == "NOUN"]
            if nouns:
                # Sort by length (longer words often more specific)
                nouns.sort(key=len, reverse=True)
                return " ".join(nouns[:2])
                
            return ""
            
        except Exception as e:
            print(f"Spacy extraction failed: {e}")
            # Fallback to simple splitting
            return " ".join(text.split()[:2])

    def _generate_openai(self, system_prompt, user_prompt):
        import openai
        client = openai.OpenAI(api_key=self.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o", # or gpt-3.5-turbo
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return self._parse_json(content)

    def _generate_gemini(self, system_prompt, user_prompt):
        if not self.genai_module:
            raise ImportError("Google Generative AI module not available.")
        model = self.genai_module.GenerativeModel('gemini-pro')
        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        return self._parse_json(response.text)

    def _parse_json(self, content):
        import json
        import re
        
        try:
            # 1. Clean markdown code blocks if present
            cleaned_content = content.replace("```json", "").replace("```", "").strip()
            
            # 2. Try direct parse
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # 3. Try to extract JSON object/array via regex
                # Look for { ... } or [ ... ]
                match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned_content)
                if match:
                    data = json.loads(match.group(0))
                else:
                    raise

            # 4. Normalize to list of segments
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                if "segments" in data:
                    return data["segments"]
                elif "script" in data:
                    return data["script"]
                else:
                    # Look for any list in the dict
                    for key in data:
                        if isinstance(data[key], list):
                            return data[key]
                    
                    # If no list found, but it is a valid dict, return the dict itself
                    # This allows callers expecting a specific dict schema (like KaraokeGenerator) to handle it
                    return data
            
            print(f"⚠️ JSON parsed but unexpected format. Type: {type(data)}")
            return data if isinstance(data, (dict, list)) else []

        except Exception as e:
            print(f"❌ Failed to parse JSON response: {e}")
            print(f"❌ Content received: {content[:500]}...") 
            return []

if __name__ == "__main__":
    # Test
    pass

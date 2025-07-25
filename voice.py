import asyncio
import base64
import numpy as np
import pyaudio
from google import genai
from google.genai import types
import tool
import concurrent.futures
api_key = 'YOUR_GENMINI_API_KEY'
model_name = 'gemini-live-2.5-flash-preview'

system_prompt = """
You are a flight consultant, required to call tools in information search and booking tasks.
(1) You ask the customer for basic flight requirements including:
departure, destination , flight date, flight time (hh/mm), airline, seat class and luggage weight. Note that the seat class accepts 3 types: economy, premium economy, and business corresponding to id 0, 1, 2.
If the user is not clear about the date, time, airline, you should suggest them, make sure this information is clear, if the points do not have an airport, you must suggest the nearest airport.
note: user provides city name you must implicitly know the airport code in that city (Ha Noi -> airport code is HAN, Ho Chi Minh City -> airport code: SGN)
(2) You ask the user to confirm and proceed to find flights (call function search_flight_info) according to the request and provide the user with price, airline, departure, destination and departure time.
(3) After the user selects the flight, automatically provide weather information (call function get_weather_inf) at the destination at the time of landing (if the weather is too bad, warn)
(4) Continue to ask for personal information including:
last name, first name + last name, phone number, email, title (mr, ms, mrs), personal ID number, date of birth (dd/mm/yyyy). last name and middle name without Vietnamese accents
(5) Ask the user to confirm the information just provided.
(6) After confirming the information, create a summary of the request as well as personal information.
The summary is in the form: "find a flight from A to B (A, B is airport code) on date ... by airline(s) C, seat class, departing at ... (hh:mm), and has ...kg of luggage
Personal information is: (these categories will be in English) first name: Phan, last name: A Hao, phone: 0357224, email: ..., ..."
(7) Ask the user if they want to book a flight, if so, proceed to book (call tool do_booking).
Be proactive in asking questions, calling tools, suggesting and dividing the elements to ask.
"""

search_flight_info = {
            "name": "search_flight_info",
            "description": "Tìm danh sách các chuyến bay dựa vào các thông tin đã cho",
            "parameters": {
                "type": "object",
                "properties": {
                    "depart": {"type": "string", "description": "mã sân bay nơi khởi hành (DAD, HUI)"},
                    "destination": {"type": "string", "description": "mã sân bay của điểm đến (HAN, SGN)"},
                    "target_day_d": {"type": "integer", "description": "ngày khởi hành"},
                    "target_month": {"type": "integer", "description": "tháng khởi hành"},
                    "target_year": {"type": "integer", "description": "năm khởi hành"},
                    "id_class": {"type": "integer", "description": "id của hạng ghế. bắt đầu từ 0, 1, 2"},
                    "time_str": {"type": "string", "description": "thời gian khởi hành"},
                    "brand_list": {"type": "array", "items": {"type": "string"}, "description": "tên của các hãng bay"}
                },
                "required": ["depart", "destination", "target_day_d", "target_month", "target_year", "id_class", "time_str", "brand_list"]
            }
        }

do_booking = {
            "name": "do_booking",
            "description": "thực hiện book chuyến bay thực tế",
            "parameters": {
                "type": "object",
                "properties": {
                    "finalrequest": {"type": "string", "description": "các thông tin yêu cầu của chuyến bay và thông tin cá nhân người dùng"},
                },
                "required": ["finalrequest"]
            }
        }

get_weather_inf = {
            "name": "get_weather_inf",
            "description": "cung cấp thông tin về thời tiết tại điểm đến của chuyến bay theo ngày tháng năm khởi hành",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "điểm đến của chuyến bay, nơi cần kiểm tra thời tiết"},
                    "day_depart": {"type": "integer", "description": "ngày"},
                    "month_depart": {"type": "integer", "description": "tháng"},
                    "year_depart": {"type": "integer", "description": "năm"},
                },
                "required": ["destination", "day_depart", "month_depart", "year_depart"]
            }
        }

tools = [{"function_declarations": [search_flight_info, do_booking, get_weather_inf]}]


class AudioUtils:
    @staticmethod
    def encode_bytes(data: bytes) -> str:
        return base64.b64encode(data).decode('utf-8')
    
    @staticmethod
    def create_blob(data: np.ndarray) -> dict:
        """Convert float32 audio data to blob format for Gemini"""
        # Convert float32 (-1 to 1) to int16 (-32768 to 32767)
        int16_data = (data * 32768).astype(np.int16)
        
        # Convert to bytes
        audio_bytes = int16_data.tobytes()
        
        return {
            'data': AudioUtils.encode_bytes(audio_bytes),
            'mimeType': 'audio/pcm;rate=16000'
        }
    
    @staticmethod
    def decode_audio_data(data: bytes, sample_rate: int = 24000, num_channels: int = 1) -> np.ndarray:
        """Decode audio data from bytes to float32 array"""
        int16_data = np.frombuffer(data, dtype=np.int16)
        float32_data = int16_data.astype(np.float32) / 32768.0
        if num_channels == 1:
            return float32_data
        else:
            # Deinterleave channels
            return float32_data.reshape(-1, num_channels)

class GeminiLiveAudio:
    def __init__(self):
        self.is_recording = False
        self.is_starting = False
        self.is_session_ready = False
        self.status = ""
        self.error = ""
        
        self.input_sample_rate = 16000
        self.output_sample_rate = 24000
        self.chunk_size = 1500
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        
        self.client = None
        self.session = None
        self.endturn = False
        self.stop_put = False
        
        self.audio_queue = asyncio.Queue()
        self.playback_queue = asyncio.Queue()
        self.transcript_queue = asyncio.Queue()
        self.sources = set()
        
        # Initialize
        self.init_client()
    
    def init_client(self):
        """Initialize Gemini client"""
        try:
            self.client = genai.Client(api_key=api_key)              
            self.update_status("Client initialized")
            asyncio.create_task(self.init_session())
        except Exception as e:
            self.update_error(f"Failed to initialize client: {str(e)}")

            
    async def init_session(self):
        """Initialize Gemini live session"""
    
        self.update_status("Connecting to Gemini...")
        config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_prompt,
        "tools": tools,
        "realtime_input_config": {
        "automatic_activity_detection": {
                    "disabled": False, # default
                    "silence_duration_ms": 800,
                }
            }
        }
        
        async with self.client.aio.live.connect(model=model_name, config=config) as session:
            self.session = session
            self.is_session_ready = True
            self.update_status("Ready to chat!")

            while True:
                self.endturn = False
                self.stop_put = False
                self.audio_queue = asyncio.Queue()
                self.playback_queue = asyncio.Queue()
                send_task = asyncio.create_task(self._process_audio())
                receive_task = asyncio.create_task(self._listen_for_gemini_responses())
                playback_task = asyncio.create_task(self._handle_playback())
                await asyncio.gather(send_task, receive_task, playback_task)
        return

    def update_status(self, msg: str):
        self.status = msg
        if msg:
            self.error = ""
        print(f"Status: {msg}")
    
    def update_error(self, msg: str):
        self.error = msg
        print(f"Error: {msg}")
    
    def start_recording(self):
        """Start audio recording"""
        if self.is_recording and self.is_starting:
            return
        
        self.is_starting = True
        self.update_status("Starting microphone...")
        
        try:
            # Initialize input stream
            self.input_stream = self.audio.open(
                format=self.audio_format,
                input_device_index=1,#in my computer 1 is default micro
                channels=self.channels,#1
                rate=self.input_sample_rate,#16000
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            # Initialize output stream for playback
            self.output_stream = self.audio.open(
                format=self.audio_format,
                input_device_index=2,
                channels=self.channels,
                rate=self.output_sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size
            )
            
            self.input_stream.start_stream()
            self.output_stream.start_stream()
            
            self.is_recording = True
            self.update_status("🔴 Recording...")

            
        except Exception as e:
            self.update_error(f"Error starting recording: {str(e)}")
            self.stop_recording()
        finally:
            self.is_starting = False
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio input callback"""
        if self.is_recording:
            audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
            try:
                if not self.stop_put:
                    self.audio_queue.put_nowait(audio_data)
                else:
                    audio_data = None
            except asyncio.QueueFull:
                pass  # Skip if queue is full
        
        return (None, pyaudio.paContinue)
    
    async def _process_audio(self):#send
        """Process audio data and send to Gemini"""
        while self.is_recording:
            try:
                if self.endturn == True or self.stop_put == True:
                    break
                audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=2)                
                if self.session and self.is_session_ready:
                    # Create blob and send to Gemini
                    blob = AudioUtils.create_blob(audio_data)
                    # Send audio to Gemini
                    await self.session.send_realtime_input(audio=types.Blob(data = blob['data'],
                                                                            mime_type = blob['mimeType']))
                else:
                    pass 
            except asyncio.TimeoutError:
                continue        
    
    async def _listen_for_gemini_responses(self):#get
            # Iterate asynchronously over responses from the Gemini session
        async for response in self.session.receive():
            if response.tool_call:
                print('call toollllllllllllllll')
                function_responses = []
                for fc in response.tool_call.function_calls:
                    if fc.name == 'search_flight_info':
                        loop = asyncio.get_running_loop()
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = await loop.run_in_executor(
                                pool,
                                tool.search_flight_info,
                                fc.args.get("depart"),
                                fc.args.get("destination"),
                                fc.args.get("target_day_d"),
                                fc.args.get("target_month"),
                                fc.args.get("target_year"),
                                fc.args.get("id_class"),
                                fc.args.get("time_str"),
                                fc.args.get("brand_list")
                            )
                        func_response = types.FunctionResponse(
                            id=fc.id,
                            name=fc.name,
                            response= {
                                "result": result,
                            }
                        )
                        function_responses.append(func_response)
                    elif fc.name == 'get_weather_inf':
                        result = tool.get_weather_inf(
                            destination = fc.args.get("destination"),
                            day_depart = fc.args.get("day_depart"),
                            month_depart = fc.args.get("month_depart"),
                            year_depart = fc.args.get("year_depart")
                        )
                        func_response = types.FunctionResponse(
                            id=fc.id,
                            name=fc.name,
                            response= {
                                "result": result,
                            }
                        )
                        function_responses.append(func_response)
                    elif fc.name == 'do_booking':
                        loop = asyncio.get_running_loop()
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = await loop.run_in_executor(
                                pool,
                                tool.do_booking,
                                fc.args.get("finalrequest"),
                            )
                        func_response = types.FunctionResponse(
                            id=fc.id,
                            name=fc.name,
                            response= {
                                "result": result,
                            }
                        )
                        function_responses.append(func_response)
                await self.session.send_tool_response(function_responses=function_responses)
            elif response.data:
                await self.playback_queue.put(response.data)
            if getattr(response.server_content, 'turn_complete', False):
                await self.playback_queue.put("end//")

    
    async def _handle_playback(self):#read
        while self.is_recording:
            try:
                # Get audio data for playback
                audio_data = await asyncio.wait_for(self.playback_queue.get(), timeout=3)
                if audio_data == 'end//':#xem lại còn cahcs nào thay audiodata == None không, chỗ listen for gemini
                    self.endturn = True
                    print('end turn')
                    break
                if self.output_stream and self.output_stream.is_active():
                    # Convert and play audio
                    audio_bytes = AudioUtils.decode_audio_data(audio_data, self.output_sample_rate)
                    int16_data = (audio_bytes * 32768).astype(np.int16)
                    self.stop_put = True
                    self.output_stream.write(int16_data.tobytes())

                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error during playback: {e}")


    def stop_recording(self):
        """Stop audio recording"""
        if not self.is_recording:
            return
        
        self.update_status("Stopping recording...")
        
        self.is_recording = False
        
        # Stop and close streams
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        
        self.update_status("Recording stopped. Click Start to begin again.")
    
    def reset(self):
        """Reset the session"""
        if self.is_recording:
            self.stop_recording()
        
        self.is_session_ready = False
        self.session = None
        
        # Reinitialize session
        asyncio.create_task(self.init_session())
        self.update_status("Session reset.")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_recording()
        if self.audio:
            self.audio.terminate()


  
# asyncio.run(main())
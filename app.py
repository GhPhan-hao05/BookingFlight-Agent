


from flask import Flask, render_template, request, jsonify
from google import genai
import os
import tool
from voice import *
from google.genai import types
from state import get_audio_chat

api_key = 'YOUR_GEMINI_API_KEY' 

client = genai.Client(api_key=api_key)
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Messages lưu hội thoại
global messages
messages = []
system_prompt = """
        Bạn là nhà tư vấn chuyến bay.
        (1) Bạn sẽ hỏi khách hàng các yêu cầu cơ bản của 1 chuyến bay bao gồm:
        nơi đi, nơi đến, ngày bay, giờ bay(hh/mm), hãng bay, hạng ghế và khối lượng hành lý. Chú ý hạng ghế chấp nhận 3 loại: phổ thông - economy, phổ thông đặc biệt - premium economy, và thương gia - business ứng với id là 0, 1, 2.
        nếu người dùng không rõ ràng về ngày, giờ, hãng bay bạn hãy gợi ý cho họ, đừng để những thông tin này thiếu rõ ràng,
        user cung cấp tên thành phố bạn phải ngầm biết (implicit)mã sân bay tại thành phố đó (Ví dụ: Đà Nẵng là DAN, Hà Nội là HAN, Hồ Chí Minh là SGN, ...). nếu nơi khởi hành và nơi đến đó không có sân bay bạn cũng phải thông báo và gợi ý sân bay gần đó nhất
        (2) Bạn yêu cầu user xác nhận và tìm các chuyến bay theo yêu cầu và cung cấp cho người dùng bao gồm giá, hãng bay, nơi đi, nơi đến và giờ khởi hành.
        (3) Sau khi người dùng chọn chuyến bay theo, tự động cung cấp thông tin thời tiết dự báo ở destination tại thời điểm hạ cánh (nếu thời tiết quá xấu thì gợi ý ngày giờ khác)
        (4) Tiếp tục hỏi về các thông tin cá nhân:
        họ, đêm + tên, sđt, email, danh xưng ( mr, ms, mrs), số id cá nhân, ngày tháng năm sinh (dd/mm/yyyy). họ đệm và tên không có dấu tiếng việt
        (5) Sau khi thu thập đủ, yêu cầu người dùng xác nhận lại thông tin.
        (6) Sau khi thông tin được xác nhận, tạo tóm tắt về yêu cầu và thông tin cá nhân.
        Bản tóm tắt có dạng: "tìm chuyến bay từ A đến B (A B là mã sân bay - không phải tên thành phố) vào ngày ... của (các) hãng bay C, hạng ghế, khởi hành lúc ... (hh:mm), và có ...kg hành lý
        Thông tin cá nhân là:(các category là tiếng anh) first name: Phan, last name: A Hao, phone: 0357224, email:..., ..."
        (7) Hỏi người dùng có muốn book chuyến bay không, nếu có thì tiến hành book.
        Hãy chủ động trong việc hỏi đáp, gợi ý các yêu cầu xác nhận và booking nhé."""


get_flight = {
            "name": "search_flight_info",
            "description": "Tìm danh sách các chuyến bay dựa vào các thông tin đã cho",
            "parameters": {
                "type": "object",
                "properties": {
                    "depart": {"type": "string", "description": "mã sân bay nơi khởi hành (DAD, HUI)"},
                    "destination": {"type": "string", "description": "mã sân bay của điểm đến (SGN, HAN)"},
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

booking = {
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

weather_inf = {
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

tools = types.Tool(function_declarations=[get_flight, weather_inf, booking])
config = types.GenerateContentConfig(tools = [tools],
                                     system_instruction = system_prompt
                                    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/visual")
def visual():
    return render_template("visual.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "Missing 'message' parameter"}), 400
    messages.append(types.Content(role = "user", parts=[types.Part(text=user_input)]))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents = messages,
        config=config,
        )
    reply_part = response.candidates[0].content.parts[0]
    show_flights = False
    assistant_response = ""

    if reply_part.function_call:
        tool_call = reply_part.function_call
        function_name = tool_call.name
        args = tool_call.args
        print(args)

        if function_name == "search_flight_info":
            result = tool.search_flight_info(
                depart = args.get("depart"),
                destination = args.get("destination"),
                target_day_d = args.get("target_day_d"),
                target_month = args.get("target_month"),
                target_year = args.get("target_year"),
                id_class = args.get("id_class"),
                time_str = args.get("time_str"),
                brand_list = args.get("brand_list")
            )

            function_response_part = types.Part.from_function_response(
                name=tool_call.name,
                response={"result": result},
            )
            ####thêm code chuyển json
            

            messages.append(response.candidates[0].content)
            messages.append(types.Content(role="tool", parts=[function_response_part]))

            final_response  = client.models.generate_content(
                model="gemini-2.5-flash",
                contents = messages,
                config=config
                )
            assistant_response = final_response.text
            messages.append(types.Content(role = "model", parts=[types.Part(text=assistant_response)]))

        elif function_name == "get_weather_inf": 
            result = tool.get_weather_inf(
                destination = args.get("destination"),
                day_depart = args.get("day_depart"),
                month_depart = args.get("month_depart"),
                year_depart = args.get("year_depart")
            )

            function_response_part = types.Part.from_function_response(
                name=tool_call.name,
                response={"result": result},
            )
            messages.append(response.candidates[0].content)
            messages.append(types.Content(role="tool", parts=[function_response_part]))

            final_response  = client.models.generate_content(
                model="gemini-2.5-flash",
                contents = messages,
                config=config
                )
            assistant_response = final_response.text
            messages.append(types.Content(role = "model", parts=[types.Part(text=assistant_response)])) 
        elif function_name == "do_booking": 
            result = tool.do_booking(
                finalrequest = args.get("finalrequest"),
            )

            function_response_part = types.Part.from_function_response(
                name=tool_call.name,
                response={"result": result},
            )
            messages.append(response.candidates[0].content)
            messages.append(types.Content(role="tool", parts=[function_response_part]))

            final_response  = client.models.generate_content(
                model="gemini-2.5-flash",
                contents = messages,
                config=config
                )
            assistant_response = final_response.text
            messages.append(types.Content(role = "model", parts=[types.Part(text=assistant_response)])) 

        else:
            assistant_response = "Không thể gọi hàm."
    else:
        assistant_response = reply_part.text
        messages.append(types.Content(role = "model", parts=[types.Part(text=assistant_response)]))


    return jsonify({
        "reply": assistant_response,
        "show_flights": show_flights
    })

async def start_voice_chat():
    audio_chat = await get_audio_chat()
    audio_chat.mic_on = True
    audio_chat.start_recording()
    # Keep running
    while True:
        await asyncio.sleep(1)

@app.route("/start-mic", methods=["POST"])
def start_mic():
    asyncio.run(start_voice_chat())
    
        
@app.route("/end-mic", methods=["POST"])
async def end_mic():
    audio_chat = await get_audio_chat()
    audio_chat.mic_on = False
    return jsonify({"status": "recording stopped"})


if __name__ == "__main__":
    app.run(debug=True)


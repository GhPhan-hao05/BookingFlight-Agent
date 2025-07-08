# from flask import Flask, render_template, request, jsonify, session
# import openai
# import json
# import os
# from tool import get_flight_options

# client = openai.OpenAI(api_key='[your_openai_api]')
# app = Flask(__name__)
# app.secret_key = os.urandom(24)
# global messages
# messages = [
#     {"role": "system", "content": "Bạn là một trợ lý du lịch có thể hỗ trợ tìm chuyến bay."},
# ]
# functions = [{
#     "type": "function",
#     "function": {
#         "name": "get_flight_options",
#         "description": "Lấy danh sách chuyến bay giữa 2 địa điểm",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "departure": {"type": "string", "description": "Sân bay đi, ví dụ SGN",},
#                 "destination": {"type": "string", "description": "Sân bay đến, ví dụ HAN",}
#             },
#             "required": ["departure", "destination"],
#             "additionalProperties": False
#         },
#         "strict": True
#     }
# }]

# @app.route("/")
# def index():
#     return render_template("index.html")

# @app.route("/chat", methods=["POST"])
# def chat():
#     user_message = request.json.get("message", "")
#     # messages = session.get("messages", [])
#     messages.append({"role": "user", "content": user_message})

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=messages,
#         tools=functions,
#         tool_choice="auto",
#     )

#     msg = response.choices[0].message
#     assistant_response = ""
#     show_flights = False

#     if msg.tool_calls:
#         tool_call = msg.tool_calls[0] # Assuming only one tool call for simplicity
#         function_name = tool_call.function.name
#         arguments = json.loads(tool_call.function.arguments)
#         if function_name == "get_flight_options":
#             result = get_flight_options(
#                 departure=arguments.get("departure"),
#                 destination=arguments.get("destination"),
#             )

#             # Save result
#             with open("static/flight_results.json", "w", encoding="utf-8") as f:
#                 json.dump(result, f, ensure_ascii=False, indent=2)
#             show_flights = True

#             messages.append(msg)
#             messages.append({
#                 "tool_call_id": tool_call.id, # Include tool_call_id
#                 "role": "tool", # Use 'tool' role
#                 "name": function_name,
#                 "content": json.dumps(result, ensure_ascii=False)
#             })

#             follow_up = client.chat.completions.create(
#                 model="gpt-4",
#                 messages=messages,
#             )
#             assistant_response = follow_up.choices[0].message.content
#             messages.append({"role": "assistant", "content": assistant_response})
#         else:
#             assistant_response = "Không thể gọi hàm."
#     else:
#         assistant_response = msg.content
#         messages.append({"role": "assistant", "content": assistant_response})


#     return jsonify({"reply": assistant_response,
#                     "show_flights": show_flights
#                     })


# if __name__ == "__main__":
#     app.run(debug=True)



from flask import Flask, render_template, request, jsonify
from google import genai
import json
import os
from tool import *
from google.genai import types

api_key = '[your_gemini_api]' 

client = genai.Client(api_key=api_key)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Messages lưu hội thoại
global messages
messages = [
    types.Content(
        role="user", parts=[types.Part(text="""
                                       Bạn là nhà tư vấn chuyến bay.
                                       (1) Đầu tiên bạn sẽ hỏi khách hàng các yêu cầu cơ bản của 1 chuyến bay bao gồm:
                                       nới đi, nới đến, ngày bay, giờ bay(hh/mm), hãng bay, hạng ghế và khối lượng hành lý. Chú ý đối với hạng ghế chỉ chấp nhận 3 loại đóa là phổ thông - economy, phổ thông đặc biệt - premium economy, và thương gia - business ứng với id là 0, 1, 2.
                                       nếu người dùng mập mờ, không rõ ràng về ngày, giờ, hãng bay bạn hãy gợi ý cho họ, đừng để những thông tin này thiếu rõ ràng gây khó khăn, ngoài ra với những địa điểm khởi hành và điểm đích, nếu nơi đó không có sân bay bạn cũng phải nói cho họ
                                       (2) Sau đó tìm thông tin các chuyến bay theo yêu cầu và cung cấp cho người dùng.
                                       (3)Sau khi người dùng chọn chuyến bay theo ý muốn, tiếp tục hỏi về các thông tin cá nhân gồm:
                                       họ, đêm + tên, sđt, email, danh xưng ( mr, ms, mrs), số id cá nhân, ngày tháng năm sinh (dd/mm/yyyy).
                                       (4) Sau khi thu thập đủ, yêu cầu người dùng xác nhận lại thông tin.
                                       (5)Sau khi thông tin được xác nhận và không còn chỉnh sửa, tạo một bảng tóm tắt về yêu cầu cũng như thông tin cá nhân.
                                       Bản tóm tắt sẽ có dạng: "tìm chuyến bay từ A đến B vào ngày ... của hãng bay C, khởi hành lúc ... (hh:mm), và có ...kg hành lý
                                       Thông tin cá nhân là:(các category này sẽ là tiếng anh nha) first name: Phan, last name: A Hảo, phone: 0357224, email:..., ..."
                                       (6) Hỏi người dùng có muốn book chuyến bay không, nếu có thì tiến hành book.
                                       Hãy chủ động trong việc hỏi đáp, gợi ý các yêu cầu xác nhận và booking nhé.""")]
    )
]


get_flight = {
            "name": "search_flight_inf",
            "description": "Tìm danh sách các chuyến bay dựa vào các thông tin đã cho",
            "parameters": {
                "type": "object",
                "properties": {
                    "depart": {"type": "string", "description": "tên hoặc mã sân bay nơi khởi hành (ví dụ Đà Nẵng hoặc DAD)"},
                    "destination": {"type": "string", "description": "tên hoặc mã sân bay của điểm đến (ví dụ Hà Nội hoặc HAN)"},
                    "target_day": {"type": "integer", "description": "ngày khởi hành - chỉ có ngày thôi, ví dụ 12, 28"},
                    "target_month": {"type": "integer", "description": "tháng khởi hành"},
                    "target_year": {"type": "integer", "description": "năm khởi hành"},
                    "id_class": {"type": "integer", "description": "id của hạng ghế. bắt đầu từ 0, 1, 2"},
                    "time_str": {"type": "string", "description": "thời gian khởi hành"},
                    "brand_str": {"type": "string", "description": "tên của hãng bay"}
                },
                "required": ["depart", "destination", "target_day", "target_month", "target_year", "id_class", "time_str", "brand_str"]
            }
        }

booking = {
            "name": "do_booking",
            "description": "thực hiện book chuyến bay thực tế",
            "parameters": {
                "type": "object",
                "properties": {
                    "finalrequest": {"type": "string", "description": "các thoonng tin yêu cầu của chuyến bay và thông tin cá nhân người dùng"},
                },
                "required": ["finalrequest"]
            }
        }

tools = types.Tool(function_declarations=[get_flight, booking])
config = types.GenerateContentConfig(tools=[tools])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    messages.append(types.Content(role = "user", parts=[types.Part(text=user_message)]))

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

        if function_name == "search_flight_inf":
            result = search_flight_inf(
                depart = args.get("depart"),
                destination = args.get("destination"),
                target_day = args.get("target_day"),
                target_month = args.get("target_month"),
                target_year = args.get("target_year"),
                id_class = args.get("id_class"),
                time_str = args.get("time_str"),
                brand_str = args.get("brand_str")
            )

            with open("static/flight_results.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            show_flights = True

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
            result = do_booking(
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

if __name__ == "__main__":
    app.run(debug=True)

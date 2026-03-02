from fastapi import Request
from fastapi.responses import Response
from oberoende_bot.app.graph.graph_engine import graph

async def handle_whatsapp(request: Request):
    form = await request.form()
    from_number = form.get("From")
    message_body = form.get("Body")

    if not message_body:
        return Response("OK", status_code=200)

    result = graph.invoke({
        "user_id": from_number,
        "user_message": message_body,
        "response": "",
        "decision": None
    })

    response_text = result["response"]

    twiml_response = f"""
    <Response>
        <Message>{response_text}</Message>
    </Response>
    """
    return Response(content=twiml_response, media_type="application/xml")
from fastapi import Request
from fastapi.responses import Response
#from app.services.llm_service import ask_llm
#from oberoende_bot.app.services.rag_service import ask_llm
from oberoende_bot.app.services.llm_service import ask_llm
async def handle_whatsapp(request: Request):

    form = await request.form()

    from_number = form.get("From")
    message_body = form.get("Body")

    if not message_body:
        return Response("OK", status_code=200)

    response_text = ask_llm(message_body, from_number)

    twiml_response = f"""
    <Response>
        <Message>{response_text}</Message>
    </Response>
    """

    return Response(content=twiml_response, media_type="application/xml")
import openai
from flask import Flask, request, jsonify
from flask_cors import CORS
import settings
import openAIEmbeddings as oae

app = Flask(__name__)
cors = CORS(app)

openai.api_type = settings.APITYPE
openai.api_base = settings.APIBASE
openai.api_key = settings.APIKEY
openai.api_version = settings.APIVERSION

messageOr = [{'role': "system", 'content': settings.PROMPT2}]

def get_completion(prompt, model=settings.MODELNAMEGPT):
    messages1 = [{"role": "system", "content": "Toma esta pregunta y reformúlala en caso de que tenga errores gramaticales o de redacción. Luego de esto respóndela de la mejor manera posible. En tu respuesta debes incluir tanto la pregunta reescrita como la respuesta a la misma. No incluyas explícitamente una separación entre estos elementos, solo con la información es suficiente."}]
    messages1.append({"role": "user", "content": prompt})
    response = openai.ChatCompletion.create(
        engine=model,
        messages=messages1,
        temperature=0,
    )
    return response.choices[0].message["content"]

def get_completion_from_messages(messages, model=settings.MODELNAMEGPT, temperature=0):
    last_user_message = messages[-1]['content']

    tema_elegido = None

    if last_user_message.strip() in ['1', '2']:
        tema_elegido = 'Proyecto de Grado en Bellas Artes' if last_user_message.strip() == '1' else 'Diseño Gráfico en Bellas Artes'
        messages_with_initial = [{'role': 'system', 'content': messageOr[0]['content'] + f'"{settings.PROMPT2}" Tema seleccionado: {tema_elegido}'}] + messages
        return f'Perfecto! ¿Qué te gustaría saber sobre {tema_elegido}?.'
    else:
        initial_hyde = get_completion(messages[-1]['content'] + "// NO JUSTIFIQUES TUS RESPUESTAS. NO DES INFORMACIÓN FUERA DEL CONTEXTO PROPORCIONADO.")
        context = oae.pinecone_relatedness(query=initial_hyde)
        messages_with_initial = [{'role': 'system', 'content': messageOr[0]['content'] + f'"{context}"'}] + messages

        response = openai.ChatCompletion.create(
            engine=model,
            messages=messages_with_initial,
            temperature=temperature,
        )
        return response.choices[0].message["content"]





@app.route("/")
def hello():
    print("Este es el back de manchita")
    return "Este es el back de manchita"

@app.post("/answer")
def askModel():
    data = request.get_json()
    answer = get_completion_from_messages(data['REQUEST'])
    return jsonify({'result': answer})

@app.post('/anwer')
def askModelMessages():
    data = request.get_json()
    print(data)
    if 'text' in data:
        input_text = data['text'] 
        answer = get_completion_from_messages(input_text)
        return jsonify({'result': answer})
    else:
        return jsonify({'error': 'Invalid input'}), 400

if __name__ == "__main__":
  app.run()

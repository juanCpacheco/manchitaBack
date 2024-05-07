import glob
import os
import openai
import settings
import pandas as pd
from spicy import spatial
from PyPDF2 import PdfReader 
from langchain.vectorstores import Pinecone
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
import time

openai.api_type = settings.APITYPE
openai.api_base = settings.APIBASE
openai.api_key = settings.APIKEY
openai.api_version = settings.APIVERSION

pinecone.init(
    api_key = settings.DATABASEKEY,
    environment=settings.DATABASEENV
)

content = "content"
lemb = OpenAIEmbeddings(
    model=settings.MODELNAMEEMB,
    openai_api_type='azure', 
    openai_api_key=settings.APIKEY, 
    openai_api_base=settings.APIBASE, 
    openai_api_version=settings.APIVERSION,
    deployment=settings.MODELNAMEEMB)

pinecone_index = pinecone.Index("manchita-vectors")
vectorstore = Pinecone(pinecone_index, lemb.embed_query, content)

def get_embedding(text, model=settings.MODELNAMEEMB):
    result = openai.Embedding.create(
        engine = model,
        input = text
    )
    return result['data'][0]['embedding']

def embeddings_for_dataframe(df):
    embeddings = {}
    for idx, row in df.iterrows():
        embeddings[idx] = get_embedding(row.content)
        if (idx + 1) % 50 == 0:  # Cada 50 filas
            time.sleep(20)  # Esperar 20 segundos
    return embeddings

def strings_ranked_by_relatedness(
    query: str,
    df: pd.DataFrame,
    relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y),
    top_n: int = 100
) -> tuple[list[str], list[float]]:
    
    query_embedding = get_embedding(query)
    strings_and_relatednesses = [
        (row["content"], relatedness_fn(query_embedding, row["Embeddings"]))
        for i, row in df.iterrows()
    ]
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n]

def load_embeddings_from_file(path):
    embi = []
    try:
        embRead = open(path, 'r')
        for line in embRead:
            lis = line.split(',')
            lis = [float(i) for i in lis]
            embi.append(lis)
    except:
        print("File not accessible") 
    return embi

def combine_columns(row):
    return f"Pregunta: {row['Pregunta']} // Respuesta: {row['Respuesta']} // Enlace: {row['Enlace']}"

def build_dataframe(pathExcel, pathEmbeddings):
    xls = pd.ExcelFile(pathExcel)
    sheets = xls.sheet_names
    data = {sheet_name: xls.parse(sheet_name) for sheet_name in sheets}
    
    df_def = pd.DataFrame()
    for k in data.keys():
    
        df = xls.parse(k, header=1)
        df = df.drop(df.columns[0], axis=1)
        df['content'] = df.apply(combine_columns, axis=1)
        df_def = pd.concat([df_def, df])
    df_def = df_def.drop(df_def.columns[4], axis=1)
    
    pre = df_def['content'].tolist()
    
    co = []

    folder_path = 'Data/ProyectoGrado'

    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))

    for pdf_file in pdf_files:
        nombre_documento = os.path.basename(pdf_file)
    
        with open(pdf_file, 'rb') as file:
            reader = PdfReader(file)
            for num_page, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                co.append(f"Tema: Proyecto de grado, Nombre Documento: {nombre_documento}, NumeroPagina: {num_page}, Contenido: {page_text}")

    content = pre + co
    
    df_final = pd.DataFrame(content, columns=['content'])
    df_final = df_final.replace('\n',' ', regex=True)

    embi = load_embeddings_from_file(pathEmbeddings)
    df_final['Embeddings'] = embi
    return df_final

def pinecone_relatedness(query):
    results = vectorstore.similarity_search(query, k=4)
    usable_results = []
    for re in results:
        messages1 = [{"role": "system", "content": f'''Vas a tomar SOLAMENTE la pregunta del query que se proporcionará 
                      y determinarás si es posible resolverla con el contexto proporcionado a continuación (entre comillas sencillas).
                      No debes responder a la pregunta como tal, solamente debes responder 
                      'True' en caso de que el contexto tenga relación con la pregunta o 
                      'False' en caso contrario. No responderás absolutamente 
                      nada más que una de estas dos opciones, sin utilizar ningún tipo 
                      de puntuación o caracteres distintos. Este es el contexto:{re.page_content}'''}]
        messages1.append({"role": "user", "content": query})
        response = openai.ChatCompletion.create(
            engine=settings.MODELNAMEGPT,
            messages=messages1,
            temperature=0,
        )
        rta = response.choices[0].message["content"]
        if rta == 'True':
            usable_results.append(re)
        time.sleep(0.5)
    knowledge = "\n".join([result.page_content for result in usable_results])
    return knowledge